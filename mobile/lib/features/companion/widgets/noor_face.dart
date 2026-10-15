/// NoorFace — «نور» in the «ورق مقصوص» paper-cut set (2026-10-14).
///
/// The face used to be drawn in code on a night-navy disc; the owner chose a
/// paper-cut direction instead, and Noor is now seven hand-written SVGs under
/// assets/svg/noor/ — an ivory crescent with a solid emerald paper shadow,
/// on a transparent ground. Six of them are the states here:
///
///   * [NoorFaceState.calm] — eyes closed in contentment (noor_calm).
///   * [NoorFaceState.awake] — eyes open, attending (noor_awake).
///   * [NoorFaceState.happy] — a moment earned (noor_happy).
///   * [NoorFaceState.thinking] — while an answer is written (noor_thinking).
///   * [NoorFaceState.night] — after dark, sleepy (noor_sleepy).
///   * [NoorFaceState.tender] — for «لم تنجح»: warmth, not pity (noor_tender).
///
/// Two motions live on one 4-second cycle: a ~2% breath over the whole pass,
/// and — on the open-eyed faces, awake and happy — a blink: noor_calm shown
/// for the first 140 ms. Both pictures stay mounted and only their opacity
/// flips, so a blink never waits on a parse. The cycle goes through
/// [syncLoop]: under `disableAnimations`, or in a tab whose TickerMode is
/// off, the face rests — eyes open, mid-breath — instead of flickering (CI
/// journeys run with animations disabled; a looping face would hang them).
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../../core/motion.dart';

/// The six expressions. Calm is the resting face; the others are moments.
enum NoorFaceState { calm, awake, happy, thinking, night, tender }

/// The SVG each state shows. [NoorFaceState.night] is the sleepy face.
String noorFaceAsset(NoorFaceState state) => switch (state) {
  NoorFaceState.calm => 'assets/svg/noor/noor_calm.svg',
  NoorFaceState.awake => 'assets/svg/noor/noor_awake.svg',
  NoorFaceState.happy => 'assets/svg/noor/noor_happy.svg',
  NoorFaceState.thinking => 'assets/svg/noor/noor_thinking.svg',
  NoorFaceState.night => 'assets/svg/noor/noor_sleepy.svg',
  NoorFaceState.tender => 'assets/svg/noor/noor_tender.svg',
};

/// The faces with open eyes — the only ones a blink means anything on.
const _blinks = {NoorFaceState.awake, NoorFaceState.happy};

/// «نور» at [size]. The SVG is drawn on a 240 grid and the crescent fills a
/// little over half of it, leaving room for the paper shadow.
class NoorFace extends StatefulWidget {
  const NoorFace({
    super.key,
    this.size = 56,
    this.state = NoorFaceState.calm,
    this.semanticLabel,
  });

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

  /// Whether the blink frame (noor_calm over an open-eyed face) is showing
  /// right now. Visible for tests: a resting face never sits mid-blink.
  @visibleForTesting
  bool get blinking =>
      _blinks.contains(widget.state) && _blinking(_cycle.value);

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
    // Rest value 0.5: past the blink window (eyes open), mid-breath — a
    // complete, calm frame. Re-synced on dependency changes so toggling the
    // system setting mid-session, or leaving a tab, is honoured immediately.
    syncLoop(context, _cycle, restValue: .5);
  }

  @override
  void dispose() {
    _cycle.dispose();
    super.dispose();
  }

  SvgPicture _picture(NoorFaceState state) => SvgPicture.asset(
    noorFaceAsset(state),
    width: widget.size,
    height: widget.size,
    excludeFromSemantics: true,
  );

  @override
  Widget build(BuildContext context) {
    final canBlink = _blinks.contains(widget.state);
    final face = _picture(widget.state);
    // Mounted beside the face (at opacity 0) only where a blink can happen,
    // so the closed-eye frame is parsed and ready before the first blink.
    final closed = canBlink ? _picture(NoorFaceState.calm) : null;

    return Semantics(
      label: widget.semanticLabel,
      excludeSemantics: widget.semanticLabel == null,
      child: SizedBox(
        width: widget.size,
        height: widget.size,
        child: RepaintBoundary(
          child: AnimatedBuilder(
            animation: _cycle,
            builder: (context, _) {
              final phase = _cycle.value;
              final blink = canBlink && _blinking(phase);
              // One sine per pass, 1.00 → 1.02 → 1.00: a breath, not a bob.
              final breath = 1 + .01 * (1 - math.cos(phase * 2 * math.pi));
              return Transform.scale(
                scale: breath,
                // Its own layer: the breath only re-composites it, the
                // pictures are not re-recorded every frame.
                child: RepaintBoundary(
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Opacity(opacity: blink ? 0 : 1, child: face),
                      if (closed != null)
                        Opacity(opacity: blink ? 1 : 0, child: closed),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

/// One blink per cycle: closed only in the first 140 ms of the 4 s pass.
bool _blinking(double phase) => phase < 0.035;
