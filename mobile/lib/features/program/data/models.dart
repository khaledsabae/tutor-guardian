/// Curriculum content models — Phase 4 (Flutter UI).
///
/// These mirror the JSON shapes served by the backend
/// (`knowledge_base/curriculum/schema/*.schema.json`) and the
/// `routers/program.py` endpoints under `/api/program/*`.
///
/// All fields are parsed strictly; unknown fields are tolerated on the
/// wire (per `MOBILE_API.md` v1 contract — "clients must ignore unknown
/// fields"). Numbers and durations are decoded conservatively.
library;

import '../../models/enums.dart';

/// A "journey" — 3-10 lessons over 1-30 days for a specific age+domain.
class CurriculumPath {
  final String id;
  final String title;
  final String ageGroup; // canonical wire value, e.g. "4-6"
  final String domain; // canonical: medical | cyber | islamic_parenting | development
  final String description;
  final List<String> lessonIds;
  final int estimatedDays;
  final String? pedagogicalFramework;
  final PathReference? primaryReference;
  final List<String> prerequisites;
  final bool isPublished;
  final String? version;

  const CurriculumPath({
    required this.id,
    required this.title,
    required this.ageGroup,
    required this.domain,
    required this.description,
    required this.lessonIds,
    required this.estimatedDays,
    this.pedagogicalFramework,
    this.primaryReference,
    this.prerequisites = const [],
    this.isPublished = true,
    this.version,
  });

  factory CurriculumPath.fromJson(Map<String, dynamic> json) {
    return CurriculumPath(
      id: json['id'] as String,
      title: json['title'] as String,
      ageGroup: json['age_group'] as String,
      domain: json['domain'] as String,
      description: json['description'] as String? ?? '',
      lessonIds: ((json['lesson_ids'] as List?) ?? const [])
          .map((e) => e as String)
          .toList(),
      estimatedDays: (json['estimated_days'] as num?)?.toInt() ?? 0,
      pedagogicalFramework: json['pedagogical_framework'] as String?,
      primaryReference: json['primary_reference'] == null
          ? null
          : PathReference.fromJson(
              json['primary_reference'] as Map<String, dynamic>,
            ),
      prerequisites: ((json['prerequisites'] as List?) ?? const [])
          .map((e) => e as String)
          .toList(),
      isPublished: json['is_published'] as bool? ?? true,
      version: json['version'] as String?,
    );
  }

  /// Human-readable age label (uses the same mapping as `models/enums.dart`
  /// for the canonical enums; falls back to the raw wire value).
  String get ageLabel {
    final ag = AgeGroup.fromWire(ageGroup);
    return ag == AgeGroup.unspecified ? ageGroup : ag.arabicLabel;
  }

  /// Human-readable domain label.
  String get domainLabel => _domainLabel(domain);

  static String _domainLabel(String wire) {
    switch (wire) {
      case 'islamic_parenting':
        return 'تربية إسلامية';
      case 'development':
        return 'تنمية';
      case 'medical':
        return 'صحة';
      case 'cyber':
        return 'أمان رقمي';
      default:
        return wire;
    }
  }
}

/// Book/hadith/journal reference attached to a path.
class PathReference {
  final String type; // canonical reference_type
  final String info;

  const PathReference({required this.type, required this.info});

  factory PathReference.fromJson(Map<String, dynamic> json) {
    return PathReference(
      type: json['type'] as String,
      info: json['info'] as String? ?? '',
    );
  }
}

/// A single lesson — 3-15 minutes, 1-10 knowledge unit_ids.
class CurriculumLesson {
  final String id;
  final String pathId;
  final String title;
  final String ageGroup;
  final String domain;
  final List<String> unitIds;
  final String summary;
  final String tryThis;
  final int order;
  final int estimatedMinutes;
  final List<String> reflectionPrompts;
  final List<String> warningFlags;
  final bool isPublished;
  final String? version;

  const CurriculumLesson({
    required this.id,
    required this.pathId,
    required this.title,
    required this.ageGroup,
    required this.domain,
    required this.unitIds,
    required this.summary,
    required this.tryThis,
    required this.order,
    required this.estimatedMinutes,
    this.reflectionPrompts = const [],
    this.warningFlags = const [],
    this.isPublished = true,
    this.version,
  });

