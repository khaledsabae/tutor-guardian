/// «شمعة وقتك» — the child's time as a paper candle that grows shorter.
///
/// The study's rule (scratch/game-study/REPORT.md): time is shown as a candle,
/// never as a number. A number is something to bargain with — «خمس دقائق
/// كمان» is only a sentence you can say if you can read the five — and a
/// countdown pulls the eye to itself. A candle is felt: tall, shorter, a stub.
///
/// Two parts:
///  * [CandleClock] turns the server's `remaining_seconds` into how tall the
///    candle stands. It only ever goes down. The corner's session moves
///    between surfaces (story → game → task), and each new surface comes with
///    its own allowance, which can be larger than what was left — a candle
///    that grew back would teach that time comes back if you switch.
///  * [PaperCandle] draws it: an ivory stick on an emerald dish, with its solid
///    offset paper shadow, and a gold flame while time remains. The flame
///    sways a little through `syncLoop`, so with reduced motion (and on CI,
///    which runs with animations off) it stands perfectly still.
///
/// Words, not digits, in the label and for screen readers alike.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/motion.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_colors.dart';

/// Below this share of the allowance the candle says «بقي قليل».
const double kCandleLowBelow = .3;

/// The candle's height as a share of the first allowance it saw, never rising.
class CandleClock {
  int _full = 0;
  double _shown = 1;

  /// Whether the server gave a time at all. A session without one (the child
  /// surface switched off on the server) has no candle to draw.
  bool get known => _full > 0;

  /// 1 = a full candle, 0 = burnt down.
  double get fraction => _shown;

  /// Fold in the latest `remaining_seconds`. Null (no session, or between two
  /// surfaces) changes nothing.
  void observe(int? remaining) {
    if (remaining == null) return;
    if (_full == 0) {
      if (remaining <= 0) return;
      _full = remaining;
    }
    final next = (remaining / _full).clamp(0.0, 1.0);
    if (next < _shown) _shown = next;
  }

  /// The time is over: the candle rests as a stub, whatever comes next.
  void burnOut() => _shown = 0;
}

/// The three words the candle can say.
enum CandleState { bright, low, out }

CandleState candleStateFor(double fraction, {bool exitRitual = false}) {
  if (fraction <= 0) return CandleState.out;
  if (exitRitual || fraction < kCandleLowBelow) return CandleState.low;
  return CandleState.bright;
}

String candleWords(AppLocalizations l10n, CandleState state) => switch (state) {
  CandleState.bright => l10n.childCornerCandleBright,
  CandleState.low => l10n.childCornerCandleLow,
  CandleState.out => l10n.childCornerCandleOut,
};

/// The candle with its two lines: «شمعة وقتك» and how it is burning.
class CornerCandle extends StatelessWidget {
  const CornerCandle({
    super.key,
    required this.fraction,
    this.exitRitual = false,
    this.compact = false,
  });

  final double fraction;
  final bool exitRitual;

  /// One line, a smaller candle — inside the game, above its question.
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final paper = context.colors.corner;
    final state = candleStateFor(fraction, exitRitual: exitRitual);
    final words = candleWords(l10n, state);
    final theme = Theme.of(context);
    final label = l10n.childCornerCandleLabel;

    final candle = PaperCandle(
      key: const ValueKey('child_corner_candle'),
      fraction: fraction,
      size: compact ? 30 : 44,
    );

