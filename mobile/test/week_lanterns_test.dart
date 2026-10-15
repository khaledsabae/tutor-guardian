/// «قناديل الأسبوع» under ① on «اليوم» (نور والقناديل phase 3, MOBILE_API §12).
///
/// Pinned here: the client hides everything on an older server (404) and on
/// any failure; only the week's lit lanterns are drawn — one per local day
/// with an act — plus one dashed «next» lantern; a lantern this phone has not
/// shown lights once, with one success tap, and never again; a lantern waits
/// while «اليوم» is covered; and a tap lists the week's acts.
library;

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/lanterns/data/family_week.dart';
import 'package:almorabbi/features/lanterns/data/lantern_seen_store.dart';
import 'package:almorabbi/features/lanterns/providers/lantern_providers.dart';
import 'package:almorabbi/features/lanterns/widgets/lantern_row.dart';
import 'package:almorabbi/features/lanterns/widgets/week_lantern_string.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/widgets/ui/paper_lantern.dart';

import 'lantern_fakes.dart';
import 'memory_fakes.dart';

/// A real TgClient over a scripted HTTP server — the contract is read at the
/// wire, not through an overridden method.
class _WireClient extends TgClient {
  _WireClient(http.Client c)
      : super.forTesting(baseUrl: 'http://fake.invalid', httpClient: c);

  @override
  Future<SessionResponse> ensureSession() async =>
      const SessionResponse(sessionId: 's1', token: 't1');
}

Widget _today({bool reduceMotion = false}) => Builder(
      builder: (context) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: reduceMotion),
        child: Scaffold(
          body: ListView(
            padding: const EdgeInsets.all(16),
            children: const [WeekLanternString()],
          ),
        ),
      ),
    );

/// «اليوم» again over the same container (the same phone and preferences).
Future<void> _repump(WidgetTester tester, ProviderContainer container) =>
    tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: _today(),
      ),
    ));

/// Records every haptic pulse the app asks for.
List<String> _recordHaptics(WidgetTester tester) {
  final pulses = <String>[];
  tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
    SystemChannels.platform,
    (call) async {
      if (call.method == 'HapticFeedback.vibrate') {
        pulses.add('${call.arguments}');
      }
      return null;
    },
  );
  addTearDown(() => tester.binding.defaultBinaryMessenger
      .setMockMethodCallHandler(SystemChannels.platform, null));
  return pulses;
}

List<bool> _lit(WidgetTester tester) => [
      for (final l in tester.widgetList<PaperLantern>(find.byType(PaperLantern)))
        l.lit,
    ];

LanternRowState _row(WidgetTester tester) =>
    tester.state<LanternRowState>(find.byType(LanternRow));

/// Three acts on two days: Monday (two) and Wednesday (one).
Map<String, dynamic> _twoDays() => familyWeekJson(acts: [
      act('lesson', 0, hour: 9, title: 'النوم والتركيز'),
      act('question', 0, hour: 20),
      act('mission', 2, title: 'صيّاد الأخضر'),
    ]);

