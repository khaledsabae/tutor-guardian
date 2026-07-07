/// Riverpod providers for the daily routine tracker.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';

import 'package:almorabbi/features/routine/models/routine_models.dart';

/// Async stream of today's routine for the active child.
final todayRoutineProvider = StreamProvider.autoDispose.family<RoutineDay, int>(
  (ref, childId) async* {
    final client = TgClient();
    while (true) {
      try {
        final raw = await client.fetchTodayRoutine(childId);
        yield RoutineDay.fromJson(raw);
      } on TgApiError catch (e) {
        if (e.statusCode == 401) {
          await client.ensureSession();
        }
        yield const RoutineDay(routineId: 0, childId: 0, routineDate: '', events: []);
      }
      await Future.delayed(const Duration(seconds: 30));
    }
  },
);

/// Summary for the active child (last N days).
final routineSummaryProvider = FutureProvider.autoDispose.family<RoutineSummary, int>(
  (ref, childId) async {
    final raw = await TgClient().fetchRoutineSummary(childId, days: 7);
    return RoutineSummary.fromJson(raw);
  },
);

/// Convenience provider that watches the active child id and surfaces it.
final routineActiveChildIdProvider = Provider<int?>((ref) {
  return ref.watch(activeChildIdProvider);
});
