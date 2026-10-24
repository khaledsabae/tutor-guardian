/// «صورة حيّة» — the original painted pages, alive (living_picture.dart).
///
/// Pins:
///   1. The word engine: Arabic prefixes and a closed list of endings, `=`
///      for an exact word, English plurals — and broken narration gives no
///      cues instead of an error.
///   2. Every cue word on the sample pages is said on its page in Arabic or
///      English, on the real recordings (test/fixtures/narration/, copied
///      from the server), and every region with cues is named at least once.
///   3. The camera never goes past kMaxLivingZoom and never frames outside
///      the picture.
///   4. Reduced motion: the still painting, whole — no ticker, no zoom, no
///      particles, and the narrator's words move nothing.
///   5. With motion: a named region takes the camera, and lets it go.
///   6. The reader shows the living picture only where the catalogue has one,
///      and follows only a recording of the page's exact text.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/story_models.dart';
import 'package:almorabbi/features/program/screens/story_reader_screen.dart';
import 'package:almorabbi/features/stories/living/living_picture.dart';
import 'package:almorabbi/features/stories/living/living_picture_catalog.dart';
import 'package:almorabbi/features/stories/narration/story_narration.dart';
import 'package:almorabbi/features/stories/narration/word_cues.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/theme/app_colors.dart';
import 'package:almorabbi/theme/app_palette.dart';

StoryNarration _manifest(String id, String lang) => StoryNarration.tryParse(
  jsonDecode(
    File('test/fixtures/narration/${id}_$lang.json').readAsStringSync(),
  ),
)!;

List<NarrationSentence> _even(String text, double seconds) => [
  NarrationSentence(from: 0, to: text.length, start: 0, end: seconds),
];

Widget _host(Widget child, {bool still = false}) => ProviderScope(
  child: MaterialApp(
    locale: const Locale('ar'),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    theme: ThemeData(extensions: const [AppColors(AppPalette.light)]),
    home: Builder(
      builder: (context) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: still),
        child: Scaffold(
          body: Center(child: SizedBox(width: 300, child: child)),
        ),
      ),
    ),
  ),
);

