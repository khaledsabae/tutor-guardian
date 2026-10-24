/// Renders story scenes to PNG — the before/after sheets for a palette or
/// catalogue change, drawn by the app's own widget and flutter_svg, not by a
/// look-alike renderer.
///
/// Not part of the suite (it lives in tool/, and writes files). Run:
///
///   STORY_RENDER_OUT=/tmp/scenes flutter test tool/render_story_scenes_test.dart
///
/// Optional STORY_RENDER_IDS=kitten_kindness,maryam_toys limits the stories.
/// STORY_RENDER_FACES=1 also writes `<out>/faces/<person>_<face>.png` (240²),
/// every person piece in every expression.
/// Writes `<out>/<story>_<page>.png` (1-based, like docs/stories/) and
/// `<out>/<story>_cover.png`, 720×480.
library;

import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/stories/scene/scene_people.g.dart';
import 'package:almorabbi/features/stories/scene/story_scene.dart';
import 'package:almorabbi/features/stories/scene/story_scene_catalog.dart';

void main() {
  final out = Platform.environment['STORY_RENDER_OUT'];
  final only = Platform.environment['STORY_RENDER_IDS']
      ?.split(',')
      .where((s) => s.isNotEmpty)
      .toSet();

  Future<void> capture(
    WidgetTester tester,
    Widget child,
    Size size,
    String file,
  ) async {
    final boundary = GlobalKey();
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: Directionality(
          textDirection: TextDirection.ltr,
          child: Center(
            child: RepaintBoundary(
              key: boundary,
              child: SizedBox.fromSize(size: size, child: child),
            ),
          ),
        ),
      ),
    );
    for (var i = 0; i < 6; i++) {
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 60)),
      );
      await tester.pump();
    }
    await tester.runAsync(() async {
      final ro =
          boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final image = await ro.toImage(
        pixelRatio:
            double.tryParse(Platform.environment['STORY_RENDER_PX'] ?? '') ?? 1,
      );
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      File(file).writeAsBytesSync(bytes!.buffer.asUint8List());
      image.dispose();
    });
  }

  testWidgets('render faces', (tester) async {
    if (out == null || Platform.environment['STORY_RENDER_FACES'] == null) {
      return;
    }
    Directory('$out/faces').createSync(recursive: true);
    tester.view.physicalSize = const Size(720, 480);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    for (final person in scenePeople.keys) {
      for (final face in SceneFace.values) {
        await capture(
          tester,
          StorySceneView(
            scene: StoryScene('bg_bedroom', [
              // Close on the head: a child's sits at .43 of its box, an
              // adult's at .21.
              SceneLayer(
                person,
                x: .5,
                size: 2.4,
                y: .45 + 2.4 * (scenePeople[person] == 'child' ? .567 : .792),
                face: face,
              ),
            ]),
            animate: false,
          ),
          const Size(360, 240),
          '$out/faces/${person}_${face.name}.png',
        );
      }
    }
  });

  testWidgets('render story scenes', (tester) async {
    if (out == null) return; // a no-op unless asked
    Directory(out).createSync(recursive: true);
    tester.view.physicalSize = const Size(720, 480);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    final stories =
        (jsonDecode(File('assets/data/stories.json').readAsStringSync())
                as List)
            .cast<Map<String, dynamic>>();
    for (final s in stories) {
      final id = s['id'] as String;
      if (only != null && !only.contains(id)) continue;
      final pages = (s['pages'] as List).length;
      final targets = <String, StoryScene>{
        for (var i = 0; i < pages; i++) '${id}_${i + 1}': sceneFor(id, i),
        '${id}_cover': coverSceneFor(id),
      };
      for (final MapEntry(:key, :value) in targets.entries) {
        final boundary = GlobalKey();
        await tester.pumpWidget(
          MediaQuery(
            data: const MediaQueryData(disableAnimations: true),
            child: Directionality(
              textDirection: TextDirection.ltr,
              child: Center(
                child: RepaintBoundary(
                  key: boundary,
                  child: SizedBox(
                    width: 720,
                    height: 480,
                    child: StorySceneView(scene: value, animate: false),
                  ),
                ),
              ),
            ),
          ),
        );
        // flutter_svg parses off the test's fake clock.
        for (var i = 0; i < 6; i++) {
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 60)),
          );
          await tester.pump();
        }
        await tester.runAsync(() async {
          final ro =
              boundary.currentContext!.findRenderObject()!
                  as RenderRepaintBoundary;
          final image = await ro.toImage(
        pixelRatio:
            double.tryParse(Platform.environment['STORY_RENDER_PX'] ?? '') ?? 1,
      );
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          File('$out/$key.png').writeAsBytesSync(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }
    }
  });
}
