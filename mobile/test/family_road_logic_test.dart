// «درب {الاسم}» (عالم الأسرة): the gates ahead and what is behind «أنتم هنا».
//
// The road opens on what is ahead — the empty road is the risk — so these
// pin that the horizon comes from real server answers only, nearest first,
// with no gate for worship or for anything undone; and that behind «أنتم
// هنا» only what was done is ever drawn.
import 'package:almorabbi/features/family_road/logic/horizon.dart';
import 'package:almorabbi/features/family_road/logic/road_past.dart';
import 'package:almorabbi/features/lanterns/data/family_week.dart';
import 'package:almorabbi/features/program/data/models.dart';
import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/programs/data/programs_models.dart';
import 'package:flutter_test/flutter_test.dart';

import 'lantern_fakes.dart';

final _today = DateTime(2026, 10, 15);

CurriculumPath _path(String id, int lessons, {String? title}) =>
    CurriculumPath(
      id: id,
      title: title ?? 'مسار $id',
      ageGroup: '4-6',
      domain: 'islamic_parenting',
      description: '',
      lessonIds: [for (var i = 0; i < lessons; i++) '$id-$i'],
      estimatedDays: 5,
    );

ChildProgressBundle _bundle(List<(String, String, String, String?)> lessons) =>
    ChildProgressBundle.fromJson({
      'child_id': 1,
      'lessons': [
        for (final (path, lesson, status, at) in lessons)
          {
            'lesson_id': lesson,
            'path_id': path,
            'status': status,
            'completed_at': at,
          },
      ],
    });

