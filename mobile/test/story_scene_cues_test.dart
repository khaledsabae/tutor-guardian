/// «صور أغنى» — the story scene follows the narrator (scene_cues.dart).
///
/// Pins:
///   1. Cue words match Arabic with its glued prefixes and a closed list of
///      endings (so «هر» catches «هراً», «بالهر» — never «هرب»), and English
///      plurals and possessives.
///   2. The prototype stories' cues land in BOTH recordings — Arabic and
///      English split the same page into different sentence counts — using
///      the real manifests (test/fixtures/narration/, copied from the server,
///      not written by hand).
///   3. Missing or broken narration means fewer cues, never an error: no
///      sentences, ranges outside the text, zero-length timings.
///   4. An unknown story falls back to the night sky, and gets camera beats
///      only.
///   5. Reduced motion: with cues live and the clock running past every
///      beat, nothing hops, enters, leans or loops — and every piece,
///      including the ones that would wait for the narrator, is on the page.
///   6. With motion: the pieces come on stage, a visitor waits for its word
///      and walks in when the clock reaches it, a named piece hops.
///   7. The reader hands the picture a narrator only for a recording of the
///      page's exact text, and only while listening.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/story_models.dart';
import 'package:almorabbi/features/program/screens/story_reader_screen.dart';
import 'package:almorabbi/features/stories/narration/story_narration.dart';
import 'package:almorabbi/features/stories/scene/scene_cues.dart';
import 'package:almorabbi/features/stories/scene/scene_people.g.dart';
import 'package:almorabbi/features/stories/scene/story_scene.dart';
import 'package:almorabbi/features/stories/scene/story_scene_catalog.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/theme/app_colors.dart';
import 'package:almorabbi/theme/app_palette.dart';

StoryNarration _manifest(String id, String lang) => StoryNarration.tryParse(
  jsonDecode(
    File('test/fixtures/narration/${id}_$lang.json').readAsStringSync(),
  ),
)!;

List<Story> _bundled(String file) =>
    (jsonDecode(File('assets/data/$file').readAsStringSync()) as List)
        .map((j) => Story.fromJson(j as Map<String, dynamic>))
        .toList();

/// A one-sentence page: the whole text heard evenly over [seconds].
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
        child: Scaffold(body: child),
      ),
    ),
  ),
);

/// A cat behind a girl who walks in when named.
final _scene = StoryScene('bg_bedroom', const [
  SceneLayer('girl', x: .3, cue: ['مريم', 'maryam']),
  SceneLayer('girl_friend', x: .7, cue: ['فاطم', 'fatimah'], entersOnCue: true),
  SceneLayer('kitten', x: .5, size: .4, cue: ['هر', 'cat']),
]);
const _text = 'جلست مريم تنتظر. ثم جاءت فاطمة ومعها الهر الصغير.';

List<SceneBeat> _pieceBeats(List<SceneBeat> b) =>
    b.where((x) => x.kind != SceneBeatKind.camera).toList();

