/// NoorPresence — «نور» in a moon window (NOOR_WAL_QANADIL_PLAN, Phase 1).
///
/// A framed, breathing character rather than a loose illustration:
///
///   * a [ClipOval] moon window around [NoorFace] — the «ورق مقصوص» SVG
///     face, at every size (2026-10-14: the 1024² Recraft webp it showed at
///     hero sizes were rejected, and an SVG costs the same at 44 dp and 160);
///   * the window ground is the brand emerald #0F6B5C in BOTH themes — the
///     art's own card colour, so the ivory moon reads on a light page and a
///     dark one alike — with a rim in the live palette's accent;
///   * a drawn halo (CustomPainter), theme-driven, with two states — calm is
///     one soft breathing ring, proud adds rays and twin stars;
///   * the halo loop goes through `syncLoop`, so `reduceMotion` holds it
///     still instead of flickering at 20× speed (the face inside does the
///     same with its own breath and blink).
///
/// Used by the onboarding pages and waiting overlay, the tour card, Today's
/// header, the celebration overlay and the first-tip card.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/motion.dart';
import '../../../theme/app_colors.dart';
import 'noor_face.dart';

/// The two halo states. Calm is the default; proud marks a moment that was
/// earned (the last tour stop, a completed first lesson).
enum NoorMood { calm, proud }

/// The art's card colour (assets/svg/STYLE.md): the ground every «ورق مقصوص»
/// illustration is cut from. Fixed, not a palette role — it is the paper.
const kNoorWindowGround = Color(0xFF0F6B5C);

/// Below this window size a light-mode calm window keeps to one ring — its
/// rim — instead of rim plus breathing halo ring; at avatar sizes two rings
/// read as a target, not a moon.
const _kCompactBelow = 64.0;

class NoorPresence extends StatefulWidget {
  const NoorPresence({
    super.key,
    this.size = 96,
    this.mood = NoorMood.calm,
    this.semanticLabel,
    this.face,
  });

  /// The face's state, when the caller knows more than calm/proud
  /// («نور يتذكّر»: awake while asking, night after dark). Null → from [mood].
  final NoorFaceState? face;

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

  NoorFaceState get _faceState =>
      widget.face ??
      switch (widget.mood) {
        NoorMood.calm => NoorFaceState.calm,
        NoorMood.proud => NoorFaceState.happy,
      };

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final size = widget.size;
    final rim = math.max(1.5, size * .028);

    final window = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: kNoorWindowGround,
        // The rim is the live palette's gold, so the window still belongs
        // to the theme it sits in.
        border: Border.all(color: colors.accent, width: rim),
      ),
      child: ClipOval(
        // The crescent fills ~55% of the SVG's square; ×1.1 sets it at a
        // little under two thirds of the window, the paper shadow inside.
        child: OverflowBox(
          maxWidth: size * 1.1,
          maxHeight: size * 1.1,
          child: NoorFace(size: size * 1.1, state: _faceState),
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
              isDark: colors.isDark,
              compact: size < _kCompactBelow,
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
    required this.isDark,
    required this.compact,
  });

  final NoorMood mood;
  final double progress;
  final Color halo;
  final Color glow;
  final bool isDark;
  final bool compact;

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

    // The breathing ring. A compact light-mode calm window keeps to its rim
    // alone — one clean ring at avatar size.
    if (mood == NoorMood.proud || isDark || !compact) {
      canvas.drawCircle(
        center,
        radius * (1.0 + 0.045 * breathe),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(1.2, radius * .035)
          ..color = halo.withValues(alpha: 0.35 + 0.35 * breathe),
      );
    }

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
      old.mood != mood ||
      old.progress != progress ||
      old.halo != halo ||
      old.isDark != isDark ||
      old.compact != compact;
}
