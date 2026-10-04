// Fixtures and a fake client for the family-programs tests.
//
// The payloads mirror the samples in MOBILE_API.md §11 (backend schema v34),
// trimmed to what the screens read. Not a test file itself (no `_test`
// suffix): the programs_*_test.dart files import it.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/data/story_models.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/programs/widgets/ramadan_widgets.dart';
import 'package:almorabbi/features/quran/providers/quran_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/theme/app_theme.dart';

const kChildId = 12;
const kChildName = 'سارة';

Map<String, dynamic> seasonJson({int days = 30, int shift = 0, String source = 'estimate'}) => {
      'hijri_year': 1448,
      'starts_on': '2027-02-08',
      'days': days,
      'eid_on': days == 30 ? '2027-03-10' : '2027-03-09',
      'bridge_ends_on': '2027-04-07',
      'start_source': source,
      'days_confirmed': false,
      'shift_days': shift,
    };

Map<String, dynamic> ageJson({String band = '7-9'}) =>
    {'basis': 'birth_month', 'band': band, 'months': 95, 'years': 7};

Map<String, dynamic> programsJson({
  String state = 'ramadan',
  int? day = 3,
  int? daysUntil,
  bool recap = false,
  String? eligibleTrack = 'journey',
  bool enrolled = false,
  int? stage,
  int pending = 0,
  int due = 1,
  List<String> needsProfile = const [],
  bool withSeason = true,
}) =>
    {
      'date': '2027-02-10',
      'tz_offset_minutes': 180,
      'server_features': <String>[],
      'ramadan': {
        'state': state,
        'season': withSeason ? seasonJson() : null,
        'day': day,
        'days_until_start': daysUntil,
        'after_week': state == 'after' ? 2 : null,
        'recap_available': recap,
      },
      'children': [
        {
          'child_id': kChildId,
          'age': ageJson(),
          'ramadan': {'variant_band': '7-9'},
          'prayer_journey': {
            'eligible_track': eligibleTrack,
            'enrolled': enrolled,
            'track': enrolled ? 'journey' : null,
            'stage': stage,
            'advance_suggested': false,
            'can_graduate': false,
            'pending_confirmations': pending,
          },
          'milestones': {'due': due, 'needs_profile': needsProfile},
        },
      ],
    };

const hadith = {
  'id': 'h_bismillah',
  'kind': 'hadith',
  'text_ar': 'يا غلام سم الله وكل بيمينك وكل مما يليك',
  'source': 'صحيح البخاري — حديث ٥٣٧٦',
  'provenance': {'book': 'البخاري', 'number': 5376},
  'context': 'On table manners',
  'meaning': 'Boy, say Bismillah, eat with your right hand…',
};

Map<String, dynamic> dayContentJson({int day = 3, List<String>? tracks, bool word = false, bool oddNight = false}) => {
      'day': day,
      'phase': 'first_ten',
      'key': 'iftar_table',
      'title': 'The iftar table',
      'family_challenge': {
        'title': 'Set the table together and begin with Bismillah',
        'steps': ['Hand out small jobs before the adhan.', 'Sit together a few minutes before.'],
        'minutes': 10,
        'cost': 'free',
        'at_home': true,
        'when': 'at_iftar',
        'materials': <String>[],
      },
      'parent_note': {
        'text': 'In the attached hadith the Prophet taught a boy table manners.',
        'evidence': [hadith],
      },
      'variant': {'band': '7-9', 'addressed_to': 'child', 'text': 'Your job: water and cups on the table.'},
      'quran': {
        'together': {'surah': 114, 'from': 1, 'to': 6},
        'theme_ref': null,
        'parent_juz': 3,
      },
      'story_id': 'abdullah_bismillah',
      'last_ten': false,
      'odd_night': oddNight,
      'may_not_occur': false,
      'tracks': tracks ?? ['challenge_done', 'wird_done', 'story_heard', 'juz_read'],
      'family_word_choices': word ? ['Mercy', 'Patience', 'Joy'] : null,
    };

