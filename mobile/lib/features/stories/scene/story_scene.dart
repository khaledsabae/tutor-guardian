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
/// On the open page the pieces come on stage one after another, like a
/// pop-up book, and — while «اسمعها من نور» reads — follow the narrator
/// (scene_cues.dart): the piece being named hops, a visitor walks in when the
/// voice brings them, and the picture leans gently towards each sentence's
/// subject. All of it rides on the picture only; the text and the audio
/// never wait for it.
///
/// Motion follows the app's rule (core/motion.dart): with the system's
/// "remove animations" on, the idle loop does not run, nothing slides on a
/// turn, nothing enters or hops — the page is a still paper picture with
/// every piece on it.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../../core/motion.dart';
import 'scene_cues.dart';

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
    this.cue = const [],
    this.entersOnCue = false,
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

  /// Words that name this piece, in any language the story is told in —
  /// stems, matched with Arabic prefixes and a few endings (scene_cues.dart).
  /// When the narrator says one, the piece hops.
  final List<String> cue;

  /// While the narrator reads, the piece waits off the page until its first
  /// [cue] word, then walks in. Read silently, it is simply there.
  final bool entersOnCue;
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
    this.staged = false,
    this.active = true,
    this.cues,
    this.semanticLabel,
  });

  final StoryScene scene;

  /// The page's distance from rest while turning, −1 … 1. Pieces shift by
  /// it times their depth.
  final double parallax;

  /// Whether the idle loop may run at all (the shelf's small covers keep
  /// still; the open page breathes).
  final bool animate;

  /// The pieces come on stage one by one the first time the scene is
  /// [active]; until then only the backdrop shows. Off (the default), every
  /// piece is simply there.
  final bool staged;

  /// This scene's page is the one being read.
  final bool active;

  /// The narrator to follow, while one is reading this page. Null → no cues.
  final SceneCues? cues;

  /// What the picture shows, for a screen reader. Null → decorative.
  final String? semanticLabel;

  @override
  State<StorySceneView> createState() => StorySceneViewState();
}

