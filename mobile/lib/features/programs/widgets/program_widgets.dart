/// Building blocks shared by the family-programs screens.
///
/// Every colour comes from `context.colors` (the palette ThemeExtension), so
/// the screens follow dark mode without a single hard-coded ground; every row
/// grows with its text (no fixed heights), so 200% text wraps instead of
/// clipping; and server text is laid out in its own direction — an English
/// parent can receive an Arabic paragraph whenever a translation is missing.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../../api/tg_client.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/error_retry_view.dart';
import '../../program/data/story_models.dart';
import '../../program/providers/program_providers.dart';
import '../../quran/models/surah_names.dart';
import '../../quran/providers/quran_providers.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';

// ── Formatting ──────────────────────────────────────────────────────────────

String _localeTag(BuildContext context) =>
    Localizations.localeOf(context).toLanguageTag();

/// "8 Feb 2027" / "٨ فبراير ٢٠٢٧".
String programDate(BuildContext context, DateTime date) {
  try {
    return DateFormat.yMMMd(_localeTag(context)).format(date);
  } catch (_) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-'
        '${date.day.toString().padLeft(2, '0')}';
  }
}

/// "March 2019" / "مارس ٢٠١٩".
String programMonthYear(BuildContext context, int year, int month) {
  try {
    return DateFormat.yMMMM(_localeTag(context)).format(DateTime(year, month));
  } catch (_) {
    return '$year-${month.toString().padLeft(2, '0')}';
  }
}

/// Just the month's name, for the picker grid.
String programMonthName(BuildContext context, int month) {
  try {
    return DateFormat.MMMM(_localeTag(context)).format(DateTime(2000, month));
  } catch (_) {
    return '$month';
  }
}

// ── Text in its own direction ───────────────────────────────────────────────

/// Server text, laid out by its own script rather than the chrome's.
class ContentText extends StatelessWidget {
  const ContentText(this.text, {super.key, this.style, this.textAlign});

  final String text;
  final TextStyle? style;
  final TextAlign? textAlign;

  @override
  Widget build(BuildContext context) {
    final dir = ContentDirectionality.resolve(
      text: text,
      fallback: Directionality.of(context),
    );
    return Text(
      text,
      textDirection: dir,
      textAlign: textAlign ?? TextAlign.start,
      style:
          style ??
          TextStyle(color: context.colors.ink, fontSize: 14.5, height: 1.65),
    );
  }
}

/// A list of server sentences, each with a marker.
class ProgramBullets extends StatelessWidget {
  const ProgramBullets(
    this.items, {
    super.key,
    this.numbered = false,
    this.marker,
  });

  final List<String> items;
  final bool numbered;

  /// Overrides the default "•" (e.g. a warning sign on red flags).
  final String? marker;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var i = 0; i < items.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 26,
                  child: Text(
                    numbered ? '${i + 1}.' : (marker ?? '•'),
                    style: TextStyle(
                      color: c.primary,
                      fontWeight: FontWeight.w800,
                      height: 1.65,
                    ),
                  ),
                ),
                Expanded(child: ContentText(items[i])),
              ],
            ),
          ),
      ],
    );
  }
}

// ── Cards ───────────────────────────────────────────────────────────────────

/// A titled card on the screen's ground.
class ProgramSection extends StatelessWidget {
  const ProgramSection({
    super.key,
    required this.child,
    this.title,
    this.emoji,
    this.trailing,
    this.tone = SectionTone.plain,
  });

  final String? title;
  final String? emoji;
  final Widget child;
  final Widget? trailing;
  final SectionTone tone;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final (Color ground, Color border, Color ink) = switch (tone) {
      SectionTone.plain => (c.surface, c.track, c.ink),
      SectionTone.highlight => (
        c.primary.withValues(alpha: .08),
        c.primary.withValues(alpha: .35),
        c.ink,
      ),
      SectionTone.danger => (
        c.dangerBg,
        c.dangerFg.withValues(alpha: .55),
        c.dangerFg,
      ),
      SectionTone.warning => (
        c.warningBg,
        c.warningFg.withValues(alpha: .45),
        c.warningFg,
      ),
    };
    // A Material ground, not a decorated box: switch and expansion tiles in a
    // section paint their ink on the nearest Material, and a coloured box
    // between them hides it (Flutter asserts on exactly that).
    return Padding(
      padding: const EdgeInsets.only(bottom: Dt.s12),
      child: Material(
        color: ground,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Dt.rCard - 6),
          side: BorderSide(color: border),
        ),
        clipBehavior: Clip.antiAlias,
        child: Padding(
          padding: const EdgeInsets.all(Dt.s16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (title != null) ...[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (emoji != null) ...[
                      ExcludeSemantics(
                        child: Text(
                          emoji!,
                          style: const TextStyle(fontSize: 18),
                        ),
                      ),
                      const SizedBox(width: 8),
                    ],
                    Expanded(
                      child: Semantics(
                        header: true,
                        child: Text(
                          title!,
                          style: Theme.of(context).textTheme.titleSmall
                              ?.copyWith(
                                fontWeight: FontWeight.w800,
                                color: ink,
                                height: 1.35,
                              ),
                        ),
                      ),
                    ),
                    ?trailing,
                  ],
                ),
                const SizedBox(height: Dt.s12),
              ],
              child,
            ],
          ),
        ),
      ),
    );
  }
}

