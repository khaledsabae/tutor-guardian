/// «صورة حيّة» — the story's own painted picture, alive.
///
/// The children kept choosing the original raster pages (docs/stories/,
/// Aug 2026) over every redrawn style, so this keeps the picture exactly as
/// painted and moves the camera over it instead:
///
///  * At rest, a slow Ken-Burns drift — never more than a gentle push.
///  * While «اسمعها من نور» reads, each named thing in the picture has a
///    region and the words that name it (word_cues.dart, Arabic and English
///    in one list); when the narrator says one, the camera eases towards that
///    region (zoom ≤ [kMaxLivingZoom], always framed inside the picture),
///    holds a moment, and drifts back.
///  * A light layer of particles on top — dust motes in the window light, a
///    few sparkles or hearts where the text is happy.
///  * Optionally the people are cut out ([LivingPicture.foreground] over an
///    inpainted [LivingPicture.background]) and breathe with a little
///    parallax over the room.
///
/// The picture never delays the text or the audio: it only follows the
/// recording's clock. With the system's "remove animations" on, it is the
/// still painting — whole, uncropped — with nothing moving and no cues.
library;

import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../../../config/app_config.dart';
import '../../../core/motion.dart';
import '../narration/word_cues.dart';

/// A picture path as the story library writes it: `docs/…` is served by the
/// backend (the same files the reader showed before the paper-cut scenes),
/// anything else is a bundled asset.
ImageProvider livingImage(String path) => path.startsWith('docs/')
    ? NetworkImage('${AppConfig.apiBaseUrl}/$path')
    : AssetImage(path) as ImageProvider;

/// The camera never goes closer than this (1 = the whole picture).
const kMaxLivingZoom = 1.25;

enum PictureBurst { sparkles, hearts }

enum PictureAmbient { none, dust, sparkles }

/// A thing in the picture the narrator can name.
@immutable
class PictureRegion {
  const PictureRegion(this.name, this.rect, {this.cue = const [], this.burst});

  /// For tests and reports only.
  final String name;

  /// Normalised to the picture, 0 … 1 both ways.
  final Rect rect;

  /// The words that name it, Arabic and English together.
  final List<String> cue;

  /// A little burst of particles when it is named.
  final PictureBurst? burst;
}

@immutable
class LivingPicture {
  const LivingPicture({
    required this.image,
    this.background,
    this.foreground,
    this.regions = const [],
    this.ambient = PictureAmbient.dust,
  });

  /// The painted page, whole (shown as is with reduced motion).
  final String image;

  /// The page with its people painted out, and the people alone — both or
  /// neither.
  final String? background;
  final String? foreground;

  final List<PictureRegion> regions;
  final PictureAmbient ambient;

  bool get layered => background != null && foreground != null;

  /// The zoom and centre that frame [r]: close enough to tell, never past
  /// [kMaxLivingZoom], never showing past the picture's edge.
  static ({double zoom, Offset centre}) frame(Rect r) {
    final side = math.max(r.width, r.height);
    final zoom = (0.85 / side).clamp(1.08, kMaxLivingZoom).toDouble();
    return (zoom: zoom, centre: clampCentre(r.center, zoom));
  }

  static Offset clampCentre(Offset c, double zoom) {
    final half = 0.5 / zoom;
    return Offset(
      c.dx.clamp(half, 1 - half).toDouble(),
      c.dy.clamp(half, 1 - half).toDouble(),
    );
  }
}

/// What a living picture follows: the cues of the page being read, and the
/// recording's clock.
@immutable
class LivingCues {
  const LivingCues({required this.cues, required this.clock});

  final List<WordCue> cues;
  final ValueListenable<Duration> clock;
}

class LivingPictureView extends StatefulWidget {
  const LivingPictureView({
    super.key,
    required this.picture,
    this.cues,
    this.animate = true,
    this.fallback,
    this.semanticLabel,
  });

  final LivingPicture picture;
  final LivingCues? cues;
  final bool animate;

