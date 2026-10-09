/// NoorFace — «نور» drawn entirely in code (جولة الحرفة, item 4).
///
/// The three mascot images are hero art: 1024² illustrations for onboarding
/// and celebrations. What the app lacked is a face that can live at 44 dp in
/// a chat bubble or beside a greeting without decoding an asset — and that
/// can *change expression* the way a companion does. This is that face:
/// a filled crescent opening toward the top-right (the same silhouette as
/// [BrandIcon.crescent]), stroked features in the thin-line language of the
/// brand glyphs, and six states:
///
///   * [NoorFaceState.calm] — eyes closed in contentment, soft smile.
///   * [NoorFaceState.awake] — eyes open, attending.
///   * [NoorFaceState.happy] — golden rays and a rising star; a moment earned.
///   * [NoorFaceState.thinking] — three cycling dots while an answer is written.
///   * [NoorFaceState.night] — the late sky's emerald, tiny stars, sleepy.
///   * [NoorFaceState.tender] — burnished amber for «لم تنجح»: warmth, not pity.
///
/// Two motions live on one 4-second cycle: a blink in the first 150 ms and a
/// halo breath over the whole pass. Both go through [syncLoop], so under
/// `disableAnimations` the face rests — eyes open, halo mid-swell — instead
/// of flickering (CI journeys run with animations disabled; a looping face
/// would hang them).
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/motion.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_palette.dart';

/// The six expressions. Calm is the resting face; the others are moments.
enum NoorFaceState { calm, awake, happy, thinking, night, tender }

/// A drawn «نور» face. [size] is the square canvas; the crescent fills ~78%
/// of it, leaving headroom for the happy rays and the thinking dots.
class NoorFace extends StatefulWidget {
  const NoorFace({
    super.key,
    this.size = 56,
    this.state = NoorFaceState.calm,
    this.semanticLabel,
  });

  /// 44–96 dp by design; below 44 the strokes stop reading, above 96 the
  /// mascot images take over (hero art for heroic moments).
  final double size;
  final NoorFaceState state;
  final String? semanticLabel;

  @override
  State<NoorFace> createState() => NoorFaceWidgetState();
}

