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
  StreamSubscription<SupportEvent>? _sub;
  SupportOutcome? _shown;

  /// The product whose sheet is open.
  String? _busyProductId;

  /// Tokens the coordinator had already seen when the parent tapped: older
  /// purchases, whatever they do while this sheet is open.
  Set<String> _olderTokens = const {};

  /// The token of the purchase this screen started, once Play has named it —
  /// so its later updates (a pending payment completing) still reach it.
  String? _liveToken;

  @override
  void initState() {
    super.initState();
    unawaited(Analytics.supportOpened());
    // The coordinator owns the purchase stream for the whole app; this screen
    // only shows what it reports about the purchase started here. start() is
    // a no-op when the app root has already started it, which it has whenever
    // this screen is reachable.
    final coordinator = ref.read(supportCoordinatorProvider)..start();
    _sub = coordinator.events.listen(_onEvent);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  /// Whether [e] is about the purchase the parent started on this screen.
  ///
  /// The stream also carries older purchases — a cash payment from last week
  /// re-delivered by the resume-time restore. Taken as this screen's, one used
  /// to put "pending" over the card payment that had just gone through, and
  /// to clear the spinner of a purchase still in flight.
  bool _isLive(SupportEvent e) {
    final live = _liveToken;
    if (e.token.isNotEmpty && live != null && e.token == live) return true;
    final busy = _busyProductId;
    if (busy == null || e.restored) return false;
    // Android answers an open sheet's cancel or billing error with a bare
    // update that names no product — it can only be this sheet's answer.
    if (e.productId.isEmpty) return true;
    // An older purchase — known before the tap — is never the live one, even
    // for the same product. Recognised by token: no clock is trusted, since
    // a device's clock can be hours off.
    return e.productId == busy && !_olderTokens.contains(e.token);
  }

  void _onEvent(SupportEvent e) {
    if (!mounted || !_isLive(e)) return;
    setState(() {
      if (e.token.isNotEmpty) _liveToken = e.token;
      // Whatever happened, the sheet is closed: the buttons come back.
      _busyProductId = null;
      // A cancelled sheet needs no message — the parent chose to close it.
      final outcome = e.outcome;
      if (outcome != null && outcome != SupportOutcome.cancelled) {
        _shown = outcome;
      }
    });
    if (e.outcome == SupportOutcome.thanked) {
      ref.invalidate(supportTransparencyProvider);
    }
  }

  Future<void> _buy(ProductDetails product) async {
    if (_busyProductId != null) return;
    unawaited(Analytics.supportTapped(product.id));
    setState(() {
      _busyProductId = product.id;
      _olderTokens = ref.read(supportCoordinatorProvider).seenTokens;
      _liveToken = null;
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
    // Purchases Play has not priced yet are in no sum: while any exist, the
    // figure is a floor, and the page says "about" rather than a number it
    // knows to be short.
    final unpriced = (data['unpriced'] as num?)?.toInt() ?? 0;
    final approximate = unpriced > 0;
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
              approximate
                  ? l10n.supportCoveredPctApprox(pct ?? 0)
                  : l10n.supportCoveredPct(pct ?? 0),
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
              approximate
                  ? l10n.supportCoveredAmountApprox(_usd(covered))
                  : l10n.supportCoveredAmount(_usd(covered)),
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
          if (approximate) ...[
            const SizedBox(height: 8),
            Text(
              l10n.supportUnpricedNote(unpriced),
              style: TextStyle(
                  fontSize: 12, color: AppTheme.textSecondary, height: 1.5),
            ),
          ],
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
