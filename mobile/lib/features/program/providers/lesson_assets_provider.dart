import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/lesson_assets.dart';
import 'program_providers.dart';

final lessonAssetsProvider = FutureProvider.autoDispose
    .family<LessonAssets?, String>((ref, lessonId) {
  final repo = ref.watch(programRepositoryProvider);
  return repo.getLessonAssets(lessonId);
});
