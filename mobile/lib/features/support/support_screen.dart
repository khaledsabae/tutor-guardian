/// «ادعم المربّي» — transparency first, then the amounts.
///
/// The page opens with what the app costs this month and how much of it
/// supporters covered, because that is what turns a payment into trust: the
/// parent sees where it goes before being asked. The amounts come from the
/// store (Play formats the local price); none of them unlocks anything.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import '../../core/analytics.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import 'support_providers.dart';

class SupportScreen extends ConsumerStatefulWidget {
  const SupportScreen({super.key});

  @override
  ConsumerState<SupportScreen> createState() => _SupportScreenState();
}

class _SupportScreenState extends ConsumerState<SupportScreen> {
  StreamSubscription<SupportOutcome?>? _sub;
  SupportOutcome? _shown;
  String? _busyProductId;

  @override
  void initState() {
    super.initState();
    unawaited(Analytics.supportOpened());
    // The coordinator owns the purchase stream for the whole app; this screen
    // only shows what it reports. start() is a no-op when the app root has
    // already started it, which it has whenever this screen is reachable.
    final coordinator = ref.read(supportCoordinatorProvider)..start();
    _sub = coordinator.outcomes.listen(_onOutcome);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  void _onOutcome(SupportOutcome? outcome) {
    if (!mounted) return;
    setState(() {
      // Whatever happened, the sheet is closed: the buttons come back.
      _busyProductId = null;
      // A cancelled sheet needs no message — the parent chose to close it.
      if (outcome != null && outcome != SupportOutcome.cancelled) {
        _shown = outcome;
      }
    });
    if (outcome == SupportOutcome.thanked) {
      ref.invalidate(supportTransparencyProvider);
    }
  }

  Future<void> _buy(ProductDetails product) async {
    if (_busyProductId != null) return;
    unawaited(Analytics.supportTapped(product.id));
    setState(() {
      _busyProductId = product.id;
      _shown = null;
    });
    var started = false;
    try {
      started = await ref.read(supportCoordinatorProvider).buy(product);
    } catch (_) {
      started = false;
    }
    if (!started && mounted) {
      setState(() {
        _busyProductId = null;
        _shown = SupportOutcome.error;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final products = ref.watch(supportProductsProvider);
    final list = products.valueOrNull;
    final transparency = ref.watch(supportTransparencyProvider).valueOrNull;
    final shown = _shown;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.supportTitle)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
        children: [
          Text(
            l10n.supportIntro,
            style: TextStyle(
              fontSize: 15,
              height: 1.7,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 20),
          if (transparency != null) ...[
            _TransparencyCard(data: transparency),
            const SizedBox(height: 24),
          ],
          if (shown != null) ...[
            _OutcomeBanner(outcome: shown),
            const SizedBox(height: 16),
          ],
          Text(
            l10n.supportChooseAmount,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textSecondary,
                ),
          ),
          const SizedBox(height: 10),
          // The provider never errors (it degrades to an empty list), so the
          // only states are "asking the store" and an answer.
          if (list == null)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: CircularProgressIndicator(),
              ),
            )
          else if (list.isEmpty)
            Text(l10n.supportStoreUnavailable,
                style: TextStyle(color: AppTheme.textMuted))
          else
            for (final p in list)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _ProductButton(
                  label: _labelFor(l10n, p),
                  price: p.price,
                  busy: _busyProductId == p.id,
                  enabled: _busyProductId == null,
                  onTap: () => _buy(p),
                ),
              ),
          const SizedBox(height: 16),
          Text(
            l10n.supportNoPerks,
            style: TextStyle(
              fontSize: 12,
              height: 1.6,
              color: AppTheme.textMuted,
            ),
          ),
        ],
      ),
    );
  }

  String _labelFor(AppLocalizations l10n, ProductDetails p) => switch (p.id) {
        'support_small' => l10n.supportProductSmall,
        'support_medium' => l10n.supportProductMedium,
        'support_large' => l10n.supportProductLarge,
        // Play appends the app name in brackets; the parent knows which app.
        _ => p.title.replaceAll(RegExp(r'\s*\(.*\)\s*$'), ''),
      };
}