void main() {
  group('the horizon', () {
    test('Ramadan ahead, from the server\'s days_until_start', () {
      final g = horizonGates(
        HorizonInputs(
          today: _today,
          ramadanState: 'upcoming',
          ramadanDaysUntil: 116,
        ),
      );
      expect(g.single.kind, GateKind.ramadan);
      expect(g.single.days, 116);
      expect(stripGate(g)!.kind, GateKind.ramadan);
    });

    test('in the month the gate is the month itself; after it, none', () {
      final now = horizonGates(
        HorizonInputs(today: _today, ramadanState: 'ramadan', ramadanDay: 3),
      );
      expect(now.single.kind, GateKind.ramadanNow);
      expect(now.single.ramadanDay, 3);
      for (final state in ['eid', 'after', 'off_season', null]) {
        expect(
          horizonGates(HorizonInputs(today: _today, ramadanState: state)),
          isEmpty,
          reason: '$state',
        );
      }
    });

    test('seven years old: from a real birth month, within two years', () {
      HorizonGate? seven(int months, {bool birth = true}) => horizonGates(
        HorizonInputs(
          today: _today,
          child: HorizonChild(ageMonths: months, ageFromBirthMonth: birth),
        ),
      ).where((g) => g.kind == GateKind.ageSeven).firstOrNull;
      expect(seven(80)!.months, 4);
      expect(seven(80)!.days, inInclusiveRange(100, 140));
      expect(seven(60)!.months, 24);
      expect(seven(59), isNull, reason: 'more than two years off');
      expect(seven(84), isNull, reason: 'already seven');
      expect(seven(80, birth: false), isNull, reason: 'a band guess');
    });

    test('nearest first, the next path before every dated gate', () {
      final g = horizonGates(
        HorizonInputs(
          today: _today,
          ramadanState: 'upcoming',
          ramadanDaysUntil: 116,
          child: const HorizonChild(ageMonths: 82, ageFromBirthMonth: true),
          nextPathId: 'p2',
          nextPathTitle: 'الغضب',
          milestones: [
            HorizonMilestone(
              key: 'school_entry',
              title: 'دخول المدرسة',
              state: 'upcoming',
              dueOn: DateTime(2027, 9, 1),
            ),
          ],
        ),
      );
      expect(g.map((e) => e.kind), [
        GateKind.nextPath,
        GateKind.ageSeven,
        GateKind.ramadan,
        GateKind.milestone,
      ]);
      // The strip names a time, never the next path (that is ① already).
      expect(stripGate(g)!.kind, GateKind.ageSeven);
    });

    test('a due milestone is now; seven is not shown twice', () {
      final g = horizonGates(
        HorizonInputs(
          today: _today,
          ramadanState: 'upcoming',
          ramadanDaysUntil: 116,
          child: const HorizonChild(
            ageMonths: 80,
            ageFromBirthMonth: true,
            milestonesDue: 1,
          ),
          milestones: [
            const HorizonMilestone(
              key: 'tamyeez',
              title: 'سنّ التمييز',
              state: 'due',
            ),
            HorizonMilestone(
              key: kPrayerStartKey,
              title: 'بداية تعليم الصلاة',
              state: 'upcoming',
              dueOn: DateTime(2027, 2, 1),
            ),
          ],
        ),
      );
      expect(g.first.kind, GateKind.milestoneDue);
      expect(g.first.title, 'سنّ التمييز');
      expect(g.first.milestoneKey, 'tamyeez');
      expect(g.where((e) => e.milestoneKey == kPrayerStartKey), isEmpty);
      expect(g.where((e) => e.kind == GateKind.ageSeven), hasLength(1));
    });

    test('no birth month: the dated gates wait for it, last', () {
      final g = horizonGates(
        HorizonInputs(
          today: _today,
          ramadanState: 'upcoming',
          ramadanDaysUntil: 116,
          child: const HorizonChild(needsBirthMonth: true),
        ),
      );
      expect(g.last.kind, GateKind.birthMonth);
      expect(stripGate(g)!.kind, GateKind.ramadan);
      expect(
        stripGate(const [HorizonGate(kind: GateKind.birthMonth)]),
        isNull,
      );
    });

    test('a horizon, not a checklist: four gates at most', () {
      final g = horizonGates(
        HorizonInputs(
          today: _today,
          ramadanState: 'upcoming',
          ramadanDaysUntil: 40,
          nextPathId: 'p',
          child: const HorizonChild(
            ageMonths: 82,
            ageFromBirthMonth: true,
            milestonesDue: 1,
          ),
          milestones: [
            HorizonMilestone(
              key: 'k',
              title: 't',
              state: 'upcoming',
              dueOn: DateTime(2027, 3, 1),
            ),
          ],
        ),
      );
      expect(g, hasLength(kMaxGates));
    });

    test('far or past milestones are not on the horizon', () {
      final g = horizonGates(
        HorizonInputs(
          today: _today,
          milestones: [
            HorizonMilestone(
              key: 'far',
              title: 'far',
              state: 'upcoming',
              dueOn: DateTime(2029, 1, 1),
            ),
            HorizonMilestone(
              key: 'gone',
              title: 'gone',
              state: 'past',
              dueOn: DateTime(2025, 1, 1),
            ),
          ],
        ),
      );
      expect(g, isEmpty);
    });
  });

  group('where «أنتم هنا» stands', () {
    final paths = [_path('a', 3), _path('b', 2), _path('c', 4)];

    test('the most recently touched unfinished path is resumed', () {
      final b = _bundle([
        ('a', 'a-0', 'completed', '2026-10-01'),
        ('c', 'c-0', 'completed', '2026-10-02'),
      ]);
      final here = resumePath(paths, b)!;
      expect(here.path.id, 'c');
      expect(here.done, 1);
      // The next path is one not touched at all.
      expect(nextPath(paths, b)!.id, 'b');
    });

    test('no progress: nothing to resume; the first path is next', () {
      expect(resumePath(paths, null), isNull);
      expect(nextPath(paths, null)!.id, 'a');
    });

    test('«اكتمل البدر»: finished paths only, most recent first', () {
      final b = _bundle([
        ('b', 'b-0', 'completed', '2026-09-01'),
        ('b', 'b-1', 'completed', '2026-09-02'),
        ('a', 'a-0', 'completed', '2026-10-01'),
        ('a', 'a-1', 'completed', '2026-10-02'),
        ('a', 'a-2', 'completed', '2026-10-03'),
        ('c', 'c-0', 'completed', '2026-10-04'),
      ]);
      expect(fullMoons(paths, b).map((p) => p.id), ['a', 'b']);
    });
  });

  group('behind «أنتم هنا»', () {
    test('only lit days and lit weeks — this week is not counted twice', () {
      final week = FamilyWeek.fromJson(
        familyWeekJson(
          acts: [act('lesson', 0), act('question', 2), act('lesson', 2)],
          litWeeksTotal: 9,
        ),
      );
      final past = RoadPast.from(week, const []);
      expect(past.weekLanterns, 2);
      // familyWeekJson lights the even weeks back: 2, 4, 6 of the last 7.
      expect(past.earlierLitWeeks, 3);
      expect(past.litWeeksTotal, 9);
      expect(past.isEmpty, isFalse);
      expect(past.showsTotal, isTrue);
    });

    test('a family that has done nothing yet has an empty past', () {
      final week = FamilyWeek.fromJson({
        'week_start': '2026-10-12',
        'acts': <Object>[],
        'lit_this_week': false,
        'lit_weeks_total': 0,
        'last_8': [
          for (var i = 0; i < 8; i++) {'week_start': '2026-08-24', 'lit': false},
        ],
      });
      expect(RoadPast.from(week, const []).isEmpty, isTrue);
      expect(RoadPast.from(null, const []).isEmpty, isTrue);
    });

    test('a first lit week alone adds no «since the start» line', () {
      const past = RoadPast(weekLanterns: 1, litWeeksTotal: 1);
      expect(past.showsTotal, isFalse);
    });
  });

  test('hijri_season parses the three seasons and ignores any other', () {
    HijriSeason? parse(Object? m) =>
        ProgramsOverview.fromJson({'hijri_season': m}).hijriSeason;
    expect(
      parse({'month': 'rajab', 'day': 5, 'hijri_year': 1448})!.month,
      HijriSeasonMonth.rajab,
    );
    expect(parse({'month': 'shaban'})!.month, HijriSeasonMonth.shaban);
    expect(
      parse({'month': 'dhul_hijjah'})!.month.wire,
      'dhul_hijjah',
    );
    expect(parse({'month': 'muharram'}), isNull);
    expect(parse(null), isNull);
    expect(ProgramsOverview.fromJson({}).hijriSeason, isNull);
  });
}