    return Semantics(
      container: true,
      label: '$label: $words',
      excludeSemantics: true,
      child: Container(
        padding: EdgeInsetsDirectional.fromSTEB(10, 6, compact ? 12 : 14, 6),
        decoration: BoxDecoration(
          color: paper.card,
          borderRadius: BorderRadius.circular(compact ? 16 : 20),
          boxShadow: [
            BoxShadow(color: paper.cardShadow, offset: const Offset(3, 4)),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            candle,
            const SizedBox(width: 8),
            Flexible(
              child: compact
                  // Inside a story or a game the candle beside it says what
                  // it is; the words alone are enough.
                  ? Text(
                      words,
                      style: theme.textTheme.labelLarge?.copyWith(
                        color: paper.ink,
                        fontWeight: FontWeight.w700,
                      ),
                    )
                  : Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          label,
                          style: theme.textTheme.labelMedium?.copyWith(
                            color: paper.ink.withValues(alpha: .8),
                            height: 1.3,
                          ),
                        ),
                        Text(
                          words,
                          style: theme.textTheme.titleSmall?.copyWith(
                            color: paper.ink,
                            fontWeight: FontWeight.w800,
                            height: 1.3,
                          ),
                        ),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The drawing alone: [size] tall, half as wide.
class PaperCandle extends StatefulWidget {
  const PaperCandle({super.key, required this.fraction, this.size = 44});

  /// 1 = full height, 0 = a stub with no flame.
  final double fraction;
  final double size;

  @override
  State<PaperCandle> createState() => PaperCandleState();
}

class PaperCandleState extends State<PaperCandle>
    with SingleTickerProviderStateMixin {
  late final AnimationController _sway = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  );

  /// Visible for tests: the reduced-motion contract is pinned, not assumed.
  @visibleForTesting
  bool get swaying => _sway.isAnimating;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncSway();
  }

  @override
  void didUpdateWidget(PaperCandle oldWidget) {
    super.didUpdateWidget(oldWidget);
    _syncSway();
  }

  void _syncSway() {
    if (widget.fraction <= 0) {
      // Burnt down: nothing left to sway.
      _sway
        ..stop()
        ..value = .5;
      return;
    }
    syncLoop(context, _sway, reverse: true, restValue: .5);
  }

  @override
  void dispose() {
    _sway.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final paper = c.corner;
    return ExcludeSemantics(
      child: SizedBox(
        width: widget.size * .5,
        height: widget.size,
        child: AnimatedBuilder(
          animation: _sway,
          builder: (context, _) => CustomPaint(
            painter: PaperCandlePainter(
              fraction: widget.fraction,
              sway: _sway.value * 2 - 1,
              wax: c.paperIvory,
              waxShadow: paper.cardShadow,
              dish: c.paperEmerald,
              dishShadow: c.paperShadow,
              flame: c.paperGold,
              wick: paper.onGold,
            ),
          ),
        ),
      ),
    );
  }
}

/// Paints the candle. [sway] runs −1…1 and only tilts the flame.
class PaperCandlePainter extends CustomPainter {
  const PaperCandlePainter({
    required this.fraction,
    required this.sway,
    required this.wax,
    required this.waxShadow,
    required this.dish,
    required this.dishShadow,
    required this.flame,
    required this.wick,
  });

  final double fraction;
  final double sway;
  final Color wax;
  final Color waxShadow;
  final Color dish;
  final Color dishShadow;
  final Color flame;
  final Color wick;

  /// The stick's height at a given fraction, as a share of the canvas — kept
  /// public so a test can measure "shorter" without reading pixels.
  static double stickShare(double fraction) =>
      .08 + .5 * fraction.clamp(0.0, 1.0);

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final unit = h / 48;
    final shadow = Offset(1.5 * unit, 2 * unit);
    final fill = Paint()..isAntiAlias = true;

    // The dish.
    final dishRect = RRect.fromRectAndRadius(
      Rect.fromLTWH(w * .05, h * .84, w * .9, h * .1),
      Radius.circular(h * .05),
    );
    canvas.drawRRect(dishRect.shift(shadow), fill..color = dishShadow);
    canvas.drawRRect(dishRect, fill..color = dish);

    // The stick, standing on the dish.
    final stickH = h * stickShare(fraction);
    final stickW = w * .46;
    final stickLeft = (w - stickW) / 2;
    final stickTop = h * .84 - stickH;
    final stick = RRect.fromRectAndCorners(
      Rect.fromLTWH(stickLeft, stickTop, stickW, stickH),
      topLeft: Radius.circular(stickW * .3),
      topRight: Radius.circular(stickW * .3),
    );
    canvas.drawRRect(stick.shift(shadow), fill..color = waxShadow);
    canvas.drawRRect(stick, fill..color = wax);

    // One drip down the side — the paper-cut detail that makes it a candle
    // and not a bar.
    if (stickH > h * .2) {
      final drip = Path()
        ..moveTo(stickLeft + stickW * .62, stickTop + stickW * .2)
        ..lineTo(stickLeft + stickW, stickTop + stickW * .2)
        ..lineTo(stickLeft + stickW, stickTop + stickH * .45)
        ..arcToPoint(
          Offset(stickLeft + stickW * .62, stickTop + stickH * .38),
          radius: Radius.circular(stickW * .2),
        )
        ..close();
      canvas.drawPath(drip, fill..color = waxShadow);
    }

    // The wick.
    final wickTop = Offset(w / 2, stickTop - h * .06);
    canvas.drawLine(
      Offset(w / 2, stickTop + unit),
      wickTop,
      Paint()
        ..color = wick
        ..strokeWidth = math.max(1.2, unit * 1.4)
        ..strokeCap = StrokeCap.round,
    );

    if (fraction <= 0) return;

    // The flame: a gold leaf on the wick, leaning with the sway.
    final fh = h * .22;
    final fw = w * .42;
    canvas.save();
    canvas.translate(wickTop.dx, wickTop.dy + unit);
    canvas.rotate(sway * .08);
    final leaf = Path()
      ..moveTo(0, -fh)
      ..cubicTo(fw * .55, -fh * .55, fw * .55, 0, 0, 0)
      ..cubicTo(-fw * .55, 0, -fw * .55, -fh * .55, 0, -fh)
      ..close();
    canvas.drawPath(leaf, fill..color = flame);
    canvas.restore();
  }

  @override
  bool shouldRepaint(PaperCandlePainter old) =>
      old.fraction != fraction ||
      old.sway != sway ||
      old.wax != wax ||
      old.waxShadow != waxShadow ||
      old.dish != dish ||
      old.dishShadow != dishShadow ||
      old.flame != flame ||
      old.wick != wick;
}
