/// «رحلة الطفل» — per-child Quran memorization tracking (Phase 4).
///
/// The Quran feature itself tracks nothing memorized; this is a small,
/// local, per-child store of memorized surah numbers (1..114), persisted
/// as one JSON blob under [_kMemorization]. It feeds the «حفظ أول سورة»
/// spiritual milestone in the journey.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class MemorizationStore {
  MemorizationStore(this._prefs);

  static const String _kMemorization = 'tg.memorization.v1';

  final SharedPreferences _prefs;

  /// Memorized surah numbers (1..114) for one child.
  Set<int> loadForChild(int childId) {
    return _loadAll()[childId.toString()] ?? <int>{};
  }

  Future<Set<int>> toggle(int childId, int surah) async {
    final all = _loadAll();
    final cid = childId.toString();
    final set = all[cid] ?? <int>{};
    if (!set.remove(surah)) {
      set.add(surah);
    }
    all[cid] = set;
    await _persist(all);
    return set;
  }

  Map<String, Set<int>> _loadAll() {
    final raw = _prefs.getString(_kMemorization);
    if (raw == null || raw.isEmpty) return {};
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      return {
        for (final e in decoded.entries)
          e.key: {
            for (final n in (e.value as List)) (n as num).toInt(),
          },
      };
    } catch (_) {
      return {};
    }
  }

  Future<void> _persist(Map<String, Set<int>> all) async {
    final raw = jsonEncode({
      for (final e in all.entries) e.key: e.value.toList()..sort(),
    });
    await _prefs.setString(_kMemorization, raw);
  }
}
