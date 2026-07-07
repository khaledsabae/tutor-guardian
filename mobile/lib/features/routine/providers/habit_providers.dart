/// Riverpod providers for the habit tracker (ميزان العادات).
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';

import 'package:almorabbi/features/routine/models/habit_models.dart';

/// Async stream of today's habits for the active child.
final todayHabitsProvider =
    StreamProvider.autoDispose.family<HabitDay, int>(
  (ref, childId) async* {
    final client = TgClient();
    while (true) {
      try {
        final raw = await client.fetchTodayHabits(childId);
        yield HabitDay.fromJson(raw);
      } on TgApiError catch (e) {
        if (e.statusCode == 401) {
          await client.ensureSession();
        }
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
    return TgClient().fetchHabitSummary(childId, days: 7);
  },
);

/// Convenience provider that watches the active child id.
final habitActiveChildIdProvider = Provider<int?>((ref) {
  return ref.watch(activeChildIdProvider);
});

/// Custom habit templates for a child. Refreshable after add/archive/unarchive.
final habitTemplatesProvider =
    FutureProvider.autoDispose.family<List<HabitTemplate>, int>(
  (ref, childId) async {
    final raw = await TgClient().listHabitTemplates(childId);
    final list = (raw['templates'] as List?)
            ?.map((t) => HabitTemplate.fromJson(t as Map<String, dynamic>))
            .toList() ??
        [];
    return list;
  },
);