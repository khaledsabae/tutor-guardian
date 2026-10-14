/// The pieces of «رمضان العائلة»: a day's card, the family's «تمّ» marks, the
/// fasting summary and the moon-sighting settings.
///
/// Marks are tick-only. A day not ticked is not a "missed" day anywhere on
/// screen — no red, no cross, no "0 of 4" — because a shame metric is the one
/// thing this program must never become (MOBILE_API §11.0). Each mark is a
/// paper lantern that lights when ticked; an unticked one is plain paper.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../core/haptics.dart';
import '../../../core/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../../../state/chat_notifier.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/paper_lantern.dart';
import '../../program/data/story_models.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';
import 'program_widgets.dart';

/// The clock the Ramadan screens read — a provider so tests can pin the hour
/// (day 29's "Is tomorrow Eid?" appears in the evening).
final programsClockProvider = Provider<DateTime Function()>(
  (_) => DateTime.now,
);

/// The marks a day can carry, in the order they are shown.
const List<String> kRamadanTickMarks = [
  'challenge_done',
  'wird_done',
  'story_heard',
  'juz_read',
  'night_joined',
];

String ramadanMarkLabel(AppLocalizations l10n, String mark) => switch (mark) {
  'challenge_done' => l10n.ramadanMarkChallenge,
  'wird_done' => l10n.ramadanMarkWird,
  'story_heard' => l10n.ramadanMarkStory,
  'juz_read' => l10n.ramadanMarkJuz,
  'night_joined' => l10n.ramadanMarkNight,
  _ => mark,
};

String? _phaseLabel(AppLocalizations l10n, String? phase) => switch (phase) {
  'first_ten' => l10n.ramadanPhaseFirstTen,
  'middle_ten' => l10n.ramadanPhaseMiddleTen,
  'last_ten' => l10n.ramadanPhaseLastTen,
  _ => null,
};

String? _whenLabel(AppLocalizations l10n, String? when) => switch (when) {
  'suhoor' => l10n.ramadanWhenSuhoor,
  'before_iftar' => l10n.ramadanWhenBeforeIftar,
  'at_iftar' => l10n.ramadanWhenAtIftar,
  'after_iftar' => l10n.ramadanWhenAfterIftar,
  'night' => l10n.ramadanWhenNight,
  'anytime' => l10n.ramadanWhenAnytime,
  _ => null,
};

/// One day of the month: the family challenge, the child's part, the note for
/// the parents, the Quran portion, tonight's story, and the family's ticks.
class RamadanDayCard extends ConsumerWidget {
  const RamadanDayCard({
    super.key,
    required this.childId,
    required this.childName,
    required this.content,
    this.marks,
    this.markable = false,
    this.onMarksChanged,
  });

  final int childId;
  final String childName;
  final RamadanDayContent content;

  /// Null when the day cannot be ticked (a future day).
  final RamadanMarks? marks;
  final bool markable;

