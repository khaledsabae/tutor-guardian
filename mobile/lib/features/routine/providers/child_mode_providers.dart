import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../api/tg_client.dart';
import '../../../core/analytics.dart';
import '../../../state/chat_notifier.dart';
import '../models/habit_models.dart';
import '../services/child_mode_secure_storage.dart';

final childModeProvider = StateNotifierProvider<ChildModeNotifier, ChildModeState>(
  (ref) => ChildModeNotifier(ref.read(tgClientProvider)),
);

/// Stable error codes surfaced through [ChildModeState.error].
/// The UI maps these to localized messages; anything else is shown raw.
const kChildModeErrorPinRequired = 'child_mode_pin_required';
const kChildModeErrorPinIncorrect = 'child_mode_pin_incorrect';
const kChildModeErrorSessionExpired = 'child_mode_session_expired';

/// The day's time is spent. Not an error — the UI shows a closing screen.
const kChildModeBudgetSpent = 'child_mode_budget_spent';

/// No signed family agreement yet, so the only surface that opens is the
/// agreement itself. The child-mode screen renders it rather than an error.
const kChildModeAgreementRequired = 'child_mode_agreement_required';

/// Two heartbeats in a row failed to reach the server, so the surface closes.
///
/// The budget is enforced server-side, which is only true while the client is
/// talking to the server. A child in aeroplane mode with the app open is a
/// child with no limit at all, so losing contact ends the session here rather
/// than waiting to be told. Two failures rather than one absorbs a single
/// dropped request on a train.
const kChildModeOffline = 'child_mode_offline';
const _kMaxHeartbeatFailures = 2;

class ChildModeState {
  const ChildModeState({
    this.active = false,
    this.loading = false,
    this.error,
    this.childId,
    this.day,
    this.submittedHabits = const {},
    this.sessionId,
    this.remainingSeconds,
    this.exitRitual = false,
  });

  final bool active;
  final bool loading;
  final String? error;
  final int? childId;
  final HabitDay? day;
  final Set<String> submittedHabits;

  /// The open screen session. Null means no surface is running.
  final int? sessionId;

  /// Seconds left on this surface, as the server last reported them.
  ///
  /// Shown to the child as a shortening bar or a candle, never as a number —
  /// a countdown in digits is a thing to bargain with.
  final int? remainingSeconds;

  /// The last minute has started: wind down, do not cut off.
  final bool exitRitual;

  ChildModeState copyWith({
    bool? active,
    bool? loading,
    String? error,
    int? childId,
    HabitDay? day,
    Set<String>? submittedHabits,
    int? sessionId,
    int? remainingSeconds,
    bool? exitRitual,
  }) =>
      ChildModeState(
        active: active ?? this.active,
        loading: loading ?? this.loading,
        error: error,
        childId: childId ?? this.childId,
        day: day ?? this.day,
        submittedHabits: submittedHabits ?? this.submittedHabits,
        sessionId: sessionId ?? this.sessionId,
        remainingSeconds: remainingSeconds ?? this.remainingSeconds,
        exitRitual: exitRitual ?? this.exitRitual,
      );

  bool isSubmitted(String habitName) => submittedHabits.contains(habitName);
}

class ChildModeNotifier extends StateNotifier<ChildModeState> {
  ChildModeNotifier(this._client) : super(const ChildModeState());

  final TgClient _client;

  Future<void> restore() async {
    final active = await isChildModeActive();
    final childId = await _loadChildId();
    if (active && childId != null) {
      state = state.copyWith(active: true, childId: childId);
      await refresh();
    }
  }

  /// The only way into a child surface.
  ///
  /// Every screen a child can reach goes through here: the PIN proves a parent
  /// opened it, and the session it creates is what the server checks on every
  /// subsequent request. A second entry point that skipped this would be a
  /// child surface with no gate in front of it.
  Future<bool> enter({
    required int childId,
    String? pin,
    String surface = 'habit',
  }) async {
    state = state.copyWith(loading: true, error: null);
    try {
      if (pin == null || pin.isEmpty) {
        state = state.copyWith(loading: false, error: kChildModeErrorPinRequired);
        return false;
      }
      final hasPin = await hasChildModePin();
      if (hasPin) {
        final ok = await verifyChildModePin(pin);
        if (!ok) {
          state = state.copyWith(
            loading: false,
            error: kChildModeErrorPinIncorrect,
          );
          return false;
        }
      } else {
        await setChildModePin(pin);
      }
      final session = await _client.createChildSession(childId, surface: surface);
      await saveChildToken(session['token'] as String);
      await setChildModeActive(true);
      await _saveChildId(childId);
      state = state.copyWith(
        active: true,
        loading: false,
        childId: childId,
        sessionId: session['session_id'] as int?,
        remainingSeconds: session['allowed_seconds'] as int?,
        exitRitual: false,
      );
      // No session id means the server has the child surface switched off and
      // handed back a plain token. Nothing to report on, so nothing beats.
      if (session['session_id'] != null) {
        _startHeartbeat(
          intervalSeconds: (session['heartbeat_interval_seconds'] as int?) ?? 30,
        );
      }
      await refresh();
      return true;
    } catch (e) {
      state = state.copyWith(loading: false, error: _classify(e));
      return false;
    }
  }