class NoorFaceWidgetState extends State<NoorFace>
    with SingleTickerProviderStateMixin {
  late final AnimationController _cycle;

  /// Whether the blink/breath cycle is running — pins the reduced-motion
  /// contract in tests instead of assuming it.
  @visibleForTesting
  bool get cycling => _cycle.isAnimating;

  @override
  void initState() {
    super.initState();
    _cycle = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 4),
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Rest value 0.5: past the blink window (eyes open), halo mid-swell —
    // a complete, calm frame. Re-synced on dependency changes so toggling
    // the system setting mid-session is honoured immediately.
    syncLoop(context, _cycle, restValue: .5);
  }

  @override
  void dispose() {
    _cycle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = context.colors;
    return RepaintBoundary(
      child: Semantics(
        label: widget.semanticLabel,
        excludeSemantics: widget.semanticLabel == null,
        child: SizedBox(
          width: widget.size,
          height: widget.size,
          child: AnimatedBuilder(
            animation: _cycle,
            builder: (context, _) => CustomPaint(
              size: Size.square(widget.size),
              painter: _NoorFacePainter(
                state: widget.state,
                phase: _cycle.value,
                palette: palette,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// One blink per cycle: closed only in the first 150 ms of the 4 s pass.
bool _blinking(double phase) => phase < 0.0375;

class _NoorFacePainter extends CustomPainter {
  const _NoorFacePainter({
    required this.state,
    required this.phase,
    required this.palette,
  });

  final NoorFaceState state;
  final double phase;
  final AppPalette palette;

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.shortestSide;
    final scale = s / 100;
    final center = Offset(50 * scale, 54 * scale);

    // — The night-navy disc: matches the mascot art exactly. —
    final discRadius = math.max(40.0 * scale, s * 0.44);
    final discColor = palette.isDark
        ? const Color(0xFF09141F) // audit-ok: brand night disc
        : const Color(0xFF0F1E2E); // audit-ok: brand night disc
    canvas.drawCircle(
      center,
      discRadius,
      Paint()
        ..color = discColor
        ..style = PaintingStyle.fill,
    );
    // In light mode: exactly one delicate ring around the night disc (not 3).
    canvas.drawCircle(
      center,
      discRadius,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(1.0, s * 0.022)
        ..color = palette.accent.withValues(alpha: palette.isDark ? 0.35 : 0.45),
    );

    // — The head: a refined crescent, opening toward the top-right. —
    final body = math.max(30.0 * scale, s * 0.32);
    final bite = math.max(25.0 * scale, s * 0.27);
    final biteOffset = Offset(16 * scale, -3 * scale);

    final moon = Path.combine(
      PathOperation.difference,
      Path()..addOval(Rect.fromCircle(center: center, radius: body)),
      Path()
        ..addOval(Rect.fromCircle(center: center + biteOffset, radius: bite)),
    );

    // Warm ivory/cream for resting face; gold is reserved for happy only.
    final fill = switch (state) {
      NoorFaceState.happy => palette.accent,
      NoorFaceState.tender => const Color(0xFFFFF7ED), // audit-ok: brand crescent fill
      _ => const Color(0xFFFBF8F2), // audit-ok: brand crescent fill
    };
    canvas.drawPath(
      moon,
      Paint()
        ..color = fill
        ..style = PaintingStyle.fill,
    );
    // A thin delicate rim around the crescent.
    canvas.drawPath(
      moon,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(1.0, s * 0.016)
        ..color = state == NoorFaceState.happy
            ? palette.accentDeep
            : const Color(0xFFE2D8CC), // audit-ok: brand crescent fill
    );

    // — The halo breath: in dark mode or happy state only, keeping light mode to 1 clean ring. —
    if (state == NoorFaceState.happy || (palette.isDark && state != NoorFaceState.night)) {
      final breathe = (math.sin(phase * 2 * math.pi) + 1) / 2;
      canvas.drawCircle(
        center,
        body * (1.04 + 0.05 * breathe),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(1.2, s * 0.022)
          ..color = palette.accent.withValues(alpha: 0.18 + 0.20 * breathe),
      );
    }

    // — Happy: rays and one rising star — enough to read as earned. —
    if (state == NoorFaceState.happy) {
      final breathe = (math.sin(phase * 2 * math.pi) + 1) / 2;
      final ray = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = math.max(1.2, s * 0.026)
        ..color = palette.accent.withValues(alpha: 0.85);
      for (final angle in const [150.0, 200.0, 250.0]) {
        final a = angle * math.pi / 180;
        canvas.drawLine(
          center + Offset(math.cos(a) * body * 1.08, math.sin(a) * body * 1.08),
          center +
              Offset(
                math.cos(a) * body * (1.24 + 0.05 * breathe),
                math.sin(a) * body * (1.24 + 0.05 * breathe),
              ),
          ray,
        );
      }
      // The star climbs the crescent's opening and settles.
      final rise = (math.sin(phase * 2 * math.pi) + 1) / 2;
      _star(
        canvas,
        center + biteOffset * (0.55 + 0.25 * rise) + Offset(4 * scale, 0),
        math.max(2.2, s * 0.040),
        palette.accent,
      );
    }

    // — Night: three tiny, still stars in the late sky. —
    if (state == NoorFaceState.night) {
      _star(canvas, Offset(78 * scale, 22 * scale), s * 0.028, palette.inkSoft);
      _star(canvas, Offset(20 * scale, 24 * scale), s * 0.022, palette.inkSoft);
      _star(canvas, Offset(74 * scale, 64 * scale), s * 0.020, palette.inkSoft);
    }

    // — Thinking: three dots cycling above the opening. —
    if (state == NoorFaceState.thinking) {
      for (var i = 0; i < 3; i++) {
        final t = (phase + i / 3) % 1.0;
        // A bump that peaks at t = 0 and fades over a third of the cycle.
        final bump = math.max(0.0, 1.0 - t * 3);
        canvas.drawCircle(
          center + biteOffset * 0.85 + Offset((i - 1) * 9 * scale, 0),
          math.max(1.4, s * (0.020 + 0.008 * bump)),
          Paint()
            ..color = palette.accentDeep.withValues(alpha: 0.35 + 0.6 * bump),
        );
      }
    }

    // — The features, drawn directly on the ivory crescent's broad belly. —
    final featureColor = state == NoorFaceState.happy
        ? palette.onAccent
        : const Color(0xFF0F1E2E); // audit-ok: brand night disc
    final featureStroke = math.max(1.6, s * 0.050);
    final feature = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = featureStroke
      ..color = featureColor;

    final eyeL = center + Offset(-21 * scale, -3 * scale);
    final eyeR = center + Offset(-12.5 * scale, -3 * scale);
    final eyeR_ = math.max(3.0 * scale, s * 0.038);
    final blink = _blinking(phase);

    switch (state) {
      case NoorFaceState.calm:
      case NoorFaceState.night:
      case NoorFaceState.tender:
        // Closed eyes: two gentle downward arcs — contentment.
        _arcEye(canvas, eyeL, eyeR_, feature, up: false);
        _arcEye(canvas, eyeR, eyeR_, feature, up: false);
        _smile(canvas, center, scale, feature, open: false);
      case NoorFaceState.awake:
        if (blink) {
          _arcEye(canvas, eyeL, eyeR_, feature, up: false);
          _arcEye(canvas, eyeR, eyeR_, feature, up: false);
        } else {
          _openEye(canvas, eyeL, eyeR_, feature);
          _openEye(canvas, eyeR, eyeR_, feature);
        }
        _smile(canvas, center, scale, feature, open: false);
      case NoorFaceState.happy:
        // Happy closed eyes arc upward — the grin does the rest.
        _arcEye(canvas, eyeL, eyeR_, feature, up: true);
        _arcEye(canvas, eyeR, eyeR_, feature, up: true);
        _smile(canvas, center, scale, feature, open: true);
      case NoorFaceState.thinking:
        if (blink) {
          _arcEye(canvas, eyeL, eyeR_, feature, up: false);
          _arcEye(canvas, eyeR, eyeR_, feature, up: false);
        } else {
          // Eyes attend upward, toward the dots.
          _openEye(canvas, eyeL + Offset(0, -1.5 * scale), eyeR_, feature);
          _openEye(canvas, eyeR + Offset(0, -1.5 * scale), eyeR_, feature);
        }
        _smile(canvas, center, scale, feature, open: false, small: true);
    }
  }

  void _openEye(Canvas canvas, Offset c, double r, Paint paint) =>
      canvas.drawCircle(c, r * 0.55, paint..style = PaintingStyle.fill);

  void _arcEye(
    Canvas canvas,
    Offset c,
    double r,
    Paint paint, {
    required bool up,
  }) {
    final rect = Rect.fromCircle(center: c, radius: r);
    canvas.drawArc(
      rect,
      up ? 0 : math.pi,
      math.pi,
      false,
      paint..style = PaintingStyle.stroke,
    );
  }

  void _smile(
    Canvas canvas,
    Offset center,
    double scale,
    Paint paint, {
    required bool open,
    bool small = false,
  }) {
    final w = (small ? 5.5 : 7.0) * scale;
    final rect = Rect.fromCenter(
      center: center + Offset(-17 * scale, 7 * scale),
      width: w * 2,
      height: (open ? 9.0 : 6.0) * scale,
    );
    canvas.drawArc(
      rect,
      0,
      math.pi,
      false,
      paint..style = PaintingStyle.stroke,
    );
    if (open) {
      // The open grin fills in — the one filled feature on the face.
      canvas.drawArc(rect, 0, math.pi, true, paint..style = PaintingStyle.fill);
    }
  }

  /// A four-point sparkle star — two thin diamonds crossed.
  void _star(Canvas canvas, Offset c, double r, Color color) {
    final paint = Paint()
      ..style = PaintingStyle.fill
      ..color = color;
    final path = Path();
    for (var i = 0; i < 4; i++) {
      final a = i * math.pi / 2;
      final outward = Offset(math.cos(a), math.sin(a)) * r;
      final side =
          Offset(math.cos(a + math.pi / 4), math.sin(a + math.pi / 4)) *
          r *
          0.32;
      path
        ..moveTo(c.dx + outward.dx, c.dy + outward.dy)
        ..lineTo(c.dx + side.dx, c.dy + side.dy);
    }
    path.close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_NoorFacePainter old) =>
      old.state != state || old.phase != phase || old.palette != palette;
}
