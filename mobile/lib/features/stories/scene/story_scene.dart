/// A story page drawn as «ورق مقصوص» — paper pieces on a paper ground.
///
/// A scene is one backdrop (assets/svg/stories/bg_*.svg, 360×240) and a few
/// props (240×240 each) placed on it. They stay separate pieces on purpose:
/// that is what lets a page move like layered paper — near pieces slide
/// further than far ones while the page is being turned (parallax), and a
/// few of them breathe, sway or twinkle while it rests.
///
/// The pieces are drawn by tool/story_art.py; which pieces make which page is
/// story_scene_catalog.dart.
///
/// Motion follows the app's rule (core/motion.dart): with the system's
/// "remove animations" on, the idle loop does not run and nothing slides on a
/// turn — the page is a still paper picture.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../../core/motion.dart';

/// How a piece moves while the page rests.
enum SceneMotion {
  /// Does not move.
  still,

  /// Leans side to side from its base, like a plant or a child rocking.
  sway,

  /// Rises and settles, like breathing or a bird hopping.
  bob,

  /// Swells a little and back.
  breathe,

  /// Fades in and out, for stars.
  twinkle,

  /// Wanders a few points sideways, for clouds.
  drift,
}

/// One paper piece on a scene.
@immutable
class SceneLayer {
  const SceneLayer(
    this.piece, {
    required this.x,
    this.y = .97,
    this.size = .8,
    this.depth = .5,
    this.motion = SceneMotion.still,
    this.flip = false,
    this.phase = 0,
  });

  /// The file name under assets/svg/stories/, without `.svg`.
  final String piece;

  /// Centre of the piece across the frame, 0 (left) … 1 (right). Physical,
  /// not directional: a picture is not mirrored for Arabic.
  final double x;

  /// Where the bottom of the piece's 240-box sits, as a fraction of the frame
  /// height. People and furniture stand on .97, the floor line.
  final double y;

  /// The piece's 240-box edge as a fraction of the frame height. All people
  /// share .8, so a child stands about two-thirds as tall as a parent.
  final double size;

  /// 0 far … 1 near: how far the piece slides while the page turns.
  final double depth;

  final SceneMotion motion;

  /// Mirror the piece (to face the other way).
  final bool flip;

  /// Offset in the idle loop, 0 … 1, so two swaying pieces are not in step.
  final double phase;
}

@immutable
class StoryScene {
  const StoryScene(this.backdrop, this.layers);

  /// A bg_* file under assets/svg/stories/, without `.svg`.
  final String backdrop;
  final List<SceneLayer> layers;
}

String scenePieceAsset(String piece) => 'assets/svg/stories/$piece.svg';

/// The frame every scene is drawn in.
const kSceneAspect = 3 / 2;

/// One scene, drawn to fill a 3:2 frame.
class StorySceneView extends StatefulWidget {
  const StorySceneView({
    super.key,
    required this.scene,
    this.parallax = 0,
    this.animate = true,
    this.semanticLabel,
  });

  final StoryScene scene;

  /// The page's distance from rest while turning, −1 … 1. Pieces shift by
  /// it times their depth.
  final double parallax;

  /// Whether the idle loop may run at all (the shelf's small covers keep
  /// still; the open page breathes).
  final bool animate;

  /// What the picture shows, for a screen reader. Null → decorative.
  final String? semanticLabel;

  @override
  State<StorySceneView> createState() => StorySceneViewState();
}

class StorySceneViewState extends State<StorySceneView>
    with SingleTickerProviderStateMixin {
  late final AnimationController _idle = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 6),
  );

  /// Visible for tests: the reduce-motion contract is pinned, not assumed.
  @visibleForTesting
  bool get idleLooping => _idle.isAnimating;

  bool get _moves =>
      widget.animate &&
      widget.scene.layers.any((l) => l.motion != SceneMotion.still);

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncIdle();
  }

  @override
  void didUpdateWidget(StorySceneView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.animate != widget.animate ||
        oldWidget.scene != widget.scene) {
      _syncIdle();
    }
  }

  void _syncIdle() {
    if (_moves) {
      syncLoop(context, _idle);
    } else {
      _idle
        ..stop()
        ..value = 0;
    }
  }

  @override
  void dispose() {
    _idle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final still = reduceMotion(context);
    final parallax = still ? 0.0 : widget.parallax.clamp(-1.0, 1.0);
    final picture = AspectRatio(
      aspectRatio: kSceneAspect,
      child: LayoutBuilder(
        builder: (context, box) {
          final w = box.maxWidth;
          final h = box.maxHeight;
          return ClipRect(
            child: Stack(
              clipBehavior: Clip.hardEdge,
              children: [
                Positioned.fill(
                  child: SvgPicture.asset(
                    scenePieceAsset(widget.scene.backdrop),
                    fit: BoxFit.cover,
                    excludeFromSemantics: true,
                  ),
                ),
                for (final layer in widget.scene.layers)
                  _positioned(layer, w, h, parallax),
              ],
            ),
          );
        },
      ),
    );
    final label = widget.semanticLabel;
    return label == null
        ? ExcludeSemantics(child: picture)
        : Semantics(image: true, label: label, child: picture);
  }

  Widget _positioned(SceneLayer layer, double w, double h, double parallax) {
    final side = h * layer.size;
    final left = layer.x * w - side / 2 + parallax * layer.depth * w * .12;
    final top = layer.y * h - side;
    Widget piece = SvgPicture.asset(
      scenePieceAsset(layer.piece),
      width: side,
      height: side,
      excludeFromSemantics: true,
    );
    if (layer.flip) {
      piece = Transform.flip(flipX: true, child: piece);
    }
    if (layer.motion != SceneMotion.still && widget.animate) {
      piece = AnimatedBuilder(
        animation: _idle,
        child: piece,
        builder: (context, child) =>
            _moved(layer, (_idle.value + layer.phase) % 1, side, child!),
      );
    }
    return Positioned(
      left: left,
      top: top,
      width: side,
      height: side,
      child: piece,
    );
  }

  /// One frame of a piece's idle motion. `t` runs 0 … 1 around the loop.
  static Widget _moved(SceneLayer layer, double t, double side, Widget child) {
    final wave = math.sin(t * 2 * math.pi);
    switch (layer.motion) {
      case SceneMotion.still:
        return child;
      case SceneMotion.sway:
        return Transform.rotate(
          angle: wave * .035,
          alignment: Alignment.bottomCenter,
          child: child,
        );
      case SceneMotion.bob:
        return Transform.translate(
          offset: Offset(0, -side * .018 * (wave + 1)),
          child: child,
        );
      case SceneMotion.breathe:
        return Transform.scale(
          scale: 1 + .025 * wave,
          alignment: Alignment.bottomCenter,
          child: child,
        );
      case SceneMotion.twinkle:
        return Opacity(opacity: .7 + .3 * (wave + 1) / 2, child: child);
      case SceneMotion.drift:
        return Transform.translate(
          offset: Offset(side * .05 * wave, 0),
          child: child,
        );
    }
  }
}