String _usd(num value) {
  final whole = value == value.roundToDouble();
  return '\$${value.toStringAsFixed(whole ? 0 : 2)}';
}

class _TransparencyCard extends StatelessWidget {
  const _TransparencyCard({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final cost = (data['cost_usd'] as num?)?.toDouble();
    final covered = (data['covered_usd'] as num?)?.toDouble() ?? 0;
    final pct = (data['covered_pct'] as num?)?.toInt();
    final breakdown = (data['breakdown'] as List?)
            ?.whereType<Map>()
            .map((m) => MapEntry('${m['key']}', (m['usd'] as num?)?.toDouble() ?? 0))
            .toList() ??
        const <MapEntry<String, double>>[];

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Dt.surface,
        borderRadius: BorderRadius.circular(Dt.rCard),
        border: Border.all(color: AppTheme.primary.withValues(alpha: .2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (cost != null) ...[
            Text(
              l10n.supportMonthCost(_usd(cost)),
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w800,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: ((pct ?? 0) / 100).clamp(0.0, 1.0),
                minHeight: 10,
                color: AppTheme.primary,
                backgroundColor: AppTheme.primary.withValues(alpha: .15),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.supportCoveredPct(pct ?? 0),
              style: TextStyle(
                fontWeight: FontWeight.w700,
                color: AppTheme.primary,
              ),
            ),
            if (breakdown.isNotEmpty) ...[
              const SizedBox(height: 12),
              for (final item in breakdown)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          _costLabel(l10n, item.key),
                          style: TextStyle(color: AppTheme.textSecondary),
                        ),
                      ),
                      Text(
                        _usd(item.value),
                        style: TextStyle(color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
            ],
          ] else
            // Without a declared cost a percentage would be of nothing; say
            // what was given and stop there.
            Text(
              l10n.supportCoveredAmount(_usd(covered)),
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
          const SizedBox(height: 10),
          Text(
            l10n.supportApproxNote,
            style: TextStyle(fontSize: 11.5, color: AppTheme.textMuted, height: 1.5),
          ),
        ],
      ),
    );
  }

  String _costLabel(AppLocalizations l10n, String key) => switch (key) {
        'server' => l10n.supportCostServer,
        'ai' => l10n.supportCostAi,
        'domain' => l10n.supportCostDomain,
        _ => l10n.supportCostOther,
      };
}

class _ProductButton extends StatelessWidget {
  const _ProductButton({
    required this.label,
    required this.price,
    required this.busy,
    required this.enabled,
    required this.onTap,
  });

  final String label;
  final String price;
  final bool busy;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: enabled ? onTap : null,
      style: OutlinedButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        side: BorderSide(color: AppTheme.primary.withValues(alpha: .5)),
      ),
      child: Row(
        children: [
          const Text('🤍', style: TextStyle(fontSize: 18)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
          ),
          if (busy)
            const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          else
            Text(
              price,
              style: TextStyle(
                fontWeight: FontWeight.w800,
                color: AppTheme.primary,
              ),
            ),
        ],
      ),
    );
  }
}

class _OutcomeBanner extends StatelessWidget {
  const _OutcomeBanner({required this.outcome});

  /// Never [SupportOutcome.cancelled] — the screen does not show one.
  final SupportOutcome outcome;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final isError = outcome == SupportOutcome.error;
    final text = switch (outcome) {
      SupportOutcome.thanked => l10n.supportThanks,
      SupportOutcome.pending => l10n.supportPending,
      SupportOutcome.retryLater => l10n.supportRetryLater,
      SupportOutcome.error || SupportOutcome.cancelled => l10n.supportError,
    };
    final color =
        isError ? Theme.of(context).colorScheme.error : AppTheme.primary;
    return Semantics(
      liveRegion: true,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: color.withValues(alpha: .10),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          text,
          style: TextStyle(fontWeight: FontWeight.w700, color: color, height: 1.5),
        ),
      ),
    );
  }
}
