// «ركن الطفل» — the child's corner after the hand-over gate.
//
// What has to hold (scratch/game-study/REPORT.md, the brief of 2026-10-15):
//  * only what the child's band is allowed is in the corner — no game for a
//    4-6 child, and no corner at all under four;
//  * for this launch no game for anyone (kChildCornerGameEnabled: the games'
//    questions are written for parents) — the game's path stays covered
//    with the switch turned on;
//  * no coins and no points anywhere in it, the game included;
//  * the session ends on the task away from the screen, then «أعِد الجهاز
//    إلى أهلك» — whether the child chose it, finished everything, or ran out
//    of time;
//  * time is a candle that only grows shorter, never a number, and stands
//    still under reduced motion;
//  * no «come back tomorrow», no streak, no counting — in any of its strings.

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/analytics.dart';
import 'package:almorabbi/core/app_routes.dart';
import 'package:almorabbi/features/child_corner/child_corner_screen.dart';
import 'package:almorabbi/features/child_corner/corner_picks.dart';
import 'package:almorabbi/features/child_corner/paper_candle.dart';
import 'package:almorabbi/features/coins/coins_providers.dart';
import 'package:almorabbi/features/companion/widgets/noor_presence.dart';
import 'package:almorabbi/features/games/shared/edu_game_shell.dart';
import 'package:almorabbi/features/handover/child_surface_policy.dart';
import 'package:almorabbi/features/handover/handover_gate_screen.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/data/story_models.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/features/routine/screens/habit_child_mode_screen.dart';
import 'package:almorabbi/features/routine/services/child_mode_secure_storage.dart';
import 'package:almorabbi/features/routine/widgets/child_mode_shell.dart';
import 'package:almorabbi/features/routine/widgets/quiet_time_bar.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/widgets/ui/brand_glyph.dart';

final Map<String, String> _secure = {};

class _FakeClient extends TgClient {
  final sessions = <String>[];
  final ended = <String>[];
  Map<String, dynamic>? mission = {
    'mission_id': 3,
    'title_ar': 'اسقِ نبتة في البيت',
    'instruction_ar': 'ابحث عن نبتة واسقها قليلًا من الماء.',
    'status': 'assigned',
  };

  /// What `allowed_seconds` the next session carries.
  int allowed = 600;

  @override
  Future<ChildMissionToday?> fetchChildMission(String childToken) async =>
      ChildMissionToday(mission: mission);

  @override
  Future<Map<String, dynamic>> createChildSession(int childId,
      {String surface = 'habit'}) async {
    sessions.add(surface);
    // No session id: nothing heartbeats, so no timer outlives the test. The
    // allowance is still read — what the candle is drawn from.
    return {'token': 'child-token', 'surface': surface, 'allowed_seconds': allowed};
  }

  @override
  Future<void> endChildSession({
    required String childToken,
    required int sessionId,
    String reason = 'completed',
  }) async {
    ended.add('$sessionId:$reason');
  }
}

Story _story(String id, int pages, {String language = 'ar'}) => Story(
      id: id,
      title: 'حكاية $id',
      description: '',
      coverImage: '',
      themeColor: '#0F6B5C',
      language: language,
      pages: [
        for (var i = 1; i <= pages; i++)
          StoryPage(pageNumber: i, text: 'الصفحة رقم $i من $id', image: ''),
      ],
    );

final _stories = [_story('a', 2), _story('b', 3)];

Future<ProviderContainer> _pump(
  WidgetTester t, {
  String band = '7-9',
  Locale locale = const Locale('ar'),
  _FakeClient? client,
  bool reduceMotion = false,
  bool gameOn = false,
  int? sessionId = 11,
  int? remaining = 600,
  List<Story>? stories,
  Size size = const Size(400, 900),
}) async {
  t.view.physicalSize = size * 2;
  t.view.devicePixelRatio = 2;
  addTearDown(t.view.reset);
  final container = ProviderContainer(overrides: [
    tgClientProvider.overrideWithValue(client ?? _FakeClient()),
    storiesProvider.overrideWith((ref) async => stories ?? _stories),
    activeChildProfileProvider.overrideWithValue(
        ActiveChildProfile(id: 7, name: 'سارة', ageGroup: band)),
    childCornerNowProvider.overrideWithValue(() => DateTime(2026, 10, 15)),
    childCornerGameEnabledProvider.overrideWithValue(gameOn),
  ]);
  addTearDown(container.dispose);
  container.read(childModeProvider.notifier).state = ChildModeState(
    active: true,
    childId: 7,
    sessionId: sessionId,
    surface: 'story',
    remainingSeconds: remaining,
    cornerBand: band,
  );
  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: reduceMotion),
        child: child!,
      ),
      home: const ChildModeShell(child: HabitChildModeScreen()),
    ),
  ));
  await _settle(t);
  return container;
}

