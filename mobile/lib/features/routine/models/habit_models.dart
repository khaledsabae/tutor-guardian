/// Habit models for «ميزان العادات» — age-dynamic habit tracker.
library;

enum HabitCategory { worship, selfBuilding, study }

extension HabitCategoryX on HabitCategory {
  static HabitCategory fromWireName(String name) {
    return HabitCategory.values.firstWhere(
      (c) => c.wireName == name,
      orElse: () => HabitCategory.selfBuilding,
    );
  }

  String get wireName {
    switch (this) {
      case HabitCategory.worship:
        return 'worship';
      case HabitCategory.selfBuilding:
        return 'self_building';
      case HabitCategory.study:
        return 'study';
    }
  }

  String get label {
    switch (this) {
      case HabitCategory.worship:
        return 'العبادات';
      case HabitCategory.selfBuilding:
        return 'بناء الذات';
      case HabitCategory.study:
        return 'المذاكرة';
    }
  }

  String get icon {
    switch (this) {
      case HabitCategory.worship:
        return '🕌';
      case HabitCategory.selfBuilding:
        return '🌱';
      case HabitCategory.study:
        return '📚';
    }
  }
}

enum HabitStatus { completed, partially, missed }

extension HabitStatusX on HabitStatus {
  String get wireName {
    switch (this) {
      case HabitStatus.completed:
        return 'completed';
      case HabitStatus.partially:
        return 'partially';
      case HabitStatus.missed:
        return 'missed';
    }
  }

  String get label {
    switch (this) {
      case HabitStatus.completed:
        return 'تم';
      case HabitStatus.partially:
        return 'جزئي';
      case HabitStatus.missed:
        return 'لم يتم';
    }
  }

  String get icon {
    switch (this) {
      case HabitStatus.completed:
        return '✅';
      case HabitStatus.partially:
        return '🟡';
      case HabitStatus.missed:
        return '❌';
    }
  }

  static HabitStatus fromWireName(String name) {
    return HabitStatus.values.firstWhere(
      (s) => s.wireName == name,
      orElse: () => HabitStatus.missed,
    );
  }
}

class HabitItem {
  final HabitCategory category;
  final String habitName;

  const HabitItem({required this.category, required this.habitName});
}

class HabitEvent {
  final int? id;
  final int childId;
  final HabitCategory category;
  final String habitName;
  final HabitStatus status;
  final String createdAt;

  const HabitEvent({
    this.id,
    required this.childId,
    required this.category,
    required this.habitName,
    required this.status,
    required this.createdAt,
  });

  factory HabitEvent.fromJson(Map<String, dynamic> json) {
    return HabitEvent(
      id: json['id'] as int?,
      childId: json['child_id'] as int,
      category: HabitCategoryX.fromWireName(json['category'] as String),
      habitName: json['habit_name'] as String,
      status: HabitStatus.values.firstWhere(
        (s) => s.wireName == (json['status'] as String),
        orElse: () => HabitStatus.missed,
      ),
      createdAt: json['created_at'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'category': category.wireName,
      'habit_name': habitName,
      'status': status.wireName,
    };
  }
}

/// A merged row returned by `GET /api/value-tracking/today`.
/// Represents one habit for the day — either a default or a custom template —
/// optionally with an already-recorded event.
class TodayHabitItem {
  final HabitCategory category;
  final String habitName;
  final String source; // 'default' | 'custom'
  final HabitStatus? status;
  final int? eventId;
  final int? templateId;

  const TodayHabitItem({
    required this.category,
    required this.habitName,
    required this.source,
    this.status,
    this.eventId,
    this.templateId,
  });

  factory TodayHabitItem.fromJson(Map<String, dynamic> json) {
    final rawStatus = json['status'] as String?;
    return TodayHabitItem(
      category: HabitCategoryX.fromWireName(json['category'] as String),
      habitName: json['habit_name'] as String,
      source: json['source'] as String,
      status: rawStatus == null
          ? null
          : HabitStatus.values.firstWhere(
              (s) => s.wireName == rawStatus,
              orElse: () => HabitStatus.missed,
            ),
      eventId: json['event_id'] as int?,
      templateId: json['template_id'] as int?,
    );
  }
}

class HabitDay {
  final int childId;
  final String date;
  final List<HabitEvent> events;
  final double points;
  final List<TodayHabitItem> habits;

