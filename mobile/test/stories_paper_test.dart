/// «القصص» — the paper-cut reader and shelf (2026-10, docs/STORIES_AUDIT.md).
///
/// Pins:
///   1. A story opens on its own first leaf — no adhkar gate in front of it —
///      and the leaves run intro → pages (+ the pause after its page) → end.
///   2. Every bundled story, Arabic and English, has a drawn scene for every
///      page, and every piece a scene names is a file in the bundle.
///   3. Pauses are well-formed and the same in both languages.
///   4. Narration plays only text it recorded, lights the sentence being
///      heard, and turns the page when a recording ends.
///   5. The page text reads in dark mode (the old reader painted #2D2D2D on
///      a surface that turns dark).
///   6. Reduced motion holds the scene still.
///   7. The shelf filters by age and shows every story's drawn cover.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/story_models.dart';
import 'package:almorabbi/features/program/screens/story_bookshelf_screen.dart';
import 'package:almorabbi/features/program/screens/story_reader_screen.dart';
import 'package:almorabbi/features/stories/narration/story_narration.dart';
import 'package:almorabbi/features/stories/scene/story_scene.dart';
import 'package:almorabbi/features/stories/scene/story_scene_catalog.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/theme/app_colors.dart';
import 'package:almorabbi/theme/app_palette.dart';

List<Story> _bundled(String file) =>
    (jsonDecode(File('assets/data/$file').readAsStringSync()) as List)
        .map((j) => Story.fromJson(j as Map<String, dynamic>))
        .toList();

Story _story({StoryPause? pause, int pages = 3}) => Story(
      id: 'layla_star',
      title: 'ليلى ونجمتها الصغيرة',
      description: '',
      coverImage: '',
      themeColor: '0xFF0D9488',
      ageGroup: '3-6 سنوات',
      pages: [
        for (var i = 1; i <= pages; i++)
          StoryPage(pageNumber: i, text: 'جملة أولى $i. جملة ثانية $i.', image: ''),
      ],
      discussionQuestions: const ['س١؟', 'س٢؟', 'س٣؟'],
      actionChallenge: 'تحدٍّ صغير.',
      pause: pause,
    );

Widget _host(Widget child, {AppPalette palette = AppPalette.light, bool still = false}) {
  return ProviderScope(
    child: MaterialApp(
      locale: const Locale('ar'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      theme: ThemeData(
        brightness: palette.brightness,
        extensions: [AppColors(palette)],
      ),
      home: Builder(
        builder: (context) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: still),
          child: child,
        ),
      ),
    ),
  );
}

/// A player that does what the test tells it to.
class _FakePlayer implements NarrationPlayer {
  final positions = StreamController<Duration>.broadcast();
  final ends = StreamController<void>.broadcast();
  final loaded = <Uri>[];
  bool playing = false;

  @override
  Stream<Duration> get position => positions.stream;
  @override
  Stream<void> get completed => ends.stream;
  @override
  Future<void> load(Uri uri) async => loaded.add(uri);
  @override
  Future<void> play() async => playing = true;
  @override
  Future<void> pause() async => playing = false;
  @override
  Future<void> stop() async => playing = false;
  @override
  Future<void> dispose() async {
    await positions.close();
    await ends.close();
  }
}

StoryNarration _narrationFor(Story story) => StoryNarration(pages: [
      for (final p in story.pages)
        NarrationPage(
          audio: 'docs/stories/narration/ar/${story.id}_p${p.pageNumber}.m4a',
          text: p.text,
          sentences: [
            NarrationSentence(
                from: 0, to: p.text.indexOf('.') + 1, start: 0, end: 2),
            NarrationSentence(
                from: p.text.indexOf('.') + 2,
                to: p.text.length,
                start: 2.4,
                end: 4),
          ],
        ),
    ]);

/// A phone-sized screen (360×780 dp), so the intro's buttons are on it.
void _phone(WidgetTester tester) {
  tester.view.physicalSize = const Size(1080, 2340);
  tester.view.devicePixelRatio = 3;
  addTearDown(tester.view.reset);
}

