/// «حصاد الجمعة» — Noor's Friday card (نور والقناديل, phase 3).
///
/// Gathered on the phone from `/api/family/week` alone: the week's lanterns
/// light again one after another, the acts are summed up by kind («٣ دروس،
/// سؤالان، مهمة واحدة»), and the card closes with a du'a — the guarded verse
/// [kHarvestDuaId] from the family pack, picked by its id and never typed
/// here (pre-commit's scripture guards check the pack). No server composer,
/// no new notification.
///
/// The shared image carries the lanterns, the summary and the du'a, and is
/// built from those alone, so no child's name can reach it.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../core/app_routes.dart';
import '../../../core/haptics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../l10n/l10n_global.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_theme.dart';
import '../../../widgets/ui/paper_lantern.dart';
import '../../adhkar/data/family_adhkar.dart';
import '../../companion/widgets/noor_face.dart';
import '../../companion/widgets/noor_presence.dart';
import '../../share/share_service.dart';
import '../../share/shareable_moment_card.dart';
import '../data/family_week.dart';
import '../data/lantern_copy.dart';
import 'lantern_row.dart';

/// Al-Furqan 25:74 — the believers' du'a for their spouses and offspring, in
/// the plural the card speaks in. Chosen by id from
/// `assets/content/adhkar/family_adhkar.*.json`; its text and source come
/// from there and nowhere else (both packs carry the verse in Arabic).
const kHarvestDuaId = 'v_025_074';

/// The closing du'a from the loaded pack, or null (pack not loaded, or the
/// id gone) — then the card simply ends without one.
ParentingContent? harvestDua([List<ParentingContent>? pack]) {
  for (final c in pack ?? FamilyAdhkar.items) {
    if (c.id == kHarvestDuaId) return c;
  }
  return null;
}

Future<void> showFridayHarvest(BuildContext context, FamilyWeek week) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      routeSettings: const RouteSettings(name: Screens.fridayHarvest),
      builder: (_) => FridayHarvestCard(week: week, dua: harvestDua()),
    );

class FridayHarvestCard extends StatefulWidget {
  const FridayHarvestCard({super.key, required this.week, this.dua});

  final FamilyWeek week;
  final ParentingContent? dua;

  @override
  State<FridayHarvestCard> createState() => _FridayHarvestCardState();
}

class _FridayHarvestCardState extends State<FridayHarvestCard> {
  bool _sharing = false;

  Future<void> _share() async {
    if (_sharing) return;
    Haptics.selection();
    setState(() => _sharing = true);
    final share = harvestShare(AppL10n.current, widget.week, dua: widget.dua);
    await ShareService.shareMomentCard(
      card: share.card,
      message: share.message,
      fileTag: 'harvest_${widget.week.weekKey}',
    );
    if (mounted) setState(() => _sharing = false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final week = widget.week;
    final dua = widget.dua;
    final summary = harvestSummary(l10n, week);
    return ConstrainedBox(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * .85,
      ),
      child: ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        children: [
          Row(
            children: [
              const NoorPresence(size: 48, face: NoorFaceState.happy),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.harvestTitle,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                        color: colors.ink,
                      ),
                    ),
                    Text(
                      l10n.harvestFromNoor,
                      style: TextStyle(color: colors.textSecondary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            l10n.harvestIntro,
            style: TextStyle(color: colors.textSecondary, height: 1.5),
          ),
          const SizedBox(height: 10),
          Center(
            child: LanternRow(
              count: week.lanterns,
              height: 44,
              stagger: const Duration(milliseconds: 260),
            ),
          ),
          if (summary.isNotEmpty) ...[
            const SizedBox(height: 14),
            Text(
              l10n.harvestSummary(summary),
              style: TextStyle(
                color: colors.ink,
                fontWeight: FontWeight.w700,
                fontSize: 15.5,
                height: 1.6,
              ),
            ),
          ],
          if (dua != null) ...[
            const SizedBox(height: 18),
            Text(
              l10n.harvestDuaLead,
              style: TextStyle(color: colors.textSecondary, height: 1.5),
            ),
            const SizedBox(height: 8),
            HarvestDuaText(dua: dua, color: colors.primary),
          ],
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _sharing ? null : _share,
            icon: const Icon(Icons.share_outlined),
            label: Text(l10n.harvestShare),
          ),
        ],
      ),
    );
  }
}