enum SectionTone { plain, highlight, danger, warning }

/// A tappable row inside a section: label (and subtitle), forward chevron.
class ProgramLinkRow extends StatelessWidget {
  const ProgramLinkRow({
    super.key,
    required this.label,
    required this.onTap,
    this.subtitle,
    this.emoji,
    this.badge,
  });

  final String label;
  final String? subtitle;
  final String? emoji;
  final String? badge;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    // One node, announced as a button: the label, the subtitle and the badge
    // read together ("The Prayer Journey, stage 2, button"). An InkWell alone
    // gives a tap action but no role, so a screen reader said only the text.
    return MergeSemantics(
      child: Semantics(
        button: true,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: onTap,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: Dt.minTouch),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
                child: Row(
                  children: [
                    if (emoji != null) ...[
                      ExcludeSemantics(
                        child: Text(
                          emoji!,
                          style: const TextStyle(fontSize: 20),
                        ),
                      ),
                      const SizedBox(width: 10),
                    ],
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            label,
                            style: TextStyle(
                              color: c.ink,
                              fontWeight: FontWeight.w700,
                              fontSize: 14.5,
                              height: 1.4,
                            ),
                          ),
                          if (subtitle != null) ...[
                            const SizedBox(height: 2),
                            Text(
                              subtitle!,
                              style: TextStyle(
                                color: c.textSecondary,
                                fontSize: 12.5,
                                height: 1.45,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    if (badge != null) ...[
                      const SizedBox(width: 8),
                      CountBadge(badge!),
                    ],
                    const SizedBox(width: 4),
                    const DirectionalChevron(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A small pill with a count or a short status.
class CountBadge extends StatelessWidget {
  const CountBadge(this.text, {super.key, this.accent = false});
  final String text;
  final bool accent;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final bg = accent ? c.accent : c.primary.withValues(alpha: .12);
    final fg = accent ? c.onAccent : c.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(Dt.rChip),
      ),
      child: Text(
        text,
        style: TextStyle(color: fg, fontWeight: FontWeight.w700, fontSize: 12),
      ),
    );
  }
}

/// A big centred note — for "nothing here yet" and "not available".
class ProgramNote extends StatelessWidget {
  const ProgramNote({
    super.key,
    required this.emoji,
    required this.text,
    this.action,
    this.onAction,
  });

  final String emoji;
  final String text;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) => EmptyState(
    emoji: emoji,
    title: text,
    actionLabel: action,
    onAction: onAction,
  );
}

/// The error view for a programs screen. "The server has no programs" is not
/// shown as an error: it says so plainly, with no retry to hammer.
class ProgramErrorView extends StatelessWidget {
  const ProgramErrorView({
    super.key,
    required this.error,
    required this.onRetry,
  });
  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    if (programsUnavailable(error)) {
      return ProgramNote(
        emoji: '🌙',
        text: AppLocalizations.of(context).programsUnavailable,
      );
    }
    return ErrorRetryView(error: error, onRetry: onRetry);
  }
}

// ── Evidence and Quran ──────────────────────────────────────────────────────

/// Hadith cards — the only place a hadith is ever shown. The Arabic text and
/// its source always; in English, the meaning under a label saying so.
class EvidenceCards extends StatelessWidget {
  const EvidenceCards(this.cards, {super.key});
  final List<EvidenceCard> cards;

  @override
  Widget build(BuildContext context) {
    if (cards.isEmpty) return const SizedBox.shrink();
    final c = context.colors;
    final english = Localizations.localeOf(context).languageCode != 'ar';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final card in cards)
          Container(
            margin: const EdgeInsets.only(top: Dt.s8),
            decoration: BoxDecoration(
              color: c.surfaceAlt,
              borderRadius: BorderRadius.circular(14),
            ),
            clipBehavior: Clip.antiAlias,
            child: IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Container(width: 4, color: c.accent),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.all(Dt.s12),
                      child: _EvidenceBody(card: card, english: english),
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class _EvidenceBody extends StatelessWidget {
  const _EvidenceBody({required this.card, required this.english});
  final EvidenceCard card;
  final bool english;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          card.textAr,
          textDirection: TextDirection.rtl,
          textAlign: TextAlign.right,
          style: TextStyle(
            color: c.ink,
            fontSize: 15.5,
            fontWeight: FontWeight.w700,
            height: 1.8,
          ),
        ),
        const SizedBox(height: 6),
        ContentText(
          card.source,
          style: TextStyle(color: c.textSecondary, fontSize: 12.5, height: 1.5),
        ),
        if (english && card.meaning != null) ...[
          const SizedBox(height: 8),
          Text(
            l10n.programsMeaningLabel,
            style: TextStyle(
              color: c.primary,
              fontWeight: FontWeight.w800,
              fontSize: 12.5,
            ),
          ),
          const SizedBox(height: 2),
          ContentText(card.meaning!),
        ],
      ],
    );
  }
}

