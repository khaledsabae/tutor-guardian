/// A finger signature, drawn on a CustomPaint.
///
/// No package for this. `signature_pad` would be a new dependency for what is
/// a list of points and a Path, and the export path already needs a
/// RepaintBoundary — which this sits inside — so the widget tree does the work
/// either way.
///
/// The strokes are kept as separate lists rather than one point list with
/// break markers, because a signature lifted mid-name and continued is two
/// strokes, and joining them draws a line across the gap.
library;

import 'dart:ui' show PointMode;

import 'package:flutter/material.dart';

class SignaturePad extends StatefulWidget {
  const SignaturePad({
    super.key,
    required this.label,
    this.height = 140,
    this.onChanged,
  });

  final String label;
  final double height;

  /// Called with true once anything has been drawn. The screen uses it to
  /// enable the sign button — an empty box is not a signature.
  final ValueChanged<bool>? onChanged;

  @override
  State<SignaturePad> createState() => SignaturePadState();
}

class SignaturePadState extends State<SignaturePad> {
  final List<List<Offset>> _strokes = [];

  bool get isEmpty => _strokes.every((s) => s.isEmpty);

  void clear() {
    setState(_strokes.clear);
    widget.onChanged?.call(false);
  }

  void _start(Offset p) {
    setState(() => _strokes.add([p]));
    widget.onChanged?.call(true);
  }

  void _extend(Offset p) {
    if (_strokes.isEmpty) return;
    setState(() => _strokes.last.add(p));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(widget.label,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(fontWeight: FontWeight.w700)),
            if (!isEmpty)
              TextButton(onPressed: clear, child: const Text('امسح')),
          ],
        ),
        const SizedBox(height: 6),
        Container(
          height: widget.height,
          decoration: BoxDecoration(
            border: Border.all(color: theme.dividerColor),
            borderRadius: BorderRadius.circular(12),
          ),
          child: GestureDetector(
            onPanStart: (d) => _start(d.localPosition),
            onPanUpdate: (d) => _extend(d.localPosition),
            child: CustomPaint(
              painter: _SignaturePainter(_strokes, theme.colorScheme.onSurface),
              size: Size.infinite,
            ),
          ),
        ),
      ],
    );
  }
}

class _SignaturePainter extends CustomPainter {
  _SignaturePainter(this.strokes, this.color);

  final List<List<Offset>> strokes;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final brush = Paint()
      ..color = color
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..style = PaintingStyle.stroke;

    for (final stroke in strokes) {
      if (stroke.length == 1) {
        // A dot is a legitimate mark — a single tap should leave something.
        canvas.drawPoints(PointMode.points, stroke, brush);
        continue;
      }
      final path = Path()..moveTo(stroke.first.dx, stroke.first.dy);
      for (final p in stroke.skip(1)) {
        path.lineTo(p.dx, p.dy);
      }
      canvas.drawPath(path, brush);
    }
  }

  // Always. `strokes` is the same List instance for the pad's whole life —
  // _start and _extend mutate it in place — so `old.strokes != strokes` was
  // false on every single comparison and the canvas never repainted. A
  // signature appeared only for the one frame that clear() forced, by
  // changing the layout above it. Comparing identity of a mutable field is
  // the bug; a stroke list this small is not worth a defensive copy to make
  // the comparison meaningful.
  @override
  bool shouldRepaint(_SignaturePainter old) => true;
}
