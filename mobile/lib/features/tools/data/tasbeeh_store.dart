/// Persistence for the tasbeeh counter.
///
/// Two things survive a close: the running count and the chosen target. A
/// counter that forgets is not a counter — someone part-way through a wird who
/// takes a phone call and comes back to zero has lost the thing the tool was
/// for.
///
/// Follows the store shape used elsewhere in the app (see
/// `features/journey/data/memorization_store.dart`): plain class, injected
/// `SharedPreferences`, one namespaced key. Injection rather than
/// `SharedPreferences.getInstance()` inside, so a test can hand it mock values
/// instead of reaching for a real platform channel.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Preset targets, plus free counting.
///
/// 33 is the tasbeeh after prayer; 100 is the wording of «من قال لا إله إلا
/// الله وحده لا شريك له… في يوم مائة مرة». `null` means no target: count on.
const List<int?> kTasbeehTargets = <int?>[33, 100, null];

class TasbeehState {
  final int count;

  /// The active target, or `null` for free counting.
  final int? target;

  const TasbeehState({required this.count, required this.target});

  static const TasbeehState initial = TasbeehState(count: 0, target: 33);

  /// True when a target exists and the count has reached it.
  bool get isComplete => target != null && count >= target!;

  TasbeehState copyWith({int? count, int? target, bool clearTarget = false}) =>
      TasbeehState(
        count: count ?? this.count,
        target: clearTarget ? null : (target ?? this.target),
      );
}

class TasbeehStore {
  TasbeehStore(this._prefs);

  static const String _kTasbeeh = 'tg.tasbeeh.v1';

  final SharedPreferences _prefs;

  TasbeehState load() {
    final raw = _prefs.getString(_kTasbeeh);
    if (raw == null || raw.isEmpty) return TasbeehState.initial;
    try {
      final j = jsonDecode(raw) as Map<String, dynamic>;
      final count = (j['count'] as num?)?.toInt() ?? 0;
      final target = (j['target'] as num?)?.toInt();
      return TasbeehState(
        count: count < 0 ? 0 : count,
        // An unrecognised target from a future version falls back to free
        // counting rather than snapping the user to a number they did not pick.
        target: (target != null && kTasbeehTargets.contains(target))
            ? target
            : null,
      );
    } catch (_) {
      return TasbeehState.initial;
    }
  }

  Future<void> save(TasbeehState state) async {
    await _prefs.setString(
      _kTasbeeh,
      jsonEncode({'count': state.count, 'target': state.target}),
    );
  }
}
