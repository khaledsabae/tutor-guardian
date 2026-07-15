/// Riverpod providers for the daily routine tracker.
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/state/chat_notifier.dart';

import 'package:almorabbi/features/routine/models/routine_models.dart';

/// How often to refresh the routine stream while the screen is visible.
const _routineRefreshInterval = Duration(seconds: 30);

/// Maximum number of consecutive transient failures before the stream
/// surfaces the error to the UI instead of silently returning an empty day.
const _maxTransientRetries = 3;

/// Async stream of today's routine for the active child.
///
/// - Uses a single [TgClient] from [tgClientProvider] (not a fresh instance
///   per frame) so auth-state changes (e.g. clearing a bad token) propagate.
/// - On 401 it clears the cached session and re-creates one, then retries once.
/// - On other transient errors it retries up to [_maxTransientRetries] with the
///   same 30s cadence, then rethrows so the UI can show a real error state.
/// - The stream never yields a fake "empty day" as a substitute for failure.
final todayRoutineProvider = StreamProvider.autoDispose.family<RoutineDay, int>(
  (ref, childId) async* {
    final client = ref.watch(tgClientProvider);
    int transientFailures = 0;

    while (true) {
      try {
        final raw = await client.fetchTodayRoutine(childId);
        transientFailures = 0;
        yield RoutineDay.fromJson(raw);
      } on TgApiError catch (e) {
        if (e.statusCode == 401 || e.statusCode == 404) {
          // Auth failure or session was deleted server-side. Drop the cached
          // token and create a fresh session for the next loop iteration.
          await client.endSession();
          transientFailures = 0;
          // Do not yield here; the next loop tick will fetch with the new
          // session after the standard delay. If creation also fails it will
          // count as a transient failure below.
        } else if (transientFailures < _maxTransientRetries) {
          transientFailures++;
          // Keep the stream alive and retry on the next tick.
        } else {
          rethrow;
        }
      } on TimeoutException {
        if (transientFailures < _maxTransientRetries) {
          transientFailures++;
        } else {
          rethrow;
        }
      }
      await Future.delayed(_routineRefreshInterval);
    }
  },
);

/// Summary for the active child (last N days).
final routineSummaryProvider = FutureProvider.autoDispose.family<RoutineSummary, int>(
  (ref, childId) async {
    final client = ref.watch(tgClientProvider);
    final raw = await client.fetchRoutineSummary(childId, days: 7);
    return RoutineSummary.fromJson(raw);
  },
);

/// Convenience provider that watches the active child id and surfaces it.
final routineActiveChildIdProvider = Provider<int?>((ref) {
  return ref.watch(activeChildIdProvider);
});