  /// Shown instead when the painting cannot be loaded (offline, a server
  /// without the file) — the reader passes the page's paper-cut scene.
  final Widget? fallback;
  final String? semanticLabel;

  @override
  State<LivingPictureView> createState() => LivingPictureViewState();
}

class LivingPictureViewState extends State<LivingPictureView>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker = createTicker(_tick);
  Duration _elapsed = Duration.zero;
  double _t = 0;

  double _zoom = 1, _cx = .5, _cy = .5;
  int? _focus;
  double _focusSince = -100;
  double? _lastClock;
  bool _still = false;

  final List<_Particle> _particles = [];
  final math.Random _rand = math.Random(7);

  static const _hold = 2.6;

  /// Visible for tests.
  @visibleForTesting
  bool get moving => _ticker.isActive;
  @visibleForTesting
  double get zoom => _zoom;
  @visibleForTesting
  Offset get centre => Offset(_cx, _cy);
  @visibleForTesting
  int? get focus => _isFocused ? _focus : null;
  @visibleForTesting
  int get particles => _particles.length;

  bool _failed = false;

  /// Visible for tests: the painting could not be loaded.
  @visibleForTesting
  bool get failed => _failed;

  bool get _isFocused => _focus != null && _t - _focusSince < _hold;
  bool get _alive => widget.animate && !_still;

  @override
  void initState() {
    super.initState();
    widget.cues?.clock.addListener(_onClock);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _still = reduceMotion(context);
    _sync();
  }

  @override
  void didUpdateWidget(LivingPictureView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.cues?.clock != widget.cues?.clock) {
      oldWidget.cues?.clock.removeListener(_onClock);
      widget.cues?.clock.addListener(_onClock);
      _lastClock = null;
    }
    if (widget.cues == null) _focus = null;
    _sync();
  }

  void _sync() {
    final run = _alive && TickerMode.valuesOf(context).enabled;
    if (run && !_ticker.isActive) {
      _ticker.start();
    } else if (!run && _ticker.isActive) {
      _ticker.stop();
    }
    if (!run) {
      _zoom = 1;
      _cx = _cy = .5;
      _focus = null;
      _particles.clear();
    }
  }

  void _onClock() {
    final cues = widget.cues;
    if (cues == null || !_alive) return;
    final now = cues.clock.value.inMilliseconds / 1000;
    final prev = _lastClock;
    _lastClock = now;
    // Only a step the size of a position tick plays what it crossed; a jump
    // (a reopened page, a seek) just moves on.
    if (prev == null || now < prev || now - prev > 1.5) return;
    for (final c in cues.cues) {
      if (c.at > prev &&
          c.at <= now &&
          c.target < widget.picture.regions.length) {
        _name(c.target);
      }
    }
  }

  void _name(int region) {
    _focus = region;
    _focusSince = _t;
    final burst = widget.picture.regions[region].burst;
    if (burst != null) _burst(widget.picture.regions[region].rect, burst);
  }

  void _tick(Duration elapsed) {
    final dt = ((elapsed - _elapsed).inMicroseconds / 1e6).clamp(0.0, .1);
    _elapsed = elapsed;
    _t += dt;

    // Where the camera wants to be: the named thing, or the resting drift.
    double tz, tx, ty;
    if (_isFocused) {
      final f = LivingPicture.frame(widget.picture.regions[_focus!].rect);
      tz = f.zoom;
      tx = f.centre.dx;
      ty = f.centre.dy;
    } else {
      final p = _t / 18 * 2 * math.pi;
      tz = 1.07 + .03 * math.sin(p);
      final c = LivingPicture.clampCentre(
        Offset(.5 + .035 * math.sin(p * .7), .5 + .03 * math.cos(p * .5)),
        tz,
      );
      tx = c.dx;
      ty = c.dy;
    }
    final k = 1 - math.exp(-dt / (_isFocused ? .55 : .9));
    _zoom += (tz - _zoom) * k;
    _cx += (tx - _cx) * k;
    _cy += (ty - _cy) * k;
    final c = LivingPicture.clampCentre(Offset(_cx, _cy), _zoom);
    _cx = c.dx;
    _cy = c.dy;

    _stepParticles(dt);
    if (mounted) setState(() {});
  }

  // ── particles ──────────────────────────────────────────────────────────
  void _stepParticles(double dt) {
    final ambient = widget.picture.ambient;
    final motes = _particles.where((p) => p.ambient).length;
    if (ambient != PictureAmbient.none && motes < 12) {
      _particles.add(_Particle.ambient(_rand, ambient));
    }
    for (final p in _particles) {
      p.age += dt;
      p.pos += p.vel * dt;
    }
    _particles.removeWhere((p) => p.age >= p.life);
  }

  void _burst(Rect r, PictureBurst kind) {
    for (var i = 0; i < 7; i++) {
      _particles.add(_Particle.burst(_rand, r, kind));
    }
  }

  @override
  void dispose() {
    widget.cues?.clock.removeListener(_onClock);
    _ticker.dispose();
    super.dispose();
  }

  Widget _image(String path) => Image(
    image: livingImage(path),
    fit: BoxFit.cover,
    excludeFromSemantics: true,
    gaplessPlayback: true,
    frameBuilder: (context, child, frame, sync) => sync
        ? child
        : AnimatedOpacity(
            opacity: frame == null ? 0 : 1,
            duration: const Duration(milliseconds: 300),
            child: child,
          ),
    errorBuilder: (context, error, stack) {
      if (!_failed) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) setState(() => _failed = true);
        });
      }
      return const SizedBox.expand();
    },
  );

  @override
  Widget build(BuildContext context) {
    final pic = widget.picture;
    final fallback = widget.fallback;
    if (_failed && fallback != null) return fallback;
    final Widget body;
    if (!_alive) {
      body = _image(pic.image);
    } else {
      body = LayoutBuilder(
        builder: (context, box) {
          final w = box.maxWidth, h = box.maxHeight;
          final camera = Matrix4.identity()
            ..translateByDouble(w / 2, h / 2, 0, 1)
            ..scaleByDouble(_zoom, _zoom, 1, 1)
            ..translateByDouble(-_cx * w, -_cy * h, 0, 1);
          Widget stage;
          if (pic.layered) {
            // The people lean against the camera's drift and breathe.
            final par = Offset((_cx - .5) * -w * .05, (_cy - .5) * -h * .03);
            final breath = math.sin(_t / 3.4 * 2 * math.pi);
            stage = Stack(
              fit: StackFit.expand,
              children: [
                _image(pic.background!),
                Transform.translate(
                  offset: par + Offset(0, -h * .004 * breath),
                  child: Transform.scale(
                    scale: 1 + .006 * breath,
                    alignment: Alignment.bottomCenter,
                    child: _image(pic.foreground!),
                  ),
                ),
              ],
            );
          } else {
            stage = _image(pic.image);
          }
          return Stack(
            fit: StackFit.expand,
            children: [
              Transform(transform: camera, child: stage),
              IgnorePointer(
                child: CustomPaint(
                  painter: _ParticlePainter(
                    _particles,
                    zoom: _zoom,
                    centre: Offset(_cx, _cy),
                  ),
                ),
              ),
            ],
          );
        },
      );
    }
    final picture = ClipRect(child: AspectRatio(aspectRatio: 1, child: body));
    final label = widget.semanticLabel;
    return label == null
        ? ExcludeSemantics(child: picture)
        : Semantics(image: true, label: label, child: picture);
  }
}

