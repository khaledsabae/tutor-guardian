import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../l10n/l10n_global.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../models/flashcard_deck.dart';
import '../models/lesson_assets.dart';
import '../models/quiz_deck.dart';
import 'program_providers.dart';

/// Language for lesson media (podcast, video), sent as `?lang=` to
/// `/lesson-assets`.
///
/// **Derived from the app language — it is not a setting of its own.**
///
/// There used to be two switches: one for the interface and curriculum text
/// (`appLocaleProvider` → `TgClient.uiLanguage`) and a second, separate one for
/// media, stored under `content_language`. They could disagree, and they did:
/// a parent on an English phone read English lessons and was handed the Arabic
/// podcast, because the media switch defaulted to a hard-coded `'ar'` and never
/// asked what language they were reading in.
///
/// Making the media switch *follow* the UI language fixed the default but kept
/// two controls, on the argument that English text with Arabic audio is a real
/// preference. That argument only held while there was no English media to
/// choose. There is now, so the second control is a second way to get the app
/// into a state nobody asked for — and one more thing to explain to a parent
/// who just wants the app in English.
///
/// One language. `appLocaleProvider` is the setting; this reads it.
/// The resolution itself lives in [resolvedContentLanguage] so that
/// `TgClient.uiLanguage` — which decides the language of curriculum *text* —
/// cannot drift from the one media reads. It did drift: text stayed Arabic
/// while media followed the device, so an English phone got English audio over
/// Arabic lessons.
final contentLanguageProvider = Provider<String>((ref) {
  return resolvedContentLanguage(ref.watch(appLocaleProvider)?.languageCode);
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