/// Juz boundaries (surah, ayah) of the Madani mushaf the app bundles — the
/// same table `ops/tools/check_programs.py` verifies against the ۞ marks.
const List<(int, int)> kJuzStarts = [
  (1, 1),
  (2, 142),
  (2, 253),
  (3, 93),
  (4, 24),
  (4, 148),
  (5, 82),
  (6, 111),
  (7, 88),
  (8, 41),
  (9, 93),
  (11, 6),
  (12, 53),
  (15, 1),
  (17, 1),
  (18, 75),
  (21, 1),
  (23, 1),
  (25, 21),
  (27, 56),
  (29, 46),
  (33, 31),
  (36, 28),
  (39, 32),
  (41, 47),
  (46, 1),
  (51, 31),
  (58, 1),
  (67, 1),
  (78, 1),
];

/// A Quran passage, from the bundled mushaf, in Arabic — never translated.
/// English readers get a line saying the text is shown in Arabic.
class QuranPassage extends ConsumerWidget {
  const QuranPassage({super.key, required this.reference, this.label});

  final QuranRef reference;
  final String? label;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final data = ref.watch(quranDataProvider).valueOrNull;
    final verses = data?['${reference.surah}'];
    final name = reference.surah <= surahNames.length
        ? surahNames[reference.surah - 1]
        : '';
    final range = reference.from == reference.to
        ? '${reference.from}'
        : '${reference.from}–${reference.to}';
    final lines = <String>[
      if (verses != null)
        for (final v in verses)
          if (v is Map &&
              v['verse'] is int &&
              (v['verse'] as int) >= reference.from &&
              (v['verse'] as int) <= reference.to)
            '${v['text']} ﴿${_arabicDigits(v['verse'] as int)}﴾',
    ];
    final english = Localizations.localeOf(context).languageCode != 'ar';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (label != null)
          Text(
            label!,
            style: TextStyle(
              color: c.textSecondary,
              fontWeight: FontWeight.w700,
              fontSize: 12.5,
            ),
          ),
        Text(
          l10n.programsSurahRange(name, range),
          style: TextStyle(
            color: c.primary,
            fontWeight: FontWeight.w800,
            fontSize: 13.5,
            height: 1.5,
          ),
        ),
        if (lines.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(
            lines.join(' '),
            textDirection: TextDirection.rtl,
            textAlign: TextAlign.justify,
            style: GoogleFonts.amiriQuran(
              color: c.ink,
              fontSize: 19,
              height: 2.0,
            ),
          ),
        ],
        if (english) ...[
          const SizedBox(height: 4),
          Text(
            l10n.programsQuranArabicNote,
            style: TextStyle(
              color: c.textSecondary,
              fontSize: 11.5,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
        if (data != null)
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton.icon(
              onPressed: () => Navigator.of(context).push(
                AppRoutes.surahReading(
                  chapterNumber: reference.surah,
                  initialVerse: reference.from,
                  quranData: data,
                ),
              ),
              icon: const Icon(Icons.menu_book_outlined, size: 18),
              label: Text(l10n.programsOpenInQuran),
            ),
          ),
      ],
    );
  }
}

String _arabicDigits(int n) =>
    '$n'.split('').map((d) => '٠١٢٣٤٥٦٧٨٩'[int.parse(d)]).join();

/// The parents' juz for the day, with a way into the mushaf at its first ayah.
class JuzLink extends ConsumerWidget {
  const JuzLink({super.key, required this.juz});
  final int juz;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final data = ref.watch(quranDataProvider).valueOrNull;
    final valid = juz >= 1 && juz <= kJuzStarts.length;
    return ProgramLinkRow(
      emoji: '📖',
      label: l10n.ramadanParentJuz(juz),
      onTap: () {
        if (data == null || !valid) {
          Navigator.of(context).push(AppRoutes.quran());
          return;
        }
        final (surah, ayah) = kJuzStarts[juz - 1];
        Navigator.of(context).push(
          AppRoutes.surahReading(
            chapterNumber: surah,
            initialVerse: ayah,
            quranData: data,
          ),
        );
      },
    );
  }
}