Map<String, dynamic> fastingSummaryJson({String? step = 'morning_hours', bool practised = false, int week = 0, bool rest = false}) => {
      'ladder_band': '7-9',
      'fasts': 'partial',
      'reached_puberty': false,
      'current_step': step == null
          ? null
          : {'key': step, 'label': 'Morning hours', 'until': 'mid_morning', 'approx_hours': 3, 'max_days_per_week': 3},
      'practised_today': practised,
      'practised_this_week': week,
      'rest_suggested': rest,
    };

Map<String, dynamic> ramadanTodayJson({
  String state = 'ramadan',
  int? day = 3,
  Map<String, dynamic>? marks,
  Map<String, dynamic>? content,
  bool recap = false,
  Map<String, dynamic>? fasting,
  bool noFasting = false,
}) =>
    {
      'program': 'ramadan_family',
      'child_id': kChildId,
      'date': '2027-02-10',
      'state': state,
      'season': state == 'off_season' ? null : seasonJson(),
      'title': 'Family Ramadan',
      'subtitle': 'Thirty days of worship and joy, together',
      'age': ageJson(),
      'variant_band': '7-9',
      'bands_text': 'The program is for the whole family.',
      'days_until_start': state == 'upcoming' ? 12 : null,
      'day': state == 'ramadan' ? day : null,
      'after_week': state == 'after' ? 4 : null,
      'kickoff': state == 'upcoming'
          ? {
              'title': 'Before Ramadan begins',
              'text': 'Thirty days, a family challenge each day.',
              'setup_steps': ['Pick a fixed time for the challenge.', "Set each child's fasting step."],
            }
          : null,
      'content': state == 'ramadan' ? (content ?? dayContentJson(day: day ?? 3)) : null,
      'eid': state == 'eid'
          ? {
              'title': 'Eid day',
              'activities': ['Wear your best clothes.', 'Say the takbir together.'],
              'parent_note': {'text': 'Eid is joy after fasting.', 'evidence': <Object>[]},
              'variant': null,
              'quran': {},
              'evidence': <Object>[],
            }
          : null,
      'after': state == 'after'
          ? {
              'title': 'After Ramadan: keep going together',
              'text': 'Keep the two habits.',
              'keep_habits': [
                {'key': 'charity_box', 'title': 'The charity box', 'text': 'It stays in its place.'},
              ],
              'week': {
                'week': 4,
                'title': 'Week 4: Beyond the bridge',
                'text': 'Keep the two habits, and choose a path for each child.',
                'requires_feature': 'weekly_plan',
                'feature_available': false,
              },
              'weeks': <Object>[],
              'links': {'program_ids': ['prayer_journey'], 'path_ids': <String>[], 'lesson_ids': <String>[]},
              'evidence': <Object>[],
            }
          : null,
      'marks': state == 'ramadan'
          ? (marks ?? {'challenge_done': false, 'wird_done': false, 'story_heard': false, 'juz_read': false})
          : null,
      'fasting': noFasting ? null : (fasting ?? fastingSummaryJson()),
      'recap_available': recap,
    };

