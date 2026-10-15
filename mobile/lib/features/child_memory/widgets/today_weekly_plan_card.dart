/// «خطة الأسبوع» on Today — plan §1.3 (MOBILE_API §9.5).
///
/// One focus, three small actions, one act of worship together, one lesson —
/// for the active child, for the parent's local ISO week as the SERVER drew
/// it (`week_start`). Collapsed to the focus by default: Today was cut to three
/// stops because «مش عارف أبدأ منين», and the week's plan must not undo that.
///
/// Every step can be ticked with one tap (نور والقناديل phase 3, §9.5.1): the
/// tick shows at once, a snack bar offers «تراجع» (the DELETE), and the
/// server's `marks` then replace the local copy. A ticked action lights a
/// lantern of the week; the worship item shows ticked but lights none — the
/// server decides that, not this card. Only what was done is drawn: no step
/// is ever shown as missed.
///
/// The Monday reveal: the first open of the new plan's Monday opens the card
/// and brings its steps in one after another — once a week per child, and
/// with no motion under reduced motion.
///
/// Every band has a plan (the server's banks cover prenatal-1 … 16-18), so
/// nothing here is band-gated. Hides itself while loading, on any failure, on
/// an older server, and when the plan has no focus or actions.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../core/clock.dart';
import '../../../core/haptics.dart';
import '../../../core/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../../lanterns/providers/lantern_providers.dart';
import '../../onboarding/providers/onboarding_providers.dart'
    show sharedPreferencesProvider;
import '../data/memory_models.dart';
import '../providers/memory_providers.dart';
import 'memory_errors.dart';

class TodayWeeklyPlanCard extends ConsumerStatefulWidget {
  const TodayWeeklyPlanCard({
    super.key,
    required this.childId,
    required this.childName,
    required this.ageGroup,
  });

  final int childId;
  final String childName;
  final String ageGroup;

  /// Where the phone remembers the week it revealed for a child (Monday).
  static String revealKey(int childId) => 'plan.reveal.v1.$childId';

  @override
  ConsumerState<TodayWeeklyPlanCard> createState() =>
      _TodayWeeklyPlanCardState();
}

class _TodayWeeklyPlanCardState extends ConsumerState<TodayWeeklyPlanCard> {
  late final AppLifecycleListener _lifecycle;
  bool _expanded = false;

  /// The week whose rollover was already asked for, so a stale plan is
  /// refetched once — not on every frame until the new one arrives.
  String? _refreshedWeek;

  /// The ticks as drawn: the plan's, then each tap applied at once, then the
  /// server's answer to the latest request.
  List<String> _marks = const [];
  String? _marksWeek;

  /// Only the answer to the newest tick may overwrite [_marks]: a PUT and its
  /// undo can come back in either order.
  int _seq = 0;

  /// This open brings the steps in one by one (Monday's reveal).
  bool _revealing = false;
  String? _revealChecked;

  WeeklyPlanKey _key(BuildContext context) => (
        childId: widget.childId,
        lang: Localizations.localeOf(context).languageCode == 'en' ? 'en' : 'ar',
      );