// ── Errors from a change ────────────────────────────────────────────────────

/// One sentence for a refused change: the known codes in the reader's
/// language, anything else through the app's usual failure wording.
String programChangeError(AppLocalizations l10n, Object error) {
  if (error is TgApiError) {
    switch (error.code) {
      case 'step_not_for_age':
        return l10n.fastingErrorNotForAge;
      case 'not_in_season':
        return l10n.programsErrorNotInSeason;
      case 'no_step_set':
        return l10n.fastingErrorNoStep;
      case 'already_enrolled':
        return l10n.prayerErrorAlreadyEnrolled;
      case 'not_eligible':
      case 'track_not_for_age':
        return l10n.prayerErrorNotForAge;
      case 'one_stage_at_a_time':
        return l10n.prayerErrorOneStage;
      case 'graduation_not_yet':
        return l10n.prayerErrorGraduationNotYet;
      case 'day_not_markable':
        return l10n.ramadanErrorDayNotMarkable;
    }
  }
  return describeFailure(l10n, error);
}

void showProgramSnack(BuildContext context, String text) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(text)));
}

// ── Links into the rest of the app ──────────────────────────────────────────

/// A program's or milestone's links: other programs, paths, lessons, stories
/// and existing screens. Titles are looked up; until they arrive (or if they
/// cannot), a plain label keeps the row usable.
class ProgramLinksList extends ConsumerWidget {
  const ProgramLinksList({
    super.key,
    required this.links,
    required this.childId,
    this.childName,
  });

  final ProgramLinks links;
  final int childId;
  final String? childName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final stories = ref.watch(storiesProvider).valueOrNull ?? const <Story>[];
    final rows = <Widget>[
      for (final id in links.programIds)
        if (id == 'ramadan_family')
          ProgramLinkRow(
            emoji: '🌙',
            label: l10n.programsRamadanTitle,
            onTap: () => Navigator.of(context).push(AppRoutes.ramadan(childId)),
          )
        else if (id == 'prayer_journey')
          ProgramLinkRow(
            emoji: '🕌',
            label: l10n.programsPrayerTitle,
            onTap: () =>
                Navigator.of(context).push(AppRoutes.prayerJourney(childId)),
          ),
      for (final id in links.pathIds)
        ProgramLinkRow(
          emoji: '🧭',
          label:
              ref
                  .watch(
                    pathDetailProvider(
                      PathDetailArgs(pathId: id, includeLessons: false),
                    ),
                  )
                  .valueOrNull
                  ?.path
                  .title ??
              l10n.programsPathFallback,
          onTap: () => Navigator.of(context).push(AppRoutes.pathDetail(id, '')),
        ),
      for (final id in links.lessonIds)
        ProgramLinkRow(
          emoji: '📘',
          label:
              ref.watch(lessonProvider(id)).valueOrNull?.title ??
              l10n.programsLessonFallback,
          onTap: () => Navigator.of(
            context,
          ).push(AppRoutes.lesson(id, '', childId: childId)),
        ),
      for (final id in links.storyIds)
        for (final s in stories)
          if (s.id == id)
            ProgramLinkRow(
              emoji: '🌛',
              label: s.title,
              onTap: () => Navigator.of(context).push(AppRoutes.storyReader(s)),
            ),
      for (final f in links.features)
        if (_featureRoute(f, childName ?? l10n.childFallbackName)
            case final route?)
          ProgramLinkRow(
            emoji: _featureEmoji(f),
            label: _featureLabel(l10n, f),
            onTap: () => Navigator.of(context).push(route()),
          ),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: rows,
    );
  }

  /// Existing parent screens a link may name. `assistant` is a tab, not a
  /// route, so it is left to the tab bar.
  static Route<void> Function()? _featureRoute(
    String feature,
    String childName,
  ) => switch (feature) {
    'agreement' => () => AppRoutes.agreement(childName: childName),
    'license' => AppRoutes.parentLicense,
    'missions' => AppRoutes.parentDay,
    'covenant' => AppRoutes.covenant,
    'screen_off' => AppRoutes.screenOffPicker,
    _ => null,
  };

  static String _featureEmoji(String feature) => switch (feature) {
    'agreement' => '🤝',
    'license' => '🪪',
    'missions' => '🧭',
    'covenant' => '📜',
    'screen_off' => '🎧',
    _ => '•',
  };

  static String _featureLabel(AppLocalizations l10n, String feature) =>
      switch (feature) {
        'agreement' => l10n.agreementTitle,
        'license' => l10n.licenseTitle,
        'missions' => l10n.hubParentDay,
        'covenant' => l10n.covenant,
        'screen_off' => l10n.screenOffPickerTitle,
        _ => feature,
      };
}
