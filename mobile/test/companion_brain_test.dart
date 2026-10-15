// «نور يتذكّر» — the priority rule and the anti-nag rules, pinned.
import 'package:almorabbi/features/companion/data/companion_store.dart';
import 'package:almorabbi/features/companion/logic/companion_brain.dart';
import 'package:flutter_test/flutter_test.dart';

final _wed = DateTime(2026, 10, 14, 9); // a Wednesday morning
final _mon = DateTime(2026, 10, 19, 9); // a Monday
final _fri = DateTime(2026, 10, 16, 9); // a Friday

Promise _promise({
  int id = 1,
  int child = 7,
  PromiseSlot slot = PromiseSlot.tonight,
  DateTime? made,
  int? followupId,
  String? outcome,
}) => Promise(
  id: id,
  childId: child,
  step: 'امدح صدقه أولًا',
  slot: slot,
  madeOn: made ?? DateTime(2026, 10, 13),
  followupId: followupId,
  outcome: outcome,
);

CompanionInputs _in({
  DateTime? now,
  CompanionMemory memory = const CompanionMemory(),
  int? childId = 7,
  int missions = 0,
  List<DueFollowup> followups = const [],
  int? ramadan,
  int? ramadanDay,
  int ramadanYear = 2027,
  bool plan = false,
  bool firstDay = false,
  ChildNotices notices = const ChildNotices(),
  int weekActs = 0,
}) => CompanionInputs(
  now: now ?? _wed,
  memory: memory,
  childId: childId,
  childName: 'سارة',
  missionsWaiting: missions,
  dueFollowups: followups,
  ramadanDaysUntil: ramadan,
  ramadanYear: ramadanYear,
  ramadanDay: ramadanDay,
  hasWeeklyPlan: plan,
  weekActs: weekActs,
  firstDay: firstDay,
  notices: notices,
);

