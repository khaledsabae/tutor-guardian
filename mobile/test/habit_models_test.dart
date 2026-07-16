// Unit tests for habit models and age-gating logic (ميزان العادات).
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/screens/daily_routine_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/app_localizations_ar.dart';

void main() {
  group('habitAgeAllowed (7-18)', () {
    test('returns true for 7-9', () {
      expect(habitAgeAllowed('7-9'), isTrue);
    });
    test('returns true for 10-12', () {
      expect(habitAgeAllowed('10-12'), isTrue);
    });
    test('returns true for 13-15', () {
      expect(habitAgeAllowed('13-15'), isTrue);
    });
    test('returns true for 16-18', () {
      expect(habitAgeAllowed('16-18'), isTrue);
    });
    test('returns false for baby ages', () {
      expect(habitAgeAllowed('0-3'), isFalse);
      expect(habitAgeAllowed('2-3'), isFalse);
      expect(habitAgeAllowed('4-6'), isFalse);
    });
    test('returns false for unspecified', () {
      expect(habitAgeAllowed('unspecified'), isFalse);
    });
  });

  group('routineAgeAllowed (0-6 regression)', () {
    test('returns true for baby ages', () {
      expect(routineAgeAllowed('0-3'), isTrue);
      expect(routineAgeAllowed('2-3'), isTrue);
      expect(routineAgeAllowed('4-6'), isTrue);
    });
    test('returns false for habit ages (7-18)', () {
      expect(routineAgeAllowed('7-9'), isFalse);
      expect(routineAgeAllowed('10-12'), isFalse);
      expect(routineAgeAllowed('13-15'), isFalse);
      expect(routineAgeAllowed('16-18'), isFalse);
    });
  });

  group('HabitCategory', () {
    test('wireName matches backend contract', () {
      expect(HabitCategory.worship.wireName, 'worship');
      expect(HabitCategory.selfBuilding.wireName, 'self_building');
      expect(HabitCategory.study.wireName, 'study');
    });
    test('labels are Arabic', () {
      expect(HabitCategory.worship.label, 'العبادات');
      expect(HabitCategory.selfBuilding.label, 'بناء الذات');
      expect(HabitCategory.study.label, 'المذاكرة');
    });
  });

  group('HabitStatus', () {
    test('wireName matches backend contract', () {
      expect(HabitStatus.completed.wireName, 'completed');
      expect(HabitStatus.partially.wireName, 'partially');
      expect(HabitStatus.missed.wireName, 'missed');
    });
    test('labels are Arabic', () {
      expect(HabitStatus.completed.label, 'تم');
      expect(HabitStatus.partially.label, 'جزئي');
      expect(HabitStatus.missed.label, 'لم يتم');
    });
  });

  group('HabitEvent.fromJson', () {
    test('parses a completed worship event', () {
      final json = {
        'id': 1,
        'child_id': 5,
        'category': 'worship',
        'habit_name': 'صلاة الفجر',
        'status': 'completed',
        'created_at': '2026-07-07T10:00:00',
      };
      final event = HabitEvent.fromJson(json);
      expect(event.id, 1);
      expect(event.childId, 5);
      expect(event.category, HabitCategory.worship);
      expect(event.habitName, 'صلاة الفجر');
      expect(event.status, HabitStatus.completed);
    });
    test('parses a partially study event', () {
      final json = {
        'id': 2,
        'child_id': 5,
        'category': 'study',
        'habit_name': 'أداء الواجب',
        'status': 'partially',
        'created_at': '2026-07-07T11:00:00',
      };
      final event = HabitEvent.fromJson(json);
      expect(event.category, HabitCategory.study);
      expect(event.status, HabitStatus.partially);
    });
  });

  group('HabitDay.fromJson', () {
    test('parses empty events list', () {
      final json = {
        'child_id': 5,
        'date': '2026-07-07',
        'events': [],
      };
      final day = HabitDay.fromJson(json);
      expect(day.childId, 5);
      expect(day.date, '2026-07-07');
      expect(day.events, isEmpty);
      expect(day.habits, isEmpty);
      expect(day.points, 0.0);
    });
    test('parses habits list from merged response', () {
      final json = {
        'child_id': 5,
        'date': '2026-07-07',
        'events': [],
        'points': 2.5,
        'habits': [
          {
            'category': 'worship',
            'habit_name': 'صلاة الفجر',
            'source': 'default',
            'status': 'completed',
            'event_id': 1,
          },
          {
            'category': 'self_building',
            'habit_name': 'مساعدة الوالدة',
            'source': 'custom',
            'status': null,
            'template_id': 7,
          },
        ],
      };
      final day = HabitDay.fromJson(json);
      expect(day.habits.length, 2);
      expect(day.habits[0].source, 'default');
      expect(day.habits[1].source, 'custom');
      expect(day.habits[1].templateId, 7);
      expect(day.points, 2.5);
    });
  });

  group('HabitTemplate.fromJson', () {
    test('parses active custom template', () {
      final json = {
        'id': 7,
        'child_id': 5,
        'category': 'self_building',
        'custom_name': 'مساعدة الوالدة',
        'is_active': 1,
        'created_at': '2026-07-07T10:00:00',
        'updated_at': '2026-07-07T10:00:00',
      };
      final t = HabitTemplate.fromJson(json);
      expect(t.id, 7);
      expect(t.customName, 'مساعدة الوالدة');
      expect(t.category, HabitCategory.selfBuilding);
      expect(t.isActive, isTrue);
    });
    test('parses archived template', () {
      final json = {
        'id': 8,
        'child_id': 5,
        'category': 'study',
        'custom_name': 'تمرين السباحة',
        'is_active': 0,
        'created_at': '2026-07-07T10:00:00',
        'updated_at': '2026-07-07T10:00:00',
      };
      final t = HabitTemplate.fromJson(json);
      expect(t.isActive, isFalse);
    });
  });

  group('kAgeBandedHabits', () {
    test('7-9 band includes النوم المبكر instead of detailed prayers', () {
      final habits = habitsForAge('7-9');
      expect(habits[HabitCategory.worship]!.contains('ورد القرآن'), isTrue);
      expect(habits[HabitCategory.selfBuilding]!.contains('النوم المبكر'), isTrue);
      expect(habits[HabitCategory.selfBuilding]!.contains('التحكم بالغضب'), isFalse);
    });
    test('10-18 band includes full adolescent set', () {
      final habits = habitsForAge('10-12');
      expect(habits[HabitCategory.worship]!.contains('قراءة القرآن'), isTrue);
      expect(habits[HabitCategory.selfBuilding]!.contains('التحكم بالغضب'), isTrue);
    });
    test('unknown age falls back to adolescent band', () {
      final habits = habitsForAge('unknown');
      expect(habits[HabitCategory.study]!.contains('القراءة'), isTrue);
    });
  });

  group('habitTabLabel', () {
    final l10n = AppLocalizationsAr();
    test('0-6 -> حساب اليوم', () {
      expect(habitTabLabel('4-6', l10n), l10n.routineDailyTracker);
    });
    test('7-18 -> ميزان العادات', () {
      expect(habitTabLabel('7-9', l10n), l10n.routineTitle);
      expect(habitTabLabel('10-12', l10n), l10n.routineTitle);
    });
    test('empty/unknown -> حساب اليوم', () {
      expect(habitTabLabel('', l10n), l10n.routineDailyTracker);
    });
  });
}