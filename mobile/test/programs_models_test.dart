// The programs payloads parse as MOBILE_API §11 documents them — and degrade
// to "not shown" rather than crash when a field is missing, because the
// contract is additive and the server ships on its own schedule.

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/programs/data/programs_models.dart';
import 'package:almorabbi/features/programs/widgets/birth_month_field.dart';
import 'package:almorabbi/features/programs/widgets/ramadan_recap_card.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

import 'programs_support.dart';

void main() {
  group('GET /api/programs', () {
    test('reads the calendar and each child', () {
      final o = ProgramsOverview.fromJson(programsJson(enrolled: true, stage: 2, pending: 3));
      expect(o.ramadan.state, RamadanState.ramadan);
      expect(o.ramadan.day, 3);
      expect(o.ramadan.season!.hijriYear, 1448);
      expect(o.ramadan.season!.isEstimate, isTrue);
      expect(o.ramadan.isActive, isTrue);
      final child = o.forChild(kChildId)!;
      expect(child.prayer.eligibleTrack, PrayerTrack.journey);
      expect(child.prayer.stage, 2);
      expect(child.prayer.pendingConfirmations, 3);
      expect(child.milestonesDue, 1);
      expect(o.forChild(999), isNull);
    });

    test('no season → not active; null eligible track → hide the journey', () {
      final o = ProgramsOverview.fromJson(programsJson(state: 'off_season', withSeason: false, eligibleTrack: null));
      expect(o.ramadan.isActive, isFalse);
      expect(o.children.single.prayer.eligibleTrack, isNull);
    });

    test('an unknown state is treated as off season, unknown fields are ignored', () {
      final o = ProgramsOverview.fromJson({
        'ramadan': {'state': 'something_new', 'season': seasonJson(), 'surprise': true},
        'children': [
          {'child_id': 1, 'new_program': {}},
          {'no_id': true},
        ],
      });
      expect(o.ramadan.state, RamadanState.offSeason);
      expect(o.children, hasLength(1));
      expect(o.children.single.prayer.eligibleTrack, isNull);
    });
  });

  group('Ramadan', () {
    test("today's card", () {
      final t = RamadanToday.fromJson(ramadanTodayJson());
      expect(t.content!.day, 3);
      expect(t.content!.familyChallenge!.steps, hasLength(2));
      expect(t.content!.variant!.forChild, isTrue);
      expect(t.content!.quran.together!.surah, 114);
      expect(t.content!.quran.parentJuz, 3);
      expect(t.content!.parentNote!.evidence.single.source, contains('البخاري'));
      expect(t.marks!.isDone('challenge_done'), isFalse);
      expect(t.fasting!.currentStep!.key, 'morning_hours');
    });

    test('marks are ticks only; the family word is read when present', () {
      final m = RamadanMarks.fromJson({
        'challenge_done': true,
        'wird_done': false,
        'family_word': {'choice_index': 3, 'word': 'Joy'},
      })!;
      expect(m.isDone('challenge_done'), isTrue);
      expect(m.isDone('wird_done'), isFalse);
      expect(m.isDone('juz_read'), isFalse); // absent = not ticked, never "missed"
      expect(m.familyWord, 'Joy');
      expect(m.familyWordIndex, 3);
    });

    test('prenatal-1: no fasting block at all', () {
      expect(RamadanToday.fromJson(ramadanTodayJson(noFasting: true)).fasting, isNull);
    });

    test('a Quran reference out of range is dropped, not rendered', () {
      expect(QuranRef.fromJson({'surah': 115, 'from': 1, 'to': 2}), isNull);
      expect(QuranRef.fromJson({'surah': 2, 'from': 0}), isNull);
      expect(QuranRef.fromJson({'surah': 2, 'from': 5, 'to': 3})!.to, 5);
    });

    test('the ladder keeps the safety guidance and per-step eligibility', () {
      final l = FastingLadder.fromJson(ladderJson(current: 'morning_hours'));
      expect(l.guidance!.urgentSigns, isNotEmpty);
      expect(l.guidance!.urgentAction, isNotNull);
      expect(l.steps.where((s) => !s.eligible).single.key, 'until_asr');
      expect(l.canPractise, isTrue);
      expect(FastingLadder.fromJson(ladderJson(state: 'upcoming')).canPractise, isFalse);
    });

    test('the recap card carries only the card; family_only stays apart', () {
      final r = RamadanRecap.fromJson(recapJson());
      expect(r.card!.lines, ['Family challenges: 12', 'Our Ramadan word: Joy']);
      expect(r.familyOnly.single.key, 'fasting_steps');
      expect(RamadanRecap.fromJson(recapJson(available: false)).card, isNull);
    });

    test("the share text is the server's, and never mentions the fasting", () {
      final card = RamadanRecap.fromJson(recapJson()).card!;
      expect(recapShareMessage(card), card.shareText);
      expect(recapShareMessage(card), contains('referrer=ref_X'));
      final noText = RecapCard(headline: 'H', lines: const ['A: 1'], closing: 'C');
      expect(recapShareMessage(noText), 'H\nA: 1\nC');
      expect(recapShareMessage(card).toLowerCase(), isNot(contains('fasting')));
    });
  });

  group('Prayer Journey', () {
    test('enrolled on the journey', () {
      final j = PrayerJourney.fromJson(journeyJson(pending: 2, advance: true));
      expect(j.enrolled, isTrue);
      expect(j.enrolment!.track, PrayerTrack.journey);
      expect(j.stage!.parentAssignments.single, contains('Pray one prayer'));
      expect(j.tasks.single.coins, 10);
      expect(j.tasks.single.thisWeek.recorded, 2);
      expect(j.advancement!.advanceSuggested, isTrue);
      expect(j.advancement!.nextStage, 2);
      expect(j.coinsConfirmedInStage, 40);
      expect(j.stages, hasLength(6));
    });

    test('not enrolled: no stage, no tasks', () {
      final j = PrayerJourney.fromJson(journeyJson(enrolled: false));
      expect(j.enrolled, isFalse);
      expect(j.tasks, isEmpty);
      expect(j.stage, isNull);
      expect(j.eligible, isTrue);
    });

    test('child mode: a task with no slot left is done, not refused', () {
      final t = ChildPrayerToday.fromJson(childPrayerJson(slotsLeft: 0));
      expect(t.hasTasks, isTrue);
      expect(t.tasks.single.doneForToday, isTrue);
      expect(ChildPrayerToday.fromJson(childPrayerJson(enrolled: false)).hasTasks, isFalse);
    });
  });

  group('Milestones', () {
    test('sections, red flags, links', () {
      final m = MilestonesList.fromJson(milestonesJson(needs: ['birth_month']));
      expect(m.needsBirthMonth, isTrue);
      expect(m.due.single.medical, isTrue);
      expect(m.due.single.redFlags, isNotEmpty);
      expect(m.due.single.cards, hasLength(3));
      expect(m.due.single.links.programIds, ['prayer_journey']);
      expect(m.upcoming.single.state, 'upcoming');
    });
  });

  group('the copy', () {
    final ar = lookupAppLocalizations(const Locale('ar'));
    final en = lookupAppLocalizations(const Locale('en'));

    test('Arabic counts agree with their number', () {
      expect(ar.ramadanCountdown(0), 'يبدأ رمضان اليوم');
      expect(ar.ramadanCountdown(1), 'بقي يوم واحد على رمضان');
      expect(ar.ramadanCountdown(2), 'بقي يومان على رمضان');
      expect(ar.ramadanCountdown(5), 'بقي 5 أيام على رمضان');
      expect(ar.ramadanCountdown(12), 'بقي 12 يومًا على رمضان');
      expect(ar.programsCoins(2), 'عملتان');
      expect(ar.programsCoins(10), '10 عملات');
      expect(ar.programsPrayerPending(1), 'مهمة واحدة تنتظر تثبيتك');
      expect(ar.fastingHours(0), 'بلا إمساك');
      expect(ar.fastingHours(3), 'نحو 3 ساعات');
    });

    test('English counts too', () {
      expect(en.ramadanCountdown(1), '1 day until Ramadan');
      expect(en.ramadanCountdown(12), '12 days until Ramadan');
      expect(en.programsCoins(1), '1 coin');
      expect(en.missionCoinsEarned(10), '10 coins added');
      expect(en.programsMilestonesDueFor(2, 'Omar'), "2 stages in Omar's life are due now");
    });
  });

  group('birth month', () {
    test('the child profile reads it, and knows whether the server does', () {
      final withField = ChildProfile.fromJson({
        'id': 1, 'name': 'أحمد', 'age_group': '7-9', 'birth_month': null,
      });
      final oldServer = ChildProfile.fromJson({'id': 1, 'name': 'أحمد', 'age_group': '7-9'});
      expect(withField.serverKnowsBirthMonth, isTrue);
      expect(withField.birthMonth, isNull);
      expect(oldServer.serverKnowsBirthMonth, isFalse);
      expect(ChildProfile.fromJson({'id': 1, 'name': 'x', 'age_group': '7-9', 'birth_month': '2019-03'}).birthMonth,
          '2019-03');
    });

    test('the band follows the same rule as the server', () {
      final today = DateTime(2026, 10, 4);
      expect(bandForBirthMonth('2026-05', today), 'prenatal-1'); // 5 months
      expect(bandForBirthMonth('2027-03', today), 'prenatal-1'); // expected baby
      expect(bandForBirthMonth('2024-10', today), '2-3'); // exactly 2
      expect(bandForBirthMonth('2022-11', today), '2-3'); // 3y11m
      expect(bandForBirthMonth('2022-10', today), '4-6'); // 4
      expect(bandForBirthMonth('2019-10', today), '7-9'); // 7
      expect(bandForBirthMonth('2019-11', today), '4-6'); // 6y11m
      expect(bandForBirthMonth('2016-10', today), '10-12');
      expect(bandForBirthMonth('2013-10', today), '13-15');
      expect(bandForBirthMonth('2010-10', today), '16-18');
      expect(bandForBirthMonth(null, today), isNull);
      expect(bandForBirthMonth('2019-13', today), isNull);
    });

    test('the picker range matches what the server accepts', () {
      final (earliest, latest) = birthMonthRange(DateTime(2026, 10, 4));
      expect(earliest, DateTime(2007, 10));
      expect(latest, DateTime(2027, 8));
      expect(parseBirthMonth('2019-03'), (2019, 3));
      expect(formatBirthMonth(2019, 3), '2019-03');
    });
  });
}
