/// A row of the week's paper lanterns ([PaperLantern] — one lantern shape in
/// the whole app), lighting one after another, and the dashed «next» lantern.
///
/// Shared by the string under ① on «اليوم», the Friday harvest card (which
/// replays the week's lanterns) and the shared harvest image (all lit at
/// once). Lighting is one short glow per lantern, nothing loops, and under
/// reduced motion every lantern is simply lit.
library;

import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' show PathMetric;

import 'package:flutter/material.dart';

import '../../../core/motion.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/paper_lantern.dart';

/// How long one lantern takes to light.
const kLanternLight = Duration(milliseconds: 350);

class LanternRow extends StatefulWidget {
  const LanternRow({
    super.key,
    required this.count,
    this.litFrom = 0,
    this.lighting = true,
    this.showNext = false,
    this.nextLabel,
    this.height = 30,
    this.stagger = const Duration(milliseconds: 180),
  });

  /// Lanterns in the row (one per lit day, seven at most).
  final int count;

  /// How many are lit from the first frame; the rest light one by one.
  final int litFrom;

  /// While false the unlit ones wait (the row is not on screen yet).
  final bool lighting;

  /// Add the dashed lantern a parenting step will light next.
  final bool showNext;

  /// Screen-reader label of the dashed lantern.
  final String? nextLabel;
  final double height;

  /// The pause before each next lantern lights.
  final Duration stagger;

  @override
  State<LanternRow> createState() => LanternRowState();
}

class LanternRowState extends State<LanternRow> {
  late int _shown = widget.litFrom.clamp(0, widget.count);
  Timer? _timer;

  /// Lanterns drawn lit right now (tests read it).
  @visibleForTesting
  int get shown => _shown;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _schedule();
  }

  @override
  void didUpdateWidget(LanternRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_shown > widget.count) _shown = widget.count;
    _schedule();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _schedule() {
    if (!widget.lighting || _shown >= widget.count || _timer != null) return;
    // No glow to watch under reduced motion: build draws them all lit.
    if (reduceMotion(context)) return;
    _timer = Timer(widget.stagger, () {
      _timer = null;
      if (!mounted) return;
      setState(() => _shown = math.min(_shown + 1, widget.count));
      _schedule();
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.lighting && reduceMotion(context)) _shown = widget.count;
    return Wrap(
      spacing: widget.height * .2,
      runSpacing: 6,
      crossAxisAlignment: WrapCrossAlignment.end,
      children: [
        for (var i = 0; i < widget.count; i++)
          PaperLantern(
            key: ValueKey('lantern-$i'),
            lit: i < _shown,
            height: widget.height,
            lightDuration: kLanternLight,
          ),
        if (widget.showNext)
          NextLantern(height: widget.height, label: widget.nextLabel),
      ],
    );
  }
}

/// The lantern a parenting step will light next: the same outline, dashed,
/// on nothing. An invitation — not a lantern that went out.
class NextLantern extends StatelessWidget {
  const NextLantern({super.key, this.height = 30, this.label});

  final double height;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final drawing = SizedBox(
      width: height * .75,
      height: height,
      child: CustomPaint(
        painter: NextLanternPainter(
          color: c.inkSoft.withValues(alpha: c.isDark ? .75 : .6),
        ),
      ),
    );
    return label == null
        ? ExcludeSemantics(child: drawing)
        : Semantics(label: label, excludeSemantics: true, child: drawing);
  }
}

/// The paper lantern's outline (its 48-grid ring, cap, pane and foot) in a
/// dashed line.
class NextLanternPainter extends CustomPainter {
  const NextLanternPainter({required this.color});

  final Color color;

  static const double _grid = 48;

  static final Path _outline = Path()
    ..addOval(Rect.fromCircle(center: const Offset(24, 7.5), radius: 2.6))
    // cap
    ..moveTo(14.5, 17.5)
    ..cubicTo(14.5, 13.5, 20, 12.5, 24, 9.5)
    ..cubicTo(28, 12.5, 33.5, 13.5, 33.5, 17.5)
    ..close()
    // pane
    ..moveTo(16, 19.5)
    ..lineTo(32, 19.5)
    ..lineTo(35, 27)
    ..lineTo(31, 35)
    ..lineTo(17, 35)
    ..lineTo(13, 27)
    ..close()
    // foot
    ..moveTo(18, 37)
    ..lineTo(30, 37)
    ..lineTo(28, 41.5)
    ..lineTo(20, 41.5)
    ..close();

  @override
  void paint(Canvas canvas, Size size) {
    final scale = size.height / _grid;
    if (scale <= 0) return;
    canvas.save();
    canvas.translate((size.width - _grid * scale) / 2, 0);
    canvas.scale(scale);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.8
      ..strokeCap = StrokeCap.round;
    for (final PathMetric m in _outline.computeMetrics()) {
      const dash = 2.6, gap = 2.2;
      var d = 0.0;
      while (d < m.length) {
        canvas.drawPath(m.extractPath(d, math.min(d + dash, m.length)), paint);
        d += dash + gap;
      }
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(NextLanternPainter old) => old.color != color;
}
