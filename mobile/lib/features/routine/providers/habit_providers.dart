/// Riverpod providers for the habit tracker (ميزان العادات).
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';

import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/state/chat_notifier.dart' show tgClientProvider;

/// Async stream of today's habits for the active child.
///
/// Polls every 30 s. Broad catch keeps the stream alive across transient
/// network glitches (SocketException, timeout) so the UI never shows a
/// fatal error screen — it just yields empty data until the next tick.
final todayHabitsProvider =
    StreamProvider.autoDispose.family<HabitDay, int>(
  (ref, childId) async* {
    final client = ref.watch(tgClientProvider);
    while (true) {
      try {
        final raw = await client.fetchTodayHabits(childId);
        yield HabitDay.fromJson(raw);
      } on TgApiError catch (e) {
        if (e.statusCode == 401) {
          await client.ensureSession();
        }
        yield HabitDay(childId: childId, date: '', events: [], habits: []);
      } catch (_) {
        // SocketException (DNS failure, offline), TimeoutException, etc.
        // Yield empty data — next poll in 30 s may succeed.
        yield HabitDay(childId: childId, date: '', events: [], habits: []);
      }
      await Future.delayed(const Duration(seconds: 30));
    }
  },
);

/// Summary for the active child (last N days).
final habitSummaryProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, int>(
  (ref, childId) async {
    return ref.watch(tgClientProvider).fetchHabitSummary(childId, days: 7);
  },
);

/// The 7-day strip per habit for the active child (UX_UI_ROADMAP §3.2).
/// Empty on any failure: the strip is a glance, never a reason for an error.
final habitWeekProvider =
    FutureProvider.autoDispose.family<HabitWeek, int>((ref, childId) async {
  try {
    final raw =
        await ref.watch(tgClientProvider).fetchHabitSummary(childId, days: 7);
    return HabitWeek.fromSummaryJson(raw);
  } catch (_) {
    return const HabitWeek();
  }
});

/// Convenience provider that watches the active child id.
final habitActiveChildIdProvider = Provider<int?>((ref) {
  return ref.watch(activeChildIdProvider);
});

/// Custom habit templates for a child. Refreshable after add/archive/unarchive.
final habitTemplatesProvider =
    FutureProvider.autoDispose.family<List<HabitTemplate>, int>(
  (ref, childId) async {
    final raw = await ref.watch(tgClientProvider).listHabitTemplates(childId);
    final list = (raw['templates'] as List?)
            ?.map((t) => HabitTemplate.fromJson(t as Map<String, dynamic>))
            .toList() ??
        [];
    return list;
  },
);