  @override
  void initState() {
    super.initState();
    _lifecycle = AppLifecycleListener(onResume: _checkWeek);
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  /// A new plan appears on the family's Monday. The app may have slept
  /// through it, so a plan whose week has ended is asked for again.
  void _checkWeek() {
    if (!mounted) return;
    final key = _key(context);
    final plan = ref.read(weeklyPlanProvider(key)).valueOrNull;
    final next = plan?.nextWeekStart;
    if (plan == null || next == null || _refreshedWeek == plan.week) return;
    if (!DateTime.now().isBefore(next)) {
      _refreshedWeek = plan.week;
      ref.invalidate(weeklyPlanProvider(key));
    }
  }

  /// Monday, and this is the new week's plan, and this phone has not shown
  /// it yet: open the card and bring the steps in one after another.
  void _checkReveal(WeeklyPlan plan) {
    if (!mounted || _revealChecked == plan.week) return;
    _revealChecked = plan.week;
    final now = ref.read(clockProvider)();
    final start = plan.weekStart;
    if (now.weekday != DateTime.monday ||
        start == null ||
        !DateUtils.isSameDay(start, now)) {
      return;
    }
    final prefs = ref.read(sharedPreferencesProvider).valueOrNull;
    final week = plan.weekStartWire;
    final key = TodayWeeklyPlanCard.revealKey(widget.childId);
    if (prefs == null || week == null || prefs.getString(key) == week) return;
    unawaited(prefs.setString(key, week));
    setState(() {
      _expanded = true;
      _revealing = true;
    });
  }

  Future<void> _setMark(WeeklyPlan plan, PlanItem item, bool marked) async {
    final week = plan.weekStartWire;
    if (week == null || item.key.isEmpty) return;
    final seq = ++_seq;
    setState(() {
      _marks = [
        for (final m in _marks)
          if (m != item.key) m,
        if (marked) item.key,
      ];
    });
    try {
      final marks = await ref.read(memoryRepositoryProvider).setPlanMark(
            widget.childId,
            weekStart: week,
            itemKey: item.key,
            marked: marked,
          );
      if (!mounted) return;
      if (seq == _seq) setState(() => _marks = marks);
      // A ticked action lights a lantern of the week (§12).
      ref.invalidate(familyWeekProvider);
    } catch (e) {
      if (!mounted || seq != _seq) return;
      // The tap did not reach the server: put the step back as it was.
      setState(() {
        _marks = [
          for (final m in _marks)
            if (m != item.key) m,
          if (!marked) item.key,
        ];
      });
      // The «done» line (and its undo) no longer holds: say why instead.
      ScaffoldMessenger.maybeOf(context)
        ?..removeCurrentSnackBar()
        ..showSnackBar(
            SnackBar(content: Text(describeActionFailure(context, e))));
    }
  }

  void _tap(WeeklyPlan plan, PlanItem item) {
    final l10n = AppLocalizations.of(context);
    final marked = !_marks.contains(item.key);
    unawaited(Analytics.todayBlockTapped(
        'loop', marked ? 'plan_mark' : 'plan_unmark'));
    if (marked) {
      Haptics.success();
      final messenger = ScaffoldMessenger.maybeOf(context);
      messenger?.hideCurrentSnackBar();
      messenger?.showSnackBar(SnackBar(
        content: Text(l10n.planMarkDone),
        action: SnackBarAction(
          label: l10n.planMarkUndo,
          onPressed: () {
            if (!mounted) return;
            unawaited(Analytics.todayBlockTapped('loop', 'plan_undo'));
            unawaited(_setMark(plan, item, false));
          },
        ),
      ));
    } else {
      Haptics.selection();
    }
    unawaited(_setMark(plan, item, marked));
  }

  @override
  Widget build(BuildContext context) {
    final key = _key(context);
    final plan = ref.watch(weeklyPlanProvider(key)).valueOrNull;
    if (plan == null) return const SizedBox.shrink();
    if (_marksWeek != plan.week) {
      _marksWeek = plan.week;
      _marks = List.of(plan.marks);
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkWeek();
      _checkReveal(plan);
    });

    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final dir = directionOfLanguage(plan.lang);
    final range = _weekRange(context, plan);
    final planKeys = {
      for (final a in plan.actions) a.key,
      if (plan.worship != null) plan.worship!.key,
    };
    final done = _marks.where(planKeys.contains).length;

    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Container(
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: BorderRadius.circular(Dt.rCard),
          border: Border.all(color: colors.track),
        ),
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.calendar_month_outlined,
                    color: colors.accentDeep, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    l10n.planTitleFor(widget.childName),
                    style: TextStyle(
                      color: colors.accentDeep,
                      fontWeight: FontWeight.w800,
                      fontSize: 13,
                    ),
                  ),
                ),
                if (range != null)
                  Text(range,
                      style: TextStyle(color: colors.inkSoft, fontSize: 11.5)),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              plan.focusTitle,
              textDirection: dir,
              style: TextStyle(
                color: colors.ink,
                fontWeight: FontWeight.w800,
                fontSize: 16,
                height: 1.4,
              ),
            ),
            if (plan.focusReasonText != null) ...[
              const SizedBox(height: 4),
              Text(
                plan.focusReasonText!,
                textDirection: dir,
                style: TextStyle(
                    color: colors.textSecondary, fontSize: 12.5, height: 1.5),
              ),
            ],
            if (done > 0) ...[
              const SizedBox(height: 6),
              Row(
                children: [
                  Icon(Icons.check_circle_rounded,
                      color: colors.success, size: 16),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      l10n.planMarkedCount(done),
                      style: TextStyle(
                        color: colors.successText,
                        fontWeight: FontWeight.w700,
                        fontSize: 12.5,
                      ),
                    ),
                  ),
                ],
              ),
            ],
            if (_expanded) ..._details(context, plan, dir),
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: TextButton(
                onPressed: () {
                  if (!_expanded) {
                    unawaited(Analytics.todayBlockTapped('loop', 'plan_expand'));
                  }
                  setState(() {
                    _expanded = !_expanded;
                    _revealing = false;
                  });
                },
                child: Text(_expanded ? l10n.planShowLess : l10n.planShowAll),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Monday's reveal brings each row in after the one before it.
  Widget _reveal(Widget child, int index) {
    if (!_revealing || reduceMotion(context)) return child;
    return child
        .animate(delay: Duration(milliseconds: 140 * index))
        .fadeIn(duration: Dt.base)
        .slideY(begin: .25, end: 0, duration: Dt.base, curve: Curves.easeOut);
  }

  List<Widget> _details(BuildContext context, WeeklyPlan plan, TextDirection dir) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    Widget heading(String text) => Padding(
          padding: const EdgeInsets.only(top: 14, bottom: 6),
          child: Text(text,
              style: TextStyle(
                  color: colors.textSecondary,
                  fontWeight: FontWeight.w700,
                  fontSize: 12.5)),
        );
    var row = 0;
    return [
      heading(l10n.planSteps),
      for (var i = 0; i < plan.actions.length; i++)
        _reveal(
          _MarkRow(
            item: plan.actions[i],
            number: i + 1,
            marked: _marks.contains(plan.actions[i].key),
            dir: dir,
            onTap: () => _tap(plan, plan.actions[i]),
          ),
          row++,
        ),
      if (plan.adaptedFromOutcomes)
        Text(l10n.planAdapted,
            style: TextStyle(color: colors.inkSoft, fontSize: 12, height: 1.5)),
      if (plan.worship != null) ...[
        heading(l10n.planWorship),
        _reveal(
          _MarkRow(
            item: plan.worship!,
            marked: _marks.contains(plan.worship!.key),
            dir: dir,
            onTap: () => _tap(plan, plan.worship!),
          ),
          row++,
        ),
      ],
      if (plan.lesson != null) ...[
        heading(l10n.planLesson),
        _reveal(
          _LessonRow(
            lesson: plan.lesson!,
            dir: dir,
            onTap: () {
              unawaited(Analytics.todayBlockTapped('loop', 'plan_lesson'));
              Navigator.of(context).push(AppRoutes.lesson(
                plan.lesson!.id,
                widget.ageGroup,
                childId: widget.childId,
              ));
            },
          ),
          row++,
        ),
      ],
      const SizedBox(height: 4),
    ];
  }

  /// "5 Oct – 11 Oct" on the family's calendar, from the server's Monday.
  String? _weekRange(BuildContext context, WeeklyPlan plan) {
    final start = plan.weekStart;
    if (start == null) return null;
    final m = MaterialLocalizations.of(context);
    final end = start.add(const Duration(days: 6));
    return '${m.formatShortMonthDay(start)} – ${m.formatShortMonthDay(end)}';
  }
}

