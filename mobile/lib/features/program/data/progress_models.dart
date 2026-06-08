/// Phase 5 models — children + lesson progress.
///
/// These mirror the wire format from
/// `routers/children.py` + `routers/program.py::patch_lesson_progress`.
library;

import 'models.dart'; // reuse CurriculumPath/CurriculumLesson

/// One child profile, owned by a single device.
class ChildProfile {
  final int id;
  final String name;
  final String ageGroup; // canonical wire value
  final String? gender;
  final String? avatarEmoji;
  final String? createdAt;
  final String? updatedAt;

  const ChildProfile({
    required this.id,
    required this.name,
    required this.ageGroup,
    this.gender,
    this.avatarEmoji,
    this.createdAt,
    this.updatedAt,
  });

  factory ChildProfile.fromJson(Map<String, dynamic> json) {
    return ChildProfile(
      id: (json['id'] as num).toInt(),
      name: json['name'] as String,
      ageGroup: json['age_group'] as String,
      gender: json['gender'] as String?,
      avatarEmoji: json['avatar_emoji'] as String?,
      createdAt: json['created_at'] as String?,
      updatedAt: json['updated_at'] as String?,
    );
  }
}

/// One row of `lesson_progress`. The backend never sends rows for
/// lessons the user hasn't touched — the Flutter UI treats "no row"
/// as "not_started".
enum ProgressStatus { notStarted, inProgress, completed }

ProgressStatus _statusFromWire(String? s) {
  switch (s) {
    case 'in_progress':
      return ProgressStatus.inProgress;
    case 'completed':
      return ProgressStatus.completed;
    case 'not_started':
    default:
      return ProgressStatus.notStarted;
  }
}

String progressStatusToWire(ProgressStatus s) {
  switch (s) {
    case ProgressStatus.inProgress:
      return 'in_progress';
    case ProgressStatus.completed:
      return 'completed';
    case ProgressStatus.notStarted:
      return 'not_started';
  }
}

String progressStatusLabel(ProgressStatus s) {
  switch (s) {
    case ProgressStatus.completed:
      return 'مكتمل';
    case ProgressStatus.inProgress:
      return 'قيد التنفيذ';
    case ProgressStatus.notStarted:
      return 'لم يبدأ';
  }
}

class LessonProgress {
  final String lessonId;
  final String pathId;
  final ProgressStatus status;
  final String? startedAt;
  final String? completedAt;
  final String? updatedAt;

  const LessonProgress({
    required this.lessonId,
    required this.pathId,
    required this.status,
    this.startedAt,
    this.completedAt,
    this.updatedAt,
  });

  factory LessonProgress.fromJson(Map<String, dynamic> json) {
    return LessonProgress(
      lessonId: json['lesson_id'] as String,
      pathId: json['path_id'] as String,
      status: _statusFromWire(json['status'] as String?),
      startedAt: json['started_at'] as String?,
      completedAt: json['completed_at'] as String?,
      updatedAt: json['updated_at'] as String?,
    );
  }
}

/// Bundle returned by `GET /api/children/{id}/progress`.
class ChildProgressBundle {
  final int childId;
  final String? deviceId;
  final List<LessonProgress> lessons;
  final String? fetchedAt;
  /// Phase 6 — number of consecutive UTC days (ending today or
  /// yesterday) on which the user completed at least one lesson.
  final int streakDays;
  /// Phase 6 — ISO 8601 timestamp of the most recent completion.
  final String? lastCompletedAt;

  const ChildProgressBundle({
    required this.childId,
    this.deviceId,
    required this.lessons,
    this.fetchedAt,
    this.streakDays = 0,
    this.lastCompletedAt,
  });

  factory ChildProgressBundle.fromJson(Map<String, dynamic> json) {
    return ChildProgressBundle(
      childId: (json['child_id'] as num).toInt(),
      deviceId: json['device_id'] as String?,
      lessons: ((json['lessons'] as List?) ?? const [])
          .map((e) => LessonProgress.fromJson(e as Map<String, dynamic>))
          .toList(),
      fetchedAt: json['fetched_at'] as String?,
      streakDays: (json['streak_days'] as num?)?.toInt() ?? 0,
      lastCompletedAt: json['last_completed_at'] as String?,
    );
  }

  /// Lookup helper — `null` for lessons the user hasn't touched.
  LessonProgress? forLesson(String lessonId) {
    for (final l in lessons) {
      if (l.lessonId == lessonId) return l;
    }
    return null;
  }

  /// Count of `completed` lessons in this bundle.
  int get completedCount =>
      lessons.where((l) => l.status == ProgressStatus.completed).length;
}
