/// Renders story scenes to PNG — the before/after sheets for a palette or
/// catalogue change, drawn by the app's own widget and flutter_svg, not by a
/// look-alike renderer.
///
/// Not part of the suite (it lives in tool/, and writes files). Run:
///
///   STORY_RENDER_OUT=/tmp/scenes flutter test tool/render_story_scenes_test.dart
///
/// Optional STORY_RENDER_IDS=kitten_kindness,maryam_toys limits the stories.
/// Writes `<out>/<story>_<page>.png` (1-based, like docs/stories/) and
/// `<out>/<story>_cover.png`, 720×480.
library;

import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/stories/scene/story_scene.dart';
import 'package:almorabbi/features/stories/scene/story_scene_catalog.dart';

void main() {
  final out = Platform.environment['STORY_RENDER_OUT'];
  final only = Platform.environment['STORY_RENDER_IDS']
      ?.split(',')
      .where((s) => s.isNotEmpty)
      .toSet();

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
          final image = await ro.toImage();
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          File('$out/$key.png').writeAsBytesSync(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }
    }
  });
}