/// One step of the plan, ticked with a tap. Unticked it shows its number (or
/// a plain ring for the worship act); ticked, a filled check. Nothing marks a
/// step not taken.
class _MarkRow extends StatelessWidget {
  const _MarkRow({
    required this.item,
    required this.marked,
    required this.dir,
    required this.onTap,
    this.number,
  });

  final PlanItem item;
  final bool marked;
  final TextDirection dir;
  final VoidCallback onTap;
  final int? number;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final Widget mark = AnimatedSwitcher(
      duration: reduceMotion(context) ? Duration.zero : Dt.fast,
      child: marked
          ? Container(
              key: const ValueKey('marked'),
              width: 24,
              height: 24,
              decoration:
                  BoxDecoration(color: colors.success, shape: BoxShape.circle),
              child: Icon(Icons.check_rounded, size: 16, color: colors.onPrimary),
            )
          : Container(
              key: const ValueKey('open'),
              width: 24,
              height: 24,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: colors.primary.withValues(alpha: colors.isDark ? .25 : .12),
                shape: BoxShape.circle,
              ),
              child: number == null
                  ? null
                  : Text('$number',
                      style: TextStyle(
                          color: colors.primary,
                          fontWeight: FontWeight.w800,
                          fontSize: 12)),
            ),
    );
    return Semantics(
      checked: marked,
      hint: marked ? null : l10n.planMarkHint,
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: Dt.minTouch),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 2),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  mark,
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(item.text,
                        textDirection: dir,
                        style: TextStyle(
                            color: colors.ink, fontSize: 14, height: 1.5)),
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

class _LessonRow extends StatelessWidget {
  const _LessonRow({required this.lesson, required this.dir, required this.onTap});

  final PlanLesson lesson;
  final TextDirection dir;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Material(
      color: colors.surfaceAlt,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Icon(
                lesson.completed
                    ? Icons.check_circle_rounded
                    : Icons.menu_book_rounded,
                color: lesson.completed ? colors.success : colors.primary,
                size: 22,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      lesson.title.isEmpty ? l10n.planLesson : lesson.title,
                      textDirection: dir,
                      style: TextStyle(
                          color: colors.ink,
                          fontWeight: FontWeight.w700,
                          fontSize: 14,
                          height: 1.4),
                    ),
                    if (lesson.completed || lesson.estimatedMinutes != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(
                          lesson.completed
                              ? l10n.planLessonDone
                              : l10n.lessonMinutesBadge(
                                  lesson.estimatedMinutes!),
                          style: TextStyle(
                              color: colors.inkSoft, fontSize: 12),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              DirectionalChevron(color: colors.inkSoft),
            ],
          ),
        ),
      ),
    );
  }
}
