/// NoorPresence v0 — «نور» in a moon window (NOOR_WAL_QANADIL_PLAN, Phase 1).
///
/// The mascot already exists as three near-identical images on dark tiles;
/// what was missing is a *presence*: a framed, breathing character rather
/// than a loose illustration. v0 keeps it pure code around the existing
/// assets — no new art:
///
///   * a [ClipOval] moon window (rim + night ground from the live palette)
///     around the existing mascot image, `calm` → serene, `proud` → celebrate;
///   * `cacheWidth` matching the window so the 1024² source is never decoded
///     at full size for a 44 dp tour avatar;
///   * a drawn halo (CustomPainter) with two states — calm is one soft
///     breathing ring, proud adds rays and twin stars;
///   * the halo loop goes through `syncLoop`, so `reduceMotion` holds it
///     still instead of flickering at 20× speed.
///
/// Used by the onboarding waiting overlay, the tour card and the first-tip
/// card. Home and the celebration overlay adopt it later (Phase 1 continues).
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/motion.dart';
import '../../../theme/app_colors.dart';

/// The two halo states of v0. Calm is the default; proud marks a moment
/// that was earned (the last tour stop, a completed first lesson later).
enum NoorMood { calm, proud }

class NoorPresence extends StatefulWidget {
  const NoorPresence({
    super.key,
    this.size = 96,
    this.mood = NoorMood.calm,
    this.semanticLabel,
  });

  /// Diameter of the moon window itself. The halo paints slightly outside
  /// it (×1.3), so callers size the window, not the whole footprint.
  final double size;
  final NoorMood mood;

  /// Screen-reader name. Null omits semantics (the mascot is decorative in
  /// most placements, same as [NoorMascot]).
  final String? semanticLabel;

  @override
  State<NoorPresence> createState() => NoorPresenceState();
}

class NoorPresenceState extends State<NoorPresence>
    with SingleTickerProviderStateMixin {
  late final AnimationController _halo;

  /// Whether the halo is animating. Visible for tests so the reduced-motion
  /// contract is pinned, not assumed.
  @visibleForTesting
  bool get haloLooping => _halo.isAnimating;

  @override
  void initState() {
    super.initState();
    _halo = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2600),
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Reduced motion: a static halo at its mid state (nothing half-drawn),
    // exactly like the bedtime fireflies. Runs on every dependency change so
    // toggling the system setting mid-session is honoured immediately.
    syncLoop(context, _halo, reverse: true, restValue: .5);
  }

  @override
  void dispose() {
    _halo.dispose();
    super.dispose();
  }

  String get _asset => switch (widget.mood) {
        NoorMood.calm => 'assets/images/generated/mascot_serene.webp',
        NoorMood.proud => 'assets/images/generated/mascot_celebrate.webp',
      };

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final size = widget.size;
    final rim = math.max(1.5, size * .028);
    // Decode at the window's physical pixels — never the 1024² source.
    final dpr = MediaQuery.devicePixelRatioOf(context);
    final cacheWidth = (size * dpr).round();

    final window = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        // The night ground the mascot tiles already sit on, and the gold rim
        // — both palette roles, so the window survives a theme flip.
        color: colors.surfaceAlt,
        border: Border.all(color: colors.accent, width: rim),
      ),
      child: ClipOval(
        child: Image.asset(
          _asset,
          fit: BoxFit.cover,
          cacheWidth: cacheWidth,
          filterQuality: FilterQuality.medium,
          excludeFromSemantics: true,
          // The mascot is bundled; a missing file is a build defect. The
          // crescent fallback keeps the window — and the layout around it —
          // intact instead of collapsing to an empty oval.
          errorBuilder: (_, _, _) => Icon(
            Icons.nightlight_round,
            size: size * .6,
            color: colors.primary,
          ),
        ),
      ),
    );

    return Semantics(
      label: widget.semanticLabel,
      excludeSemantics: widget.semanticLabel == null,
      child: SizedBox(
        width: size * 1.3,
        height: size * 1.3,
        child: AnimatedBuilder(
          animation: _halo,
          builder: (context, _) => CustomPaint(
            painter: _HaloPainter(
              mood: widget.mood,
              progress: _halo.value,
              halo: colors.accent,
              glow: colors.primary,
            ),
            child: Center(child: window),
          ),
        ),
      ),
    );
  }
}

/// The drawn halo. Calm: one breathing ring inside a soft glow. Proud: the
/// same ring plus four short rays and two small stars — enough to read as
/// "earned", not enough to become a party.
class _HaloPainter extends CustomPainter {
  const _HaloPainter({
    required this.mood,
    required this.progress,
    required this.halo,
    required this.glow,
  });

  final NoorMood mood;
  final double progress;
  final Color halo;
  final Color glow;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.shortestSide / 2;
    // A full sine cycle per loop pass: the ring swells and settles.
    final breathe = (math.sin(progress * 2 * math.pi) + 1) / 2;

    // Soft glow behind the window.
    canvas.drawCircle(
      center,
      radius * (0.92 + 0.06 * breathe),
      Paint()
        ..color = glow.withValues(alpha: mood == NoorMood.proud ? 0.22 : 0.12)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 14),
    );

    // The breathing ring.
    canvas.drawCircle(
      center,
      radius * (1.0 + 0.045 * breathe),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(1.2, radius * .035)
        ..color = halo.withValues(alpha: 0.35 + 0.35 * breathe),
    );

    if (mood == NoorMood.proud) {
      // Four short rays on the diagonals.
      final rayPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = math.max(1.2, radius * .04)
        ..strokeCap = StrokeCap.round
        ..color = halo.withValues(alpha: 0.85);
      for (final angle in const [45.0, 135.0, 225.0, 315.0]) {
        final a = angle * math.pi / 180;
        final inner = radius * 1.02;
        final outer = radius * (1.16 + 0.05 * breathe);
        canvas.drawLine(
          center + Offset(math.cos(a) * inner, math.sin(a) * inner),
          center + Offset(math.cos(a) * outer, math.sin(a) * outer),
          rayPaint,
        );
      }
      // Two small stars, opposite corners.
      final starPaint = Paint()..color = halo.withValues(alpha: 0.9);
      for (final (dx, dy) in const [(-0.95, -0.95), (0.95, 0.95)]) {
        canvas.drawCircle(
          center + Offset(dx * radius, dy * radius),
          math.max(1.0, radius * .035),
          starPaint,
        );
      }
    }
  }

  @override
  bool shouldRepaint(_HaloPainter old) =>
      old.mood != mood || old.progress != progress || old.halo != halo;
}
