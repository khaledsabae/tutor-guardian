import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/reciters.dart';

// Provides the entire Quran JSON loaded from assets.
// Key is chapter number as string (e.g. "1"), value is list of verses.
final quranDataProvider = FutureProvider<Map<String, List<dynamic>>>((ref) async {
  final jsonString = await rootBundle.loadString('assets/data/quran.json');
  final Map<String, dynamic> decoded = jsonDecode(jsonString);
  return decoded.map((key, value) => MapEntry(key, value as List<dynamic>));
});

// A provider to access the shared preferences instance synchronously once loaded.
// Note: SharedPreferences should be initialized in main or via a future provider.
// The app already has a `sharedPreferencesProvider` in onboarding_providers.dart,
// but we'll re-declare or use our own provider to keep this decoupled if needed,
// OR just use the global one. We'll read/write async directly for simplicity.

class LastReadState {
  final int chapter;
  final int verse;

  const LastReadState({required this.chapter, required this.verse});
}

class LastReadNotifier extends StateNotifier<AsyncValue<LastReadState?>> {
  static const _chapterKey = 'quran_last_read_chapter';
  static const _verseKey = 'quran_last_read_verse';

  LastReadNotifier() : super(const AsyncValue.loading()) {
    _load();
  }

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final chapter = prefs.getInt(_chapterKey);
      final verse = prefs.getInt(_verseKey);
      if (chapter != null && verse != null) {
        state = AsyncValue.data(LastReadState(chapter: chapter, verse: verse));
      } else {
        state = const AsyncValue.data(null);
      }
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> saveProgress(int chapter, int verse) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_chapterKey, chapter);
    await prefs.setInt(_verseKey, verse);
    state = AsyncValue.data(LastReadState(chapter: chapter, verse: verse));
  }
}

final lastReadProvider = StateNotifierProvider<LastReadNotifier, AsyncValue<LastReadState?>>((ref) {
  return LastReadNotifier();
});

/// The reciter chosen for the listen feature, persisted across sessions.
/// Defaults to Husary.
class ReciterNotifier extends StateNotifier<Reciter> {
  static const _key = 'quran_reciter_id';

  ReciterNotifier() : super(kDefaultReciter) {
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final id = prefs.getString(_key);
    if (id != null) {
      state = kReciters.firstWhere(
        (r) => r.id == id,
        orElse: () => kDefaultReciter,
      );
    }
  }

  Future<void> select(Reciter reciter) async {
    state = reciter;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, reciter.id);
  }
}

final reciterProvider = StateNotifierProvider<ReciterNotifier, Reciter>(
  (ref) => ReciterNotifier(),
);
