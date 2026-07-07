/// Habit models for «ميزان العادات» — age-dynamic habit tracker.
library;

enum HabitCategory { worship, selfBuilding, study }

extension HabitCategoryX on HabitCategory {
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
      category: HabitCategory.values.firstWhere(
        (c) => c.wireName == (json['category'] as String),
        orElse: () => HabitCategory.worship,
      ),
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

class HabitDay {
  final int childId;
  final String date;
  final List<HabitEvent> events;
  final double points;

  const HabitDay({
    required this.childId,
    required this.date,
    required this.events,
    this.points = 0.0,
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
    );
  }
}

/// Hardcoded habit presets per category (MVP — no customization).
///
/// Age-banded:
///   * 7-9 years: simplified starter set ("muruu hum bil-sala li-sab'"),
///     includes 'النوم المبكر' in place of biological sleep tracking.
///   * 10-18 years: full adolescent habit set.
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