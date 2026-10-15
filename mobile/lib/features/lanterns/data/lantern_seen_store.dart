/// How many of this week's lanterns this phone has already shown lit.
///
/// A lantern lights — a short glow and one success tap — only the first time
/// it is seen: opening «اليوم» again must not replay it. One small record,
/// `{week, count}`; a new week starts from none, so its first lantern lights
/// too.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class LanternSeenStore {
  LanternSeenStore(this._prefs);

  final SharedPreferences _prefs;

  static const key = 'lanterns.seen.v1';

  /// Lanterns already shown lit for [week] (its `week_start`); 0 for a week
  /// this phone has not shown yet.
  int seenFor(String week) {
    final raw = _prefs.getString(key);
    if (raw == null) return 0;
    try {
      final v = jsonDecode(raw);
      if (v is Map && v['week'] == week && v['count'] is int) {
        return v['count'] as int;
      }
    } catch (_) {}
    return 0;
  }

  Future<void> setSeen(String week, int count) =>
      _prefs.setString(key, jsonEncode({'week': week, 'count': count}));
}