class _Particle {
  _Particle(
    this.pos,
    this.vel,
    this.life,
    this.size,
    this.color,
    this.shape, {
    this.ambient = false,
  });

  /// Ambient motes live in view space; bursts in picture space.
  factory _Particle.ambient(math.Random r, PictureAmbient kind) => _Particle(
    Offset(r.nextDouble(), .3 + r.nextDouble() * .7),
    Offset((r.nextDouble() - .5) * .01, -.012 - r.nextDouble() * .015),
    6 + r.nextDouble() * 6,
    kind == PictureAmbient.sparkles
        ? 2.2 + r.nextDouble() * 2
        : 1.4 + r.nextDouble() * 1.8,
    kind == PictureAmbient.sparkles
        ? const Color(0xFFFFF3C4)
        : const Color(0xFFFFFBEF),
    kind == PictureAmbient.sparkles ? _Shape.sparkle : _Shape.dot,
    ambient: true,
  );

  factory _Particle.burst(math.Random r, Rect rect, PictureBurst kind) {
    final start = Offset(
      rect.left + rect.width * (.2 + r.nextDouble() * .6),
      rect.top + rect.height * (.15 + r.nextDouble() * .3),
    );
    final hearts = kind == PictureBurst.hearts;
    return _Particle(
      start,
      Offset((r.nextDouble() - .5) * .05, -.05 - r.nextDouble() * .05),
      1.6 + r.nextDouble() * .6,
      hearts ? 7 + r.nextDouble() * 4 : 5 + r.nextDouble() * 4,
      hearts ? const Color(0xFFF27B95) : const Color(0xFFFFE38A),
      hearts ? _Shape.heart : _Shape.sparkle,
    );
  }

