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
import '../../state/chat_notifier.dart' show tgClientProvider;
import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import 'support_providers.dart';

class SupportScreen extends ConsumerStatefulWidget {
  const SupportScreen({super.key});

  @override
  ConsumerState<SupportScreen> createState() => _SupportScreenState();
}

class _SupportScreenState extends ConsumerState<SupportScreen> {
  StreamSubscription<List<PurchaseDetails>>? _sub;
  SupportOutcome? _outcome;
  String? _busyProductId;
  bool _restored = false;

  @override
  void initState() {
    super.initState();
    unawaited(Analytics.supportOpened());
    final store = ref.read(supportStoreProvider);
    try {
      _sub = store.purchaseStream.listen(_onPurchases, onError: (_) {});
    } catch (_) {
      // No billing on this device; the screen still shows transparency.
    }
    ref.listenManual<AsyncValue<List<ProductDetails>>>(
      supportProductsProvider,
      (_, next) => next.whenData(_restoreOnce),
      fireImmediately: true,
    );
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  /// Once the products are known, ask Play for anything left unfinished —
  /// a purchase the server could not verify on a previous visit.
  void _restoreOnce(List<ProductDetails> products) {
    if (_restored || products.isEmpty) return;
    _restored = true;
    unawaited(ref.read(supportStoreProvider).restore().catchError((_) {}));
  }

  Future<void> _onPurchases(List<PurchaseDetails> purchases) async {
    final products = ref.read(supportProductsProvider).valueOrNull ?? const [];
    final handler = SupportPurchaseHandler(
      client: ref.read(tgClientProvider),
      store: ref.read(supportStoreProvider),
      productIds: ref.read(donationProductIdsProvider),
      productById: (id) {
        for (final p in products) {
          if (p.id == id) return p;
        }
        return null;
      },
    );
    for (final p in purchases) {
      final outcome = await handler.handle(p);
      if (outcome == null) continue;
      unawaited(Analytics.supportOutcome(switch (outcome) {
        SupportOutcome.thanked => 'thanked',
        SupportOutcome.pending => 'pending',
        SupportOutcome.retryLater => 'retry_later',
        SupportOutcome.cancelled => 'cancelled',
        SupportOutcome.error => 'error',
      }));
      if (!mounted) return;
      setState(() {
        _busyProductId = null;
        // A cancelled sheet needs no message — the parent chose to close it.
        _outcome = outcome == SupportOutcome.cancelled ? null : outcome;
      });
      if (outcome == SupportOutcome.thanked) {
        ref.invalidate(supportTransparencyProvider);
      }
    }
  }

  Future<void> _buy(ProductDetails product) async {
    if (_busyProductId != null) return;
    unawaited(Analytics.supportTapped(product.id));
    setState(() {
      _busyProductId = product.id;
      _outcome = null;
    });
    try {
      final started = await ref.read(supportStoreProvider).buy(product);
      if (!started && mounted) {
        setState(() {
          _busyProductId = null;
          _outcome = SupportOutcome.error;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _busyProductId = null;
          _outcome = SupportOutcome.error;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final products = ref.watch(supportProductsProvider);
    final transparency = ref.watch(supportTransparencyProvider).valueOrNull;

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
          if (_outcome != null) ...[
            _OutcomeBanner(outcome: _outcome!),
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
          ...products.when(
            data: (list) => list.isEmpty
                ? [
                    Text(l10n.supportStoreUnavailable,
                        style: TextStyle(color: AppTheme.textMuted)),
                  ]
                : [
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
                  ],
            loading: () => const [
              Center(
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: CircularProgressIndicator(),
                ),
              ),
            ],
            error: (_, _) => [
              Text(l10n.supportStoreUnavailable,
                  style: TextStyle(color: AppTheme.textMuted)),
            ],
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

  final SupportOutcome outcome;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final (text, good) = switch (outcome) {
      SupportOutcome.thanked => (l10n.supportThanks, true),
      SupportOutcome.pending => (l10n.supportPending, true),
      SupportOutcome.retryLater => (l10n.supportRetryLater, true),
      SupportOutcome.error => (l10n.supportError, false),
      SupportOutcome.cancelled => ('', true),
    };
    final color = good ? AppTheme.primary : Theme.of(context).colorScheme.error;
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