void main() {
  group('leaves', () {
    test('intro, pages, the pause after its page, end', () {
      final story = _story(
        pause: const StoryPause(afterPage: 2, question: 'ماذا ستفعل؟', options: ['أ', 'ب']),
      );
      final leaves = storyLeaves(story);
      expect(leaves.map((l) => l.runtimeType.toString()).toList(),
          ['IntroLeaf', 'PageLeaf', 'PageLeaf', 'PauseLeaf', 'PageLeaf', 'EndLeaf']);
    });

    test('a pause after the last page is dropped, not shown after the end', () {
      final story = _story(
        pause: const StoryPause(afterPage: 3, question: '؟', options: ['أ', 'ب']),
      );
      expect(storyLeaves(story).whereType<PauseLeaf>(), isEmpty);
    });

    test('a malformed pause is ignored, not fatal', () {
      expect(StoryPause.tryParse({'afterPage': 1, 'question': 'x'}), isNull);
      expect(StoryPause.tryParse({'afterPage': '1', 'question': 'x', 'options': ['a', 'b']}), isNull);
      expect(StoryPause.tryParse({'afterPage': 1, 'question': 'x', 'options': ['a']}), isNull);
      expect(StoryPause.tryParse({'afterPage': 1, 'question': 'x', 'options': ['a', 'b']}), isNotNull);
      // A caring index outside the options is dropped, not trusted.
      expect(StoryPause.tryParse({'afterPage': 1, 'question': 'x', 'options': ['a', 'b'], 'caring': 5})!.caring, isNull);
    });

    test('the nudge needs a caring option and words to say', () {
      const p = StoryPause(afterPage: 1, question: 'q', options: ['a', 'b'], caring: 0, affirm: 'yes', nudge: 'hmm?');
      expect(p.nudges(0), isFalse);
      expect(p.nudges(1), isTrue);
      expect(p.replyTo(0), 'yes');
      expect(p.replyTo(1), 'hmm?');
      const open = StoryPause(afterPage: 1, question: 'q', options: ['a', 'b'], affirm: 'yes');
      expect(open.nudges(1), isFalse);
      expect(open.replyTo(1), 'yes');
    });
  });

  group('the bundled library', () {
    final ar = _bundled('stories.json');
    final en = _bundled('stories_en.json');

    test('every story has a drawn scene for every page', () {
      for (final s in [...ar, ...en]) {
        expect(hasScenesFor(s.id), isTrue, reason: '${s.id} has no scenes');
        expect(scenePageCount(s.id), s.pages.length, reason: s.id);
      }
    });

    test('every piece a scene names is on disk and bundled', () {
      final pubspec = File('pubspec.yaml').readAsStringSync();
      expect(pubspec, contains('- assets/svg/stories/'));
      for (final s in ar) {
        final scenes = [
          coverSceneFor(s.id),
          for (var i = 0; i < s.pages.length; i++) sceneFor(s.id, i),
        ];
        for (final scene in scenes) {
          expect(File(scenePieceAsset(scene.backdrop)).existsSync(), isTrue,
              reason: '${s.id}: ${scene.backdrop}');
          expect(scene.backdrop, startsWith('bg_'));
          for (final l in scene.layers) {
            expect(File(scenePieceAsset(l.piece)).existsSync(), isTrue,
                reason: '${s.id}: ${l.piece}');
          }
        }
      }
    });

    test('every story has a pause, inside the story, the same in both languages', () {
      final enById = {for (final s in en) s.id: s};
      for (final s in ar) {
        final p = s.pause;
        expect(p, isNotNull, reason: s.id);
        expect(p!.afterPage, inInclusiveRange(1, s.pages.length - 1), reason: s.id);
        expect(p.options.length, 2, reason: s.id);
        final twin = enById[s.id]!.pause;
        expect(twin?.afterPage, p.afterPage, reason: s.id);
        expect(twin?.options.length, p.options.length, reason: s.id);
        // Gentle guidance, the same in both languages.
        expect(twin?.caring, p.caring, reason: s.id);
        expect(p.affirm, isNotNull, reason: '${s.id}: no affirmation');
        expect(twin?.affirm, isNotNull, reason: '${s.id}: no English affirmation');
        if (p.caring != null) {
          expect(p.nudge, isNotNull, reason: '${s.id}: a caring option needs a nudge');
          expect(twin?.nudge, isNotNull, reason: s.id);
          expect(p.nudge!.contains('؟'), isTrue, reason: '${s.id}: the nudge asks');
          expect(twin!.nudge!.contains('?'), isTrue, reason: s.id);
        }
      }
    });

    test('Noor never scores a child or promises a reward at the pause', () {
      for (final s in [...ar, ...en]) {
        final p = s.pause!;
        for (final line in [p.affirm, p.nudge]) {
          if (line == null) continue;
          for (final banned in [
            'خطأ', 'خاطئ', 'صح', 'صحيح', '✓', '✗', 'نقطة', 'نقاط', 'أجر', 'ثواب', 'الجنة',
            'wrong', 'correct', 'right answer', 'point', 'reward', 'Paradise',
          ]) {
            expect(line.contains(banned), isFalse, reason: '${s.id}: «$banned» in «$line»');
          }
        }
      }
    });

    test('no story text still teaches the corrections of the audit', () {
      final all = File('assets/data/stories.json').readAsStringSync();
      for (final gone in [
        'وعاء حليب', // cow's milk for a kitten
        'وجعلنا مسلمين', // a weak du'a presented as Sunnah
        'وتوضأ بماء بارد ليطفئ', // wudu for anger, from a weak hadith
        'وما نقص مال أو خير', // Muslim 2588 with words added
        'النظافة من الإيمان', // not a hadith in this wording
        'أعظم طريق لرضا الله', // a superlative promise
        'استأذن بأدب ثلاث مرات قبل', // the Sunnah turned around
      ]) {
        expect(all, isNot(contains(gone)), reason: gone);
      }
    });

    test('the shelf\'s age filter reads both digit systems', () {
      expect(ageRangeOf('3-6 سنوات'), (min: 3, max: 6));
      expect(ageRangeOf('٥–٨ سنوات'), (min: 5, max: 8));
      expect(ageRangeOf('Ages 4-7'), (min: 4, max: 7));
      expect(ageRangeOf('الروضة'), isNull);
      final young = ar.where((s) => storyMatchesFilter(s, StoryShelfFilter.young));
      final older = ar.where((s) => storyMatchesFilter(s, StoryShelfFilter.older));
      expect(young.every((s) => ageRangeOf(s.ageGroup)!.min <= 4), isTrue);
      expect(older.every((s) => ageRangeOf(s.ageGroup)!.max >= 7), isTrue);
      // The old «٧ سنوات فأكثر» chip matched any label with a 5, 7 or 8.
      expect(older.any((s) => s.ageGroup == '3-6 سنوات'), isFalse);
    });
  });

  group('narration', () {
    final story = _story();

    test('a page plays only the text it recorded', () {
      final n = _narrationFor(story);
      expect(n.pageFor(0, story.pages[0].text), isNotNull);
      expect(n.pageFor(0, '${story.pages[0].text} (corrected)'), isNull);
      expect(n.pageFor(9, story.pages[0].text), isNull);
    });

    test('sentenceAt follows the timings, and is null in the gap', () {
      final page = _narrationFor(story).pages.first;
      expect(page.sentenceAt(const Duration(milliseconds: 500)), 0);
      expect(page.sentenceAt(const Duration(milliseconds: 2200)), isNull);
      expect(page.sentenceAt(const Duration(seconds: 3)), 1);
    });

    test('a manifest with a range outside its text is rejected whole', () {
      expect(
        StoryNarration.tryParse({
          'pages': [
            {
              'audio': 'a.m4a',
              'text': 'قصير.',
              'sentences': [
                {'from': 0, 'to': 99, 'start': 0, 'end': 1},
              ],
            },
          ],
        }),
        isNull,
      );
    });
  });

  group('reader', () {
    testWidgets('opens on the story, not on an adhkar gate', (tester) async {
      _phone(tester);
      final story = _story();
      await tester.pumpWidget(_host(
        StoryReaderScreen(story: story, narrationLoader: (_, _) async => null),
        still: true,
      ));
      await tester.pump(const Duration(milliseconds: 300));
      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      expect(find.text(story.title), findsWidgets);
      expect(find.text(l10n.storyReadTogether), findsOneWidget);
      // No recording → no listen button, anywhere.
      expect(find.text(l10n.storyListenWithNoor), findsNothing);
      expect(find.textContaining('بِاسْمِكَ'), findsNothing);

      await tester.tap(find.text(l10n.storyReadTogether));
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      final state = tester.state<StoryReaderScreenState>(find.byType(StoryReaderScreen));
      expect(state.leaf, 1);
      expect(find.textContaining('جملة أولى 1'), findsOneWidget);
    });

    testWidgets('listening lights the sentence heard and turns the page at its end',
        (tester) async {
      final story = _story();
      final player = _FakePlayer();
      _phone(tester);
      await tester.pumpWidget(_host(
        StoryReaderScreen(
          story: story,
          narrationLoader: (_, _) async => _narrationFor(story),
          playerFactory: () => player,
        ),
        still: true,
      ));
      await tester.pump(const Duration(milliseconds: 300));
      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      await tester.tap(find.text(l10n.storyListenWithNoor));
      await tester.pumpAndSettle(const Duration(milliseconds: 100));

      final state = tester.state<StoryReaderScreenState>(find.byType(StoryReaderScreen));
      expect(state.leaf, 1);
      expect(state.listening, isTrue);
      expect(player.loaded.single.path, endsWith('layla_star_p1.m4a'));
      expect(player.playing, isTrue);

      player.positions.add(const Duration(seconds: 3));
      await tester.pump();
      expect(state.litSentence, 1);

      player.ends.add(null);
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      expect(state.leaf, 2);
      expect(player.loaded.last.path, endsWith('layla_star_p2.m4a'));
    });

    Future<StoryReaderScreenState> openPause(WidgetTester tester, StoryPause pause) async {
      _phone(tester);
      await tester.pumpWidget(_host(
        StoryReaderScreen(story: _story(pause: pause), narrationLoader: (_, _) async => null),
        still: true,
      ));
      await tester.pump(const Duration(milliseconds: 300));
      final state = tester.state<StoryReaderScreenState>(find.byType(StoryReaderScreen));
      state.goTo(2);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      return state;
    }

    const guided = StoryPause(
      afterPage: 1,
      question: 'ماذا ستفعل؟',
      options: ['أساعده', 'أمضي'],
      caring: 0,
      affirm: 'ما أرحم قلبك!',
      nudge: 'أفهم أنك مستعجل… كيف يشعر هو؟',
    );

    testWidgets('a caring choice is affirmed by name, and the story goes on', (tester) async {
      final state = await openPause(tester, guided);
      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      expect(find.text('ماذا ستفعل؟'), findsOneWidget);
      expect(find.text(l10n.storyContinue), findsNothing);
      await tester.tap(find.text('أساعده'));
      await tester.pump();
      expect(find.text('ما أرحم قلبك!'), findsOneWidget);
      expect(find.text(l10n.storyPauseChooseAgain), findsNothing);
      await tester.tap(find.text(l10n.storyContinue));
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      expect(state.leaf, 3);
    });

    testWidgets('the other choice gets a gentle question — choose again or read on, never a wall',
        (tester) async {
      final state = await openPause(tester, guided);
      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      await tester.tap(find.text('أمضي'));
      await tester.pump();
      expect(find.text('أفهم أنك مستعجل… كيف يشعر هو؟'), findsOneWidget);
      expect(find.text('ما أرحم قلبك!'), findsNothing);
      // Choose again clears the answer…
      await tester.tap(find.text(l10n.storyPauseChooseAgain));
      await tester.pump();
      expect(find.byKey(const ValueKey('story-pause-reply')), findsNothing);
      // …and reading on after a nudge is always allowed.
      await tester.tap(find.text('أمضي'));
      await tester.pump();
      await tester.tap(find.text(l10n.storyContinue));
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      expect(state.leaf, 3);
    });

    testWidgets('an open question affirms every answer',
        (tester) async {
      await openPause(tester, const StoryPause(
        afterPage: 1, question: 'ماذا أحببت؟', options: ['أ', 'ب'], affirm: 'ما أجمل هذا!'));
      await tester.tap(find.text('ب'));
      await tester.pump();
      expect(find.text('ما أجمل هذا!'), findsOneWidget);
      expect(find.text('أختار مرة أخرى'), findsNothing);
    });

    testWidgets('a pause with no words of its own falls back to the generic line', (tester) async {
      await openPause(tester, const StoryPause(afterPage: 1, question: '؟', options: ['أ', 'ب']));
      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      await tester.tap(find.text('ب'));
      await tester.pump();
      expect(find.text(l10n.storyPauseThanks), findsOneWidget);
    });

    testWidgets('page text is the palette ink — readable in dark mode', (tester) async {
      final story = _story();
      _phone(tester);
      await tester.pumpWidget(_host(
        StoryReaderScreen(story: story, narrationLoader: (_, _) async => null),
        palette: AppPalette.dark,
        still: true,
      ));
      await tester.pump(const Duration(milliseconds: 300));
      tester.state<StoryReaderScreenState>(find.byType(StoryReaderScreen)).goTo(1);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      final text = tester.widget<Text>(find.byKey(const ValueKey('story-text-0')));
      expect(text.textSpan!.style!.color, AppPalette.dark.ink);
    });
  });

  testWidgets('reduced motion holds a scene still', (tester) async {
    await tester.pumpWidget(_host(
      Scaffold(body: StorySceneView(scene: sceneFor('layla_star', 5))),
      still: true,
    ));
    expect(tester.state<StorySceneViewState>(find.byType(StorySceneView)).idleLooping, isFalse);

    await tester.pumpWidget(_host(
      Scaffold(body: StorySceneView(scene: sceneFor('layla_star', 4))),
    ));
    expect(tester.state<StorySceneViewState>(find.byType(StorySceneView)).idleLooping, isTrue);
  });

  testWidgets('the shelf shows every story and filters by age', (tester) async {
    final stories = _bundled('stories.json');
    tester.view.physicalSize = const Size(1080, 6000);
    tester.view.devicePixelRatio = 2.5;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_host(Scaffold(body: StoryShelf(stories: stories))));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byType(StoryBookCard), findsNWidgets(stories.length));
    final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
    await tester.tap(find.text(l10n.storyFilterOlder));
    await tester.pump(const Duration(milliseconds: 300));
    expect(
      find.byType(StoryBookCard),
      findsNWidgets(stories.where((s) => storyMatchesFilter(s, StoryShelfFilter.older)).length),
    );
  });
}