Map<String, dynamic> ladderJson({String? current, bool puberty = false, String state = 'ramadan'}) => {
      'child_id': kChildId,
      'date': '2027-02-10',
      'state': state,
      'season': seasonJson(),
      'day': 3,
      'age': ageJson(),
      'ladder_band': '7-9',
      'fasts': 'partial',
      'summary': 'Hours, not full days.',
      'reached_puberty': puberty,
      'current_step': current == null ? null : {'key': current, 'label': 'Morning hours', 'approx_hours': 3},
      'steps': [
        {'key': 'morning_hours', 'label': 'Morning hours', 'until': 'mid_morning', 'approx_hours': 3, 'min_age_years': 7, 'max_days_per_week': 3, 'advance_when': 'After two or three easy days.', 'text': 'About three hours after suhoor.', 'eligible': true},
        {'key': 'until_dhuhr', 'label': 'Until dhuhr', 'until': 'dhuhr', 'approx_hours': 6, 'min_age_years': 7, 'max_days_per_week': 4, 'advance_when': 'After a comfortable week.', 'text': 'Until the dhuhr adhan.', 'eligible': true},
        {'key': 'until_asr', 'label': 'Until asr', 'until': 'asr', 'approx_hours': 9, 'min_age_years': 9, 'max_days_per_week': 2, 'advance_when': 'The top step at this age.', 'text': 'Only from nine.', 'eligible': false},
      ],
      'practised_today': false,
      'practised_this_week': 0,
      'rest_suggested': false,
      'guidance': {
        'title': 'The fasting ladder',
        'principles': ['Before puberty fasting is training, not an obligation.'],
        'doctor_first': ['Diabetes or any chronic illness.'],
        'stop_signs': ['Dizziness or blurred vision.'],
        'stop_action': 'The child breaks the fast at once with water and a date.',
        'urgent_signs': ['Fainting or a seizure.'],
        'urgent_action': 'Call an ambulance at once; nothing by mouth until fully awake.',
        'tips': ['Water in small amounts from iftar to sleep.'],
        'evidence': <Object>[],
      },
    };

Map<String, dynamic> recapJson({bool available = true}) => {
      'hijri_year': 1448,
      'available': available,
      'available_on': '2027-03-10',
      'show_on': 'eid',
      'card': available
          ? {
              'title': "Our Family's Ramadan",
              'headline': "Our Family's Ramadan 1448",
              'lines': [
                {'keys': ['challenges_done'], 'text': 'Family challenges: 12'},
                {'keys': ['family_word'], 'text': 'Our Ramadan word: Joy'},
              ],
              'metrics': <Object>[],
              'closing': 'May Allah accept from us and from you',
              'share_text': 'This was our family\'s Ramadan with the Almorabbi app. https://play.google.com/store/apps/details?id=com.alsaba.almorabbi&referrer=ref_X',
            }
          : null,
      'progress': [
        {'key': 'challenges_done', 'label': 'Family challenges', 'value': 12, 'max': 30},
      ],
      'family_only': [
        {'key': 'fasting_steps', 'label': 'Fasting steps our children climbed', 'value': 2},
      ],
      'privacy': 'The card carries no children\'s names, ages, photos or anything anyone has typed.',
    };