  Offset pos;
  final Offset vel;
  final double life;
  final double size;
  final Color color;
  final _Shape shape;
  final bool ambient;
  double age = 0;

  /// Fades in, holds, fades out.
  double get alpha {
    final f = age / life;
    return (f < .2 ? f / .2 : (f > .7 ? (1 - f) / .3 : 1.0)).clamp(0.0, 1.0);
  }
}

enum _Shape { dot, sparkle, heart }

class _ParticlePainter extends CustomPainter {
  _ParticlePainter(this.particles, {required this.zoom, required this.centre});

  final List<_Particle> particles;
  final double zoom;
  final Offset centre;

  @override
  void paint(Canvas canvas, Size size) {
    for (final p in particles) {
      // Bursts belong to the picture: follow the camera to stay on their
      // subject. Motes float in the air between the picture and the child.
      final at = p.ambient
          ? Offset(p.pos.dx * size.width, p.pos.dy * size.height)
          : Offset(
              size.width / 2 + (p.pos.dx - centre.dx) * size.width * zoom,
              size.height / 2 + (p.pos.dy - centre.dy) * size.height * zoom,
            );
      final paint = Paint()
        ..color = p.color.withValues(alpha: p.alpha * (p.ambient ? .55 : .95));
      switch (p.shape) {
        case _Shape.dot:
          canvas.drawCircle(at, p.size, paint);
        case _Shape.sparkle:
          final s = p.size;
          final path = Path()
            ..moveTo(at.dx, at.dy - s)
            ..quadraticBezierTo(at.dx, at.dy, at.dx + s, at.dy)
            ..quadraticBezierTo(at.dx, at.dy, at.dx, at.dy + s)
            ..quadraticBezierTo(at.dx, at.dy, at.dx - s, at.dy)
            ..quadraticBezierTo(at.dx, at.dy, at.dx, at.dy - s)
            ..close();
          canvas.drawPath(path, paint);
        case _Shape.heart:
          final s = p.size;
          final path = Path()
            ..moveTo(at.dx, at.dy + s * .9)
            ..cubicTo(
              at.dx - s * 1.3,
              at.dy,
              at.dx - s * .6,
              at.dy - s * .9,
              at.dx,
              at.dy - s * .3,
            )
            ..cubicTo(
              at.dx + s * .6,
              at.dy - s * .9,
              at.dx + s * 1.3,
              at.dy,
              at.dx,
              at.dy + s * .9,
            )
            ..close();
          canvas.drawPath(path, paint);
      }
    }
  }

  @override
  bool shouldRepaint(_ParticlePainter old) => true;
}
