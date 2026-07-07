import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';

void main() {
  group('HabitDay.fromJson', () {
    test('parses child-mode today payload', () {
      final raw = jsonDecode(_samplePayload) as Map<String, dynamic>;
      final day = HabitDay.fromJson(raw);
      expect(day.childId, 5);
      expect(day.habits.length, 2);
      expect(day.habits.first.habitName, 'صلاة الفجر');
      expect(day.habits.first.category, HabitCategory.worship);
      expect(day.points, 0.0);
    });
  });

  group('ChildModeState', () {
    test('tracks submitted habits excluding missed', () {
      final state = ChildModeState(
        submittedHabits: {'صلاة الفجر', 'أداء الواجب'},
      );
      expect(state.isSubmitted('صلاة الفجر'), isTrue);
      expect(state.isSubmitted('نوم مبكر'), isFalse);
    });
  });
}

const _samplePayload = '''
{
  "child_id": 5,
  "date": "2026-07-07",
  "events": [],
  "habits": [
    {
      "category": "worship",
      "habit_name": "صلاة الفجر",
      "source": "default",
      "status": null,
      "event_id": null,
      "template_id": null
    },
    {
      "category": "study",
      "habit_name": "أداء الواجب",
      "source": "default",
      "status": null,
      "event_id": null,
      "template_id": null
    }
  ]
}
''';