  /// The day's marks as the parent leaves them, on every tap (and again if
  /// the server refuses one and it is put back).
  final ValueChanged<RamadanMarks>? onMarksChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final phase = _phaseLabel(l10n, content.phase);
    final challenge = content.familyChallenge;
    final variant = content.variant;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 6,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            CountBadge(l10n.ramadanDayN(content.day), accent: true),
            if (phase != null) CountBadge(phase),
          ],
        ),
        const SizedBox(height: 10),
        ContentText(
          content.title,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w800,
            color: c.ink,
            height: 1.35,
          ),
        ),
        const SizedBox(height: 12),
        if (content.oddNight)
          ProgramSection(
            tone: SectionTone.highlight,
            child: Text(
              '✨ ${l10n.ramadanOddNight}',
              style: TextStyle(
                color: c.ink,
                fontWeight: FontWeight.w700,
                height: 1.5,
              ),
            ),
          ),
        if (content.mayNotOccur)
          ProgramSection(
            child: Text(
              l10n.ramadanMayNotOccur,
              style: TextStyle(color: c.textSecondary, height: 1.5),
            ),
          ),
        if (challenge != null)
          ProgramSection(
            title: l10n.ramadanFamilyChallenge,
            emoji: '👨‍👩‍👧',
            child: _ChallengeBody(challenge: challenge),
          ),
        if (variant != null)
          ProgramSection(
            title: l10n.ramadanChildPart(childName),
            emoji: '🧒',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ContentText(variant.text),
                if (variant.forChild) ...[
                  const SizedBox(height: 6),
                  Text(
                    l10n.ramadanReadWithChild(childName),
                    style: TextStyle(color: c.textSecondary, fontSize: 12.5),
                  ),
                ],
              ],
            ),
          ),
        if (content.parentNote != null)
          ProgramSection(
            title: l10n.ramadanParentNote,
            emoji: '💬',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ContentText(content.parentNote!.text),
                EvidenceCards(content.parentNote!.evidence),
              ],
            ),
          ),
        if (!content.quran.isEmpty)
          ProgramSection(
            title: l10n.ramadanWirdTitle,
            emoji: '📗',
            child: RamadanQuranBlock(quran: content.quran),
          ),
        if (content.storyId != null) _StoryRow(storyId: content.storyId!),
        if (marks != null && markable)
          RamadanMarksPanel(
            day: content.day,
            tracks: content.tracks,
            initial: marks!,
            wordChoices: content.familyWordChoices,
            onChanged: onMarksChanged,
          ),
      ],
    );
  }
}

class _ChallengeBody extends StatelessWidget {
  const _ChallengeBody({required this.challenge});
  final FamilyChallenge challenge;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final when = _whenLabel(l10n, challenge.when);
    final chips = <String>[
      if (challenge.minutes != null) l10n.ramadanMinutes(challenge.minutes!),
      ?when,
      if (challenge.cost == 'free') l10n.ramadanCostFree,
      if (challenge.cost == 'low') l10n.ramadanCostLow,
      if (challenge.atHome == true) l10n.ramadanAtHome,
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ContentText(
          challenge.title,
          style: TextStyle(
            color: c.ink,
            fontWeight: FontWeight.w800,
            fontSize: 15.5,
            height: 1.5,
          ),
        ),
        const SizedBox(height: 8),
        if (chips.isNotEmpty) ...[
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [for (final t in chips) CountBadge(t)],
          ),
          const SizedBox(height: 10),
        ],
        ProgramBullets(challenge.steps, numbered: true),
        if (challenge.materials.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            l10n.ramadanMaterials,
            style: TextStyle(
              color: c.textSecondary,
              fontWeight: FontWeight.w700,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 4),
          ProgramBullets(challenge.materials),
        ],
      ],
    );
  }
}

/// The family's Quran for the day: the short surah read together, the day's
/// passage, and the parents' juz.
class RamadanQuranBlock extends StatelessWidget {
  const RamadanQuranBlock({super.key, required this.quran});
  final RamadanQuran quran;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (quran.together != null)
          QuranPassage(
            reference: quran.together!,
            label: l10n.ramadanWirdTogether,
          ),
        if (quran.themeRef != null) ...[
          const SizedBox(height: 8),
          QuranPassage(
            reference: quran.themeRef!,
            label: l10n.ramadanWirdTheme,
          ),
        ],
        if (quran.parentJuz != null) JuzLink(juz: quran.parentJuz!),
      ],
    );
  }
}

/// Tonight's story, opened in the app's own reader. Hidden when the story is
/// not in the bundled library (the content check keeps that from happening).
class _StoryRow extends ConsumerWidget {
  const _StoryRow({required this.storyId});
  final String storyId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final stories = ref.watch(storiesProvider).valueOrNull;
    Story? story;
    for (final s in stories ?? const <Story>[]) {
      if (s.id == storyId) story = s;
    }
    if (story == null) return const SizedBox.shrink();
    final found = story;
    return ProgramSection(
      child: ProgramLinkRow(
        emoji: '🌛',
        label: l10n.ramadanStoryTonight(found.title),
        subtitle: l10n.ramadanReadStory,
        onTap: () {
          unawaited(Analytics.programAction('ramadan', 'story'));
          Navigator.of(context).push(AppRoutes.storyReader(found));
        },
      ),
    );
  }
}