  const HabitDay({
    required this.childId,
    required this.date,
    required this.events,
    this.points = 0.0,
    this.habits = const [],
  });

  factory HabitDay.fromJson(Map<String, dynamic> json) {
    return HabitDay(
      childId: json['child_id'] as int,
      date: json['date'] as String,
      events: (json['events'] as List?)
              ?.map((e) => HabitEvent.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      points: (json['points'] as num?)?.toDouble() ?? 0.0,
      habits: (json['habits'] as List?)
              ?.map((h) => TodayHabitItem.fromJson(h as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

/// Custom habit template created by the parent for a specific child.
class HabitTemplate {
  final int id;
  final int childId;
  final HabitCategory category;
  final String customName;
  final bool isActive;
  final String createdAt;
  final String updatedAt;

  const HabitTemplate({
    required this.id,
    required this.childId,
    required this.category,
    required this.customName,
    this.isActive = true,
    required this.createdAt,
    required this.updatedAt,
  });

  factory HabitTemplate.fromJson(Map<String, dynamic> json) {
    return HabitTemplate(
      id: json['id'] as int,
      childId: json['child_id'] as int,
      category: HabitCategoryX.fromWireName(json['category'] as String),
      customName: json['custom_name'] as String,
      isActive: (json['is_active'] as int? ?? 1) == 1,
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }

  Map<String, dynamic> toCreateJson() {
    return {
      'category': category.wireName,
      'custom_name': customName,
    };
  }

  Map<String, dynamic> toUpdateJson() {
    return {'is_active': isActive};
  }
}

/// Age-banded default habit presets.
///
/// 7-9 years: simplified starter set ("muruu hum bil-sala li-sab'"),
///   includes 'النوم المبكر' in place of biological sleep tracking.
/// 10-18 years: full adolescent habit set.
const Map<String, Map<HabitCategory, List<String>>> kAgeBandedHabits = {
  // 7-9: starter routine — prayers, Quran, homework, respect, early sleep.
  '7-9': {
    HabitCategory.worship: [
      'صلاة الفجر',
      'صلاة الظهر',
      'صلاة العصر',
      'صلاة المغرب',
      'صلاة العشاء',
      'ورد القرآن',
    ],
    HabitCategory.selfBuilding: [
      'بر الوالدين',
      'الصدق',
      'احترام الكبار',
      'ترتيب الغرفة',
      'النوم المبكر',
    ],
    HabitCategory.study: [
      'أداء الواجب',
      'المراجعة',
    ],
  },
  // 10-18: full adolescent set.
  '10-18': {
    HabitCategory.worship: [
      'صلاة الفجر',
      'صلاة الظهر',
      'صلاة العصر',
      'صلاة المغرب',
      'صلاة العشاء',
      'قراءة القرآن',
    ],
    HabitCategory.selfBuilding: [
      'التحكم بالغضب',
      'الصدق',
      'احترام الكبار',
      'ترتيب الغرفة',
    ],
    HabitCategory.study: [
      'أداء الواجب',
      'المراجعة',
      'القراءة',
    ],
  },
};

/// Helper: resolve habits for a given age group.
/// Falls back to the adolescent band for any unknown age group.
Map<HabitCategory, List<String>> habitsForAge(String ageGroup) {
  if (ageGroup == '7-9') return kAgeBandedHabits['7-9']!;
  return kAgeBandedHabits['10-18']!;
}

/// Legacy alias for code that does not yet know about age-banded habits.
@Deprecated('Use habitsForAge(ageGroup) instead')
Map<HabitCategory, List<String>> get kDefaultHabits =>
    kAgeBandedHabits['10-18']!;