void main() {
  test('no active child → no line (the plain greeting row stays)', () {
    expect(pickLine(_in(childId: null)), isNull);
  });

  test('a waiting mission comes first', () {
    final line = pickLine(
      _in(
        missions: 2,
        memory: CompanionMemory(promises: [_promise()]),
        followups: const [DueFollowup(id: 3, childId: 7, step: 'x')],
      ),
    )!;
    expect(line.kind, CompanionKind.missionsWaiting);
    expect(line.count, 2);
    expect(line.actions, [CompanionAction.confirmMissions]);
  });

  test('a promise made last night is asked this morning, not before', () {
    final made = DateTime(2026, 10, 13); // «الليلة» on Tuesday
    final memory = CompanionMemory(promises: [_promise(made: made)]);
    expect(
      pickLine(_in(now: DateTime(2026, 10, 13, 22), memory: memory))!.kind,
      isNot(CompanionKind.promiseDue),
    );
    final line = pickLine(_in(memory: memory))!;
    expect(line.kind, CompanionKind.promiseDue);
    expect(line.step, 'امدح صدقه أولًا');
    expect(line.actions, hasLength(3));
  });

  test('«هذا الأسبوع» waits seven days', () {
    final memory = CompanionMemory(
      promises: [
        _promise(slot: PromiseSlot.week, made: DateTime(2026, 10, 10)),
      ],
    );
    expect(
      pickLine(_in(memory: memory))!.kind,
      isNot(CompanionKind.promiseDue),
    );
    expect(
      pickLine(_in(now: DateTime(2026, 10, 17, 9), memory: memory))!.kind,
      CompanionKind.promiseDue,
    );
  });

  test('an answered promise is never asked again', () {
    final memory = CompanionMemory(promises: [_promise(outcome: 'worked')]);
    expect(pickLine(_in(memory: memory))!.kind, CompanionKind.greeting);
  });

  test('another child’s promise does not speak on this child’s Today', () {
    final memory = CompanionMemory(promises: [_promise(child: 99)]);
    expect(pickLine(_in(memory: memory))!.kind, CompanionKind.greeting);
  });

  test('a due follow-up is hosted when no promise carries it', () {
    final line = pickLine(
      _in(
        followups: const [DueFollowup(id: 3, childId: 7, step: 'ركن الهدوء')],
      ),
    )!;
    expect(line.kind, CompanionKind.followupDue);
    expect(line.followup!.id, 3);
  });

  test('a follow-up that a promise carries is asked once, as the promise', () {
    final memory = CompanionMemory(promises: [_promise(followupId: 3)]);
    final line = pickLine(
      _in(
        memory: memory,
        followups: const [
          DueFollowup(id: 3, childId: 7, step: 'x', source: 'lesson'),
        ],
      ),
    )!;
    expect(line.kind, CompanionKind.promiseDue);
  });

  test('two questions a day at most; one already shown may come back', () {
    final memory = CompanionMemory(
      promises: [_promise()],
      questionsByDay: {
        '2026-10-14': {'followup:1', 'followup:2'},
      },
    );
    expect(pickLine(_in(memory: memory))!.kind, CompanionKind.greeting);
    final again = CompanionMemory(
      promises: [_promise()],
      questionsByDay: {
        '2026-10-14': {'promise:1', 'followup:2'},
      },
    );
    expect(pickLine(_in(memory: again))!.kind, CompanionKind.promiseDue);
  });

  test('a line hidden for today falls through to the next', () {
    final memory = CompanionMemory(
      promises: [_promise()],
      hiddenByDay: {
        '2026-10-14': {'promise:1'},
      },
    );
    expect(pickLine(_in(memory: memory))!.kind, CompanionKind.greeting);
  });

  test('quiet mode only greets', () {
    final line = pickLine(
      _in(
        missions: 1,
        memory: CompanionMemory(promises: [_promise()], quietMode: true),
      ),
    )!;
    expect(line.kind, CompanionKind.greeting);
    expect(line.actions, isEmpty);
  });

  test('Ramadan countdown speaks on 30/14/7/1 only, once each', () {
    expect(pickLine(_in(ramadan: 8))!.kind, CompanionKind.greeting);
    final line = pickLine(_in(ramadan: 7))!;
    expect(line.kind, CompanionKind.ramadanCountdown);
    expect(line.onceOnly, isTrue);
    final seen = CompanionMemory(seenKeys: {line.key});
    expect(
      pickLine(_in(ramadan: 7, memory: seen))!.kind,
      CompanionKind.greeting,
    );
  });

  test('Monday reveals the plan once', () {
    final line = pickLine(_in(now: _mon, plan: true))!;
    expect(line.kind, CompanionKind.mondayPlan);
    expect(pickLine(_in(now: _wed, plan: true))!.kind, CompanionKind.greeting);
    expect(
      pickLine(
        _in(
          now: _mon,
          plan: true,
          memory: CompanionMemory(seenKeys: {line.key}),
        ),
      )!.kind,
      CompanionKind.greeting,
    );
  });

  group('Friday harvest («حصاد الجمعة», phase 3)', () {
    test('Friday with lanterns: the harvest line, once, with its chip', () {
      final line = pickLine(_in(now: _fri, weekActs: 4))!;
      expect(line.kind, CompanionKind.fridayHarvest);
      expect(line.key, 'harvest:2026-10-16T00:00:00.000');
      expect(line.onceOnly, isTrue);
      expect(line.isQuestion, isFalse);
      expect(line.actions, [CompanionAction.openHarvest]);
      expect(line.mood, CompanionMood.happy);
      final seen = CompanionMemory(seenKeys: {line.key});
      expect(
        pickLine(_in(now: _fri, weekActs: 4, memory: seen))!.kind,
        CompanionKind.greeting,
      );
    });

    test('a week with no lantern has no harvest — never an empty one', () {
      expect(pickLine(_in(now: _fri))!.kind, CompanionKind.greeting);
    });

    test('Friday only', () {
      for (var d = 0; d < 7; d++) {
        final day = DateTime(2026, 10, 12 + d, 9); // Mon 12 … Sun 18
        final kind = pickLine(_in(now: day, weekActs: 3))!.kind;
        expect(
          kind == CompanionKind.fridayHarvest,
          day.weekday == DateTime.friday,
          reason: '$day',
        );
      }
    });

    test('the anti-nag rules hold: hidden for today, quiet mode', () {
      final line = pickLine(_in(now: _fri, weekActs: 2))!;
      final hidden = CompanionMemory(
        hiddenByDay: {
          '2026-10-16': {line.key},
        },
      );
      expect(
        pickLine(_in(now: _fri, weekActs: 2, memory: hidden))!.kind,
        CompanionKind.greeting,
      );
      const quiet = CompanionMemory(quietMode: true);
      expect(
        pickLine(_in(now: _fri, weekActs: 2, memory: quiet))!.kind,
        CompanionKind.greeting,
      );
    });

    test('not a question: two questions asked today do not hold it back', () {
      final asked = CompanionMemory(
        questionsByDay: {
          '2026-10-16': {'followup:1', 'followup:2'},
        },
      );
      expect(
        pickLine(_in(now: _fri, weekActs: 2, memory: asked))!.kind,
        CompanionKind.fridayHarvest,
      );
    });

    test('the order above it is unchanged', () {
      // 1. a waiting mission
      expect(
        pickLine(_in(now: _fri, weekActs: 2, missions: 1))!.kind,
        CompanionKind.missionsWaiting,
      );
      // 2. a due promise (made Thursday night)
      final promise = CompanionMemory(
        promises: [_promise(made: DateTime(2026, 10, 15))],
      );
      expect(
        pickLine(_in(now: _fri, weekActs: 2, memory: promise))!.kind,
        CompanionKind.promiseDue,
      );
      // 3. a due follow-up
      expect(
        pickLine(
          _in(
            now: _fri,
            weekActs: 2,
            followups: const [DueFollowup(id: 3, childId: 7, step: 'x')],
          ),
        )!.kind,
        CompanionKind.followupDue,
      );
      // 4. a Ramadan countdown day
      expect(
        pickLine(_in(now: _fri, weekActs: 2, ramadan: 7))!.kind,
        CompanionKind.ramadanCountdown,
      );
      // 5. Monday's plan still speaks on Monday, lanterns or not.
      expect(
        pickLine(_in(now: _mon, plan: true, weekActs: 5))!.kind,
        CompanionKind.mondayPlan,
      );
    });

    test('a once-only line held for this open stays put after it is seen', () {
      final line = pickLine(_in(now: _fri, weekActs: 2))!;
      final seen = CompanionMemory(seenKeys: {line.key});
      expect(
        pickLine(
          _in(now: _fri, weekActs: 2, memory: seen.withoutSeen({line.key})),
        )!.kind,
        CompanionKind.fridayHarvest,
      );
    });
  });

  test('the greeting changes by day and holds within the day', () {
    final a = pickLine(_in(now: DateTime(2026, 10, 14, 9)))!;
    final b = pickLine(_in(now: DateTime(2026, 10, 14, 11)))!;
    final c = pickLine(_in(now: DateTime(2026, 10, 15, 9)))!;
    expect(a.key, b.key);
    expect(a.variant, isNot(c.variant));
  });

  test('time slots and the night mood', () {
    expect(slotOf(DateTime(2026, 1, 1, 5)), TimeSlot.dawn);
    expect(slotOf(DateTime(2026, 1, 1, 13)), TimeSlot.noon);
    expect(slotOf(DateTime(2026, 1, 1, 23)), TimeSlot.night);
    expect(
      pickLine(_in(now: DateTime(2026, 10, 14, 23)))!.mood,
      CompanionMood.night,
    );
  });

  test('day one introduces Noor instead of rotating', () {
    expect(pickLine(_in(firstDay: true))!.kind, CompanionKind.firstDay);
  });

  group('Noor notices', () {
    test(
      'a child of six or seven, by birth month, is invited to the Journey',
      () {
        final line = pickLine(
          _in(
            notices: const ChildNotices(
              prayerEligible: true,
              ageYears: 6,
              ageFromBirthMonth: true,
            ),
          ),
        )!;
        expect(line.kind, CompanionKind.prayerInvite);
        expect(line.actions, [CompanionAction.openPrayerJourney]);
        expect(line.onceOnly, isTrue);
      },
    );

    test('no invite from an age-band guess, once enrolled, or at nine', () {
      for (final n in const [
        ChildNotices(prayerEligible: true, ageYears: 6),
        ChildNotices(
          prayerEligible: true,
          prayerEnrolled: true,
          ageYears: 7,
          ageFromBirthMonth: true,
        ),
        ChildNotices(
          prayerEligible: true,
          ageYears: 9,
          ageFromBirthMonth: true,
        ),
      ]) {
        expect(
          pickLine(_in(notices: n))!.kind,
          isNot(CompanionKind.prayerInvite),
        );
      }
    });

    test('a stage ready outranks the rest of the notices', () {
      final line = pickLine(
        _in(
          notices: const ChildNotices(
            prayerEligible: true,
            prayerEnrolled: true,
            prayerAdvance: true,
            milestonesDue: 2,
            needsBirthMonth: true,
          ),
        ),
      )!;
      expect(line.kind, CompanionKind.prayerAdvance);
    });

    test('a milestone due, then a missing birth month', () {
      expect(
        pickLine(_in(notices: const ChildNotices(milestonesDue: 1)))!.kind,
        CompanionKind.milestoneDue,
      );
      final ask = pickLine(
        _in(notices: const ChildNotices(needsBirthMonth: true)),
      )!;
      expect(ask.kind, CompanionKind.birthMonthAsk);
      expect(ask.actions, [CompanionAction.editChild]);
    });

    test('a notice speaks once a month, then falls through', () {
      const n = ChildNotices(needsBirthMonth: true);
      final ask = pickLine(_in(notices: n))!;
      final seen = CompanionMemory(seenKeys: {ask.key});
      expect(
        pickLine(_in(notices: n, memory: seen))!.kind,
        CompanionKind.greeting,
      );
      // next month it may ask again
      expect(
        pickLine(
          _in(now: DateTime(2026, 11, 14, 9), notices: n, memory: seen),
        )!.kind,
        CompanionKind.birthMonthAsk,
      );
    });

    test('promises and waiting missions still come first', () {
      final line = pickLine(
        _in(missions: 1, notices: const ChildNotices(milestonesDue: 1)),
      )!;
      expect(line.kind, CompanionKind.missionsWaiting);
    });
  });

  group('«هلّ هلال رمضان» (phase 5)', () {
    // 1 Ramadan 1448 ≈ 8 February 2027, a Monday.
    final day1 = DateTime(2027, 2, 8, 20);
    CompanionInputs hilal({
      int? day = 1,
      int year = 1448,
      DateTime? now,
      CompanionMemory memory = const CompanionMemory(),
      int missions = 0,
      ChildNotices notices = const ChildNotices(),
      bool plan = false,
      int weekActs = 0,
      List<DueFollowup> followups = const [],
    }) => _in(
      now: now ?? day1,
      ramadanDay: day,
      ramadanYear: year,
      memory: memory,
      missions: missions,
      notices: notices,
      plan: plan,
      weekActs: weekActs,
      followups: followups,
    );

    test('the first night of the month: once-only, happy, one chip', () {
      final line = pickLine(hilal())!;
      expect(line.kind, CompanionKind.ramadanStart);
      expect(line.key, 'ramadan-start:1448');
      expect(line.onceOnly, isTrue);
      expect(line.isQuestion, isFalse);
      expect(line.mood, CompanionMood.happy);
      expect(line.actions, [CompanionAction.openRamadan]);
      expect(line.name, 'سارة');
    });

    test('the month\'s first nights only — not before it, not on day four', () {
      for (var d = 1; d <= kRamadanStartDays; d++) {
        expect(
          pickLine(hilal(day: d))!.kind,
          CompanionKind.ramadanStart,
          reason: 'day $d',
        );
      }
      for (final d in [kRamadanStartDays + 1, 15, 27, 30]) {
        expect(
          pickLine(hilal(day: d))!.kind,
          isNot(CompanionKind.ramadanStart),
          reason: 'day $d',
        );
      }
      // Outside the month the brain is given no day at all.
      expect(
        pickLine(hilal(day: null))!.kind,
        isNot(CompanionKind.ramadanStart),
      );
    });

    test('once a Hijri year: seen on day one, silent on days two and three; '
        'back next Ramadan', () {
      final line = pickLine(hilal())!;
      final seen = CompanionMemory(seenKeys: {line.key});
      for (var d = 1; d <= kRamadanStartDays; d++) {
        expect(
          pickLine(hilal(day: d, memory: seen))!.kind,
          CompanionKind.greeting,
          reason: 'day $d',
        );
      }
      final next = pickLine(
        hilal(year: 1449, now: DateTime(2028, 1, 28, 20), memory: seen),
      )!;
      expect(next.kind, CompanionKind.ramadanStart);
      expect(next.key, 'ramadan-start:1449');
    });

    test('a line held for this open stays put after it is seen', () {
      final line = pickLine(hilal())!;
      final seen = CompanionMemory(seenKeys: {line.key});
      expect(
        pickLine(hilal(memory: seen.withoutSeen({line.key})))!.kind,
        CompanionKind.ramadanStart,
      );
    });

    test('the anti-nag rules hold: hidden for today, quiet mode', () {
      final hidden = CompanionMemory(
        hiddenByDay: {
          '2027-02-08': {'ramadan-start:1448'},
        },
      );
      expect(pickLine(hilal(memory: hidden))!.kind, CompanionKind.greeting);
      expect(
        pickLine(hilal(memory: const CompanionMemory(quietMode: true)))!.kind,
        CompanionKind.greeting,
      );
    });

    test('the order around it is unchanged', () {
      // 1–3: a waiting mission, a due promise, a due follow-up still first.
      expect(pickLine(hilal(missions: 1))!.kind, CompanionKind.missionsWaiting);
      final promise = CompanionMemory(
        promises: [_promise(made: DateTime(2027, 2, 7))],
      );
      expect(pickLine(hilal(memory: promise))!.kind, CompanionKind.promiseDue);
      expect(
        pickLine(
          hilal(followups: const [DueFollowup(id: 3, childId: 7, step: 'x')]),
        )!.kind,
        CompanionKind.followupDue,
      );
      // 4: a notice about the child speaks first — and the crescent waits
      // for the next night instead of being lost for the year.
      const milestone = ChildNotices(milestonesDue: 1);
      final notice = pickLine(hilal(notices: milestone))!;
      expect(notice.kind, CompanionKind.milestoneDue);
      expect(
        pickLine(
          hilal(
            day: 2,
            now: DateTime(2027, 2, 9, 20),
            notices: milestone,
            memory: CompanionMemory(seenKeys: {notice.key}),
          ),
        )!.kind,
        CompanionKind.ramadanStart,
      );
      // 5–6: Monday's plan and Friday's harvest come after it.
      expect(pickLine(hilal(plan: true))!.kind, CompanionKind.ramadanStart);
      expect(
        pickLine(
          hilal(day: 5, now: DateTime(2027, 2, 12, 20), weekActs: 3),
        )!.kind,
        CompanionKind.fridayHarvest,
      );
      expect(
        pickLine(
          hilal(day: 3, now: DateTime(2027, 2, 12, 20), weekActs: 3),
        )!.kind,
        CompanionKind.ramadanStart,
      );
    });

    test('the countdown before the month is untouched by it', () {
      expect(
        pickLine(_in(ramadan: 1, ramadanYear: 1448))!.kind,
        CompanionKind.ramadanCountdown,
      );
    });
  });

  group('«دخل شهر …» (سماوات المواسم)', () {
    CompanionInputs season(
      String? month,
      int? day, {
      int year = 1448,
      CompanionMemory memory = const CompanionMemory(),
      int? ramadan,
    }) => CompanionInputs(
      now: _wed,
      memory: memory,
      childId: 7,
      childName: 'سارة',
      ramadanDaysUntil: ramadan,
      seasonMonth: month,
      seasonDay: day,
      seasonYear: year,
    );

    test('days two to four of each season, once a Hijri year, one chip', () {
      for (final m in kSeasonMonths) {
        final line = pickLine(season(m, 2))!;
        expect(line.kind, CompanionKind.seasonStart, reason: m);
        expect(line.season, m);
        expect(line.key, 'season:$m:1448');
        expect(line.onceOnly, isTrue);
        expect(line.isQuestion, isFalse);
        expect(line.actions, [CompanionAction.openFamilyRoad]);
        for (final d in [1, 5, 13, null]) {
          expect(
            pickLine(season(m, d))!.kind,
            CompanionKind.greeting,
            reason: '$m day $d',
          );
        }
        final seen = CompanionMemory(seenKeys: {line.key});
        expect(pickLine(season(m, 3, memory: seen))!.kind,
            CompanionKind.greeting);
        expect(
          pickLine(season(m, 3, memory: seen, year: 1449))!.kind,
          CompanionKind.seasonStart,
        );
      }
    });

    test('an unknown month, quiet mode and a hidden line say nothing', () {
      expect(pickLine(season('muharram', 2))!.kind, CompanionKind.greeting);
      expect(
        pickLine(
          season('rajab', 2, memory: const CompanionMemory(quietMode: true)),
        )!.kind,
        CompanionKind.greeting,
      );
    });

    test('the Ramadan countdown keeps its place', () {
      expect(
        pickLine(season('shaban', 2, ramadan: 30))!.kind,
        CompanionKind.ramadanCountdown,
      );
    });
  });
}