class StorySceneViewState extends State<StorySceneView>
    with TickerProviderStateMixin {
  late final AnimationController _idle = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 6),
  );

  static const _stagger = Duration(milliseconds: 110);
  static const _rise = Duration(milliseconds: 520);

  late final AnimationController _intro = AnimationController(
    vsync: this,
    duration: _stagger * widget.scene.layers.length + _rise,
    value: widget.staged ? 0 : 1,
  );

  /// One per piece that has been cued at least once.
  final Map<int, AnimationController> _hops = {};

  /// Pieces whose current hop is their entrance.
  final Set<int> _entering = {};

  /// Entering pieces the narrator has brought in.
  final Set<int> _entered = {};

  late final AnimationController _camera = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  );
  double _camFromFocus = .5, _camFromScale = 1;
  double _camToFocus = .5, _camToScale = 1;

  double? _lastClock;
  bool _still = false;

  /// Visible for tests: the reduce-motion contract is pinned, not assumed.
  @visibleForTesting
  bool get idleLooping => _idle.isAnimating;

  /// Visible for tests: something is moving because of the narrator.
  @visibleForTesting
  bool get cueing =>
      _hops.values.any((c) => c.isAnimating) || _camera.isAnimating;

  /// Visible for tests: how far the pieces' entrance has run, 0 … 1.
  @visibleForTesting
  double get entrance => _intro.value;

  /// Visible for tests: whether piece [i] is on the page at all.
  @visibleForTesting
  bool shows(int i) =>
      !_waitsForCue(i) && (_still || _intro.value > 0 || !widget.staged);

  bool get _moves =>
      widget.animate &&
      widget.scene.layers.any((l) => l.motion != SceneMotion.still);

  bool get _cuesOn => widget.cues != null && widget.animate && !_still;

  @override
  void initState() {
    super.initState();
    widget.cues?.clock.addListener(_onClock);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _still = reduceMotion(context);
    _syncIdle();
    _syncIntro();
    if (_still) _restCues();
  }

  @override
  void didUpdateWidget(StorySceneView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.animate != widget.animate ||
        oldWidget.scene != widget.scene) {
      _syncIdle();
    }
    if (oldWidget.active != widget.active) _syncIntro();
    final was = oldWidget.cues?.clock, now = widget.cues?.clock;
    if (was != now) {
      was?.removeListener(_onClock);
      now?.addListener(_onClock);
      _lastClock = null;
      if (now == null) {
        _moveCamera(.5, 1);
      } else {
        _onClock();
      }
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

  void _syncIntro() {
    if (!widget.staged || _intro.value > 0 || _intro.isAnimating) return;
    if (_still || !widget.animate) {
      _intro.value = 1;
    } else if (widget.active) {
      _intro.forward();
    }
  }

  void _restCues() {
    for (final c in _hops.values) {
      c
        ..stop()
        ..value = 0;
    }
    _entering.clear();
    _camera
      ..stop()
      ..value = 0;
    _camFromFocus = _camToFocus = .5;
    _camFromScale = _camToScale = 1;
  }

  bool _isEnterer(int i) =>
      widget.cues?.beats.any(
        (b) => b.layer == i && b.kind == SceneBeatKind.enter,
      ) ??
      false;

  bool _waitsForCue(int i) => _cuesOn && _isEnterer(i) && !_entered.contains(i);

  AnimationController _hopOf(int i) => _hops.putIfAbsent(
    i,
    () =>
        AnimationController(
          vsync: this,
          duration: const Duration(milliseconds: 700),
        )..addStatusListener((s) {
          if (s == AnimationStatus.completed) _entering.remove(i);
        }),
  );

  void _onClock() {
    final cues = widget.cues;
    if (cues == null || !_cuesOn) return;
    final now = cues.clock.value.inMilliseconds / 1000;
    final prev = _lastClock;
    _lastClock = now;
    // A step forward the size of a position tick plays what it crossed; a
    // jump (a page reopened mid-recording, a seek) only sets the state.
    final step = prev != null && now >= prev && now - prev <= 1.5;
    var changed = false;
    if (prev != null && now < prev - .5) {
      // Played again from earlier: entrances still ahead wait again.
      for (final b in cues.beats) {
        if (b.kind == SceneBeatKind.enter && b.at > now) {
          changed |= _entered.remove(b.layer);
        }
      }
    }
    SceneBeat? lean;
    for (final b in cues.beats) {
      if (b.at > now) break;
      final crossed = step && b.at > prev;
      switch (b.kind) {
        case SceneBeatKind.enter:
          if (_entered.add(b.layer)) {
            changed = true;
            if (crossed) {
              _entering.add(b.layer);
              _hopOf(b.layer).forward(from: 0);
            }
          }
        case SceneBeatKind.pop:
          if (crossed) _hopOf(b.layer).forward(from: 0);
        case SceneBeatKind.camera:
          lean = b;
      }
    }
    if (lean != null && (lean.focus != _camToFocus || _camToScale == 1)) {
      _moveCamera(lean.focus, 1.07);
    }
    if (changed && mounted) setState(() {});
  }

  void _moveCamera(double focus, double scale) {
    if (_still) return;
    final t = Curves.easeInOut.transform(_camera.value);
    _camFromFocus = _camFromFocus + (_camToFocus - _camFromFocus) * t;
    _camFromScale = _camFromScale + (_camToScale - _camFromScale) * t;
    _camToFocus = focus;
    _camToScale = scale;
    _camera.forward(from: 0);
  }

  @override
  void dispose() {
    widget.cues?.clock.removeListener(_onClock);
    _idle.dispose();
    _intro.dispose();
    _camera.dispose();
    for (final c in _hops.values) {
      c.dispose();
    }
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
          final stage = Stack(
            clipBehavior: Clip.hardEdge,
            children: [
              Positioned.fill(
                child: SvgPicture.asset(
                  scenePieceAsset(widget.scene.backdrop),
                  fit: BoxFit.cover,
                  excludeFromSemantics: true,
                ),
              ),
              for (var i = 0; i < widget.scene.layers.length; i++)
                _positioned(i, w, h, parallax),
            ],
          );
          return ClipRect(
            child: still
                ? stage
                : AnimatedBuilder(
                    animation: _camera,
                    child: stage,
                    builder: (context, child) {
                      final t = Curves.easeInOut.transform(_camera.value);
                      final focus =
                          _camFromFocus + (_camToFocus - _camFromFocus) * t;
                      final scale =
                          _camFromScale + (_camToScale - _camFromScale) * t;
                      if (scale == 1) return child!;
                      return Transform.scale(
                        scale: scale,
                        alignment: Alignment(focus * 2 - 1, .4),
                        child: child,
                      );
                    },
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

  Widget _positioned(int i, double w, double h, double parallax) {
    final layer = widget.scene.layers[i];
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
    if (!_still && widget.animate) {
      final hop = _hops[i];
      if (hop != null) {
        piece = AnimatedBuilder(
          animation: hop,
          child: piece,
          builder: (context, child) => _entering.contains(i)
              ? _walkedIn(layer, hop.value, side, child!)
              : _hopped(hop.value, side, child!),
        );
      }
      if (widget.staged) {
        final n = widget.scene.layers.length;
        final total = _intro.duration!.inMilliseconds;
        final from = _stagger.inMilliseconds * i / total;
        final to = from + _rise.inMilliseconds / total;
        piece = AnimatedBuilder(
          animation: _intro,
          child: piece,
          builder: (context, child) {
            if (_intro.value >= 1 || n == 0) return child!;
            final t = ((_intro.value - from) / (to - from)).clamp(0.0, 1.0);
            return _cameOn(t, side, child!);
          },
        );
      }
    }
    if (_waitsForCue(i)) {
      piece = Opacity(opacity: 0, child: piece);
    }
    return Positioned(
      left: left,
      top: top,
      width: side,
      height: side,
      child: piece,
    );
  }

  /// A piece coming on stage: up from a little below, swelling past its
  /// size and settling, like a pop-up page opening.
  static Widget _cameOn(double t, double side, Widget child) {
    if (t <= 0) return Opacity(opacity: 0, child: child);
    final grow = Curves.easeOutBack.transform(t);
    return Opacity(
      opacity: Curves.easeOut.transform(t),
      child: Transform.translate(
        offset: Offset(0, side * .12 * (1 - t)),
        child: Transform.scale(
          scale: .55 + .45 * grow,
          alignment: Alignment.bottomCenter,
          child: child,
        ),
      ),
    );
  }

  /// The narrator names a piece: a hop and a swell, back to rest.
  static Widget _hopped(double t, double side, Widget child) {
    if (t <= 0 || t >= 1) return child;
    final arc = math.sin(t * math.pi);
    // Two hops, the second smaller — a child bouncing on the spot.
    final bounce = t < .6
        ? math.sin(t / .6 * math.pi)
        : .35 * math.sin((t - .6) / .4 * math.pi);
    return Transform.translate(
      offset: Offset(0, -side * .14 * bounce),
      child: Transform.scale(
        scale: 1 + .08 * arc,
        alignment: Alignment.bottomCenter,
        child: child,
      ),
    );
  }

  /// A visitor walks in from the nearer edge of the frame.
  static Widget _walkedIn(
    SceneLayer layer,
    double t,
    double side,
    Widget child,
  ) {
    final e = Curves.easeOutCubic.transform(t);
    final fromRight = layer.x >= .5;
    final step = math.sin(t * math.pi * 4).abs();
    return Opacity(
      opacity: (t * 3).clamp(0.0, 1.0),
      child: Transform.translate(
        offset: Offset(
          (fromRight ? 1 : -1) * side * .9 * (1 - e),
          -side * .03 * step * (1 - e),
        ),
        child: child,
      ),
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
