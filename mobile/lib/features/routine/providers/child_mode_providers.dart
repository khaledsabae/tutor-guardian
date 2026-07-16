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

class ChildModeState {
  const ChildModeState({
    this.active = false,
    this.loading = false,
    this.error,
    this.childId,
    this.day,
    this.submittedHabits = const {},
  });

  final bool active;
  final bool loading;
  final String? error;
  final int? childId;
  final HabitDay? day;
  final Set<String> submittedHabits;

  ChildModeState copyWith({
    bool? active,
    bool? loading,
    String? error,
    int? childId,
    HabitDay? day,
    Set<String>? submittedHabits,
  }) =>
      ChildModeState(
        active: active ?? this.active,
        loading: loading ?? this.loading,
        error: error,
        childId: childId ?? this.childId,
        day: day ?? this.day,
        submittedHabits: submittedHabits ?? this.submittedHabits,
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

  Future<bool> enter({required int childId, String? pin}) async {
    state = state.copyWith(loading: true, error: null);
    try {
      if (pin == null || pin.isEmpty) {
        state = state.copyWith(loading: false, error: 'يجب تحديد رمز PIN.');
        return false;
      }
      final hasPin = await hasChildModePin();
      if (hasPin) {
        final ok = await verifyChildModePin(pin);
        if (!ok) {
          state = state.copyWith(
            loading: false,
            error: 'الرمز غير صحيح.',
          );
          return false;
        }
      } else {
        await setChildModePin(pin);
      }
      final session = await _client.createChildSession(childId);
      await saveChildToken(session['token'] as String);
      await setChildModeActive(true);
      await _saveChildId(childId);
      state = state.copyWith(
        active: true,
        loading: false,
        childId: childId,
      );
      await refresh();
      return true;
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
      return false;
    }
  }

  Future<bool> exit(String pin) async {
    final ok = await verifyChildModePin(pin);
    if (!ok) return false;
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
        state = const ChildModeState(error: 'انتهى وقت الجلسة الآمنة. يُرجى إعادة الهاتف للمربي.');
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
        state = const ChildModeState(error: 'انتهى وقت الجلسة الآمنة. يُرجى إعادة الهاتف للمربي.');
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