  /// A 403 from the session endpoint is the age gate or the day's budget, and
  /// both deserve a calm screen rather than a red error. Anything else is a
  /// real failure and keeps its message.
  String _classify(Object e) {
    final text = e.toString();
    if (text.contains('agreement_required')) {
      return kChildModeAgreementRequired;
    }
    if (text.contains('age_not_allowed') ||
        text.contains('budget_exhausted')) {
      return kChildModeBudgetSpent;
    }
    return text;
  }

  // ── Heartbeat ────────────────────────────────────────────────────────────

  Timer? _heartbeatTimer;
  int _heartbeatFailures = 0;

  void _startHeartbeat({required int intervalSeconds}) {
    _heartbeatTimer?.cancel();
    _heartbeatFailures = 0;
    _heartbeatTimer = Timer.periodic(
      Duration(seconds: intervalSeconds),
      (_) => unawaited(_beat()),
    );
  }

  Future<void> _beat() async {
    final sessionId = state.sessionId;
    final token = await getChildToken();
    if (sessionId == null || token == null) {
      _stopHeartbeat();
      return;
    }
    try {
      final result = await _client.childHeartbeat(
        childToken: token,
        sessionId: sessionId,
      );
      _heartbeatFailures = 0;
      if (result == null) {
        // The server closed it. Not a failure — the surface is simply over.
        await endSession(reason: 'completed', code: kChildModeBudgetSpent);
        return;
      }
      state = state.copyWith(
        remainingSeconds: result['remaining_seconds'] as int?,
        exitRitual: result['exit_ritual'] as bool? ?? false,
      );
    } catch (_) {
      _heartbeatFailures++;
      if (_heartbeatFailures >= _kMaxHeartbeatFailures) {
        // Server-side enforcement only holds while we can reach the server.
        await endSession(reason: 'timeout', code: kChildModeOffline);
      }
    }
  }

  void _stopHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
  }

  /// Close the running surface. [code] is what the UI renders — a quiet
  /// closing screen, never an error dialog.
  Future<void> endSession({String reason = 'completed', String? code}) async {
    _stopHeartbeat();
    final sessionId = state.sessionId;
    final token = await getChildToken();
    if (sessionId != null && token != null) {
      try {
        await _client.endChildSession(
          childToken: token,
          sessionId: sessionId,
          reason: reason,
        );
      } catch (_) {
        // The server reaps sessions that stop reporting, so a failed close is
        // recovered without us. Never block the child's exit on the network.
      }
    }
    // Constructed rather than copyWith: copyWith uses `??`, so passing null
    // for sessionId would keep the closed session's id and the next entry
    // would heartbeat against a session that is already over.
    state = ChildModeState(
      active: state.active,
      childId: state.childId,
      day: state.day,
      submittedHabits: state.submittedHabits,
      sessionId: null,
      remainingSeconds: 0,
      exitRitual: false,
      error: code,
    );
  }

  @override
  void dispose() {
    _stopHeartbeat();
    super.dispose();
  }

  Future<bool> exit(String pin) async {
    final ok = await verifyChildModePin(pin);
    if (!ok) return false;
    await endSession(reason: 'parent_exit');
    await clearChildMode();
    await _clearChildId();
    state = const ChildModeState();
    return true;
  }

  Future<void> refresh() async {
    final token = await getChildToken();
    if (token == null) {
      await clearChildMode();
      state = const ChildModeState();
      return;
    }
    state = state.copyWith(loading: true);
    try {
      final raw = await _client.fetchChildTodayHabits(childToken: token);
      final day = HabitDay.fromJson(raw);
      state = state.copyWith(
        loading: false,
        day: day,
        submittedHabits: {
          for (final e in day.events)
            if (e.status != HabitStatus.missed) e.habitName,
        },
      );
    } on TgApiError catch (e) {
      if (e.statusCode == 401) {
        await clearChildMode();
        await _clearChildId();
        state = const ChildModeState(error: kChildModeErrorSessionExpired);
      } else {
        state = state.copyWith(loading: false, error: e.toString());
      }
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  Future<bool> submit(HabitItem item, String status) async {
    final token = await getChildToken();
    if (token == null || state.isSubmitted(item.habitName)) return false;
    try {
      await _client.createChildHabitEvent(
        childToken: token,
        body: {
          'category': item.category.wireName,
          'habit_name': item.habitName,
          'status': status,
          'device_timestamp': DateTime.now().toUtc().toIso8601String(),
        },
      );
      state = state.copyWith(
        submittedHabits: {...state.submittedHabits, item.habitName},
      );
      unawaited(Analytics.habitCheckIn(status));
      return true;
    } on TgApiError catch (e) {
      if (e.statusCode == 401) {
        await clearChildMode();
        await _clearChildId();
        state = const ChildModeState(error: kChildModeErrorSessionExpired);
      } else {
        state = state.copyWith(error: e.toString());
      }
      return false;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  Future<int?> _loadChildId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt('child_mode_child_id');
  }

  Future<void> _saveChildId(int childId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('child_mode_child_id', childId);
  }

  Future<void> _clearChildId() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('child_mode_child_id');
  }
}
