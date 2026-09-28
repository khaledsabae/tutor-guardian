/// Habit models for «ميزان العادات» — age-dynamic habit tracker.
library;

import 'package:almorabbi/l10n/app_localizations.dart';

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

  String label(AppLocalizations l10n) {
    switch (this) {
      case HabitCategory.worship:
        return l10n.habitCategoryWorship;
      case HabitCategory.selfBuilding:
        return l10n.habitCategorySelfBuilding;
      case HabitCategory.study:
        return l10n.habitCategoryStudy;
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

  String label(AppLocalizations l10n) {
    switch (this) {
      case HabitStatus.completed:
        return l10n.habitChildModeDone;
      case HabitStatus.partially:
        return l10n.habitChildModePartial;
      case HabitStatus.missed:
        return l10n.habitChildModeMissed;
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

/// Run of days with effort (completed or partially), where one empty day a
/// week is forgiven — the "streak shield" (UX_UI_ROADMAP §3.3). Zero from an
/// older server that does not send it.
class HabitStreak {
  final int days;
  final bool todayActive;
  final bool shieldUsedThisWeek;

  const HabitStreak({
    this.days = 0,
    this.todayActive = false,
    this.shieldUsedThisWeek = false,
  });

  factory HabitStreak.fromJson(Object? json) {
    if (json is! Map) return const HabitStreak();
    return HabitStreak(
      days: (json['days'] as num?)?.toInt() ?? 0,
      todayActive: json['today_active'] == true,
      shieldUsedThisWeek: json['shield_used_this_week'] == true,
    );
  }
}

extension HabitStreakX on HabitStreak {
  /// The streak once today gets its first effort — the server's rule, applied
  /// locally so a milestone shows the moment it is earned. Idempotent.
  HabitStreak withEffortToday() => todayActive
      ? this
      : HabitStreak(
          days: days + 1,
          todayActive: true,
          shieldUsedThisWeek: shieldUsedThisWeek,
        );
}

/// Streak lengths worth a celebration. Capped on purpose: more than a few
/// becomes noise (§3.3).
const List<int> kStreakMilestones = [3, 7, 30];

/// The milestone crossed going from [before] to [after] days, if any.
int? streakMilestoneCrossed(int before, int after) {
  for (final m in kStreakMilestones) {
    if (before < m && after >= m) return m;
  }
  return null;
}

/// The last seven days per habit, oldest first (`GET …/summary` strip).
class HabitWeek {
  final List<String> dates;
  final Map<String, List<HabitStatus?>> byHabit;

  const HabitWeek({this.dates = const [], this.byHabit = const {}});

  factory HabitWeek.fromSummaryJson(Map<String, dynamic> json) {
    final dates = [
      for (final d in (json['strip_dates'] as List? ?? const [])) '$d',
    ];
    final raw = json['strip'];
    final byHabit = <String, List<HabitStatus?>>{};
    if (raw is Map) {
      raw.forEach((name, days) {
        if (days is! List) return;
        byHabit['$name'] = [
          for (final d in days)
            d is String ? HabitStatusX.fromWireName(d) : null,
        ];
      });
    }
    return HabitWeek(dates: dates, byHabit: byHabit);
  }

  /// Seven cells for [habitName]; the last is replaced by [today] when given,
  /// so a record just made shows before the next summary fetch.
  List<HabitStatus?> cellsFor(String habitName, {HabitStatus? today}) {
    final cells = List<HabitStatus?>.of(
      byHabit[habitName] ?? List<HabitStatus?>.filled(7, null),
    );
    while (cells.length < 7) {
      cells.insert(0, null);
    }
    if (today != null) cells[cells.length - 1] = today;
    return cells.sublist(cells.length - 7);
  }
}

class HabitDay {
  final int childId;
  final String date;
  final List<HabitEvent> events;
  final double points;
  final List<TodayHabitItem> habits;
  final HabitStreak streak;

  const HabitDay({
    required this.childId,
    required this.date,
    required this.events,
    this.points = 0.0,
    this.habits = const [],
    this.streak = const HabitStreak(),
  });

  HabitDay withStreak(HabitStreak streak) => HabitDay(
        childId: childId,
        date: date,
        events: events,
        points: points,
        habits: habits,
        streak: streak,
      );

  factory HabitDay.fromJson(Map<String, dynamic> json) {
    return HabitDay(
      childId: json['child_id'] as int,
      date: json['date'] as String,
      streak: HabitStreak.fromJson(json['streak']),
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

/// Resolves the display name for a habit.
///
/// Default habit names are Arabic wire values (part of the backend
/// value-tracking contract — never translate the wire strings themselves).
/// This maps the known defaults to localized labels; custom, user-entered
/// habit names fall through unchanged.
String habitDisplayName(String habitName, AppLocalizations l10n) {
  switch (habitName) {
    case 'صلاة الفجر':
      return l10n.habitPrayerFajr;
    case 'صلاة الظهر':
      return l10n.habitPrayerDhuhr;
    case 'صلاة العصر':
      return l10n.habitPrayerAsr;
    case 'صلاة المغرب':
      return l10n.habitPrayerMaghrib;
    case 'صلاة العشاء':
      return l10n.habitPrayerIsha;
    case 'ورد القرآن':
      return l10n.habitQuranWerd;
    case 'قراءة القرآن':
      return l10n.habitQuranReading;
    case 'بر الوالدين':
      return l10n.habitHonoringParents;
    case 'الصدق':
      return l10n.habitHonesty;
    case 'احترام الكبار':
      return l10n.habitRespectElders;
    case 'ترتيب الغرفة':
      return l10n.habitTidyRoom;
    case 'النوم المبكر':
      return l10n.habitEarlySleep;
    case 'التحكم بالغضب':
      return l10n.habitAngerControl;
    case 'أداء الواجب':
      return l10n.habitHomework;
    case 'المراجعة':
      return l10n.habitRevision;
    case 'القراءة':
      return l10n.habitReading;
    default:
      return habitName;
  }
}