/// Lets the corner's loads (story library, question pack, task) land. Not
/// pumpAndSettle: the candle's flame sways for as long as motion is allowed.
Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 6; i++) {
    await t.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 10)));
    await t.pump(const Duration(milliseconds: 300));
  }
}

Future<void> _tap(WidgetTester t, String key) async {
  final finder = find.byKey(ValueKey(key));
  await t.ensureVisible(finder);
  await t.pump();
  await t.tap(finder);
  await _settle(t);
}

final _digits = RegExp(r'[0-9٠-٩]');

/// Every string drawn under [root], and every semantics label.
List<String> _textsUnder(WidgetTester t, Finder root) => [
      for (final w in t.widgetList<Text>(find.descendant(
          of: root, matching: find.byType(Text), skipOffstage: false)))
        w.data ?? w.textSpan?.toPlainText() ?? '',
      for (final w in t.widgetList<Semantics>(find.descendant(
          of: root, matching: find.byType(Semantics), skipOffstage: false)))
        w.properties.label ?? '',
    ];

void main() {
  final events = <(String, Map<String, Object>?)>[];

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    _secure.clear();
    events.clear();
    Analytics.debugSink = (name, params) => events.add((name, params));
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async {
        final key = call.arguments['key'] as String?;
        switch (call.method) {
          case 'read':
            return _secure[key];
          case 'write':
            _secure[key!] = call.arguments['value'] as String;
            return null;
          case 'delete':
            _secure.remove(key);
            return null;
          default:
            return null;
        }
      },
    );
    await saveChildToken('child-token');
    await setChildModeActive(true);
  });
  tearDown(() => Analytics.debugSink = null);

  group('the policy decides what is in the corner', () {
    test('band by band', () {
      expect(childCornerActivitiesFor('4-6', withGame: true),
          ['story', 'mission']);
      expect(childCornerActivitiesFor('7-9', withGame: true),
          ['story', 'game', 'mission']);
      expect(childCornerActivitiesFor('13-15', withGame: true),
          ['story', 'game', 'mission']);
      for (final age in ['prenatal-1', '0-3', '2-3', null, 'nonsense']) {
        expect(childCornerOffered(age), isFalse, reason: '$age');
        expect(childCornerOpeningSurface(age), isNull, reason: '$age');
      }
      expect(childCornerOpeningSurface('4-6'), 'story');
    });

    test('this launch: the game is off — every corner is story, then task',
        () {
      expect(kChildCornerGameEnabled, isFalse,
          reason: 'the games\' questions are written for parents');
      for (final band in kChildSurfacePolicy.keys) {
        if (!childCornerOffered(band)) continue;
        expect(childCornerActivitiesFor(band), ['story', 'mission'],
            reason: band);
      }
      expect(childCornerOffered('4-6'), isTrue);
      expect(childCornerOffered('16-18'), isTrue);
    });

    test('never more than the band allows, for every band', () {
      for (final entry in kChildSurfacePolicy.entries) {
        expect(entry.value,
            containsAll(childCornerActivitiesFor(entry.key, withGame: true)),
            reason: entry.key);
      }
    });

    testWidgets('a 4-6 child has no game in the corner — not a locked one',
        (t) async {
      await _pump(t, band: '4-6');
      expect(find.byType(ChildCornerScreen), findsOneWidget);
      expect(find.byKey(const ValueKey('child_corner_story')), findsOneWidget);
      expect(find.byKey(const ValueKey('child_corner_game')), findsNothing);
      expect(find.text('لعبة قصيرة'), findsNothing);
      expect(find.text('هنا حكاية قصيرة، ثم مهمة صغيرة بعيدًا عن الشاشة.'),
          findsOneWidget);
    });

    testWidgets('this launch: a 7-9 child gets the story and the task only',
        (t) async {
      await _pump(t);
      expect(find.byKey(const ValueKey('child_corner_story')), findsOneWidget);
      expect(find.byKey(const ValueKey('child_corner_game')), findsNothing);
      expect(find.text('لعبة قصيرة'), findsNothing);
      expect(find.text('هنا حكاية قصيرة، ثم مهمة صغيرة بعيدًا عن الشاشة.'),
          findsOneWidget);
    });

    testWidgets('game switched on: a 7-9 child has story, game and task',
        (t) async {
      await _pump(t, gameOn: true);
      expect(find.byKey(const ValueKey('child_corner_story')), findsOneWidget);
      expect(find.byKey(const ValueKey('child_corner_game')), findsOneWidget);
      expect(find.byKey(const ValueKey('child_corner_mission_card')),
          findsOneWidget);
    });

    testWidgets('game switched on, English: the Arabic-only games stay out',
        (t) async {
      await _pump(t, locale: const Locale('en'), gameOn: true);
      expect(find.byKey(const ValueKey('child_corner_story')), findsOneWidget);
      expect(find.byKey(const ValueKey('child_corner_game')), findsNothing);
    });
  });

  group('the hand-over gate', () {
    testWidgets('offers the corner first for 7-9, and not for 2-3', (t) async {
      Future<void> open(String band) async {
        final container = ProviderContainer(overrides: [
          tgClientProvider.overrideWithValue(_FakeClient()),
        ]);
        addTearDown(container.dispose);
        await t.pumpWidget(UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            key: ValueKey(band),
            locale: const Locale('ar'),
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: Builder(
              builder: (context) => TextButton(
                onPressed: () => Navigator.of(context).push(
                    AppRoutes.handoverGate(
                        childId: 7, childName: 'سارة', ageGroup: band)),
                child: const Text('open'),
              ),
            ),
          ),
        ));
        await t.tap(find.text('open'));
        await t.pumpAndSettle();
      }

      await open('7-9');
      final tiles = find.byWidgetPredicate((w) =>
          w is ListTile &&
          w.key is ValueKey<String> &&
          (w.key! as ValueKey<String>).value.startsWith('handover_'));
      expect(
          (t.widget<ListTile>(tiles.first).key! as ValueKey<String>).value,
          'handover_corner');
      expect(find.text('ركن الطفل'), findsOneWidget);

      await open('2-3');
      expect(find.byKey(const ValueKey('handover_corner')), findsNothing);
    });

    testWidgets('its line promises a game only when the corner has one',
        (t) async {
      for (final (locale, band, gameOn, line) in const [
        // This launch: no game, so no band's line promises one.
        (Locale('ar'), '7-9', false, 'حكاية قصيرة، ثم مهمة بعيدًا عن الشاشة'),
        (Locale('ar'), '13-15', false, 'حكاية قصيرة، ثم مهمة بعيدًا عن الشاشة'),
        (Locale('en'), '7-9', false,
            'A short story, then a task away from the screen'),
        // With the game switched on.
        (Locale('ar'), '7-9', true,
            'حكاية قصيرة أو لعبة، ثم مهمة بعيدًا عن الشاشة'),
        (Locale('ar'), '4-6', true, 'حكاية قصيرة، ثم مهمة بعيدًا عن الشاشة'),
        (Locale('en'), '7-9', true,
            'A short story, then a task away from the screen'),
      ]) {
        await t.pumpWidget(ProviderScope(
          key: ValueKey('$locale$band$gameOn'),
          overrides: [
            tgClientProvider.overrideWithValue(_FakeClient()),
            childCornerGameEnabledProvider.overrideWithValue(gameOn),
          ],
          child: MaterialApp(
            locale: locale,
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: HandoverGateScreen(
                childId: 7, childName: 'Sara', ageGroup: band),
          ),
        ));
        await t.pump();
        expect(find.text(line), findsOneWidget,
            reason: '$locale $band game=$gameOn');
      }
    });

    testWidgets('the corner opens its session on «story», in the corner',
        (t) async {
      await setChildModePin('2580');
      final client = _FakeClient();
      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(client),
      ]);
      addTearDown(container.dispose);
      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          locale: const Locale('en'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Builder(
            builder: (context) => TextButton(
              onPressed: () => Navigator.of(context).push(
                  AppRoutes.handoverGate(
                      childId: 7, childName: 'Sara', ageGroup: '4-6')),
              child: const Text('open'),
            ),
          ),
        ),
      ));
      await t.tap(find.text('open'));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('handover_corner')));
      await t.pumpAndSettle();
      for (final d in ['2', '5', '8', '0']) {
        await t.tap(find.text(d));
        await t.pump();
      }
      await t.pump(const Duration(milliseconds: 50));
      await t.pump(const Duration(seconds: 2));
      await t.pump(const Duration(milliseconds: 50));
      await t.pumpAndSettle();

      expect(client.sessions, ['story'],
          reason: 'the corner is not a server surface');
      final state = container.read(childModeProvider);
      expect(state.active, isTrue);
      expect(state.cornerBand, '4-6');
      expect(state.corner, isTrue);
    });
  });

  group('no coins, no points', () {
    testWidgets('the corner shows neither, and its game counts nothing',
        (t) async {
      final container = await _pump(t, gameOn: true);
      final corner = find.byType(ChildCornerScreen);
      expect(_textsUnder(t, corner).where(_digits.hasMatch), isEmpty);
      expect(
          find.byWidgetPredicate(
              (w) => w is BrandGlyph && w.icon == BrandIcon.coin),
          findsNothing);

      await _tap(t, 'child_corner_game');
      final runner = t.widget<EduGameRunner>(find.byType(EduGameRunner));
      expect(runner.quiet, isTrue);

      // A right answer: no score appears in the HUD, no star burst plays.
      final question = runner.questions.first;
      final right = question.options.indexWhere((o) => o.isCorrect);
      await t.tap(find.text(question.options[right].text));
      await t.pump(const Duration(milliseconds: 300));
      expect(
          find.descendant(
              of: find.byType(EduGameRunner),
              matching: find.byWidgetPredicate(
                  (w) => w is Text && RegExp(r'^\d+$').hasMatch(w.data ?? ''))),
          findsNothing,
          reason: 'the score is not drawn in the corner');
      await t.pump(const Duration(seconds: 2));

      // Leave from the pause menu: back in the corner, nothing credited.
      await t.tap(find.byIcon(Icons.pause));
      await t.pump();
      await t.tap(find.text('خروج'));
      await _settle(t);
      expect(find.byType(EduGameRunner), findsNothing);
      expect(container.read(coinsProvider).balance, 0);
      expect(_textsUnder(t, find.byType(ChildCornerScreen))
          .where(_digits.hasMatch), isEmpty);
    });
  });

  group('the session ends on the task', () {
    testWidgets('chosen: task, then «أعِد الجهاز إلى أهلك», session closed',
        (t) async {
      final client = _FakeClient();
      final container = await _pump(t, client: client);

      await _tap(t, 'child_corner_to_mission');
      expect(find.byKey(const ValueKey('child_corner_mission_step')),
          findsOneWidget);
      expect(find.text('اسقِ نبتة في البيت'), findsOneWidget);
      expect(find.text('أعِد الجهاز إلى أهلك — شكرًا لك'), findsNothing);
      // Billed as the task while it is read.
      expect(client.sessions, ['mission']);

      await _tap(t, 'child_corner_mission_go');
      final state = container.read(childModeProvider);
      expect(state.error, kChildModeHandedBack);
      expect(state.sessionId, isNull);
      expect(state.active, isTrue, reason: 'the way out is the PIN');
      expect(find.byType(ChildCornerScreen), findsOneWidget);
      expect(find.byKey(const ValueKey('child_corner_done')), findsOneWidget);
      expect(find.text('أعِد الجهاز إلى أهلك — شكرًا لك'), findsOneWidget);
      expect(find.text('مهمتك: اسقِ نبتة في البيت'), findsOneWidget);
      // Nothing else to tap but the frame's Exit.
      expect(find.byKey(const ValueKey('child_corner_story')), findsNothing);
      expect(find.byKey(const ValueKey('child_corner_game')), findsNothing);
    });

    testWidgets('this launch: the story read → the task comes up on its own',
        (t) async {
      await _pump(t);
      await _tap(t, 'child_corner_story');
      while (find.byKey(const ValueKey('child_corner_story_next'))
          .evaluate()
          .isNotEmpty) {
        await _tap(t, 'child_corner_story_next');
      }
      await _tap(t, 'child_corner_story_back');
      expect(find.byKey(const ValueKey('child_corner_mission_step')),
          findsOneWidget);
      expect(
          events.where((e) => e.$1 == 'child_corner_mission').single.$2,
          {'reason': 'all_done'});
    });

    testWidgets('game on: story and game done → the task comes up on its own',
        (t) async {
      await _pump(t, gameOn: true);
      await _tap(t, 'child_corner_story');
      while (find.byKey(const ValueKey('child_corner_story_next'))
          .evaluate()
          .isNotEmpty) {
        await _tap(t, 'child_corner_story_next');
      }
      await _tap(t, 'child_corner_story_back');
      expect(find.text('قرأناها معًا'), findsOneWidget);
      expect(find.text('أحببت القراءة معك.'), findsOneWidget);
      expect(find.byKey(const ValueKey('child_corner_mission_step')),
          findsNothing);

      await _tap(t, 'child_corner_game');
      await t.tap(find.byIcon(Icons.pause));
      await t.pump();
      await t.tap(find.text('خروج'));
      await _settle(t);

      expect(find.byKey(const ValueKey('child_corner_mission_step')),
          findsOneWidget);
      expect(
          events.where((e) => e.$1 == 'child_corner_mission').single.$2,
          {'reason': 'all_done'});
    });

    testWidgets('closing a story early does not count it as read', (t) async {
      await _pump(t, band: '4-6');
      await _tap(t, 'child_corner_story');
      await _tap(t, 'child_corner_story_close');
      expect(find.text('قرأناها معًا'), findsNothing);
      expect(find.byKey(const ValueKey('child_corner_mission_step')),
          findsNothing);
    });

    testWidgets('the time runs out → the task, and a calm line', (t) async {
      final container = await _pump(t);
      container.read(childModeProvider.notifier).state =
          container.read(childModeProvider).copyWith(remainingSeconds: 0);
      await _settle(t);
      expect(find.byKey(const ValueKey('child_corner_mission_step')),
          findsOneWidget);
      expect(find.text('اكتملت شمعتك، والآن إلى مهمتك.'), findsOneWidget);
      expect(events.where((e) => e.$1 == 'child_corner_mission').single.$2,
          {'reason': 'time'});
    });

    testWidgets('the session closes under the child → still the task',
        (t) async {
      final container = await _pump(t);
      await container
          .read(childModeProvider.notifier)
          .endSession(code: kChildModeBudgetSpent);
      await _settle(t);
      expect(find.byType(ChildCornerScreen), findsOneWidget,
          reason: 'not the generic hand-back screen: the task comes first');
      expect(find.byKey(const ValueKey('child_corner_mission_step')),
          findsOneWidget);
    });

    testWidgets('no task from the server → the corner\'s own, still last',
        (t) async {
      final client = _FakeClient()..mission = null;
      await _pump(t, client: client);
      await _tap(t, 'child_corner_to_mission');
      expect(find.text('سأرسم شيئًا رأيته اليوم'), findsOneWidget);
    });
  });

  group('the candle', () {
    test('only ever grows shorter, across surfaces', () {
      final clock = CandleClock()..observe(600);
      expect(clock.fraction, 1);
      clock.observe(300);
      expect(clock.fraction, .5);
      clock.observe(600); // a new surface with a fresh allowance
      expect(clock.fraction, .5);
      clock.observe(null);
      expect(clock.fraction, .5);
      clock.observe(60);
      expect(clock.fraction, closeTo(.1, 1e-9));
      clock.burnOut();
      expect(clock.fraction, 0);
    });

    testWidgets('is drawn shorter as the time goes, and says words only',
        (t) async {
      final container = await _pump(t);
      expect(find.byType(QuietTimeBar), findsNothing,
          reason: 'the frame does not draw a second clock in the corner');
      double height() => t
          .widget<PaperCandle>(find.byKey(const ValueKey('child_corner_candle')))
          .fraction;
      expect(height(), 1);
      expect(find.text('ما زالت مضيئة'), findsOneWidget);

      container.read(childModeProvider.notifier).state =
          container.read(childModeProvider).copyWith(remainingSeconds: 120);
      await _settle(t);
      expect(height(), closeTo(.2, 1e-9));
      expect(find.text('بقي قليل'), findsOneWidget);

      for (final s in _textsUnder(t, find.byType(CornerCandle))) {
        expect(_digits.hasMatch(s), isFalse, reason: s);
      }
      expect(PaperCandlePainter.stickShare(.2),
          lessThan(PaperCandlePainter.stickShare(1)));
    });

    testWidgets('words, never digits, in every state and both languages',
        (t) async {
      for (final locale in AppLocalizations.supportedLocales) {
        final l10n = lookupAppLocalizations(locale);
        for (final state in CandleState.values) {
          expect(_digits.hasMatch(candleWords(l10n, state)), isFalse);
        }
        expect(_digits.hasMatch(l10n.childCornerCandleLabel), isFalse);
      }
    });

    testWidgets('sways while motion is allowed', (t) async {
      await _pump(t);
      expect(
          t.state<PaperCandleState>(find.byType(PaperCandle)).swaying, isTrue);
    });

    testWidgets('stands perfectly still under reduced motion', (t) async {
      await _pump(t, reduceMotion: true);
      expect(
          t.state<PaperCandleState>(find.byType(PaperCandle)).swaying, isFalse);
      expect(
          t.state<NoorPresenceState>(find.byType(NoorPresence)).haloLooping,
          isFalse);
      // Nothing left ticking: the corner is still.
      await t.pump(const Duration(seconds: 1));
      expect(t.binding.hasScheduledFrame, isFalse);
    });

    testWidgets('no candle when the server gives no time', (t) async {
      await _pump(t, sessionId: null, remaining: null);
      expect(find.byType(CornerCandle), findsNothing);
    });
  });

  group('words', () {
    test('no tomorrow, streak, coins, points or loss in any corner string',
        () {
      final forbidden = RegExp(
        r'غد|بكرة|غدًا|سلسل|متتال|نقاط|نقطة|عملة|عملات|فاتك|فاتت|خسر|ضاع|أجر|ثواب|'
        r'tomorrow|streak|coin|point|missed|lost|reward',
        caseSensitive: false,
      );
      for (final file in ['lib/l10n/app_ar.arb', 'lib/l10n/app_en.arb']) {
        final arb = jsonDecode(File(file).readAsStringSync())
            as Map<String, dynamic>;
        final corner = {
          for (final e in arb.entries)
            if (e.key.startsWith('childCorner')) e.key: e.value as String,
        };
        expect(corner.length, greaterThan(25), reason: file);
        for (final e in corner.entries) {
          expect(forbidden.hasMatch(e.value), isFalse,
              reason: '$file ${e.key}: ${e.value}');
          expect(e.value.contains('بابا') || e.value.contains('ماما'), isFalse,
              reason: 'family-neutral: ${e.key}');
        }
      }
    });
  });

  group('measured, without personal data', () {
    testWidgets('open → pick → task → end', (t) async {
      await _pump(t);
      await _tap(t, 'child_corner_story');
      await _tap(t, 'child_corner_story_close');
      await _tap(t, 'child_corner_to_mission');
      await _tap(t, 'child_corner_mission_go');
      final corner = events.where((e) => e.$1.startsWith('child_corner'));
      expect(corner.map((e) => e.$1), [
        'child_corner_opened',
        'child_corner_pick',
        'child_corner_mission',
        'child_corner_ended',
      ]);
      expect(corner.first.$2, {'band': '7-9'});
      expect(corner.elementAt(1).$2?['kind'], 'story');
      expect(corner.last.$2, {'story': 0, 'game': 0});
      for (final e in corner) {
        expect('${e.$2}'.contains('سارة'), isFalse);
        expect('${e.$2}'.contains('7,'), isFalse);
      }
    });
  });

  test('the day\'s picks hold all day and move with the calendar', () {
    final morning = DateTime(2026, 10, 15, 7);
    final night = DateTime(2026, 10, 15, 23);
    final tomorrow = DateTime(2026, 10, 16, 7);
    final stories = [for (var i = 0; i < 5; i++) _story('s$i', 2)];
    expect(cornerStoryFor(stories, morning)!.id,
        cornerStoryFor(stories, night)!.id);
    expect(cornerStoryFor(stories, morning)!.id,
        isNot(cornerStoryFor(stories, tomorrow)!.id));
    expect(cornerStoryFor([_story('empty', 0)], morning), isNull);
    expect(cornerGames().map((g) => g.id),
        ['data_defender', 'healthy_hero', 'tree_of_deeds', 'emotion_maze']);
    expect(cornerGamesSpeak('ar'), isTrue);
    expect(cornerGamesSpeak('en'), isFalse);
  });
}
