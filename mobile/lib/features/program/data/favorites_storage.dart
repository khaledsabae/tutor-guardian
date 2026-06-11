/// Favorites storage — P1 launch item #1 (local-only).
///
/// Backed by [SharedPreferences]. Stores two sets of IDs:
///   * lesson IDs that the user marked as favorite
///   * daily tip IDs that the user marked as favorite
///
/// The structure is intentionally simple — a single JSON map with
/// two keys: `lessons` and `tips`. If the project ever needs
/// cross-device sync, this module is the only thing to swap
/// (the key `tg.favorites.v1` stays the same).
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class FavoritesStorage {
  final SharedPreferences _prefs;

  FavoritesStorage(this._prefs);

  /// Storage key. ONE map for the whole device — favorites are
  /// not scoped per child (the parent writes them, the child
  /// doesn't see the app). If the user switches devices, they
  /// lose their favorites — that's the local-only trade-off.
  static const String _kFavorites = 'tg.favorites.v1';

  /// Load all favorites as a map with `lessons` and `tips` sets.
  Map<String, List<String>> loadAll() {
    final raw = _prefs.getString(_kFavorites);
    if (raw == null || raw.isEmpty) return {'lessons': [], 'tips': []};
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      return {
        'lessons': (decoded['lessons'] as List? ?? [])
            .map((e) => e as String)
            .toList(),
        'tips': (decoded['tips'] as List? ?? [])
            .map((e) => e as String)
            .toList(),
      };
    } catch (_) {
      // Corrupted entry — start fresh rather than crash the screen.
      return {'lessons': [], 'tips': []};
    }
  }

  /// Check if a lesson is favorited.
  bool isLessonFavorite(String lessonId) {
    return loadAll()['lessons']?.contains(lessonId) ?? false;
  }

  /// Check if a daily tip is favorited.
  bool isTipFavorite(String tipId) {
    return loadAll()['tips']?.contains(tipId) ?? false;
  }

  /// Toggle a lesson favorite (add if not present, remove if present).
  Future<void> toggleLesson(String lessonId) async {
    final all = loadAll();
    final lessons = all['lessons']!;
    if (lessons.contains(lessonId)) {
      lessons.remove(lessonId);
    } else {
      lessons.add(lessonId);
    }
    await _persist(all);
  }

  /// Toggle a daily tip favorite.
  Future<void> toggleTip(String tipId) async {
    final all = loadAll();
    final tips = all['tips']!;
    if (tips.contains(tipId)) {
      tips.remove(tipId);
    } else {
      tips.add(tipId);
    }
    await _persist(all);
  }

  /// Clear all favorites.
  Future<void> clearAll() async {
    await _prefs.remove(_kFavorites);
  }

  Future<void> _persist(Map<String, List<String>> all) async {
    final raw = jsonEncode({
      'lessons': all['lessons']!,
      'tips': all['tips']!,
    });
    await _prefs.setString(_kFavorites, raw);
  }
}
