// «نور يتذكّر» — the device memory and the promise reminder rule.
import 'package:almorabbi/features/adhkar/services/notification_service.dart';
import 'package:almorabbi/features/companion/data/companion_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<CompanionStore> _store() async {
  SharedPreferences.setMockInitialValues({});
  return CompanionStore(await SharedPreferences.getInstance());
}

void main() {
  test('a promise survives a re-read and is due on the slot’s day', () async {
    final s = await _store();
    final made = DateTime(2026, 10, 14, 21);
    final p = await s.addPromise(
      childId: 7,
      step: 'امدح صدقه',
      slot: PromiseSlot.tomorrow,
      lessonId: 'l1',
      now: made,
    );
    final back = s.read(now: made).promises.single;
    expect(back.step, 'امدح صدقه');
    expect(back.dueOn, DateTime(2026, 10, 16));
    expect(back.isDue(DateTime(2026, 10, 15, 23)), isFalse);
    expect(back.isDue(DateTime(2026, 10, 16, 6)), isTrue);
    await s.answer(p.id, 'worked');
    expect(
      s.read(now: made).promises.single.isDue(DateTime(2026, 10, 20)),
      isFalse,
    );
  });

  test('a new slot for the same lesson replaces the open promise', () async {
    final s = await _store();
    final now = DateTime(2026, 10, 14, 9);
    await s.addPromise(
      childId: 7,
      step: 'x',
      slot: PromiseSlot.tonight,
      lessonId: 'l1',
      now: now,
    );
    await s.addPromise(
      childId: 7,
      step: 'x',
      slot: PromiseSlot.week,
      lessonId: 'l1',
      now: now.add(const Duration(seconds: 1)),
    );
    final all = s.read(now: now).promises;
    expect(all, hasLength(1));
    expect(all.single.slot, PromiseSlot.week);
  });

  test('a follow-up answered in the sheet closes its promise', () async {
    final s = await _store();
    final now = DateTime(2026, 10, 14, 9);
    final p = await s.addPromise(
      childId: 7,
      step: 'x',
      slot: PromiseSlot.tonight,
      lessonId: 'l1',
      now: now,
    );
    await s.linkFollowup(p.id, 55);
    await s.answerByFollowup(55, 'partly');
    expect(s.read(now: now).promises.single.outcome, 'partly');
  });

  test('promises older than three weeks fall away', () async {
    final s = await _store();
    await s.addPromise(
      childId: 7,
      step: 'x',
      slot: PromiseSlot.tonight,
      now: DateTime(2026, 9, 1),
    );
    expect(s.read(now: DateTime(2026, 10, 14)).promises, isEmpty);
  });

  test('questions and hidden lines are counted per day', () async {
    final s = await _store();
    final d1 = DateTime(2026, 10, 14, 9);
    await s.markQuestionShown('promise:1', now: d1);
    await s.hideForToday('missions:x', now: d1);
    expect(s.read(now: d1).questionsOn(d1), {'promise:1'});
    expect(s.read(now: d1).hiddenOn(d1), {'missions:x'});
    final d2 = DateTime(2026, 10, 15, 9);
    expect(s.read(now: d2).questionsOn(d2), isEmpty);
    expect(s.read(now: d2).hiddenOn(d2), isEmpty);
  });

  test('quiet mode and seen moments persist', () async {
    final s = await _store();
    await s.setQuietMode(true);
    await s.markSeen('ramadan:1448:7');
    final m = s.read();
    expect(m.quietMode, isTrue);
    expect(m.seenKeys, contains('ramadan:1448:7'));
  });

  test('«درب اليوم» stops are marked once and only for their day', () async {
    final s = await _store();
    final d1 = DateTime(2026, 10, 14, 9);
    await s.markStop('step:7', now: d1);
    await s.markStop('step:7', now: d1);
    await s.markStop('ask', now: d1);
    expect(s.read(now: d1).stopsOn(d1), {'step:7', 'ask'});
    final d2 = DateTime(2026, 10, 15, 9);
    expect(s.read(now: d2).stopsOn(d2), isEmpty);
  });

  test('a corrupt store reads as empty, never throws', () async {
    SharedPreferences.setMockInitialValues({
      'noor.promises.v1': '{not json',
      'noor.questions.v1': '[1,2]',
    });
    final s = CompanionStore(await SharedPreferences.getInstance());
    expect(s.read().promises, isEmpty);
  });

  group('promise reminder time', () {
    test('«الليلة» reminds at 20:30 if the evening is still ahead', () {
      expect(
        NotificationService.promiseReminderAt(
          DateTime(2026, 10, 14, 17),
          'tonight',
        ),
        DateTime(2026, 10, 14, 20, 30),
      );
      expect(
        NotificationService.promiseReminderAt(
          DateTime(2026, 10, 14, 20, 20),
          'tonight',
        ),
        isNull,
      );
    });
    test('«غدًا» reminds tomorrow evening; «هذا الأسبوع» never', () {
      expect(
        NotificationService.promiseReminderAt(
          DateTime(2026, 10, 14, 22),
          'tomorrow',
        ),
        DateTime(2026, 10, 15, 18, 30),
      );
      expect(
        NotificationService.promiseReminderAt(
          DateTime(2026, 10, 14, 9),
          'week',
        ),
        isNull,
      );
    });
  });
}
