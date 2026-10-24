/// «صورة حيّة» experiment (features/stories/experiment/).
///
/// Pins:
///   1. The arm: forced by the server's mode, else a stable 50/50 hash of the
///      device id (same id → same arm, every run); no id → still.
///   2. The mode: "ab" when the field is missing or unknown; remembered for
///      an offline launch.
///   3. The reader: the `static` arm shows the same painting with no motion
///      and no narrator cues; the `motion` arm moves and follows.
///   4. Events: opened → page viewed → finished, and closed early with the
///      last page — each with variant, story, language, narration and
///      reduce-motion; reduce-motion is reported as such.
///   5. «هل أعجبتك الحكاية؟»: three faces at the end, rated once per story
///      per device, never asked again, never in the way.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/program/data/story_models.dart';
import 'package:almorabbi/features/program/screens/story_reader_screen.dart';
import 'package:almorabbi/features/stories/experiment/story_experiment.dart';
import 'package:almorabbi/features/stories/living/living_picture.dart';
import 'package:almorabbi/features/stories/narration/story_narration.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/theme/app_colors.dart';
import 'package:almorabbi/theme/app_palette.dart';

Widget _host(Widget child, {bool still = false}) => ProviderScope(
  child: MaterialApp(
    locale: const Locale('ar'),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    theme: ThemeData(extensions: const [AppColors(AppPalette.light)]),
    home: Builder(
      builder: (context) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: still),
        child: child,
      ),
    ),
  ),
);

Story _maryam() => Story(
  id: 'maryam_toys',
  title: 'مريم وصندوق الألعاب',
  description: '',
  coverImage: '',
  themeColor: '0xFF0D9488',
  ageGroup: '3-6 سنوات',
  pages: [
    StoryPage(pageNumber: 1, text: 'في يوم ميلادها فرحت مريم.', image: ''),
    StoryPage(pageNumber: 2, text: 'جاءت فاطمة إلى مريم.', image: ''),
  ],
  discussionQuestions: const ['س١؟'],
  actionChallenge: 'تحدٍّ.',
);

StoryNarration _recorded(Story s) => StoryNarration(
  pages: [
    for (final p in s.pages)
      NarrationPage(
        audio: 'docs/stories/narration/ar/${s.id}_p${p.pageNumber}.m4a',
        text: p.text,
        sentences: [
          NarrationSentence(from: 0, to: p.text.length, start: 0, end: 6),
        ],
      ),
  ],
);

class _SilentPlayer implements NarrationPlayer {
  final _pos = StreamController<Duration>.broadcast();
  final _done = StreamController<void>.broadcast();
  @override
  Stream<Duration> get position => _pos.stream;
  @override
  Stream<void> get completed => _done.stream;
  @override
  Future<void> load(Uri uri) async {}
  @override
  Future<void> play() async {}
  @override
  Future<void> pause() async {}
  @override
  Future<void> stop() async {}
  @override
  Future<void> dispose() async {
    await _pos.close();
    await _done.close();
  }
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('the arm', () {
    test('the server can put everyone in one arm', () {
      expect(resolveStoryMotionArm(mode: 'motion', deviceId: 'x'), 'motion');
      expect(resolveStoryMotionArm(mode: ' STATIC ', deviceId: 'x'), 'static');
    });

    test('"ab": a stable, even split by device id', () {
      final ids = [for (var i = 0; i < 2000; i++) 'dev-$i-${i * 7919}'];
      final arms = [
        for (final id in ids) resolveStoryMotionArm(mode: 'ab', deviceId: id),
      ];
      final motion = arms.where((a) => a == 'motion').length;
      expect(motion, inInclusiveRange(900, 1100));
      // Same id, same arm.
      expect(
        resolveStoryMotionArm(mode: 'ab', deviceId: 'dev-1-7919'),
        resolveStoryMotionArm(mode: null, deviceId: 'dev-1-7919'),
      );
      expect(fnv1a32(''), 0x811c9dc5);
      expect(fnv1a32('a'), 0xe40c292c);
    });

    test('unknown modes are "ab"; no device id keeps the picture still', () {
      expect(resolveStoryMotionArm(mode: 'both', deviceId: null), 'static');
      expect(resolveStoryMotionArm(mode: null, deviceId: ''), 'static');
    });
  });

  group('the mode', () {
    test('missing or unknown field → "ab", and it is remembered', () async {
      expect(await storyMotionMode(Future.value({'x': 1})), 'ab');
      expect(
        await storyMotionMode(Future.value({'story_motion_mode': 'static'})),
        'static',
      );
      // Offline next time: the last thing the server said.
      expect(
        await storyMotionMode(Future.error(Exception('offline'))),
        'static',
      );
    });

    test('offline with nothing remembered → "ab"', () async {
      expect(await storyMotionMode(Future.error(Exception('offline'))), 'ab');
    });
  });