/// The verse exactly as the pack holds it — right to left whatever the
/// interface language, in the bundled Qur'an face the programs use — and its
/// source. Scripture is not translated: an English reader is told so, with
/// the programs' own note.
class HarvestDuaText extends StatelessWidget {
  const HarvestDuaText({
    super.key,
    required this.dua,
    required this.color,
    this.fontSize = 18,
    this.maxLines,
  });

  final ParentingContent dua;
  final Color color;
  final double fontSize;
  final int? maxLines;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          dua.text,
          textAlign: TextAlign.center,
          textDirection: TextDirection.rtl,
          maxLines: maxLines,
          overflow: maxLines == null ? null : TextOverflow.ellipsis,
          style: GoogleFonts.amiriQuran(
            color: color,
            fontSize: fontSize,
            height: 2.0,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          dua.source,
          textAlign: TextAlign.center,
          textDirection: TextDirection.rtl,
          style: TextStyle(color: color, fontSize: fontSize * .7),
        ),
        if (Localizations.localeOf(context).languageCode != 'ar') ...[
          const SizedBox(height: 4),
          Text(
            AppLocalizations.of(context).programsQuranArabicNote,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: context.colors.textSecondary,
              fontSize: 11.5,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ],
    );
  }
}

/// What a parent shares: the line that travels with the image, and the card
/// the image is captured from. A plain function of the app's strings and the
/// week, so a test reads every word that would leave the phone.
({String message, HarvestShareCard card}) harvestShare(
  AppLocalizations l10n,
  FamilyWeek week, {
  ParentingContent? dua,
}) {
  final summary = harvestSummary(l10n, week);
  return (
    message: l10n.harvestShareMessage(summary),
    card: HarvestShareCard(
      lanterns: week.lanterns,
      summary: summary,
      dua: dua,
    ),
  );
}

/// The 1080×1080 shared image: the week's lanterns, the summary by kind and
/// the closing du'a, on the frame, brand line and QR every shared moment
/// carries. Its inputs are a number, the summary and the du'a — there is no
/// parameter a child's name could arrive through.
class HarvestShareCard extends StatelessWidget {
  const HarvestShareCard({
    super.key,
    required this.lanterns,
    required this.summary,
    this.dua,
  });

  final int lanterns;
  final String summary;
  final ParentingContent? dua;

  @override
  Widget build(BuildContext context) {
    // Captured off-tree: no Localizations, no MediaQuery — the app's strings
    // come from AppL10n.current, and the parent's text scale must not reflow
    // a fixed picture.
    final l10n = AppL10n.current;
    final dir = directionOfLanguage(l10n.localeName);
    final mq = MediaQuery.maybeOf(context);
    final image = Directionality(
      textDirection: dir,
      child: ShareCardFrame(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ShareCardEyebrow(l10n.harvestShareEyebrow),
            const SizedBox(height: 26),
            Wrap(
              spacing: 14,
              alignment: WrapAlignment.center,
              children: [
                for (var i = 0; i < lanterns.clamp(0, 7); i++)
                  const PaperLantern(lit: true, height: 92),
              ],
            ),
            const SizedBox(height: 24),
            if (summary.isNotEmpty)
              Text(
                summary,
                textAlign: TextAlign.center,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.cairo(
                  fontSize: 38,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimary,
                  height: 1.35,
                ),
              ),
            if (dua != null) ...[
              const SizedBox(height: 22),
              Text(
                dua!.text,
                textAlign: TextAlign.center,
                textDirection: TextDirection.rtl,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.amiriQuran(
                  fontSize: 30,
                  color: AppTheme.primary,
                  height: 1.9,
                ),
              ),
              Text(
                dua!.source,
                textAlign: TextAlign.center,
                textDirection: TextDirection.rtl,
                style: GoogleFonts.cairo(
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primary,
                ),
              ),
            ],
            const SizedBox(height: 24),
            const ShareCardBrandFooter(
              qrSize: 96,
            ),
          ],
        ),
      ),
    );
    return mq == null
        ? image
        : MediaQuery(
            data: mq.copyWith(textScaler: TextScaler.noScaling),
            child: image,
          );
  }
}
