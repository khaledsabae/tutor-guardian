// The ways into the family programs, and what an older server sees.
//
// A server without schema v34 answers 404 to `GET /api/programs`. Builds stay
// live for weeks, so that is a normal state: every entry point (the Home card,
// the «المزيد» tile, the birth-month field) must simply not be there — never
// an error screen behind a tile.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/deeplink/deep_link_handler.dart';
import 'package:almorabbi/features/home/widgets/today_section.dart';
import 'package:almorabbi/features/hub/screens/hub_screen.dart';
import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/program/screens/add_child_screen.dart';
import 'package:almorabbi/features/program/screens/edit_child_screen.dart';
import 'package:almorabbi/features/programs/screens/milestones_screen.dart';
import 'package:almorabbi/features/programs/screens/prayer_journey_screen.dart';
import 'package:almorabbi/features/programs/screens/programs_screen.dart';
import 'package:almorabbi/features/programs/widgets/birth_month_field.dart';
import 'package:almorabbi/features/programs/widgets/programs_home_card.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/screens/home_screen.dart';

import 'programs_support.dart';

/// The Home screen also reads progress, paths, the coach tip and the child's
/// day; they fail fast here, as from an unreachable server.
class _HomeFake extends FakeProgramsClient {
  @override
  Future<Map<String, dynamic>> getChildProgress(int childId, {String? pathId}) async =>
      {'child_id': childId, 'lessons': []};
  @override
  Future<Map<String, dynamic>> getPathsList({String? ageGroup, String? domain}) async =>
      throw const TgApiError(503, 'offline');
  @override
  Future<Map<String, dynamic>> getNextLesson(String ageGroup, {int? childId}) async =>
      throw const TgApiError(503, 'offline');
  @override
  Future<Map<String, dynamic>> getCoachTip(int childId) async => throw const TgApiError(503, 'offline');
  @override
  Future<Map<String, dynamic>> getCommunityStats() async => throw const TgApiError(503, 'offline');
  @override
  Future<Map<String, dynamic>> fetchChildDay(int childId) async => throw const TgApiError(503, 'offline');
}

class _EditFake extends FakeProgramsClient {
  final List<Map<String, Object?>> updates = [];
  final List<Map<String, Object?>> creates = [];

  @override
  Future<Map<String, dynamic>> updateChild({
    required int childId,
    String? name,
    String? ageGroup,
    String? gender,
    String? avatarEmoji,
    String? birthMonth,
    bool clearBirthMonth = false,
  }) async {
    updates.add({'birth_month': birthMonth, 'clear': clearBirthMonth, 'age_group': ageGroup});
    return {'id': childId, 'name': name ?? 'x', 'age_group': ageGroup ?? '7-9', 'birth_month': clearBirthMonth ? null : birthMonth};
  }

  @override
  Future<Map<String, dynamic>> createChild({
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
    String? birthMonth,
  }) async {
    creates.add({'birth_month': birthMonth, 'age_group': ageGroup});
    return {'id': 77, 'name': name, 'age_group': ageGroup, 'birth_month': birthMonth};
  }
}

class _ActiveChildMode extends ChildModeNotifier {
  _ActiveChildMode(super.client) {
    state = const ChildModeState(active: true, childId: kChildId);
  }
}

