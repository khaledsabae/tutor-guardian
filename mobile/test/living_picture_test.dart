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

  group('every living story, on its real recordings', () {
    final library = [
      for (final s
          in (jsonDecode(File('assets/data/stories.json').readAsStringSync())
              as List))
        s as Map<String, dynamic>,
    ];
    final en = {
      for (final s
          in (jsonDecode(File('assets/data/stories_en.json').readAsStringSync())
              as List))
        (s as Map)['id']: s,
    };

    // A real painting is ~0.5–2 MB; the placeholder frames are ~8 KB.
    bool painted(String path) {
      final f = File('../$path');
      return f.existsSync() && f.lengthSync() > 100000;
    }

    test('a story is living exactly when all its pages and its cover are '
        'painted', () {
      for (final s in library) {
        final id = s['id'] as String;
        final pages = s['pages'] as List;
        final allPainted =
            painted('docs/stories/${id}_cover.png') &&
            [
              for (var i = 1; i <= pages.length; i++)
                painted('docs/stories/${id}_$i.png'),
            ].every((p) => p);
        expect(livingStories.contains(id), allPainted, reason: id);
      }
      // Every bundled story is painted now.
      expect(livingStories.length, library.length);
      expect(library.length, 19);
    });

    for (final s in library) {
      final id = s['id'] as String;
      if (!livingStories.contains(id)) continue;
      test('$id: every page has its painting, every region its words — '
          'each said on the page in ar or en', () {
        final ar = _manifest(id, 'ar'), enN = _manifest(id, 'en');
        final pages = s['pages'] as List;
        final enPages = en[id]!['pages'] as List;
        expect(livingPictureFor(id, pages.length), isNull);
        expect(livingCoverFor(id), 'docs/stories/${id}_cover.png');
        for (var i = 0; i < pages.length; i++) {
          // The recordings read the bundled text.
          expect(ar.pageFor(i, (pages[i] as Map)['text'] as String), isNotNull);
          expect(
            enN.pageFor(i, (enPages[i] as Map)['text'] as String),
            isNotNull,
          );
          final picture = livingPictureFor(id, i)!;
          expect(picture.image, 'docs/stories/${id}_${i + 1}.png');
          expect(picture.image, (pages[i] as Map)['image']);
          expect(picture.regions, isNotEmpty, reason: '$id page ${i + 1}');
          for (final r in picture.regions) {
            expect(r.cue, isNotEmpty, reason: '$id page ${i + 1} ${r.name}');
            for (final w in r.cue) {
              final said = [ar, enN].any(
                (n) => wordCuesFor(
                  [
                    [w],
                  ],
                  n.pages[i].text,
                  n.pages[i].sentences,
                ).isNotEmpty,
              );
              expect(
                said,
                isTrue,
                reason: '$id page ${i + 1} ${r.name}: «$w» is never said',
              );
            }
          }
        }
      });
    }

    test('a story the app does not know keeps the paper-cut scenes', () {
      expect(livingPictureFor('not_a_story', 0), isNull);
      expect(livingCoverFor('not_a_story'), isNull);
    });
  });

  test('the camera frames every region within the picture, ≤ max zoom', () {
    expect(livingStories, isNotEmpty);
    for (final id in livingStories) {
      for (var i = 0; livingPictureFor(id, i) != null; i++) {
        for (final r in livingPictureFor(id, i)!.regions) {
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