Map<String, dynamic> journeyJson({
  bool enrolled = true,
  String track = 'journey',
  int stage = 1,
  int pending = 0,
  bool advance = false,
  bool graduate = false,
  String? eligible = 'journey',
  List<String> allowed = const ['journey'],
}) =>
    {
      'child_id': kChildId,
      'date': '2026-10-04',
      'age': ageJson(),
      'title': 'The Prayer Journey',
      'subtitle': 'Twelve weeks from love to responsibility',
      'eligible_track': eligible,
      'allowed_tracks': allowed,
      'bands_text': 'By age: 7 to 10 take the journey.',
      'enrolment': enrolled
          ? {'track': track, 'stage': stage, 'status': 'active', 'started_on': '2026-10-04', 'stage_started_on': '2026-10-04', 'week': 1}
          : null,
      'basis': {'text': 'The program starts at seven.', 'evidence': <Object>[]},
      'principles': ['No punishment, no comparison.'],
      'reward_policy': {'text': 'Coins encourage the effort of learning.', 'daily_cap': 60},
      'stages': [
        for (var i = 1; i <= 6; i++)
          {'stage': i, 'key': 's$i', 'title': 'Stage title $i', 'goal': 'Goal $i', 'week_from': i * 2 - 1, 'week_to': i * 2},
      ],
      'graduation': {
        'title': 'Prayer Journey graduation',
        'text': 'Twelve weeks deserve a celebration.',
        'certificate_text': 'The holder completed twelve weeks of learning to pray.',
        'covenant': {'coins_target': 300, 'examples': ['A family trip']},
        'journey_milestone_keys': ['keeps_prayer'],
        'evidence': <Object>[],
      },
      'graduated_on': null,
      'stage': enrolled && track == 'journey'
          ? {
              'stage': stage,
              'key': 'love_and_presence',
              'title': 'Prayer is a meeting we love',
              'goal': 'Link prayer with love and closeness.',
              'week_from': 1,
              'week_to': 2,
              'parent_assignments': [
                {'key': 'pray_where_seen', 'text': 'Pray one prayer a day where they can see you.'},
              ],
              'confirmation': {'how': 'In the evening you will see what the child recorded.', 'counts_when': 'It counts if they stood with you.'},
              'encouragement': ['I saw you stand beside me so calmly. Well done!'],
              'if_struggling': 'If they refuse, make it lighter.',
              'covenant': {'coins_target': 100, 'examples': ['A short walk in the park']},
              'lesson_ids': <String>[],
              'quran': <Object>[],
              'evidence': <Object>[],
              'journey_milestone_key': null,
            }
          : null,
      'preparation': null,
      'ownership': null,
      'tasks': enrolled
          ? [
              {
                'task_id': 'prayer_s1_pray_beside',
                'title': 'I pray beside Mum or Dad',
                'instruction': 'Stand beside your dad or mum in one prayer today.',
                'estimated_minutes': 7,
                'needs_parent': true,
                'materials': <String>[],
                'skill': 'Following an example',
                'coins': 10,
                'per_week': 5,
                'per_day': 1,
                'week_limit': 5,
                'today': {'recorded': 0, 'confirmed': 0, 'slots_left': 1},
                'this_week': {'recorded': 2, 'confirmed': 1},
              },
            ]
          : <Object>[],
      'advancement': enrolled
          ? {
              'days_in_stage': advance ? 14 : 0,
              'stage_planned_days': 14,
              'next_stage': stage < 6 ? stage + 1 : null,
              'advance_suggested': advance,
              'advance_suggested_on': '2026-10-18',
              'can_graduate': graduate,
              'graduation_available_on': null,
            }
          : null,
      'pending_confirmations': pending,
      'coins': enrolled ? {'confirmed_in_stage': 40, 'covenant_target': 100} : null,
    };

Map<String, dynamic> milestoneJson({String key = 'prayer_start', String state = 'due', bool medical = false}) => {
      'key': key,
      'order': 3,
      'state': state,
      'basis': 'birth_month',
      'due_on': '2026-11-01',
      'alert_on': '2026-10-01',
      'title': key == 'first_fasting' ? 'First fasting attempts' : 'Starting to teach prayer',
      'medical': medical,
      'alert': {'title': 'Turning seven next month', 'body': 'At seven, teaching prayer begins.'},
      'cards': [
        {'title': 'Love before duty', 'body': 'Start with your own example.'},
        {'title': 'One thing at a time', 'body': 'Correct gently and in private.'},
        {'title': 'No comparison', 'body': 'Never compare siblings.'},
      ],
      'red_flags': medical ? ['Fainting or confusion → emergency services at once.'] : <String>[],
      'quran': <Object>[],
      'evidence': <Object>[],
      'links': {'program_ids': ['prayer_journey'], 'path_ids': <String>[], 'lesson_ids': <String>[], 'story_ids': <String>[], 'features': ['covenant']},
      'pushed_at': null,
    };

Map<String, dynamic> milestonesJson({List<String> needs = const [], bool library = false}) => {
      'child_id': kChildId,
      'date': '2026-10-04',
      'age': ageJson(),
      'alert_policy': {'text': 'At most one notification per child per month.', 'pushes': !library},
      'needs_profile': needs,
      'due': library ? <Object>[] : [milestoneJson(medical: true, key: 'first_fasting')],
      'upcoming': library ? <Object>[] : [milestoneJson(state: 'upcoming', key: 'prayer_start')],
      'library': library ? [milestoneJson(state: 'library')] : <Object>[],
      'past': <Object>[],
    };

