// «نور يتذكّر» — the priority rule and the anti-nag rules, pinned.
import 'package:almorabbi/features/companion/data/companion_store.dart';
import 'package:almorabbi/features/companion/logic/companion_brain.dart';
import 'package:flutter_test/flutter_test.dart';

final _wed = DateTime(2026, 10, 14, 9); // a Wednesday morning
final _mon = DateTime(2026, 10, 19, 9); // a Monday

Promise _promise({int id = 1, int child = 7, PromiseSlot slot = PromiseSlot.tonight,
        DateTime? made, int? followupId, String? outcome}) =>
    Promise(
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
  bool plan = false,
  bool firstDay = false,
  ChildNotices notices = const ChildNotices(),
}) =>
    CompanionInputs(
      now: now ?? _wed,
      memory: memory,
      childId: childId,
      childName: 'سارة',
      missionsWaiting: missions,
      dueFollowups: followups,
      ramadanDaysUntil: ramadan,
      ramadanYear: 2027,
      hasWeeklyPlan: plan,
      firstDay: firstDay,
      notices: notices,
    );

void main() {
  test('no active child → no line (the plain greeting row stays)', () {
    expect(pickLine(_in(childId: null)), isNull);
  });

  test('a waiting mission comes first', () {
    final line = pickLine(_in(
      missions: 2,
      memory: CompanionMemory(promises: [_promise()]),
      followups: const [DueFollowup(id: 3, childId: 7, step: 'x')],
    ))!;
    expect(line.kind, CompanionKind.missionsWaiting);
    expect(line.count, 2);
    expect(line.actions, [CompanionAction.confirmMissions]);
  });

  test('a promise made last night is asked this morning, not before', () {
    final made = DateTime(2026, 10, 13); // «الليلة» on Tuesday
    final memory = CompanionMemory(promises: [_promise(made: made)]);
    expect(pickLine(_in(now: DateTime(2026, 10, 13, 22), memory: memory))!.kind,
        isNot(CompanionKind.promiseDue));
    final line = pickLine(_in(memory: memory))!;
    expect(line.kind, CompanionKind.promiseDue);
    expect(line.step, 'امدح صدقه أولًا');
    expect(line.actions, hasLength(3));
  });

  test('«هذا الأسبوع» waits seven days', () {
    final memory = CompanionMemory(
        promises: [_promise(slot: PromiseSlot.week, made: DateTime(2026, 10, 10))]);
    expect(pickLine(_in(memory: memory))!.kind, isNot(CompanionKind.promiseDue));
    expect(pickLine(_in(now: DateTime(2026, 10, 17, 9), memory: memory))!.kind,
        CompanionKind.promiseDue);
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
    final line = pickLine(_in(
        followups: const [DueFollowup(id: 3, childId: 7, step: 'ركن الهدوء')]))!;
    expect(line.kind, CompanionKind.followupDue);
    expect(line.followup!.id, 3);
  });

  test('a follow-up that a promise carries is asked once, as the promise', () {
    final memory = CompanionMemory(promises: [_promise(followupId: 3)]);
    final line = pickLine(_in(
        memory: memory,
        followups: const [DueFollowup(id: 3, childId: 7, step: 'x', source: 'lesson')]))!;
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
    final line = pickLine(_in(
      missions: 1,
      memory: CompanionMemory(promises: [_promise()], quietMode: true),
    ))!;
    expect(line.kind, CompanionKind.greeting);
    expect(line.actions, isEmpty);
  });

  test('Ramadan countdown speaks on 30/14/7/1 only, once each', () {
    expect(pickLine(_in(ramadan: 8))!.kind, CompanionKind.greeting);
    final line = pickLine(_in(ramadan: 7))!;
    expect(line.kind, CompanionKind.ramadanCountdown);
    expect(line.onceOnly, isTrue);
    final seen = CompanionMemory(seenKeys: {line.key});
    expect(pickLine(_in(ramadan: 7, memory: seen))!.kind, CompanionKind.greeting);
  });

  test('Monday reveals the plan once', () {
    final line = pickLine(_in(now: _mon, plan: true))!;
    expect(line.kind, CompanionKind.mondayPlan);
    expect(pickLine(_in(now: _wed, plan: true))!.kind, CompanionKind.greeting);
    expect(
        pickLine(_in(now: _mon, plan: true, memory: CompanionMemory(seenKeys: {line.key})))!
            .kind,
        CompanionKind.greeting);
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
    expect(pickLine(_in(now: DateTime(2026, 10, 14, 23)))!.mood, CompanionMood.night);
  });

  test('day one introduces Noor instead of rotating', () {
    expect(pickLine(_in(firstDay: true))!.kind, CompanionKind.firstDay);
  });

  group('Noor notices', () {
    test('a child of six or seven, by birth month, is invited to the Journey',
        () {
      final line = pickLine(_in(
          notices: const ChildNotices(
              prayerEligible: true, ageYears: 6, ageFromBirthMonth: true)))!;
      expect(line.kind, CompanionKind.prayerInvite);
      expect(line.actions, [CompanionAction.openPrayerJourney]);
      expect(line.onceOnly, isTrue);
    });

    test('no invite from an age-band guess, once enrolled, or at nine', () {
      for (final n in const [
        ChildNotices(prayerEligible: true, ageYears: 6),
        ChildNotices(
            prayerEligible: true, prayerEnrolled: true, ageYears: 7,
            ageFromBirthMonth: true),
        ChildNotices(prayerEligible: true, ageYears: 9, ageFromBirthMonth: true),
      ]) {
        expect(pickLine(_in(notices: n))!.kind, isNot(CompanionKind.prayerInvite));
      }
    });

    test('a stage ready outranks the rest of the notices', () {
      final line = pickLine(_in(
          notices: const ChildNotices(
              prayerEligible: true,
              prayerEnrolled: true,
              prayerAdvance: true,
              milestonesDue: 2,
              needsBirthMonth: true)))!;
      expect(line.kind, CompanionKind.prayerAdvance);
    });

    test('a milestone due, then a missing birth month', () {
      expect(
          pickLine(_in(notices: const ChildNotices(milestonesDue: 1)))!.kind,
          CompanionKind.milestoneDue);
      final ask = pickLine(_in(notices: const ChildNotices(needsBirthMonth: true)))!;
      expect(ask.kind, CompanionKind.birthMonthAsk);
      expect(ask.actions, [CompanionAction.editChild]);
    });

    test('a notice speaks once a month, then falls through', () {
      const n = ChildNotices(needsBirthMonth: true);
      final ask = pickLine(_in(notices: n))!;
      final seen = CompanionMemory(seenKeys: {ask.key});
      expect(pickLine(_in(notices: n, memory: seen))!.kind,
          CompanionKind.greeting);
      // next month it may ask again
      expect(
          pickLine(_in(now: DateTime(2026, 11, 14, 9), notices: n, memory: seen))!
              .kind,
          CompanionKind.birthMonthAsk);
    });

    test('promises and waiting missions still come first', () {
      final line = pickLine(_in(
          missions: 1,
          notices: const ChildNotices(milestonesDue: 1)))!;
      expect(line.kind, CompanionKind.missionsWaiting);
    });
  });
}
