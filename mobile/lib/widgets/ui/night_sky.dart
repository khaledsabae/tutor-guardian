/// Night-sky ambience shared by the bedtime surfaces.
///
/// The bedtime routine, the story bookshelf and the story reader each carried
/// their own copy of these — around 180 lines, differing only in a star count,
/// a firefly count and comment wording. The cost showed up on 2026-08-10, when
/// a post-dispose crash in [_Star] had to be found and patched twice because
/// the second copy was byte-identical to the first.
library;

import 'dart:math';

import 'package:flutter/material.dart';

/// A field of stars fading in and out at staggered intervals.
class TwinklingStars extends StatefulWidget {
  const TwinklingStars({super.key, this.count = 40});

  /// How many stars to scatter. The bookshelf uses a denser sky than the
  /// bedtime routine.
  final int count;

  @override
  State<TwinklingStars> createState() => _TwinklingStarsState();
}

class _TwinklingStarsState extends State<TwinklingStars>
    with TickerProviderStateMixin {
  late final List<_Star> _stars;

  @override
  void initState() {
    super.initState();
    final rng = Random();
    _stars = List.generate(
      widget.count,
      (_) => _Star(
        x: rng.nextDouble(),
        y: rng.nextDouble(),
        size: 1.2 + rng.nextDouble() * 2.2,
        delay: rng.nextDouble() * 3,
        duration: 2 + rng.nextDouble() * 2,
        vsync: this,
      ),
    );
  }

  @override
  void dispose() {
    for (final star in _stars) {
      star.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    return Stack(
      children: _stars
          .map(
            (s) => Positioned(
              left: s.x * size.width,
              top: s.y * size.height * 0.85,
              child: FadeTransition(
                opacity: s.animation,
                child: Container(
                  width: s.size,
                  height: s.size,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(s.size / 2),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.white.withValues(alpha: 0.6),
                        blurRadius: s.size * 1.5,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          )
          .toList(),
    );
  }
}

/// One star, owning its own controller so each can start on its own delay.
class _Star {
  _Star({
    required this.x,
    required this.y,
    required this.size,
    required this.delay,
    required this.duration,
    required TickerProvider vsync,
  }) {
    _controller = AnimationController(
      vsync: vsync,
      duration: Duration(milliseconds: (duration * 1000).round()),
    );
    animation = Tween<double>(begin: 0.15, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
    Future.delayed(Duration(milliseconds: (delay * 1000).round()), () {
      // The delay can outlive the screen: popping it before the star starts
      // would otherwise call repeat() on a disposed controller.
      if (!_disposed && !_controller.isAnimating && !_controller.isCompleted) {
        _controller.repeat(reverse: true);
      }
    });
  }

  final double x;
  final double y;
  final double size;
  final double delay;
  final double duration;
  late final AnimationController _controller;
  late final Animation<double> animation;

  bool _disposed = false;

  void dispose() {
    _disposed = true;
    _controller.dispose();
  }
}

/// Slow-drifting fireflies painted over the background.
class FloatingFireflies extends StatefulWidget {
  const FloatingFireflies({super.key, this.count = 20});

  /// How many fireflies to drift. The story reader uses a few more.
  final int count;

  @override
  State<FloatingFireflies> createState() => _FloatingFirefliesState();
}

class _FloatingFirefliesState extends State<FloatingFireflies>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  final List<_Firefly> _fireflies = [];
  final Random _random = Random();

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 40),
    )..repeat();

    for (var i = 0; i < widget.count; i++) {
      _fireflies.add(
        _Firefly(
          startX: _random.nextDouble(),
          startY: _random.nextDouble(),
          size: 1.5 + _random.nextDouble() * 3.5,
          speedY: 0.1 + _random.nextDouble() * 0.2,
          driftX: 0.02 + _random.nextDouble() * 0.04,
          maxOpacity: 0.2 + _random.nextDouble() * 0.45,
          pulseSpeed: 0.5 + _random.nextDouble() * 1.0,
        ),
      );
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return CustomPaint(
          painter: _FirefliesPainter(_fireflies, _controller.value),
          size: Size.infinite,
        );
      },
    );
  }
}

class _Firefly {
  _Firefly({
    required this.startX,
    required this.startY,
    required this.size,
    required this.speedY,
    required this.driftX,
    required this.maxOpacity,
    required this.pulseSpeed,
  });

  final double startX;
  final double startY;
  final double size;
  final double speedY;
  final double driftX;
  final double maxOpacity;
  final double pulseSpeed;
}

class _FirefliesPainter extends CustomPainter {
  _FirefliesPainter(this.fireflies, this.progress);

  final List<_Firefly> fireflies;
  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..style = PaintingStyle.fill;

    for (final f in fireflies) {
      final y = (f.startY - progress * f.speedY) % 1.0;
      final x = (f.startX + sin(progress * 2 * pi * f.pulseSpeed) * f.driftX) % 1.0;

      final pulse = (sin(progress * 4 * pi * f.pulseSpeed) + 1) / 2;
      final opacity = f.maxOpacity * (0.25 + 0.75 * pulse);
      final position = Offset(x * size.width, y * size.height);

      canvas.drawCircle(
        position,
        f.size * 2.5,
        Paint()
          ..color = const Color(0xFFFDE047).withValues(alpha: opacity * 0.25)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4.0),
      );

      paint.color = const Color(0xFFFDE047).withValues(alpha: opacity);
      canvas.drawCircle(position, f.size, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _FirefliesPainter oldDelegate) =>
      oldDelegate.progress != progress;
}