void main() {
  group('Home', () {
    testWidgets('the programs card sits below the three blocks, not among them', (tester) async {
      // A tall screen, so the blocks, the card and the divider are all built.
      await pumpPrograms(tester, HomeScreen(onGoToTab: (_) {}),
          client: _HomeFake(), phone: const Size(400, 2600));
      await settle(tester);
      // Still exactly three numbered stops (the card has no section header).
      expect(find.byType(TodaySectionHeader), findsNWidgets(3));
      final card = find.byKey(const ValueKey('programs_home_card'));
      expect(card, findsOneWidget);
      final missionHeader = find.text("سارة's mission today");
      final divider = find.text('More for today');
      expect(tester.getTopLeft(card).dy, greaterThan(tester.getTopLeft(missionHeader).dy));
      expect(tester.getTopLeft(card).dy, lessThan(tester.getTopLeft(divider).dy));
      // The lines speak about the active child.
      expect(find.text('Day 3 of 30 of Ramadan'), findsOneWidget);
      expect(find.text('The Prayer Journey: start it with سارة'), findsOneWidget);
    });

    testWidgets('an older server (404) shows no card at all', (tester) async {
      final client = _HomeFake()..programsError = oldServer404;
      await pumpPrograms(tester, HomeScreen(onGoToTab: (_) {}), client: client);
      await settle(tester);
      await scrollTo(tester, find.text('More for today'));
      expect(find.byKey(const ValueKey('programs_home_card')), findsNothing);
      expect(find.byType(ProgramsHomeCard), findsOneWidget); // mounted, renders nothing
      expect(tester.takeException(), isNull);
    });

    testWidgets('a network failure hides it too — never an error on Today', (tester) async {
      final client = FakeProgramsClient()..programsError = const TgApiError(null, 'offline');
      await pumpPrograms(tester, const Scaffold(body: ProgramsHomeCard()), client: client);
      await settle(tester);
      expect(find.byKey(const ValueKey('programs_home_card')), findsNothing);
    });

    testWidgets('tapping a line opens that program', (tester) async {
      await pumpPrograms(tester, const Scaffold(body: SingleChildScrollView(child: ProgramsHomeCard())),
          client: FakeProgramsClient());
      await settle(tester);
      await tester.tap(find.text('The Prayer Journey: start it with سارة'));
      await settle(tester);
      expect(find.byType(PrayerJourneyScreen), findsOneWidget);
    });
  });

  group('«المزيد»', () {
    testWidgets('the programs tile appears once the server offers them', (tester) async {
      await pumpPrograms(tester, const HubScreen(), client: FakeProgramsClient());
      await settle(tester);
      expect(find.text('Family programs'), findsOneWidget);
      await tester.tap(find.text('Family programs'));
      await settle(tester);
      expect(find.byType(ProgramsScreen), findsOneWidget);
    });

    testWidgets('and is absent on an older server', (tester) async {
      final client = FakeProgramsClient()..programsError = oldServer404;
      await pumpPrograms(tester, const HubScreen(), client: client);
      await settle(tester);
      expect(find.text('Family programs'), findsNothing);
      expect(find.text('My children'), findsOneWidget); // the rest of the group stays
    });
  });

  group('the programs list', () {
    testWidgets('one family Ramadan card, then each child with their programs', (tester) async {
      await pumpPrograms(tester, const ProgramsScreen(), client: FakeProgramsClient());
      await settle(tester);
      expect(find.text('Family Ramadan'), findsOneWidget);
      expect(find.text('سارة'), findsOneWidget);
      expect(find.text("سارة's part in Ramadan"), findsOneWidget);
      expect(find.text('The Prayer Journey'), findsOneWidget);
      await scrollTo(tester, find.text('Important stages'));
      expect(find.text('1 stage is due now'), findsOneWidget);
    });

    testWidgets('a child the journey is not for has no journey row', (tester) async {
      final client = FakeProgramsClient()..programs = programsJson(eligibleTrack: null);
      await pumpPrograms(tester, const ProgramsScreen(), client: client);
      await settle(tester);
      expect(find.text('The Prayer Journey'), findsNothing);
    });

    testWidgets('opened on an older server, it says so plainly', (tester) async {
      final client = FakeProgramsClient()..programsError = oldServer404;
      await pumpPrograms(tester, const ProgramsScreen(), client: client);
      await settle(tester);
      expect(find.text("These programs aren't available right now. Please try again later."), findsOneWidget);
      expect(find.text('Retry'), findsNothing);
    });
  });

  group('the milestone push deep link', () {
    testWidgets('/milestones/{child}/{key} opens that card', (tester) async {
      final key = GlobalKey<NavigatorState>();
      final client = FakeProgramsClient()..milestoneByKey['prayer_start'] = milestoneJson();
      await pumpPrograms(
        tester,
        Builder(builder: (_) => const Scaffold(body: Text('root'))),
        client: client,
        navigatorKey: key,
      );
      DeepLinkHandler.instance.handleForTest(Uri.parse('/milestones/$kChildId/prayer_start'), key);
      await settle(tester);
      expect(find.byType(MilestoneDetailScreen), findsOneWidget);
      expect(find.text('Starting to teach prayer'), findsWidgets);
      expect(client.calls, contains('milestone:prayer_start'));
    });

    testWidgets('a card that is not this child\'s falls back to the list', (tester) async {
      final key = GlobalKey<NavigatorState>();
      final client = FakeProgramsClient(); // no milestone → 404 milestone_not_found
      await pumpPrograms(tester, const Scaffold(body: Text('root')), client: client, navigatorKey: key);
      DeepLinkHandler.instance.handleForTest(Uri.parse('/milestones/$kChildId/puberty_boys'), key);
      await settle(tester, 10);
      expect(find.byType(MilestoneDetailScreen), findsNothing);
      expect(find.byType(MilestonesScreen), findsOneWidget);
    });

    testWidgets('never over a running child surface', (tester) async {
      final key = GlobalKey<NavigatorState>();
      final client = FakeProgramsClient()..milestoneByKey['prayer_start'] = milestoneJson();
      await pumpPrograms(tester, const Scaffold(body: Text('root')),
          client: client,
          navigatorKey: key,
          overrides: [childModeProvider.overrideWith((ref) => _ActiveChildMode(client))]);
      DeepLinkHandler.instance.handleForTest(Uri.parse('/milestones/$kChildId/prayer_start'), key);
      await settle(tester);
      expect(find.byType(MilestoneDetailScreen), findsNothing);
      expect(find.text('root'), findsOneWidget);
    });
  });

  group('birth month on the child profile', () {
    testWidgets('adding a child: offered when the server can store it, sent when chosen', (tester) async {
      final client = _EditFake();
      await pumpPrograms(tester, const AddChildScreen(), client: client);
      await settle(tester);
      expect(find.byKey(const ValueKey('birth_month_field')), findsOneWidget);
      expect(find.text('Birth month (optional)'), findsOneWidget);
      // Why it is asked for, in plain words.
      expect(find.textContaining('remind you before important stages'), findsOneWidget);

      await tester.enterText(find.byType(TextFormField).first, 'Omar');
      await tester.tap(find.text('7–9 years').first);
      await tester.pump();
      await tester.tap(find.byKey(const ValueKey('birth_month_choose')));
      await settle(tester);
      await tester.tap(find.byKey(const ValueKey('birth_month_year')));
      await settle(tester);
      await tester.tap(find.text('2019').last);
      await settle(tester);
      await tester.tap(find.byKey(const ValueKey('birth_month_m3')));
      await tester.pump();
      await tester.tap(find.byKey(const ValueKey('birth_month_save')));
      await settle(tester);
      expect(find.text('March 2019'), findsOneWidget);

      await tester.tap(find.text('Add')); // the app bar action
      await settle(tester);
      expect(client.creates.single['birth_month'], '2019-03');
    });

    testWidgets('an older server: no field (it would be dropped silently)', (tester) async {
      final client = _EditFake()..programsError = oldServer404;
      await pumpPrograms(tester, const AddChildScreen(), client: client);
      await settle(tester);
      expect(find.byKey(const ValueKey('birth_month_field')), findsNothing);
    });

    testWidgets('editing: removing it sends an explicit clear', (tester) async {
      final client = _EditFake();
      final child = ChildProfile.fromJson({
        'id': kChildId, 'name': kChildName, 'age_group': '7-9', 'birth_month': '2019-03',
      });
      await pumpPrograms(tester, EditChildScreen(child: child), client: client);
      await settle(tester);
      expect(find.text('March 2019'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('birth_month_clear')));
      await tester.pump();
      expect(find.text('Not set'), findsOneWidget);
      await tester.tap(find.text('Save').first);
      await settle(tester);
      expect(client.updates.single['clear'], isTrue);
      expect(client.updates.single['birth_month'], isNull);
    });

    testWidgets('editing without touching it sends nothing about it', (tester) async {
      final client = _EditFake();
      final child = ChildProfile.fromJson({
        'id': kChildId, 'name': kChildName, 'age_group': '7-9', 'birth_month': '2019-03',
      });
      await pumpPrograms(tester, EditChildScreen(child: child), client: client);
      await settle(tester);
      await tester.tap(find.text('Save').first);
      await settle(tester);
      expect(client.updates.single['clear'], isFalse);
      expect(client.updates.single['birth_month'], isNull);
    });

    testWidgets('a month that puts the child in another band offers to use it', (tester) async {
      String? used;
      await pumpPrograms(
        tester,
        Scaffold(
          body: BirthMonthField(
            value: '2016-03',
            childName: 'Omar',
            ageGroup: '7-9',
            today: DateTime(2026, 10, 4),
            onChanged: (_) {},
            onUseBand: (b) => used = b,
          ),
        ),
        client: FakeProgramsClient(),
      );
      await settle(tester);
      expect(find.textContaining('Omar is in the 10–12'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('birth_month_use_band')));
      expect(used, '10-12');
    });
  });

  testWidgets('the programs entry never throws on a slow answer', (tester) async {
    final client = _SlowClient();
    await pumpPrograms(tester, const Scaffold(body: ProgramsHomeCard()), client: client);
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byKey(const ValueKey('programs_home_card')), findsNothing); // loading → nothing
    client.gate.complete(programsJson());
    await settle(tester);
    expect(find.byKey(const ValueKey('programs_home_card')), findsOneWidget);
  });
}

class _SlowClient extends FakeProgramsClient {
  final gate = Completer<Map<String, dynamic>>();
  @override
  Future<Map<String, dynamic>> fetchPrograms() => gate.future;
}