/// The family's «تمّ» toggles for one day, as paper lanterns. Ticks only: an
/// unticked mark is drawn exactly like a mark not yet reached — never as
/// missed. When every mark of the day is ticked the panel glows a quiet
/// «الحمد لله»: no confetti, no count.
class RamadanMarksPanel extends ConsumerStatefulWidget {
  const RamadanMarksPanel({
    super.key,
    required this.day,
    required this.tracks,
    required this.initial,
    this.wordChoices = const [],
    this.onChanged,
  });

  final int day;
  final List<String> tracks;
  final RamadanMarks initial;
  final List<String> wordChoices;
  final ValueChanged<RamadanMarks>? onChanged;

  @override
  ConsumerState<RamadanMarksPanel> createState() => _RamadanMarksPanelState();
}

class _RamadanMarksPanelState extends ConsumerState<RamadanMarksPanel> {
  late RamadanMarks _marks = widget.initial;
  final Set<String> _busy = {};

  @override
  void didUpdateWidget(covariant RamadanMarksPanel old) {
    super.didUpdateWidget(old);
    if (old.initial != widget.initial && _busy.isEmpty) _marks = widget.initial;
  }

  void _set(RamadanMarks marks) {
    setState(() => _marks = marks);
    widget.onChanged?.call(marks);
  }

  Future<void> _toggle(String mark) async {
    if (_busy.contains(mark)) return;
    unawaited(Haptics.selection());
    final l10n = AppLocalizations.of(context);
    final container = programsContainerOf(context);
    final done = !_marks.isDone(mark);
    setState(() => _busy.add(mark));
    _set(
      RamadanMarks(
        ticks: {..._marks.ticks, mark: done},
        familyWord: _marks.familyWord,
        familyWordIndex: _marks.familyWordIndex,
      ),
    );
    try {
      final json = await ref
          .read(tgClientProvider)
          .setRamadanMark(mark: mark, day: widget.day, done: done);
      final fresh = RamadanMarks.fromJson(json['marks']);
      unawaited(Analytics.programAction('ramadan', done ? 'mark' : 'unmark'));
      refreshProgramsSummary(container);
      // Today's screen keeps its data on screen while it refetches, so a tick
      // made on another day's page is there when the parent comes back.
      container.invalidate(ramadanTodayProvider);
      if (!mounted) return;
      _set(fresh ?? _marks);
    } catch (e) {
      if (!mounted) return;
      _set(
        RamadanMarks(
          ticks: {..._marks.ticks, mark: !done},
          familyWord: _marks.familyWord,
          familyWordIndex: _marks.familyWordIndex,
        ),
      );
      showProgramSnack(context, programChangeError(l10n, e));
    } finally {
      if (mounted) setState(() => _busy.remove(mark));
    }
  }