Map<String, dynamic> childPrayerJson({int slotsLeft = 1, bool enrolled = true}) => {
      'date': '2026-10-04',
      'enrolled': enrolled,
      'track': enrolled ? 'journey' : null,
      'tasks': enrolled
          ? [
              {
                'task_id': 'prayer_s1_pray_beside',
                'title': 'I pray beside Mum or Dad',
                'instruction': 'Stand beside your dad or mum in one prayer today.',
                'estimated_minutes': 7,
                'needs_parent': true,
                'materials': <String>[],
                'skill': 'Following an example',
                'coins': 10,
                'per_day': 1,
                'week_limit': 5,
                'recorded_today': slotsLeft == 0 ? 1 : 0,
                'slots_left_today': slotsLeft,
                'recorded_this_week': 2,
              },
            ]
          : <Object>[],
    };

/// A server without the programs: FastAPI's "no such route".
const oldServer404 = TgApiError(404, 'Not Found');

/// Records every programs call and answers from the maps above.
class FakeProgramsClient extends TgClient {
  FakeProgramsClient() : super.forTesting(baseUrl: 'http://fake.invalid');

  Map<String, dynamic>? programs = programsJson();
  Object? programsError;
  Map<String, dynamic> ramadanToday = ramadanTodayJson();
  Map<int, Map<String, dynamic>> ramadanDays = {};
  Map<String, dynamic> ladder = ladderJson(current: 'morning_hours');
  Map<String, dynamic> recap = recapJson();
  Map<String, dynamic> journey = journeyJson();
  Map<String, dynamic> milestones = milestonesJson();
  Map<String, Map<String, dynamic>> milestoneByKey = {};
  Map<String, dynamic> childPrayer = childPrayerJson();
  Object? claimError;
  List<Map<String, dynamic>> pending = [];
  List<Map<String, dynamic>> confirmCoins = [];
  List<Map<String, dynamic>> children = [
    {'id': kChildId, 'name': kChildName, 'age_group': '7-9', 'gender': 'female', 'avatar_emoji': '👧', 'birth_month': '2019-03', 'created_at': '', 'updated_at': ''},
  ];

  final List<String> calls = [];
  final List<Map<String, dynamic>> bodies = [];

  @override
  Future<Map<String, dynamic>> fetchPrograms() async {
    calls.add('programs');
    if (programsError != null) throw programsError!;
    return programs!;
  }

  @override
  Future<Map<String, dynamic>> fetchRamadanToday(int childId) async {
    calls.add('ramadan_today:$childId');
    return ramadanToday;
  }

  @override
  Future<Map<String, dynamic>> fetchRamadanDay(int childId, int day) async {
    calls.add('ramadan_day:$day');
    return ramadanDays[day] ??
        {
          'child_id': childId,
          'date': '2027-02-10',
          'state': 'ramadan',
          'season': seasonJson(),
          'variant_band': '7-9',
          'content': dayContentJson(day: day),
          'markable': day <= 3,
          'marks': day <= 3 ? {'challenge_done': true, 'wird_done': false, 'story_heard': false, 'juz_read': false} : null,
        };
  }

  /// The family's marks by day, as the server would keep them.
  final Map<int, Map<String, dynamic>> markStore = {};

  @override
  Future<Map<String, dynamic>> setRamadanMark({required String mark, int? day, bool done = true, int? choiceIndex}) async {
    calls.add('mark');
    bodies.add({'mark': mark, 'day': day, 'done': done, 'choice_index': choiceIndex});
    final d = day ?? 3;
    final todayDay = ramadanToday['day'];
    final marks = markStore.putIfAbsent(d, () {
      final base = d == todayDay ? ramadanToday['marks'] as Map<String, dynamic>? : null;
      return {...?base};
    });
    if (mark == 'family_word') {
      marks['family_word'] = {'choice_index': choiceIndex, 'word': 'Joy'};
    } else {
      marks[mark] = done;
    }
    if (d == todayDay) ramadanToday = {...ramadanToday, 'marks': {...marks}};
    return {'hijri_year': 1448, 'day': d, 'marks': {...marks}};
  }

  @override
  Future<Map<String, dynamic>> fetchFastingLadder(int childId) async {
    calls.add('ladder');
    return ladder;
  }

