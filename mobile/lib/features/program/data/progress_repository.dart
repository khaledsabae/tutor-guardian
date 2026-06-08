/// Repository for Phase 5 (children + progress). Wraps [TgClient] and
/// keeps the [ChildProgressBundle] shape pure-typed for the UI.
library;

import '../../../api/tg_client.dart';
import 'progress_models.dart';

class ProgressRepository {
  ProgressRepository(this._client);

  final TgClient _client;

  /// `POST /api/children` — returns the new [ChildProfile].
  Future<ChildProfile> createChild({
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
  }) async {
    final json = await _client.createChild(
      name: name,
      ageGroup: ageGroup,
      gender: gender,
      avatarEmoji: avatarEmoji,
    );
    return ChildProfile.fromJson(json);
  }

  /// `GET /api/children/{id}/progress` — optional `?path_id=` filter.
  Future<ChildProgressBundle> getChildProgress(
    int childId, {
    String? pathId,
  }) async {
    final json = await _client.getChildProgress(childId, pathId: pathId);
    return ChildProgressBundle.fromJson(json);
  }

  /// `PATCH /api/program/lessons/{id}/progress` — idempotent.
  Future<LessonProgress> patchLessonProgress({
    required String lessonId,
    required ProgressStatus status,
  }) async {
    final json = await _client.patchLessonProgress(
      lessonId: lessonId,
      status: progressStatusToWire(status),
    );
    return LessonProgress.fromJson(json);
  }
}
