/// «خطة الأسبوع» on Today — plan §1.3 (MOBILE_API §9.5).
///
/// One focus, three small actions, one act of worship together, one lesson —
/// for the active child, for the parent's local ISO week as the SERVER drew
/// it (`week_start`). Collapsed to the focus by default: Today was cut to three
/// stops because «مش عارف أبدأ منين», and the week's plan must not undo that.
///
/// Every band has a plan (the server's banks cover prenatal-1 … 16-18), so
/// nothing here is band-gated. Hides itself while loading, on any failure, on
/// an older server, and when the plan has no focus or actions.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../data/memory_models.dart';
import '../providers/memory_providers.dart';

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

  @override
  Widget build(BuildContext context) {
    final key = _key(context);
    final plan = ref.watch(weeklyPlanProvider(key)).valueOrNull;
    if (plan == null) return const SizedBox.shrink();
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkWeek());

    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final dir = directionOfLanguage(plan.lang);
    final range = _weekRange(context, plan);

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
            if (_expanded) ..._details(context, plan, dir),
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: TextButton(
                onPressed: () {
                  if (!_expanded) {
                    unawaited(Analytics.todayBlockTapped('loop', 'plan_expand'));
                  }
                  setState(() => _expanded = !_expanded);
                },
                child: Text(_expanded ? l10n.planShowLess : l10n.planShowAll),
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _details(BuildContext context, WeeklyPlan plan, TextDirection dir) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final itemStyle = TextStyle(color: colors.ink, fontSize: 14, height: 1.5);
    Widget heading(String text) => Padding(
          padding: const EdgeInsets.only(top: 14, bottom: 6),
          child: Text(text,
              style: TextStyle(
                  color: colors.textSecondary,
                  fontWeight: FontWeight.w700,
                  fontSize: 12.5)),
        );
    return [
      heading(l10n.planSteps),
      for (var i = 0; i < plan.actions.length; i++)
        Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 22,
                height: 22,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: colors.primary.withValues(alpha: colors.isDark ? .25 : .12),
                  shape: BoxShape.circle,
                ),
                child: Text('${i + 1}',
                    style: TextStyle(
                        color: colors.primary,
                        fontWeight: FontWeight.w800,
                        fontSize: 12)),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(plan.actions[i].text,
                    textDirection: dir, style: itemStyle),
              ),
            ],
          ),
        ),
      if (plan.adaptedFromOutcomes)
        Text(l10n.planAdapted,
            style: TextStyle(color: colors.inkSoft, fontSize: 12, height: 1.5)),
      if (plan.worship != null) ...[
        heading(l10n.planWorship),
        Text(plan.worship!.text, textDirection: dir, style: itemStyle),
      ],
      if (plan.lesson != null) ...[
        heading(l10n.planLesson),
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