  @override
  Future<Map<String, dynamic>> updateFasting(int childId, {String? stepKey, bool? reachedPuberty}) async {
    calls.add('fasting_put');
    bodies.add({'step_key': stepKey, 'reached_puberty': reachedPuberty});
    return {...ladder, 'climbed': stepKey == 'until_dhuhr'};
  }

  @override
  Future<Map<String, dynamic>> recordFastingPractice(int childId, {int? day, bool done = true}) async {
    calls.add('practice');
    bodies.add({'day': day, 'done': done});
    return {
      'child_id': childId,
      'day': 3,
      'done': done,
      'current_step': {'key': 'morning_hours', 'label': 'Morning hours'},
      'practised_today': done,
      'practised_this_week': done ? 3 : 2,
      'rest_suggested': done,
    };
  }

  @override
  Future<Map<String, dynamic>> updateRamadanSettings({int? startShiftDays, int? monthDays, bool resetMonthDays = false}) async {
    calls.add('settings');
    bodies.add({'start_shift_days': startShiftDays, 'month_days': monthDays, 'reset': resetMonthDays});
    return {'state': 'ramadan', 'season': seasonJson(days: monthDays ?? 30, shift: startShiftDays ?? 0), 'day': 3};
  }

  @override
  Future<Map<String, dynamic>> fetchRamadanRecap({int? hijriYear}) async {
    calls.add('recap');
    return recap;
  }

  @override
  Future<Map<String, dynamic>> fetchPrayerJourney(int childId) async {
    calls.add('journey');
    return journey;
  }

  @override
  Future<Map<String, dynamic>> enrolPrayerJourney(int childId, {String? track, int? startStage, bool restart = false}) async {
    calls.add('enrol');
    bodies.add({'track': track, 'start_stage': startStage, 'restart': restart});
    return journey = journeyJson();
  }

  @override
  Future<Map<String, dynamic>> setPrayerJourneyStage(int childId, int stage) async {
    calls.add('stage');
    bodies.add({'stage': stage});
    return journey = journeyJson(stage: stage);
  }

  @override
  Future<Map<String, dynamic>> graduatePrayerJourney(int childId) async {
    calls.add('graduate');
    return journey = journeyJson(enrolled: false, eligible: 'ownership', allowed: ['ownership', 'journey']);
  }

  @override
  Future<Map<String, dynamic>> stopPrayerJourney(int childId) async {
    calls.add('stop');
    return journey = journeyJson(enrolled: false);
  }

  @override
  Future<Map<String, dynamic>> fetchMilestones(int childId) async {
    calls.add('milestones');
    return milestones;
  }

  @override
  Future<Map<String, dynamic>> fetchMilestone(int childId, String key) async {
    calls.add('milestone:$key');
    final m = milestoneByKey[key];
    if (m == null) {
      throw const TgApiError(404, 'x', code: 'milestone_not_found');
    }
    return {'child_id': childId, 'date': '2026-10-04', 'milestone': m};
  }

  @override
  Future<Map<String, dynamic>> fetchChildPrayerToday(String childToken) async {
    calls.add('child_prayer');
    return childPrayer;
  }

  @override
  Future<Map<String, dynamic>> claimChildPrayer({required String childToken, required String taskId}) async {
    calls.add('claim:$taskId');
    if (claimError != null) throw claimError!;
    return {'ok': true, 'status': 'claimed', 'mission_id': 41, 'task_id': taskId, 'slot': 1, 'recorded_today': 1, 'slots_left_today': 0};
  }

  @override
  Future<List<Map<String, dynamic>>> fetchPendingMissions() async => pending;

  /// Missions this "server" has confirmed — its `child_missions` status.
  final Set<int> confirmedIds = {};

  /// Like `confirm_batch` (backend/app/services/child_missions.py): a card it
  /// settles leaves `pending`; `settled` counts only rows this call changed;
  /// `coins` lists every prayer mission *in this request* that is confirmed —
  /// a retry reports them again — once per mission; [confirmCoins] is the
  /// table of what each prayer mission is worth.
  @override
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(List<Map<String, dynamic>> items) async {
    calls.add('settle');
    bodies.add({'items': items});
    return applySettle(items);
  }