  Future<void> _chooseWord(int index) async {
    if (_busy.contains('family_word')) return;
    final l10n = AppLocalizations.of(context);
    final container = programsContainerOf(context);
    setState(() => _busy.add('family_word'));
    try {
      final json = await ref
          .read(tgClientProvider)
          .setRamadanMark(
            mark: 'family_word',
            day: widget.day,
            choiceIndex: index,
          );
      final fresh = RamadanMarks.fromJson(json['marks']);
      unawaited(Analytics.programAction('ramadan', 'family_word'));
      container.invalidate(ramadanTodayProvider);
      if (!mounted) return;
      _set(fresh ?? _marks);
    } catch (e) {
      if (mounted) showProgramSnack(context, programChangeError(l10n, e));
    } finally {
      if (mounted) setState(() => _busy.remove('family_word'));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final ticks = [
      for (final m in kRamadanTickMarks)
        if (widget.tracks.contains(m)) m,
    ];
    final hasWord =
        widget.tracks.contains('family_word') && widget.wordChoices.isNotEmpty;
    if (ticks.isEmpty && !hasWord) return const SizedBox.shrink();
    final wordChosen =
        _marks.familyWordIndex != null || _marks.familyWord != null;
    final complete =
        ticks.every(_marks.isDone) && (!hasWord || wordChosen) &&
        (ticks.isNotEmpty || hasWord);

    return ProgramSection(
      title: l10n.ramadanMarksTitle,
      emoji: '✅',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _DayGlow(
            complete: complete,
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final m in ticks)
                  RamadanLanternToggle(
                    key: ValueKey('ramadan_mark_$m'),
                    label: ramadanMarkLabel(l10n, m),
                    lit: _marks.isDone(m),
                    onChanged: _busy.contains(m) ? null : (_) => _toggle(m),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            l10n.ramadanMarksNote,
            style: TextStyle(
              color: c.textSecondary,
              fontSize: 12.5,
              height: 1.5,
            ),
          ),
          if (hasWord) ...[
            const SizedBox(height: 14),
            Text(
              l10n.ramadanFamilyWordTitle,
              style: TextStyle(color: c.ink, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 4),
            Text(
              l10n.ramadanFamilyWordHint,
              style: TextStyle(
                color: c.textSecondary,
                fontSize: 12.5,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (var i = 0; i < widget.wordChoices.length; i++)
                  ChoiceChip(
                    label: ContentText(widget.wordChoices[i]),
                    selected:
                        _marks.familyWordIndex == i ||
                        (_marks.familyWordIndex == null &&
                            _marks.familyWord == widget.wordChoices[i]),
                    onSelected: _busy.contains('family_word')
                        ? null
                        : (_) => _chooseWord(i),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// One «تمّ» mark as a paper lantern: lit when ticked, plain paper when not.
/// To a screen reader, a toggle button named after the mark.
class RamadanLanternToggle extends StatelessWidget {
  const RamadanLanternToggle({
    super.key,
    required this.label,
    required this.lit,
    required this.onChanged,
  });

  final String label;
  final bool lit;

  /// Null while the change is on its way.
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final change = onChanged;
    final tap = change == null ? null : () => change(!lit);
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: BorderSide(
        color: lit ? c.paperGold : c.track,
        width: lit ? 1.5 : 1,
      ),
    );
    return Semantics(
      container: true,
      button: true,
      toggled: lit,
      enabled: tap != null,
      label: label,
      onTap: tap,
      excludeSemantics: true,
      child: Material(
        color: lit
            ? c.paperGold.withValues(alpha: c.isDark ? .14 : .2)
            : c.surface,
        shape: shape,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: tap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Padding(
              padding: const EdgeInsetsDirectional.fromSTEB(8, 6, 14, 6),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  PaperLantern(lit: lit, height: 32),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      label,
                      style: TextStyle(
                        color: c.ink,
                        fontWeight: lit ? FontWeight.w700 : FontWeight.w500,
                        height: 1.35,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The quiet glow round a day whose every mark is ticked: the lanterns' ground
/// warms and «الحمد لله» appears under them. Once, softly; nothing loops,
/// nothing bursts, and under reduced motion it simply is there.
class _DayGlow extends StatelessWidget {
  const _DayGlow({required this.complete, required this.child});
  final bool complete;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final duration = reduceMotion(context)
        ? Duration.zero
        : const Duration(milliseconds: 600);
    return AnimatedContainer(
      duration: duration,
      curve: Curves.easeOut,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: c.paperGold.withValues(
          alpha: complete ? (c.isDark ? .10 : .14) : 0,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: c.paperGold.withValues(alpha: complete ? .55 : 0),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          child,
          AnimatedSwitcher(
            duration: duration,
            child: complete
                ? Padding(
                    key: const ValueKey('ramadan_day_complete'),
                    padding: const EdgeInsets.only(top: 10),
                    child: Semantics(
                      liveRegion: true,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const PaperLantern(lit: true, height: 24),
                          const SizedBox(width: 6),
                          Flexible(
                            child: Text(
                              l10n.ramadanDayComplete,
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: c.ink,
                                fontWeight: FontWeight.w800,
                                fontSize: 15,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                : const SizedBox(width: double.infinity),
          ),
        ],
      ),
    );
  }
}

/// The child's step on the fasting ladder, inside the day's view.
class FastingSummaryCard extends ConsumerStatefulWidget {
  const FastingSummaryCard({
    super.key,
    required this.childId,
    required this.childName,
    required this.fasting,
    required this.inMonth,
  });

  final int childId;
  final String childName;
  final FastingSummary fasting;

  /// Practice is recorded only during the month.
  final bool inMonth;

  @override
  ConsumerState<FastingSummaryCard> createState() => _FastingSummaryCardState();
}

class _FastingSummaryCardState extends ConsumerState<FastingSummaryCard> {
  late FastingSummary _f = widget.fasting;
  bool _busy = false;

  @override
  void didUpdateWidget(covariant FastingSummaryCard old) {
    super.didUpdateWidget(old);
    if (!_busy) _f = widget.fasting;
  }

  Future<void> _practise(bool done) async {
    final l10n = AppLocalizations.of(context);
    final container = programsContainerOf(context);
    setState(() => _busy = true);
    try {
      final json = await ref
          .read(tgClientProvider)
          .recordFastingPractice(widget.childId, done: done);
      container.invalidate(fastingLadderProvider(widget.childId));
      if (!mounted) return;
      setState(
        () => _f = FastingSummary(
          ladderBand: _f.ladderBand,
          fasts: _f.fasts,
          reachedPuberty: _f.reachedPuberty,
          currentStep:
              FastingStepSummary.fromJson(json['current_step']) ??
              _f.currentStep,
          practisedToday: json['practised_today'] == true,
          practisedThisWeek:
              (json['practised_this_week'] as num?)?.toInt() ??
              _f.practisedThisWeek,
          restSuggested: json['rest_suggested'] == true,
        ),
      );
      unawaited(
        Analytics.programAction('ramadan', done ? 'practised' : 'unpractised'),
      );
    } catch (e) {
      if (mounted) showProgramSnack(context, programChangeError(l10n, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final step = _f.currentStep;
    return ProgramSection(
      title: l10n.ramadanFastingTitle,
      emoji: '🌅',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_f.noFasting)
            Text(
              l10n.ramadanNoFastingBeforeSeven,
              style: TextStyle(color: c.ink, height: 1.6),
            )
          else if (step == null)
            Text(
              l10n.ramadanFastingNoStep(widget.childName),
              style: TextStyle(color: c.ink, height: 1.6),
            )
          else ...[
            ContentText(
              l10n.ramadanFastingStep(widget.childName, step.label),
              style: TextStyle(
                color: c.ink,
                fontWeight: FontWeight.w700,
                height: 1.5,
              ),
            ),
            if (step.approxHours != null && step.approxHours! > 0)
              Text(
                l10n.fastingHours(step.approxHours!),
                style: TextStyle(color: c.textSecondary, fontSize: 13),
              ),
            if (widget.inMonth) ...[
              const SizedBox(height: 6),
              SwitchListTile.adaptive(
                key: const ValueKey('fasting_practised_today'),
                contentPadding: EdgeInsets.zero,
                title: Text(l10n.ramadanPractisedToday(widget.childName)),
                value: _f.practisedToday,
                onChanged: _busy ? null : _practise,
              ),
              if (_f.practisedThisWeek > 0)
                Text(
                  l10n.ramadanPractisedThisWeek(_f.practisedThisWeek),
                  style: TextStyle(
                    color: c.successText,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              if (_f.restSuggested) ...[
                const SizedBox(height: 6),
                Text(
                  '🌿 ${l10n.ramadanRestSuggested}',
                  style: TextStyle(color: c.ink, height: 1.5),
                ),
              ],
            ],
          ],
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton(
              onPressed: () {
                unawaited(Analytics.programAction('ramadan', 'ladder'));
                Navigator.of(
                  context,
                ).push(AppRoutes.fastingLadder(widget.childId));
              },
              child: Text(
                step == null && !_f.noFasting
                    ? l10n.ramadanChooseStep
                    : l10n.ramadanOpenLadder,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The family's own sighting: a day earlier or later, and 29 or 30 days.
Future<void> showRamadanSettingsSheet(
  BuildContext context,
  RamadanSeason season,
) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => RamadanSettingsSheet(season: season),
  );
}

class RamadanSettingsSheet extends ConsumerStatefulWidget {
  const RamadanSettingsSheet({super.key, required this.season});
  final RamadanSeason season;

  @override
  ConsumerState<RamadanSettingsSheet> createState() =>
      _RamadanSettingsSheetState();
}

class _RamadanSettingsSheetState extends ConsumerState<RamadanSettingsSheet> {
  late RamadanSeason _season = widget.season;
  bool _busy = false;

  Future<void> _send({int? shift, int? days, bool resetDays = false}) async {
    final l10n = AppLocalizations.of(context);
    final container = programsContainerOf(context);
    setState(() => _busy = true);
    try {
      final json = await ref
          .read(tgClientProvider)
          .updateRamadanSettings(
            startShiftDays: shift,
            monthDays: days,
            resetMonthDays: resetDays,
          );
      final season = RamadanSeason.fromJson(json['season']);
      unawaited(Analytics.programAction('ramadan', 'settings'));
      refreshProgramsSummary(container);
      container.invalidate(ramadanTodayProvider);
      container.invalidate(ramadanDayProvider);
      container.invalidate(fastingLadderProvider);
      if (!mounted) return;
      setState(() => _season = season ?? _season);
      showProgramSnack(context, l10n.programsSaved);
    } catch (e) {
      if (mounted) showProgramSnack(context, programChangeError(l10n, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              l10n.ramadanSettingsTitle,
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.ramadanSettingsIntro,
              style: TextStyle(color: c.textSecondary, height: 1.6),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.ramadanSettingsCurrent(
                programDate(context, _season.startsOn),
                _season.days,
              ),
              style: TextStyle(
                color: c.ink,
                fontWeight: FontWeight.w700,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 18),
            Text(
              l10n.ramadanSettingsStart,
              style: TextStyle(color: c.ink, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (shift, label) in [
                  (-1, l10n.ramadanShiftEarlier),
                  (0, l10n.ramadanShiftNone),
                  (1, l10n.ramadanShiftLater),
                ])
                  ChoiceChip(
                    key: ValueKey('ramadan_shift_$shift'),
                    label: Text(label),
                    selected: _season.shiftDays == shift,
                    onSelected: _busy || _season.shiftDays == shift
                        ? null
                        : (_) => _send(shift: shift),
                  ),
              ],
            ),
            const SizedBox(height: 18),
            Text(
              l10n.ramadanSettingsLength,
              style: TextStyle(color: c.ink, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ActionChip(
                  key: const ValueKey('ramadan_days_29'),
                  label: Text(l10n.ramadanDays29),
                  onPressed: _busy ? null : () => _send(days: 29),
                ),
                ActionChip(
                  key: const ValueKey('ramadan_days_30'),
                  label: Text(l10n.ramadanDays30),
                  onPressed: _busy ? null : () => _send(days: 30),
                ),
                ActionChip(
                  key: const ValueKey('ramadan_days_auto'),
                  label: Text(l10n.ramadanDaysAuto),
                  onPressed: _busy ? null : () => _send(resetDays: true),
                ),
              ],
            ),
            const SizedBox(height: Dt.s16),
          ],
        ),
      ),
    );
  }
}
