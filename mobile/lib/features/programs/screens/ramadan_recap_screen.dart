/// «رمضان عائلتنا» — the family's card and its in-app counters
/// (`GET /api/programs/ramadan/recap`).
///
/// Two halves that never mix. The card (from Eid on) is what may leave the
/// phone: a preview of exactly the image that is shared, and the server's own
/// share text, which carries the family's invite link. Below it, the counters
/// for the family alone — including the children's fasting steps, which are
/// the family's business and never go on the card or into the share.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/tg_client.dart';
import '../../../core/analytics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/loading_view.dart';
import '../../share/share_service.dart';
import '../../share/shareable_moment_card.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';
import '../widgets/program_widgets.dart';
import '../widgets/ramadan_recap_card.dart';

class RamadanRecapScreen extends ConsumerWidget {
  const RamadanRecapScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final recap = ref.watch(ramadanRecapProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(recap.valueOrNull?.card?.title ?? l10n.recapTitle),
      ),
      body: recap.when(
        loading: () => const LoadingView(count: 2, itemHeight: 220),
        error: (e, _) => e is TgApiError && e.code == 'no_season'
            ? ProgramNote(emoji: '🌙', text: l10n.recapNoSeason)
            : ProgramErrorView(
                error: e,
                onRetry: () => ref.invalidate(ramadanRecapProvider),
              ),
        data: (r) => _RecapBody(recap: r),
      ),
    );
  }
}

class _RecapBody extends StatefulWidget {
  const _RecapBody({required this.recap});
  final RamadanRecap recap;

  @override
  State<_RecapBody> createState() => _RecapBodyState();
}

class _RecapBodyState extends State<_RecapBody> {
  bool _sharing = false;

  Future<void> _share(RecapCard card) async {
    if (_sharing) return;
    final l10n = AppLocalizations.of(context);
    setState(() => _sharing = true);
    unawaited(Analytics.programAction('ramadan', 'recap_share'));
    // The server's share text already carries the family's attributed invite;
    // only a card without one gets the app's usual install line appended.
    final ok = await ShareService.shareMomentCard(
      card: RamadanRecapShareCard(card: card),
      message: recapShareMessage(card),
      fileTag: 'ramadan_${widget.recap.hijriYear ?? 'recap'}',
      appendInstallLink: card.shareText == null,
    );
    if (!mounted) return;
    setState(() => _sharing = false);
    if (!ok) showProgramSnack(context, l10n.recapShareFailed);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final r = widget.recap;
    final card = r.card;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      children: [
        if (card != null) ...[
          Text(
            l10n.recapPreview,
            style: TextStyle(
              color: c.textSecondary,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          // The exact widget that is captured and shared, scaled to fit.
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: AspectRatio(
              aspectRatio: 1,
              child: FittedBox(
                child: SizedBox.fromSize(
                  size: ShareableMomentCard.size,
                  child: RamadanRecapShareCard(card: card),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            key: const ValueKey('recap_share'),
            onPressed: _sharing ? null : () => _share(card),
            icon: _sharing
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.share_outlined),
            label: Text(l10n.recapShare),
          ),
          if (r.privacy != null) ...[
            const SizedBox(height: 10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.lock_outline, size: 18, color: c.textSecondary),
                const SizedBox(width: 8),
                Expanded(
                  child: ContentText(
                    r.privacy!,
                    style: TextStyle(
                      color: c.textSecondary,
                      fontSize: 12.5,
                      height: 1.55,
                    ),
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 16),
        ] else
          ProgramSection(
            tone: SectionTone.highlight,
            emoji: '🌙',
            title: l10n.recapTitle,
            child: Text(
              r.availableOn != null
                  ? l10n.recapNotYet(programDate(context, r.availableOn!))
                  : l10n.recapNotYetNoDate,
              style: TextStyle(color: c.ink, height: 1.6),
            ),
          ),
        if (r.progress.isNotEmpty)
          ProgramSection(
            emoji: '✨',
            title: l10n.ramadanSoFar,
            child: _MetricList(metrics: r.progress),
          ),
        if (r.familyOnly.isNotEmpty)
          ProgramSection(
            key: const ValueKey('recap_family_only'),
            emoji: '🔒',
            title: l10n.recapFamilyOnly,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _MetricList(metrics: r.familyOnly),
                const SizedBox(height: 6),
                Text(
                  l10n.recapFamilyOnlyNote,
                  style: TextStyle(
                    color: c.textSecondary,
                    fontSize: 12.5,
                    height: 1.55,
                  ),
                ),
              ],
            ),
          ),
        if (r.progress.isEmpty && r.familyOnly.isEmpty && card == null)
          ProgramNote(emoji: '✅', text: l10n.recapEmpty),
      ],
    );
  }
}

/// Counts only — no maximum beside them, nothing that reads as a shortfall.
class _MetricList extends StatelessWidget {
  const _MetricList({required this.metrics});
  final List<RecapMetric> metrics;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final m in metrics)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              children: [
                Expanded(
                  child: ContentText(
                    m.label,
                    style: TextStyle(color: c.ink, height: 1.5),
                  ),
                ),
                const SizedBox(width: 8),
                if (m.display.isNotEmpty) CountBadge(m.display),
              ],
            ),
          ),
      ],
    );
  }
}