void main() {
  group('client', () {
    Future<(FamilyWeek?, List<http.Request>)> read(
        http.Response Function(http.Request) answer) async {
      final requests = <http.Request>[];
      final client = _WireClient(MockClient((r) async {
        requests.add(r);
        return answer(r);
      }));
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(client),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ]);
      addTearDown(container.dispose);
      await container.read(sharedPreferencesProvider.future);
      final sub = container.listen(familyWeekProvider, (_, _) {});
      addTearDown(sub.close);
      return (await container.read(familyWeekProvider.future), requests);
    }

    test('asks with the device offset and language; reads the week', () async {
      final (week, requests) = await read((_) => http.Response.bytes(
          utf8.encode(jsonEncode(_twoDays())), 200,
          headers: {'content-type': 'application/json'}));
      final uri = requests.single.url;
      expect(uri.path, '/api/family/week');
      expect(uri.queryParameters['tz_offset_minutes'],
          '${DateTime.now().timeZoneOffset.inMinutes}');
      expect(uri.queryParameters['lang'], isNotNull);
      expect(week!.acts, hasLength(3));
      expect(week.lanterns, 2, reason: 'one lantern per local day');
      expect(week.litWeeksTotal, 3);
      expect(week.acts.first.title, 'النوم والتركيز');
      expect(week.countsByKind, {'lesson': 1, 'question': 1, 'mission': 1});
    });

    test('an older server (404) is null — the lanterns hide', () async {
      final (week, _) = await read(
          (_) => http.Response('{"detail":"Not Found"}', 404));
      expect(week, isNull);
    });

    test('any other failure is null too, never an error on «اليوم»', () async {
      for (final status in [422, 500, 503]) {
        final (week, _) = await read((_) => http.Response('{}', status));
        expect(week, isNull, reason: '$status');
      }
      final (garbled, _) = await read((_) => http.Response('[1,2', 200));
      expect(garbled, isNull);
    });

    test('an unknown kind is kept and counted as «another step»', () {
      final week = FamilyWeek.fromJson(familyWeekJson(acts: [
        act('lesson', 1),
        act('stargazing', 1),
      ]));
      expect(week.acts, hasLength(2));
      expect(week.countsByKind, {'lesson': 1, 'other': 1});
    });
  });

  testWidgets('a server without lanterns: nothing at all under ①', (
    tester,
  ) async {
    final server = FakeMemoryServer(); // familyWeek null → bare 404
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    expect(find.byType(PaperLantern), findsNothing);
    expect(find.byType(NextLantern), findsNothing);
    expect(find.text('قناديل أسبوعكم'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('only the lit lanterns, one per day, then the next one', (
    tester,
  ) async {
    final server = FakeMemoryServer()..familyWeek = _twoDays();
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester, 20);
    expect(find.text('قناديل أسبوعكم'), findsOneWidget);
    expect(_lit(tester), [true, true], reason: 'no unlit day is ever drawn');
    expect(find.byType(NextLantern), findsOneWidget);
    expect(find.bySemanticsLabel('القنديل التالي'), findsNothing,
        reason: 'the whole row reads as one button');
  });

  testWidgets('a full week of seven has no «next» lantern', (tester) async {
    final server = FakeMemoryServer()
      ..familyWeek = familyWeekJson(acts: [
        for (var d = 0; d < 7; d++) act('lesson', d),
      ]);
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester, 30);
    expect(_lit(tester), List.filled(7, true));
    expect(find.byType(NextLantern), findsNothing);
  });

  testWidgets('no act yet this week: the next lantern and the hint only', (
    tester,
  ) async {
    final server = FakeMemoryServer()..familyWeek = familyWeekJson();
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    expect(find.byType(PaperLantern), findsNothing);
    expect(find.byType(NextLantern), findsOneWidget);
    expect(find.text('كل خطوة تربوية هذا الأسبوع تضيء قنديلًا.'),
        findsOneWidget);
  });

  testWidgets('new lanterns light once — one tap — and never replay', (
    tester,
  ) async {
    final pulses = _recordHaptics(tester);
    final server = FakeMemoryServer()..familyWeek = _twoDays();
    final container =
        await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester, 2);
    // Drawn unlit first, so the glow has somewhere to rise from.
    expect(_row(tester).shown, lessThan(2));
    await settle(tester, 20);
    expect(_row(tester).shown, 2);
    expect(_lit(tester), [true, true]);
    expect(pulses.where((p) => p.contains('lightImpact')), hasLength(1));
    final prefs = await container.read(sharedPreferencesProvider.future);
    final week = FamilyWeek.fromJson(_twoDays()).weekKey;
    expect(LanternSeenStore(prefs).seenFor(week), 2);

    // «اليوم» opened again: lit from the first frame, no tap.
    pulses.clear();
    await tester.pumpWidget(const SizedBox());
    await _repump(tester, container);
    await tester.pump();
    await tester.pump();
    expect(_row(tester).shown, 2);
    await settle(tester, 20);
    expect(pulses, isEmpty);
  });

  testWidgets('one new day after the last visit: only it lights', (
    tester,
  ) async {
    final pulses = _recordHaptics(tester);
    final week = FamilyWeek.fromJson(_twoDays()).weekKey;
    final server = FakeMemoryServer()..familyWeek = _twoDays();
    final container = await pumpMemoryApp(tester, const SizedBox(),
        server: server);
    final prefs = await container.read(sharedPreferencesProvider.future);
    await LanternSeenStore(prefs).setSeen(week, 1);
    await _repump(tester, container);
    await tester.pump();
    await tester.pump();
    expect(_lit(tester).first, isTrue, reason: 'seen before: lit at once');
    expect(_row(tester).shown, 1);
    await settle(tester, 20);
    expect(_lit(tester), [true, true]);
    expect(pulses.where((p) => p.contains('lightImpact')), hasLength(1));
    expect(LanternSeenStore(prefs).seenFor(week), 2);
  });

  testWidgets('last week’s record does not hide this week’s first lantern', (
    tester,
  ) async {
    final pulses = _recordHaptics(tester);
    final server = FakeMemoryServer()
      ..familyWeek = familyWeekJson(acts: [act('lesson', 0)]);
    final container = await pumpMemoryApp(tester, const SizedBox(),
        server: server);
    final prefs = await container.read(sharedPreferencesProvider.future);
    await LanternSeenStore(prefs).setSeen('2020-01-06', 5);
    await _repump(tester, container);
    await settle(tester, 20);
    expect(_lit(tester), [true]);
    expect(pulses.where((p) => p.contains('lightImpact')), hasLength(1));
  });

  testWidgets('reduced motion: lit from the first frame, no glow', (
    tester,
  ) async {
    final pulses = _recordHaptics(tester);
    final server = FakeMemoryServer()..familyWeek = _twoDays();
    await pumpMemoryApp(tester, _today(reduceMotion: true), server: server);
    await settle(tester, 2);
    expect(_lit(tester), [true, true]);
    // Still said once — a tap is not motion.
    await settle(tester);
    expect(pulses.where((p) => p.contains('lightImpact')), hasLength(1));
  });

  testWidgets('covered by another screen: the lantern waits for the return', (
    tester,
  ) async {
    final pulses = _recordHaptics(tester);
    final navigator = GlobalKey<NavigatorState>();
    final server = FakeMemoryServer();
    await pumpMemoryApp(tester, _today(),
        server: server, navigatorKey: navigator);
    await settle(tester);
    // A lesson is open over «اليوم» when the week's first lantern arrives.
    navigator.currentState!.push(MaterialPageRoute<void>(
        builder: (_) => const Scaffold(body: Text('LESSON'))));
    await settle(tester, 20);
    server.familyWeek = familyWeekJson(acts: [act('lesson', 0)]);
    final element = tester.element(find.byType(WeekLanternString,
        skipOffstage: false));
    ProviderScope.containerOf(element).invalidate(familyWeekProvider);
    await settle(tester, 20);
    expect(pulses, isEmpty, reason: 'nobody is looking at «اليوم»');

    navigator.currentState!.pop();
    await settle(tester, 30);
    expect(_lit(tester), [true]);
    expect(pulses.where((p) => p.contains('lightImpact')), hasLength(1));
  });

  testWidgets('a tap lists the week’s acts by day, by kind, with titles', (
    tester,
  ) async {
    final server = FakeMemoryServer()..familyWeek = _twoDays();
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester, 20);
    await tester.tap(find.text('قناديل أسبوعكم'));
    await settle(tester, 10);
    expect(find.text('خطوات هذا الأسبوع'), findsOneWidget);
    for (final t in [
      'درس',
      'النوم والتركيز',
      'سؤال',
      'مهمة',
      'صيّاد الأخضر',
      '3 أسابيع مضيئة',
    ]) {
      expect(find.text(t), findsOneWidget, reason: t);
    }
    // Two days, each once — no empty days in between.
    expect(find.textContaining(' · '), findsNWidgets(2));
    expect(tester.takeException(), isNull);
  });

  testWidgets('English: the sheet speaks English', (tester) async {
    final server = FakeMemoryServer()
      ..familyWeek = familyWeekJson(acts: [
        act('lesson', 0, title: 'Sleep and focus'),
        act('plan_tick', 1, title: 'Screens off an hour before bed.'),
      ], litWeeksTotal: 1);
    await pumpMemoryApp(tester, _today(),
        server: server, locale: const Locale('en'));
    await settle(tester, 20);
    await tester.tap(find.text("Your week's lanterns"));
    await settle(tester, 10);
    for (final t in [
      "This week's steps",
      'Lesson',
      'Sleep and focus',
      'Plan step',
      '1 lit week',
    ]) {
      expect(find.text(t), findsOneWidget, reason: t);
    }
  });
}