  factory CurriculumLesson.fromJson(Map<String, dynamic> json) {
    return CurriculumLesson(
      id: json['id'] as String,
      pathId: json['path_id'] as String,
      title: json['title'] as String,
      ageGroup: json['age_group'] as String,
      domain: json['domain'] as String,
      unitIds: ((json['unit_ids'] as List?) ?? const [])
          .map((e) => e as String)
          .toList(),
      summary: json['summary'] as String? ?? '',
      tryThis: json['try_this'] as String? ?? '',
      order: (json['order'] as num?)?.toInt() ?? 0,
      estimatedMinutes: (json['estimated_minutes'] as num?)?.toInt() ?? 5,
      reflectionPrompts: ((json['reflection_prompts'] as List?) ?? const [])
          .map((e) => e as String)
          .toList(),
      warningFlags: ((json['warning_flags'] as List?) ?? const [])
          .map((e) => e as String)
          .toList(),
      isPublished: json['is_published'] as bool? ?? true,
      version: json['version'] as String?,
    );
  }

  bool get needsProfessionalFollowup =>
      warningFlags.contains('needs_professional_followup');
  bool get hasRegionalFiqhVariation =>
      warningFlags.contains('regional_fiqh_variation');
  bool get isDevelopmentalRedFlag =>
      warningFlags.contains('developmental_red_flag');
}

/// A short (≤ 280 char) daily parenting tip.
class DailyTip {
  final String id;
  final String ageGroup;
  final String domain;
  final String text;
  final String? unitId;
  final int? dayOfWeek; // 0..6 (Mon..Sun)
  final String timeOfDay; // morning | evening | bedtime | anytime
  final List<String> tags;
  final bool isPublished;
  final String? version;

  const DailyTip({
    required this.id,
    required this.ageGroup,
    required this.domain,
    required this.text,
    this.unitId,
    this.dayOfWeek,
    this.timeOfDay = 'anytime',
    this.tags = const [],
    this.isPublished = true,
    this.version,
  });

  factory DailyTip.fromJson(Map<String, dynamic> json) {
    return DailyTip(
      id: json['id'] as String,
      ageGroup: json['age_group'] as String,
      domain: json['domain'] as String,
      text: json['text'] as String? ?? '',
      unitId: json['unit_id'] as String?,
      dayOfWeek: (json['day_of_week'] as num?)?.toInt(),
      timeOfDay: json['time_of_day'] as String? ?? 'anytime',
      tags: ((json['tags'] as List?) ?? const [])
          .map((e) => e as String)
          .toList(),
      isPublished: json['is_published'] as bool? ?? true,
      version: json['version'] as String?,
    );
  }

  String get timeOfDayLabel {
    switch (timeOfDay) {
      case 'morning':
        return 'صباحاً';
      case 'evening':
        return 'مساءً';
      case 'bedtime':
        return 'قبل النوم';
      default:
        return 'أي وقت';
    }
  }
}

/// Bundle returned by `GET /api/program/paths/{id}?include=lessons`.
class PathDetail {
  final CurriculumPath path;
  final List<CurriculumLesson> lessons;

  const PathDetail({required this.path, required this.lessons});

  factory PathDetail.fromPathAndList(
    CurriculumPath path,
    List<CurriculumLesson> lessons,
  ) {
    return PathDetail(path: path, lessons: lessons);
  }
}

/// A simple "envelope" for the bare `GET /api/program/paths` response
/// `{ "count": N, "paths": [...] }`.
class PathListEnvelope {
  final int count;
  final List<CurriculumPath> paths;

  const PathListEnvelope({required this.count, required this.paths});

  factory PathListEnvelope.fromJson(Map<String, dynamic> json) {
    final list = ((json['paths'] as List?) ?? const [])
        .map((e) => CurriculumPath.fromJson(e as Map<String, dynamic>))
        .toList();
    return PathListEnvelope(
      count: (json['count'] as num?)?.toInt() ?? list.length,
      paths: list,
    );
  }
}
