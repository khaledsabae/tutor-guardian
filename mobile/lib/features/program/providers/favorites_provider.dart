/// Favorites provider — P1 launch item #1 (local-only).
///
/// Wraps [FavoritesStorage] so the rest of the app can use
/// Riverpod to consume favorites state reactively.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:almorabbi/features/program/data/favorites_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';

/// The reactive favorites notifier — wraps [FavoritesStorage] and
/// notifies listeners on every change.
final favoritesProvider = StateNotifierProvider<FavoritesNotifier, Map<String, List<String>>>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider).requireValue;
  return FavoritesNotifier(FavoritesStorage(prefs));
});

class FavoritesNotifier extends StateNotifier<Map<String, List<String>>> {
  FavoritesNotifier(this._storage) : super(_initialState()) {
    // Load initial state
    _load();
  }

  static Map<String, List<String>> _initialState() => {
    'lessons': <String>[],
    'tips': <String>[],
  };

  final FavoritesStorage _storage;

  void _load() {
    state = _storage.loadAll();
  }

  bool isLessonFavorite(String lessonId) {
    return state['lessons']?.contains(lessonId) ?? false;
  }

  bool isTipFavorite(String tipId) {
    return state['tips']?.contains(tipId) ?? false;
  }

  Future<void> toggleLesson(String lessonId) async {
    final all = Map<String, List<String>>.from(state);
    final lessons = List<String>.from(all['lessons']!);
    if (lessons.contains(lessonId)) {
      lessons.remove(lessonId);
    } else {
      lessons.add(lessonId);
    }
    all['lessons'] = lessons;
    state = all;
    await _storage.toggleLesson(lessonId);
  }

  Future<void> toggleTip(String tipId) async {
    final all = Map<String, List<String>>.from(state);
    final tips = List<String>.from(all['tips']!);
    if (tips.contains(tipId)) {
      tips.remove(tipId);
    } else {
      tips.add(tipId);
    }
    all['tips'] = tips;
    state = all;
    await _storage.toggleTip(tipId);
  }

  Future<void> clearAll() async {
    state = _initialState();
    await _storage.clearAll();
  }
}
