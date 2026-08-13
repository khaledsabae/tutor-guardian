import 'dart:io' show Platform;
import 'dart:ui' show PlatformDispatcher;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../l10n/app_localizations.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../models/flashcard_deck.dart';
import '../models/lesson_assets.dart';
import '../models/quiz_deck.dart';
import 'program_providers.dart';

class ContentLanguageNotifier extends StateNotifier<String> {
  final SharedPreferences? _prefs;

  /// [uiFallback] is the language the parent is *reading* in. A stored value
  /// beats it, because that is an explicit choice made in Settings.
  ContentLanguageNotifier(this._prefs, String uiFallback)
      : super(_prefs?.getString('content_language') ?? uiFallback);

  Future<void> setLanguage(String lang) async {
    state = lang;
    if (_prefs != null) {
      await _prefs.setString('content_language', lang);
    }
  }
}

/// Language for lesson media (podcast, video), sent as `?lang=` to
/// `/lesson-assets`.
///
/// Kept separate from the UI language on purpose — English text with Arabic
/// audio is a real preference. But its default used to be a hard-coded `'ar'`
/// read from SharedPreferences, with no reference to the UI language or to the
/// device: `TgClient.uiLanguage` drove the text and nothing connected the two.
///
/// So a parent on an English phone read English lessons and was handed the
/// Arabic podcast — and would still have been handed it once English audio
/// existed, because nothing here ever asked what language they were reading
/// in. The default now follows the UI language; an explicit choice still wins.
final contentLanguageProvider =
    StateNotifierProvider<ContentLanguageNotifier, String>((ref) {
  final prefsAsync = ref.watch(sharedPreferencesProvider);
  final prefs = prefsAsync.maybeWhen(
    data: (p) => p,
    orElse: () => null,
  );
  // Mirrors main.dart's locale resolution: an explicit app locale, else the
  // device's — pinned to Arabic under FLUTTER_TEST exactly as MaterialApp is.
  final uiCode = ref.watch(appLocaleProvider)?.languageCode ??
      (Platform.environment.containsKey('FLUTTER_TEST')
          ? 'ar'
          : PlatformDispatcher.instance.locale.languageCode);
  // Resolved against supportedLocales rather than a hard-coded ar/en pair, so
  // adding a third language does not silently leave its speakers on Arabic
  // media while their UI switches.
  final supported =
      AppLocalizations.supportedLocales.map((l) => l.languageCode).toSet();
  return ContentLanguageNotifier(prefs, supported.contains(uiCode) ? uiCode : 'ar');
});

final lessonAssetsProvider = FutureProvider.autoDispose
    .family<LessonAssets?, String>((ref, lessonId) {
  final repo = ref.watch(programRepositoryProvider);
  final lang = ref.watch(contentLanguageProvider);
  return repo.getLessonAssets(lessonId, lang: lang);
});

/// Loads every flashcard deck for a lesson and keeps the successful ones.
///
/// The family key is a comma-joined string of deck ids (lists lack value
/// equality in Dart, which would defeat Riverpod's family caching).
final flashcardDecksProvider = FutureProvider.autoDispose
    .family<List<FlashcardDeck>, String>((ref, joinedDeckIds) async {
  final repo = ref.watch(programRepositoryProvider);
  final ids = joinedDeckIds.split(',').where((s) => s.isNotEmpty).toList();
  final decks = await Future.wait(ids.map(repo.getFlashcardDeck));
  return decks.whereType<FlashcardDeck>().toList();
});

/// Loads every quiz deck for a lesson and keeps the successful ones.
///
/// Same comma-joined-key pattern as [flashcardDecksProvider].
final quizDecksProvider = FutureProvider.autoDispose
    .family<List<QuizDeck>, String>((ref, joinedQuizIds) async {
  final repo = ref.watch(programRepositoryProvider);
  final ids = joinedQuizIds.split(',').where((s) => s.isNotEmpty).toList();
  final results = await Future.wait(ids.map(repo.getQuizDeck));
  return results.whereType<QuizDeck>().toList();
});
