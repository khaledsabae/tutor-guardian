import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/flashcard_deck.dart';
import '../models/lesson_assets.dart';
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
