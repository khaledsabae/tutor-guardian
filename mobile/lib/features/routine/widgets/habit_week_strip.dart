/// The 7-day habit strip and the streak badge (UX_UI_ROADMAP §3.2–3.3).
///
/// A row of seven dots answers "is this week better than last?" at a glance:
/// filled = done, half = partly, empty = no effort recorded. "Missed" is drawn
/// exactly like "nothing recorded" — a miss is a record, not a mark against
/// anyone, and the strip exists to show effort.
library;

import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../models/habit_models.dart';

class HabitWeekStrip extends StatelessWidget {
  const HabitWeekStrip({super.key, required this.cells, this.dotSize = 10});

  /// Seven statuses, oldest first; the last is today.
  final List<HabitStatus?> cells;
  final double dotSize;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final done = cells.where((s) => s == HabitStatus.completed).length;
    final part = cells.where((s) => s == HabitStatus.partially).length;
    return Semantics(
      label: AppLocalizations.of(context).habitWeekSemantics(done, part),
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < cells.length; i++)
            Padding(
              padding: const EdgeInsetsDirectional.only(end: 4),
              child: _Dot(
                status: cells[i],
                size: dotSize,
                isToday: i == cells.length - 1,
                fill: c.primary,
                empty: c.track,
              ),
            ),
        ],
      ),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({
    required this.status,
    required this.size,
    required this.isToday,
    required this.fill,
    required this.empty,
  });

  final HabitStatus? status;
  final double size;
  final bool isToday;
  final Color fill;
  final Color empty;

  @override
  Widget build(BuildContext context) {
    final border = Border.all(
      color: status == HabitStatus.completed || status == HabitStatus.partially
          ? fill
          : empty,
      width: isToday ? 2 : 1.5,
    );
    Widget dot = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: border,
        color: status == HabitStatus.completed ? fill : null,
      ),
    );
    if (status == HabitStatus.partially) {
      // Half-filled: the start half, so it reads the same way in RTL and LTR.
      dot = Stack(
        alignment: Alignment.center,
        children: [
          dot,
          Positioned.directional(
            textDirection: Directionality.of(context),
            start: 0,
            top: 0,
            bottom: 0,
            width: size / 2,
            child: Container(
              decoration: BoxDecoration(
                color: fill,
                borderRadius: BorderRadiusDirectional.horizontal(
                  start: Radius.circular(size / 2),
                ).resolve(Directionality.of(context)),
              ),
            ),
          ),
        ],
      );
    }
    return dot;
  }
}

/// "🔥 N days" with a shield when this week's grace day has been used.
/// Hidden while there is no streak — an empty counter says nothing kind.
class HabitStreakBadge extends StatelessWidget {
  const HabitStreakBadge({super.key, required this.streak, this.large = false});

  final HabitStreak streak;
  final bool large;

  @override
  Widget build(BuildContext context) {
    if (streak.days <= 0) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final style = (large
            ? Theme.of(context).textTheme.titleMedium
            : Theme.of(context).textTheme.labelLarge)
        ?.copyWith(fontWeight: FontWeight.w700, color: c.accentDeep);
    return Semantics(
      label: streak.shieldUsedThisWeek
          ? '${l10n.habitStreakDays(streak.days)} · ${l10n.habitStreakShieldUsed}'
          : l10n.habitStreakDays(streak.days),
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('🔥', style: TextStyle(fontSize: large ? 20 : 16)),
          const SizedBox(width: 4),
          Text(l10n.habitStreakDays(streak.days), style: style),
          if (streak.shieldUsedThisWeek) ...[
            const SizedBox(width: 6),
            Tooltip(
              message: l10n.habitStreakShieldUsed,
              child: Icon(Icons.shield_rounded,
                  size: large ? 20 : 16, color: c.textSecondary),
            ),
          ],
        ],
      ),
    );
  }
}