  ({int settled, List<Map<String, dynamic>> coins}) applySettle(List<Map<String, dynamic>> items) {
    var settled = 0;
    final coins = <Map<String, dynamic>>[];
    final seen = <int>{};
    for (final item in items) {
      final id = item['mission_id'] as int;
      if (!seen.add(id)) continue;
      final wasPending = pending.any((c) => c['mission_id'] == id);
      if (wasPending) {
        pending = [for (final c in pending) if (c['mission_id'] != id) c];
        settled++;
        if (item['confirmed'] != false) confirmedIds.add(id);
      }
      if (item['confirmed'] != false && confirmedIds.contains(id)) {
        coins.addAll(confirmCoins.where((e) => e['mission_id'] == id));
      }
    }
    return (settled: settled, coins: coins);
  }

  @override
  Future<Map<String, dynamic>> listChildren() async => {'count': children.length, 'children': children};

  // Link titles fall back to plain labels in these tests.
  @override
  Future<Map<String, dynamic>> getLesson(String lessonId) async => throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> getPathDetail(String pathId, {bool includeLessons = true}) async =>
      throw const TgApiError(503, 'offline');
}

final kStory = Story(
  id: 'abdullah_bismillah',
  title: 'Abdullah and Bismillah',
  description: 'A story',
  coverImage: '',
  themeColor: '#000000',
  pages: [StoryPage(pageNumber: 1, text: 'Once upon a time', image: '')],
  language: 'en',
);

/// Pumps [home] with the fake client, an active child, and the slow loaders
/// (stories, the mushaf) replaced by small fixtures.
Future<ProviderContainer> pumpPrograms(
  WidgetTester tester,
  Widget home, {
  required FakeProgramsClient client,
  Locale locale = const Locale('en'),
  bool dark = false,
  double textScale = 1.0,
  Size phone = const Size(400, 860),
  DateTime? now,
  List<Override> overrides = const [],
  bool activeChild = true,
  GlobalKey<NavigatorState>? navigatorKey,
}) async {
  tester.view.physicalSize = phone * 3.0;
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({
    if (activeChild) ...{
      OnboardingStorage.keyActiveChildId: kChildId,
      OnboardingStorage.keyActiveChildName: kChildName,
      OnboardingStorage.keyActiveChildAgeGroup: '7-9',
    },
    OnboardingStorage.keyOnboardingCompleted: true,
  });
  final prefs = await SharedPreferences.getInstance();
  final container = ProviderContainer(overrides: [
    tgClientProvider.overrideWithValue(client),
    sharedPreferencesProvider.overrideWith((_) async => prefs),
    storiesProvider.overrideWith((ref) async => [kStory]),
    quranDataProvider.overrideWith((ref) async => {
          '114': [
            for (var v = 1; v <= 6; v++) {'chapter': 114, 'verse': v, 'text': 'آية $v'},
          ],
        }),
    if (now != null) programsClockProvider.overrideWithValue(() => now),
    ...overrides,
  ]);
  addTearDown(container.dispose);
  await container.read(sharedPreferencesProvider.future);
  if (activeChild) container.read(activeChildIdProvider.notifier).state = kChildId;
  if (dark) {
    AppPalette.current = AppPalette.dark;
    addTearDown(() => AppPalette.current = AppPalette.light);
  }
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        navigatorKey: navigatorKey,
        locale: locale,
        theme: dark ? AppTheme.dark() : AppTheme.light(),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!,
        ),
        home: home,
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
  return container;
}

/// Scrolls the first scrollable until [finder] is built and on screen.
Future<void> scrollTo(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(finder, 250, scrollable: find.byType(Scrollable).first);
  await tester.pump();
}

/// Lets futures settle without pumpAndSettle (loading views animate forever).
Future<void> settle(WidgetTester tester, [int frames = 6]) async {
  for (var i = 0; i < frames; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
}

// Keeps `unawaited` imported for callers that build on this file.
void ignoreFuture(Future<void> f) => unawaited(f);