  group('the reader', () {
    Future<(List<(String, Map<String, Object?>)>, StoryReaderScreenState)> open(
      WidgetTester tester, {
      required String arm,
      bool still = false,
    }) async {
      tester.view.physicalSize = const Size(1080, 2340);
      tester.view.devicePixelRatio = 3;
      addTearDown(tester.view.reset);
      final events = <(String, Map<String, Object?>)>[];
      final s = _maryam();
      await tester.pumpWidget(
        _host(
          StoryReaderScreen(
            story: s,
            narrationLoader: (_, _) async => _recorded(s),
            playerFactory: _SilentPlayer.new,
            motionArm: arm,
            storyEvents: (name, params) => events.add((name, params)),
          ),
          still: still,
        ),
      );
      await tester.pump(const Duration(milliseconds: 300));
      return (
        events,
        tester.state<StoryReaderScreenState>(find.byType(StoryReaderScreen)),
      );
    }

    Future<void> settle(WidgetTester tester) async {
      for (var i = 0; i < 12; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
    }

    testWidgets('static: the same painting, still, with no cues', (
      tester,
    ) async {
      final (_, state) = await open(tester, arm: 'static');
      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      await tester.tap(find.text(l10n.storyListenWithNoor));
      await settle(tester);
      state.goTo(2);
      await settle(tester);
      final view = tester.widget<LivingPictureView>(
        find.byType(LivingPictureView),
      );
      expect(view.animate, isFalse);
      expect(view.cues, isNull);
      expect(state.motionArm, 'static');
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('motion: it moves and follows the narrator', (tester) async {
      final (_, state) = await open(tester, arm: 'motion');
      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      await tester.tap(find.text(l10n.storyListenWithNoor));
      await settle(tester);
      state.goTo(2);
      await settle(tester);
      final view = tester.widget<LivingPictureView>(
        find.byType(LivingPictureView),
      );
      expect(view.animate, isTrue);
      expect(view.cues, isNotNull);
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('events: opened, pages, finished — each with the arm and the '
        'reading conditions', (tester) async {
      final (events, state) = await open(tester, arm: 'motion', still: true);
      state.goTo(1);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      state.goTo(2);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      state.goTo(state.leaves.length - 1);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      final names = [for (final (n, _) in events) n];
      expect(names, [
        'story_opened',
        'story_page_viewed',
        'story_page_viewed',
        'story_finished',
      ]);
      for (final (_, p) in events) {
        expect(p['variant'], 'motion');
        expect(p['story_id'], 'maryam_toys');
        expect(p['lang'], 'ar');
        expect(p['narration_on'], isFalse);
        expect(p['reduce_motion'], isTrue);
      }
      expect([for (final (_, p) in events) p['page_index']], [null, 0, 1, 1]);
      // Finished: closing is not "early".
      await tester.pumpWidget(const SizedBox());
      expect(events.last.$1, 'story_finished');
    });

    testWidgets('closed early: the last page read', (tester) async {
      final (events, state) = await open(tester, arm: 'static', still: true);
      state.goTo(1);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      await tester.pumpWidget(const SizedBox());
      expect(events.last.$1, 'story_closed_early');
      expect(events.last.$2['page_index'], 0);
      expect(events.last.$2['variant'], 'static');
    });

    testWidgets('«هل أعجبتك الحكاية؟»: once per story per device', (
      tester,
    ) async {
      final (events, state) = await open(tester, arm: 'static', still: true);
      state.goTo(state.leaves.length - 1);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      expect(find.text(l10n.storyRateQuestion), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('story-rate-3')));
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      expect(find.text(l10n.storyRateThanks), findsOneWidget);
      final rated = events.where((e) => e.$1 == 'story_rated').single.$2;
      expect(rated['rating'], 3);
      expect(rated['variant'], 'static');
      expect(
        (await SharedPreferences.getInstance()).getBool(
          storyRatedKey('maryam_toys'),
        ),
        isTrue,
      );
      await tester.pumpWidget(const SizedBox());

      // The same story again: not asked.
      final (_, again) = await open(tester, arm: 'static', still: true);
      again.goTo(again.leaves.length - 1);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      expect(find.text(l10n.storyRateQuestion), findsNothing);
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('skipping the question closes the story as always', (
      tester,
    ) async {
      final (events, state) = await open(tester, arm: 'motion', still: true);
      state.goTo(state.leaves.length - 1);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      await tester.pumpWidget(const SizedBox());
      expect(events.any((e) => e.$1 == 'story_rated'), isFalse);
      expect(events.any((e) => e.$1 == 'story_closed_early'), isFalse);
    });
  });
}