void main() {
  group('cue words', () {
    List<String> named(String text) => [
      for (final b in _pieceBeats(beatsFor(_scene, text, _even(text, 10))))
        _scene.layers[b.layer].piece,
    ];

    test('Arabic: harakat, tanween, glued prefixes and endings', () {
      expect(named('رأى هِرّاً'), ['kitten']);
      expect(named('ذهب إلى الهر'), ['kitten']);
      expect(named('فرح بالهرّ'), ['kitten']);
      expect(named('قدّم للهر'), ['kitten']);
      expect(named('قالت لفاطمة'), ['girl_friend']);
    });

    test('a stem is not a prefix match: «هرب» is not «هر»', () {
      expect(named('هرب الولد مسرعاً'), isEmpty);
      expect(named('ظهرها'), isEmpty);
    });

    test('English plurals and possessives', () {
      expect(named('two cats sat'), ['kitten']);
      expect(named('Fatimah’s face lit up'), ['girl_friend']);
      expect(named('a category'), isEmpty);
    });

    test('normalizing unifies the alef forms and the final ya', () {
      expect(normalizeCueWord('إخفاء'), normalizeCueWord('اخفاء'));
      expect(normalizeCueWord('مستشفى'), 'مستشفي');
    });
  });

  group('every story, on its real recordings', () {
    final ids = [for (final s in _bundled('stories.json')) s.id];

    test('the library is all here: 19 stories, both languages', () {
      expect(ids.length, 19);
      for (final id in ids) {
        expect(hasScenesFor(id), isTrue, reason: id);
      }
    });

    for (final id in ids) {
      test('$id: every cue word is said on its page (ar or en), '
          'and every face turn in both', () {
        final ar = _manifest(id, 'ar'), en = _manifest(id, 'en');
        expect(ar.pages.length, scenePageCount(id));
        expect(en.pages.length, scenePageCount(id));
        for (var i = 0; i < scenePageCount(id); i++) {
          final scene = sceneFor(id, i);
          for (final l in scene.layers) {
            for (final w in l.cue) {
              final probe = StoryScene(scene.backdrop, [
                SceneLayer(l.piece, x: .5, cue: [w]),
              ]);
              final said = [ar, en].any(
                (n) => _pieceBeats(
                  beatsFor(probe, n.pages[i].text, n.pages[i].sentences),
                ).isNotEmpty,
              );
              expect(
                said,
                isTrue,
                reason: '$id page ${i + 1}: ${l.piece} «$w» is never said',
              );
            }
            if (l.faceTo != null) {
              expect(
                l.isPerson,
                isTrue,
                reason: '$id page ${i + 1} ${l.piece}',
              );
              expect(l.faceCue, isNotEmpty);
              for (final n in [ar, en]) {
                final turns =
                    beatsFor(
                      scene,
                      n.pages[i].text,
                      n.pages[i].sentences,
                    ).where(
                      (b) =>
                          b.kind == SceneBeatKind.face &&
                          scene.layers[b.layer] == l,
                    );
                expect(
                  turns.length,
                  1,
                  reason:
                      '$id page ${i + 1}: ${l.piece} turns once, '
                      'in every language',
                );
              }
            }
            if (l.face != SceneFace.neutral) {
              expect(l.isPerson, isTrue, reason: '$id: ${l.piece} has a face');
            }
          }
          for (final n in [ar, en]) {
            final page = n.pages[i];
            final beats = beatsFor(scene, page.text, page.sentences);
            for (var k = 1; k < beats.length; k++) {
              expect(beats[k].at, greaterThanOrEqualTo(beats[k - 1].at));
            }
            for (final b in beats) {
              expect(b.at, inInclusiveRange(0, page.sentences.last.end));
            }
            // One lean per sentence, whatever the count in this language.
            expect(
              beats.where((b) => b.kind == SceneBeatKind.camera).length,
              page.sentences.length,
            );
          }
        }
      });
    }

    test('5–8 pieces a page — something to point at and name', () {
      for (final id in ids) {
        for (var i = 0; i < scenePageCount(id); i++) {
          final n = sceneFor(id, i).layers.length;
          expect(n, inInclusiveRange(5, 8), reason: '$id page ${i + 1}');
        }
      }
    });

    test('the bundled text is what the recordings read', () {
      // If a story is corrected, the reader stops playing the old recording
      // (StoryNarration.pageFor) — and these fixtures need re-copying.
      for (final (file, lang) in [
        ('stories.json', 'ar'),
        ('stories_en.json', 'en'),
      ]) {
        for (final s in _bundled(file)) {
          final n = _manifest(s.id, lang);
          for (var i = 0; i < s.pages.length; i++) {
            expect(
              n.pageFor(i, s.pages[i].text),
              isNotNull,
              reason: '${s.id} $lang page ${i + 1}',
            );
          }
        }
      }
    });

    test('a visitor enters once, then only hops', () {
      final n = _manifest('maryam_toys', 'ar');
      final scene = sceneFor('maryam_toys', 1);
      final friend = scene.layers.indexWhere((l) => l.entersOnCue);
      final beats = beatsFor(
        scene,
        n.pages[1].text,
        n.pages[1].sentences,
      ).where((b) => b.layer == friend).toList();
      expect(beats.first.kind, SceneBeatKind.enter);
      expect(beats.skip(1).every((b) => b.kind == SceneBeatKind.pop), isTrue);
    });
  });

  group('cues tolerate missing or broken narration', () {
    test('no sentences → no beats', () {
      expect(beatsFor(_scene, _text, const []), isEmpty);
    });

    test(
      'ranges outside the text and empty timings are skipped, not fatal',
      () {
        final beats = beatsFor(_scene, _text, [
          const NarrationSentence(from: 0, to: 9999, start: 0, end: 4),
          const NarrationSentence(from: 40, to: 10, start: 4, end: 8),
          const NarrationSentence(from: 0, to: 10, start: 3, end: 3),
        ]);
        expect(beats, isEmpty);
      },
    );

    test('a recording of other words cues nothing it does not say', () {
      const other = 'نص آخر تماماً لا يذكر أحداً.';
      expect(_pieceBeats(beatsFor(_scene, other, _even(other, 5))), isEmpty);
    });

    test('a story the catalogue does not know: the night sky, camera only', () {
      expect(hasScenesFor('not_a_story'), isFalse);
      expect(sceneFor('not_a_story', 3), same(fallbackScene));
      final beats = beatsFor(fallbackScene, _text, _even(_text, 6));
      expect(beats, isNotEmpty);
      expect(beats.every((b) => b.kind == SceneBeatKind.camera), isTrue);
    });
  });

  group('the scene', () {
    SceneCues cues(ValueNotifier<Duration> clock) => SceneCues(
      beats: beatsFor(_scene, _text, _even(_text, 10)),
      clock: clock,
    );

    Future<void> runClock(
      WidgetTester tester,
      ValueNotifier<Duration> clock,
      double seconds,
    ) async {
      for (var t = 0.0; t <= seconds; t += .25) {
        clock.value = Duration(milliseconds: (t * 1000).round());
        await tester.pump(const Duration(milliseconds: 250));
      }
    }

    testWidgets('reduced motion: cues live, clock running — a still picture', (
      tester,
    ) async {
      final clock = ValueNotifier(Duration.zero);
      addTearDown(clock.dispose);
      await tester.pumpWidget(
        _host(
          StorySceneView(scene: _scene, staged: true, cues: cues(clock)),
          still: true,
        ),
      );
      final state = tester.state<StorySceneViewState>(
        find.byType(StorySceneView),
      );
      for (var i = 0; i < _scene.layers.length; i++) {
        expect(state.shows(i), isTrue, reason: _scene.layers[i].piece);
      }
      expect(state.entrance, 1);
      await runClock(tester, clock, 10);
      expect(state.cueing, isFalse);
      expect(state.idleLooping, isFalse);
      for (var i = 0; i < _scene.layers.length; i++) {
        expect(state.shows(i), isTrue);
      }
    });

    testWidgets('with motion: on stage, the visitor waits for its word, '
        'the named piece hops', (tester) async {
      final clock = ValueNotifier(Duration.zero);
      addTearDown(clock.dispose);
      final sceneCues = cues(clock);
      await tester.pumpWidget(
        _host(StorySceneView(scene: _scene, staged: true, cues: sceneCues)),
      );
      final state = tester.state<StorySceneViewState>(
        find.byType(StorySceneView),
      );
      await tester.pump(const Duration(milliseconds: 100));
      expect(state.entrance, inExclusiveRange(0, 1));
      await tester.pump(const Duration(seconds: 2));
      expect(state.entrance, 1);

      const friend = 1;
      final enter = sceneCues.beats.firstWhere(
        (b) => b.kind == SceneBeatKind.enter,
      );
      expect(enter.layer, friend);
      expect(state.shows(friend), isFalse);
      expect(state.shows(0), isTrue);

      await runClock(tester, clock, enter.at - .3);
      expect(state.shows(friend), isFalse);
      await runClock(tester, clock, enter.at + .3);
      expect(state.shows(friend), isTrue);
      expect(state.cueing, isTrue);

      // The narrator stops (pause): nothing waits any more.
      await tester.pumpWidget(
        _host(StorySceneView(scene: _scene, staged: true)),
      );
      for (var i = 0; i < _scene.layers.length; i++) {
        expect(state.shows(i), isTrue);
      }
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('a page not yet turned to keeps its pieces off stage', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(StorySceneView(scene: _scene, staged: true, active: false)),
      );
      final state = tester.state<StorySceneViewState>(
        find.byType(StorySceneView),
      );
      await tester.pump(const Duration(seconds: 1));
      expect(state.entrance, 0);
      await tester.pumpWidget(
        _host(StorySceneView(scene: _scene, staged: true)),
      );
      await tester.pump(const Duration(seconds: 2));
      expect(state.entrance, 1);
      await tester.pumpWidget(const SizedBox());
    });
  });

  group('faces', () {
    test('every person has every face, and nothing else gets one', () {
      for (final MapEntry(key: piece) in scenePeople.entries) {
        expect(
          File(scenePieceAsset(piece)).existsSync(),
          isTrue,
          reason: piece,
        );
        for (final f in SceneFace.values) {
          final asset = sceneFaceAsset(piece, f)!;
          expect(File(asset).existsSync(), isTrue, reason: asset);
        }
      }
      for (final piece in [
        'kitten',
        'tree',
        'toy_chest',
        'bed_girl',
        'sujood',
      ]) {
        expect(sceneFaceAsset(piece, SceneFace.happy), isNull, reason: piece);
      }
    });

    const turning = StoryScene('bg_bedroom', [
      SceneLayer(
        'girl',
        x: .3,
        face: SceneFace.sad,
        faceTo: SceneFace.happy,
        faceCue: ['قررت', 'decided'],
      ),
      SceneLayer('toy_chest', x: .6, size: .34),
    ]);
    const said = 'كانت حزينة ثم فكرت وقررت أن تشارك.';
    SceneCues turnCues(ValueNotifier<Duration> clock) =>
        SceneCues(beats: beatsFor(turning, said, _even(said, 8)), clock: clock);

    Future<void> runTo(
      WidgetTester tester,
      ValueNotifier<Duration> clock,
      double seconds,
    ) async {
      for (var t = 0.0; t <= seconds; t += .25) {
        clock.value = Duration(milliseconds: (t * 1000).round());
        await tester.pump(const Duration(milliseconds: 250));
      }
    }

    test('the turn is timed at its word', () {
      final turn = turnCues(
        ValueNotifier(Duration.zero),
      ).beats.singleWhere((b) => b.kind == SceneBeatKind.face);
      expect(turn.layer, 0);
      expect(turn.at, closeTo(8 * said.indexOf('وقررت') / said.length, .01));
    });

    testWidgets('with motion: sad until the word, then happy; '
        'the narrator stops → the page’s own face', (tester) async {
      final clock = ValueNotifier(Duration.zero);
      addTearDown(clock.dispose);
      await tester.pumpWidget(
        _host(StorySceneView(scene: turning, cues: turnCues(clock))),
      );
      final state = tester.state<StorySceneViewState>(
        find.byType(StorySceneView),
      );
      expect(state.faceOf(0), SceneFace.sad);
      await runTo(tester, clock, 3);
      expect(state.faceOf(0), SceneFace.sad);
      await runTo(tester, clock, 7);
      expect(state.faceOf(0), SceneFace.happy);

      await tester.pumpWidget(_host(const StorySceneView(scene: turning)));
      expect(state.faceOf(0), SceneFace.sad);
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('reduced motion: the face never turns', (tester) async {
      final clock = ValueNotifier(Duration.zero);
      addTearDown(clock.dispose);
      await tester.pumpWidget(
        _host(
          StorySceneView(scene: turning, cues: turnCues(clock)),
          still: true,
        ),
      );
      final state = tester.state<StorySceneViewState>(
        find.byType(StorySceneView),
      );
      await runTo(tester, clock, 8);
      expect(state.faceOf(0), SceneFace.sad);
      expect(state.cueing, isFalse);
    });
  });

  group('the reader', () {
    Story story(String text) => Story(
      id: 'maryam_toys',
      title: 'مريم وصندوق الألعاب',
      description: '',
      coverImage: '',
      themeColor: '0xFF0D9488',
      ageGroup: '3-6 سنوات',
      pages: [
        for (var i = 1; i <= 6; i++)
          StoryPage(pageNumber: i, text: '$text $i', image: ''),
      ],
      discussionQuestions: const ['س١؟'],
      actionChallenge: 'تحدٍّ.',
    );

    StoryNarration recorded(Story s, {String? textOverride}) => StoryNarration(
      pages: [
        for (final p in s.pages)
          NarrationPage(
            audio: 'docs/stories/narration/ar/${s.id}_p${p.pageNumber}.m4a',
            text: textOverride ?? p.text,
            sentences: [
              NarrationSentence(
                from: 0,
                to: (textOverride ?? p.text).length,
                start: 0,
                end: 6,
              ),
            ],
          ),
      ],
    );

    Future<StorySceneView> listenToFirstPage(
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
      if (listen.evaluate().isNotEmpty) {
        await tester.tap(listen);
      } else {
        await tester.tap(find.text(l10n.storyReadTogether));
      }
      await tester.pumpAndSettle(const Duration(milliseconds: 100));
      return tester.widget<StorySceneView>(find.byType(StorySceneView).last);
    }

    testWidgets('a recording of this page: the picture follows it', (
      tester,
    ) async {
      final s = story('جاءت فاطمة إلى مريم ومعها الهر');
      final view = await listenToFirstPage(tester, s, recorded(s));
      expect(view.staged, isTrue);
      expect(view.cues, isNotNull);
      expect(view.cues!.beats.any((b) => b.kind == SceneBeatKind.pop), isTrue);
    });

    testWidgets('a recording of other words: no cues, every piece there', (
      tester,
    ) async {
      final s = story('جاءت فاطمة إلى مريم');
      final view = await listenToFirstPage(
        tester,
        s,
        recorded(s, textOverride: 'نص قديم سُجّل قبل التصحيح'),
      );
      expect(view.cues, isNull);
      final state = tester.state<StorySceneViewState>(
        find.byType(StorySceneView).last,
      );
      for (var i = 0; i < view.scene.layers.length; i++) {
        expect(state.shows(i), isTrue);
      }
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
