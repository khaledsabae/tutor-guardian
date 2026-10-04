/// «صلاتي اليوم» — the child's Prayer Journey tasks, inside child mode
/// (`GET/POST /api/value-tracking/child-mode/prayer/*`, Child-Bearer).
///
/// Lives on the habit surface the parent opens from the Prayer Journey
/// screen. The child taps once and is done: the claim is recorded at once and
/// the parent confirms in the evening. What the child never sees: a stage
/// number, a parent's text, a count of what is left, or an error — a task
/// already done for the day shows as ✓, a refusal shows as nothing at all.
/// A child not on the journey (or on the preparation track) sees no card.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/tg_client.dart';
import '../../../core/analytics.dart';
import '../../../core/haptics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../state/chat_notifier.dart';
import '../../../theme/app_colors.dart';
import '../../routine/services/child_mode_secure_storage.dart';
import '../data/programs_models.dart';
import 'program_widgets.dart';

/// How the card reads the child token — a provider so tests can hand one in.
final childPrayerTokenProvider = Provider<Future<String?> Function()>(
  (_) => getChildToken,
);

class ChildPrayerCard extends ConsumerStatefulWidget {
  const ChildPrayerCard({super.key});

  @override
  ConsumerState<ChildPrayerCard> createState() => _ChildPrayerCardState();
}

class _ChildPrayerCardState extends ConsumerState<ChildPrayerCard> {
  ChildPrayerToday? _today;
  final Set<String> _claiming = {};
  final Set<String> _justRecorded = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final token = await ref.read(childPrayerTokenProvider)();
    if (token == null) return;
    try {
      final json = await ref
          .read(tgClientProvider)
          .fetchChildPrayerToday(token);
      if (mounted) setState(() => _today = ChildPrayerToday.fromJson(json));
    } catch (_) {
      // A child does not get an error card. No card is a state they know.
    }
  }

  void _setTask(
    String taskId,
    ChildPrayerTask Function(ChildPrayerTask) update,
  ) {
    final today = _today;
    if (today == null) return;
    setState(
      () => _today = ChildPrayerToday(
        enrolled: today.enrolled,
        track: today.track,
        tasks: [
          for (final t in today.tasks) t.taskId == taskId ? update(t) : t,
        ],
      ),
    );
  }

  Future<void> _claim(ChildPrayerTask task) async {
    if (_claiming.contains(task.taskId) || task.doneForToday) return;
    final token = await ref.read(childPrayerTokenProvider)();
    if (token == null || !mounted) return;
    setState(() => _claiming.add(task.taskId));
    try {
      final json = await ref
          .read(tgClientProvider)
          .claimChildPrayer(childToken: token, taskId: task.taskId);
      unawaited(Haptics.success());
      unawaited(Analytics.programAction('prayer', 'child_claim'));
      _justRecorded.add(task.taskId);
      _setTask(
        task.taskId,
        (t) => t.copyWith(
          recordedToday:
              (json['recorded_today'] as num?)?.toInt() ?? t.recordedToday + 1,
          slotsLeftToday:
              (json['slots_left_today'] as num?)?.toInt() ??
              t.slotsLeftToday - 1,
          recordedThisWeek: t.recordedThisWeek + 1,
        ),
      );
    } on TgApiError catch (e) {
      switch (e.code) {
        case 'day_complete':
        case 'week_complete':
          // Already done — show it as done, never as a refusal.
          _setTask(task.taskId, (t) => t.copyWith(slotsLeftToday: 0));
        case 'already_recorded':
        case 'task_not_current':
          await _load(); // a double tap, or the stage changed: ask again
        case 'not_enrolled':
        case 'program_unavailable':
          if (mounted) setState(() => _today = null);
        default:
          break; // swallowed on purpose — the child did their part
      }
    } catch (_) {
      // Offline: nothing to show the child; the card stays as it was.
    } finally {
      if (mounted) setState(() => _claiming.remove(task.taskId));
    }
  }

  @override
  Widget build(BuildContext context) {
    final today = _today;
    if (today == null || !today.hasTasks) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    return Card(
      key: const ValueKey('child_prayer_card'),
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const ExcludeSemantics(
                  child: Text('🕌', style: TextStyle(fontSize: 28)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Semantics(
                    header: true,
                    child: Text(
                      l10n.childPrayerTitle,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
              ],
            ),
            for (final task in today.tasks) ...[
              const SizedBox(height: 14),
              ContentText(
                task.title,
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
              ),
              if (task.instruction != null) ...[
                const SizedBox(height: 4),
                ContentText(
                  task.instruction!,
                  style: TextStyle(
                    color: c.textSecondary,
                    height: 1.55,
                    fontSize: 15,
                  ),
                ),
              ],
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  if (task.coins > 0)
                    CountBadge(
                      '🪙 ${l10n.programsCoins(task.coins)}',
                      accent: true,
                    ),
                  if (task.recordedThisWeek > 0)
                    CountBadge(l10n.prayerTaskThisWeek(task.recordedThisWeek)),
                ],
              ),
              const SizedBox(height: 10),
              if (task.doneForToday)
                Container(
                  key: ValueKey('child_prayer_done_${task.taskId}'),
                  padding: const EdgeInsets.symmetric(
                    vertical: 14,
                    horizontal: 12,
                  ),
                  decoration: BoxDecoration(
                    color: c.success.withValues(alpha: .15),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(
                    _justRecorded.contains(task.taskId)
                        ? l10n.childPrayerRecorded
                        : l10n.childPrayerDoneToday,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: c.successText,
                      fontWeight: FontWeight.w800,
                      height: 1.5,
                    ),
                  ),
                )
              else
                FilledButton(
                  key: ValueKey('child_prayer_claim_${task.taskId}'),
                  onPressed: _claiming.contains(task.taskId)
                      ? null
                      : () => _claim(task),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(56),
                  ),
                  child: Text(l10n.childPrayerClaim),
                ),
              if (!task.doneForToday && _justRecorded.contains(task.taskId))
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    l10n.childPrayerRecorded,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: c.successText,
                      fontWeight: FontWeight.w700,
                      height: 1.5,
                    ),
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
