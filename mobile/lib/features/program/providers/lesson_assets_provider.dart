import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/flashcard_deck.dart';
import '../models/lesson_assets.dart';
import '../models/quiz_deck.dart';
import 'program_providers.dart';

final lessonAssetsProvider = FutureProvider.autoDispose
    .family<LessonAssets?, String>((ref, lessonId) {
  final repo = ref.watch(programRepositoryProvider);
  return repo.getLessonAssets(lessonId);
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