void main() {
  group('word cues', () {
    List<int> named(List<List<String>> t, String text) => [
      for (final c in wordCuesFor(t, text, _even(text, 10))) c.target,
    ];

    test('Arabic prefixes and endings; a stem is not a prefix match', () {
      expect(
        named([
          ['هر'],
        ], 'ذهب إلى الهرّ ورأى هِرّاً'),
        [0, 0],
      );
      expect(
        named([
          ['هر'],
        ], 'هرب الولد'),
        isEmpty,
      );
      expect(
        named([
          ['فاطم'],
        ], 'قالت لفاطمة'),
        [0],
      );
      expect(
        named([
          ['اخفت'],
        ], 'فأخفتها وراء ظهرها'),
        [0],
      );
    });

    test('`=` is an exact word', () {
      expect(
        named([
          ['=والد'],
        ], 'قال والده'),
        isEmpty,
      );
      expect(
        named([
          ['=والد'],
        ], 'ابتسم الوالد'),
        [0],
      );
    });

    test('English plurals and possessives', () {
      expect(
        named([
          ['toy'],
        ], 'her toys'),
        [0],
      );
      expect(
        named([
          ['fatimah'],
        ], 'Fatimah’s face'),
        [0],
      );
    });

    test('broken narration: no cues, no error', () {
      const t = 'جاءت فاطمة';
      expect(
        wordCuesFor(
          [
            ['فاطم'],
          ],
          t,
          const [],
        ),
        isEmpty,
      );
      expect(
        wordCuesFor(
          [
            ['فاطم'],
          ],
          t,
          const [
            NarrationSentence(from: 0, to: 999, start: 0, end: 3),
            NarrationSentence(from: 0, to: 4, start: 2, end: 2),
          ],
        ),
        isEmpty,
      );
    });
  });

  group('the sample pages, on their real recordings', () {
    final ar = _manifest('maryam_toys', 'ar');
    final en = _manifest('maryam_toys', 'en');

    test('the bundled text is what the recordings read', () {
      for (final (file, n) in [('stories.json', ar), ('stories_en.json', en)]) {
        final s =
            (jsonDecode(File('assets/data/$file').readAsStringSync()) as List)
                .cast<Map<String, dynamic>>()
                .firstWhere((s) => s['id'] == 'maryam_toys');
        final pages = s['pages'] as List;
        for (var i = 0; i < pages.length; i++) {
          expect(n.pageFor(i, (pages[i] as Map)['text'] as String), isNotNull);
        }
      }
    });

    for (final page in [1, 4]) {
      test('page ${page + 1}: every cue word is said (ar or en), '
          'every region is named', () {
        final picture = livingPictureFor('maryam_toys', page)!;
        expect(picture.regions, isNotEmpty);
        for (final r in picture.regions) {
          for (final w in r.cue) {
            final said = [ar, en].any(
              (n) => wordCuesFor(
                [
                  [w],
                ],
                n.pages[page].text,
                n.pages[page].sentences,
              ).isNotEmpty,
            );
            expect(said, isTrue, reason: '${r.name}: «$w» is never said');
          }
        }
        for (final n in [ar, en]) {
          final cues = wordCuesFor(
            [for (final r in picture.regions) r.cue],
            n.pages[page].text,
            n.pages[page].sentences,
          );
          expect(cues, isNotEmpty);
          for (final c in cues) {
            expect(c.at, inInclusiveRange(0, n.pages[page].sentences.last.end));
          }
        }
      });
    }

    test(
      'every page image is bundled, and nothing past the story is drawn',
      () {
        final pubspec = File('pubspec.yaml').readAsStringSync();
        expect(pubspec, contains('- assets/stories_art/'));
        for (var i = 0; i < 6; i++) {
          final p = livingPictureFor('maryam_toys', i)!;
          expect(File(p.image).existsSync(), isTrue, reason: p.image);
          if (p.layered) {
            expect(File(p.background!).existsSync(), isTrue);
            expect(File(p.foreground!).existsSync(), isTrue);
          }
        }
        expect(livingPictureFor('maryam_toys', 6), isNull);
        expect(livingPictureFor('not_a_story', 0), isNull);
        expect(livingPictureFor('kitten_kindness', 0), isNull);
      },
    );
  });

  test('the camera frames every region within the picture, ≤ max zoom', () {
    for (var i = 0; i < 6; i++) {
      for (final r in livingPictureFor('maryam_toys', i)!.regions) {
        final f = LivingPicture.frame(r.rect);
        expect(f.zoom, lessThanOrEqualTo(kMaxLivingZoom));
        expect(f.zoom, greaterThanOrEqualTo(1));
        final half = .5 / f.zoom;
        expect(f.centre.dx - half, greaterThanOrEqualTo(-1e-9));
        expect(f.centre.dx + half, lessThanOrEqualTo(1 + 1e-9));
        expect(f.centre.dy - half, greaterThanOrEqualTo(-1e-9));
        expect(f.centre.dy + half, lessThanOrEqualTo(1 + 1e-9));
      }
    }
  });

  group('the view', () {
    final picture = livingPictureFor('maryam_toys', 1)!;
    final text = _manifest('maryam_toys', 'ar').pages[1].text;
    final sentences = _manifest('maryam_toys', 'ar').pages[1].sentences;
    final cues = wordCuesFor(
      [for (final r in picture.regions) r.cue],
      text,
      sentences,
    );

    Future<void> runTo(
      WidgetTester tester,
      ValueNotifier<Duration> clock,
      double from,
      double to,
    ) async {
      for (var t = from; t <= to; t += .2) {
        clock.value = Duration(milliseconds: (t * 1000).round());
        await tester.pump(const Duration(milliseconds: 200));
      }
    }

    testWidgets('reduced motion: the still painting, and words move nothing', (
      tester,
    ) async {
      final clock = ValueNotifier(Duration.zero);
      addTearDown(clock.dispose);
      await tester.pumpWidget(
        _host(
          LivingPictureView(
            picture: picture,
            cues: LivingCues(cues: cues, clock: clock),
          ),
          still: true,
        ),
      );
      final state = tester.state<LivingPictureViewState>(
        find.byType(LivingPictureView),
      );
      await runTo(tester, clock, 0, sentences.last.end);
      expect(state.moving, isFalse);
      expect(state.zoom, 1);
      expect(state.centre, const Offset(.5, .5));
      expect(state.focus, isNull);
      expect(state.particles, 0);
    });

    testWidgets('with motion: a named region takes the camera, then lets go', (
      tester,
    ) async {
      final clock = ValueNotifier(Duration.zero);
      addTearDown(clock.dispose);
      await tester.pumpWidget(
        _host(
          LivingPictureView(
            picture: picture,
            cues: LivingCues(cues: cues, clock: clock),
          ),
        ),
      );
      final state = tester.state<LivingPictureViewState>(
        find.byType(LivingPictureView),
      );
      expect(state.moving, isTrue);
      final first = cues.first;
      await runTo(tester, clock, 0, first.at + .3);
      expect(state.focus, first.target);
      for (var k = 0; k < 10; k++) {
        await tester.pump(const Duration(milliseconds: 100));
        expect(state.zoom, lessThanOrEqualTo(kMaxLivingZoom + 1e-9));
      }
      // No more words for a while: the camera goes back to drifting.
      for (var k = 0; k < 40; k++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(state.focus, isNull);
      expect(state.particles, greaterThan(0)); // the dust in the light
      await tester.pumpWidget(const SizedBox());
    });
  });

  group('the reader', () {
    Story story(List<String> texts) => Story(
      id: 'maryam_toys',
      title: 'مريم وصندوق الألعاب',
      description: '',
      coverImage: '',
      themeColor: '0xFF0D9488',
      ageGroup: '3-6 سنوات',
      pages: [
        for (var i = 0; i < texts.length; i++)
          StoryPage(pageNumber: i + 1, text: texts[i], image: ''),
      ],
      discussionQuestions: const ['س١؟'],
      actionChallenge: 'تحدٍّ.',
    );

    Future<LivingPictureView> open(
      WidgetTester tester,
      Story s,
      StoryNarration n,
    ) async {
      tester.view.physicalSize = const Size(1080, 2340);
      tester.view.devicePixelRatio = 3;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        _host(
          StoryReaderScreen(
            story: s,
            narrationLoader: (_, _) async => n,
            playerFactory: _SilentPlayer.new,
          ),
          still: true,
        ),
      );
      await tester.pump(const Duration(milliseconds: 300));
      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      final listen = find.text(l10n.storyListenWithNoor);
      await tester.tap(
        listen.evaluate().isNotEmpty
            ? listen
            : find.text(l10n.storyReadTogether),
      );
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      // Page 2 is the one with regions.
      tester
          .state<StoryReaderScreenState>(find.byType(StoryReaderScreen))
          .goTo(2);
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      return tester.widget<LivingPictureView>(find.byType(LivingPictureView));
    }

    StoryNarration recorded(List<String> texts) => StoryNarration(
      pages: [
        for (var i = 0; i < texts.length; i++)
          NarrationPage(
            audio: 'docs/stories/narration/ar/maryam_toys_p${i + 1}.m4a',
            text: texts[i],
            sentences: [
              NarrationSentence(from: 0, to: texts[i].length, start: 0, end: 6),
            ],
          ),
      ],
    );

    testWidgets('a recording of this page: the picture follows it', (
      tester,
    ) async {
      final texts = ['الأولى', 'جاءت فاطمة إلى مريم'];
      final view = await open(tester, story(texts), recorded(texts));
      expect(view.cues, isNotNull);
    });

    testWidgets('a recording of other words: the picture, no cues', (
      tester,
    ) async {
      final texts = ['الأولى', 'جاءت فاطمة إلى مريم'];
      final view = await open(
        tester,
        story(texts),
        recorded(['الأولى', 'نص قديم سُجّل قبل التصحيح']),
      );
      expect(view.cues, isNull);
    });
  });
}

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
