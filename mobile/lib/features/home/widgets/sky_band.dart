/// «السماء» behind Noor on «اليوم» (plan phase 2, SkyBand): a paper-cut sky
/// that follows the local hour — dawn, day, maghrib, night — cut in the same
/// flat layers as the «ورق مقصوص» art (assets/svg/STYLE.md): no gradient, no
/// blur, two hills and a sun, or at night up to twelve stars and no sun (the
/// moon in that sky is Noor).
///
/// In Ramadan (plan phase 5, «جلد ليل رمضاني») the maghrib and night skies
/// carry one quiet touch more: a thin string of paper lanterns on the
/// horizon, lit gold. Nothing else changes — the same palette, the same
/// hills, no crescent of its own (the crescent in that sky is Noor), and
/// never by day.
///
/// Decoration only. Every word on it sits in Noor's bubble on the surface
/// colour, so the sky never carries text and its contrast never matters to
/// reading.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

enum SkyTime { dawn, day, maghrib, night }

/// The sky for a local time. Maghrib is its own short band (16–19) so the
/// sky turns before the «مساء الخير» greeting does.
SkyTime skyTimeOf(DateTime t) {
  final h = t.hour;
  if (h >= 4 && h < 7) return SkyTime.dawn;
  if (h >= 7 && h < 16) return SkyTime.day;
  if (h >= 16 && h < 19) return SkyTime.maghrib;
  return SkyTime.night;
}

/// One sky's paper: the sheet, the far and near hills, and the sun (null at
/// night).
@immutable
class SkyPaper {
  const SkyPaper({
    required this.sky,
    required this.farHill,
    required this.nearHill,
    this.sun,
    this.sunHigh = true,
  });

  final Color sky;
  final Color farHill;
  final Color nearHill;
  final Color? sun;

  /// High in the corner by day; low on the hills at dawn and maghrib.
  final bool sunHigh;

  /// The palette of assets/svg/STYLE.md. On a dark page the day skies are
  /// cut from deep emerald too — a pastel card would glare at night.
  static SkyPaper of(SkyTime time, Brightness brightness) {
    final dark = brightness == Brightness.dark;
    return switch (time) {
      SkyTime.dawn =>
        dark
            ? const SkyPaper(
                sky: Color(0xFF1B302C),
                farHill: Color(0xFF2C4842),
                nearHill: Color(0xFF094A40),
                sun: Color(0xFFF4A492),
                sunHigh: false,
              )
            : const SkyPaper(
                sky: Color(0xFFFBE7DA),
                farHill: Color(0xFFEADBC0),
                nearHill: Color(0xFFD9C7A7),
                sun: Color(0xFFF4A492),
                sunHigh: false,
              ),
      SkyTime.day =>
        dark
            ? const SkyPaper(
                sky: Color(0xFF15372F),
                farHill: Color(0xFF0D6A5A),
                nearHill: Color(0xFF094A40),
                sun: Color(0xFFF7C548),
              )
            : const SkyPaper(
                sky: Color(0xFFE8F6EF),
                farHill: Color(0xFFA8E6C4),
                nearHill: Color(0xFF7ED3A6),
                sun: Color(0xFFF7C548),
              ),
      SkyTime.maghrib =>
        dark
            ? const SkyPaper(
                sky: Color(0xFF22302C),
                farHill: Color(0xFF6B4038),
                nearHill: Color(0xFF094A40),
                sun: Color(0xFFF7C548),
                sunHigh: false,
              )
            : const SkyPaper(
                sky: Color(0xFFFBE4CC),
                farHill: Color(0xFFF4A492),
                nearHill: Color(0xFF12806D),
                sun: Color(0xFFF7C548),
                sunHigh: false,
              ),
      SkyTime.night =>
        dark
            ? const SkyPaper(
                sky: Color(0xFF0B2622),
                farHill: Color(0xFF0D4F44),
                nearHill: Color(0xFF083A33),
              )
            : const SkyPaper(
                sky: Color(0xFF0F3D36),
                farHill: Color(0xFF0D6A5A),
                nearHill: Color(0xFF094A40),
              ),
    };
  }
}

/// At most this many stars, and only at night.
const kMaxSkyStars = 12;

/// Where the stars sit, as fractions of the band — fixed, so the sky is the
/// same sky every time it is opened (and in every screenshot).
const _stars = <(double, double, double)>[
  (.08, .10, 2.4),
  (.20, .05, 1.4),
  (.33, .14, 1.8),
  (.47, .06, 1.2),
  (.58, .12, 2.6),
  (.70, .04, 1.4),
  (.82, .11, 1.8),
  (.93, .07, 2.2),
  (.14, .30, 1.2),
  (.88, .28, 1.4),
  (.52, .24, 1.2),
  (.03, .45, 1.4),
];

/// Where the Ramadan lanterns hang along the band, as fractions of its
/// width — fixed like the stars. Five, spread out: a string, not a crowd.
/// Each hangs at the low point of its own swag of thread.
const _lanterns = <double>[.1, .3, .5, .7, .9];

/// At most this many lanterns on the Ramadan string.
const kMaxSkyLanterns = 5;

/// Whether [time]'s sky takes the Ramadan skin: maghrib and night only.
bool skyTakesRamadanSkin(SkyTime time) =>
    time == SkyTime.maghrib || time == SkyTime.night;

/// Wraps Today's top (Noor and the bubble) in the sky of [now].
class SkyBand extends StatelessWidget {
  const SkyBand({
    super.key,
    required this.child,
    this.now,
    this.ramadan = false,
  });

  final Widget child;

  /// Defaults to the device's local time; tests pin it.
  final DateTime? now;

  /// The month itself is on (the server's `ramadan.state == ramadan`): the
  /// maghrib and night skies hang their lantern string.
  final bool ramadan;

  @override
  Widget build(BuildContext context) {
    final time = skyTimeOf(now ?? DateTime.now());
    final paper = SkyPaper.of(time, Theme.of(context).brightness);
    return ClipRRect(
      borderRadius: BorderRadius.circular(24),
      child: CustomPaint(
        painter: SkyPainter(
          paper: paper,
          time: time,
          textDirection: Directionality.of(context),
          ramadan: ramadan,
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 18, 12, 34),
          child: child,
        ),
      ),
    );
  }
}

class SkyPainter extends CustomPainter {
  SkyPainter({
    required this.paper,
    required this.time,
    required this.textDirection,
    this.ramadan = false,
  });

  final SkyPaper paper;
  final SkyTime time;
  final TextDirection textDirection;
  final bool ramadan;

  /// Stars painted on the last [paint] — exposed for the test that holds the
  /// «twelve at most, night only» rule.
  int starsPainted = 0;

  /// Ramadan lanterns painted on the last [paint] — the test holds «in
  /// Ramadan, maghrib and night only».
  int lanternsPainted = 0;

  static const _shadow = Color(0x220F3D36);

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    canvas.drawRect(Offset.zero & size, Paint()..color = paper.sky);

    // The far end of the band (Noor sits at the start): the sun's corner.
    final rtl = textDirection == TextDirection.rtl;
    double endX(double fromEnd) => rtl ? fromEnd : w - fromEnd;

    starsPainted = 0;
    if (time == SkyTime.night) {
      final star = Paint()..color = const Color(0xFFF7C548);
      final dot = Paint()..color = const Color(0xFFFBF1DE);
      for (final (fx, fy, r) in _stars.take(kMaxSkyStars)) {
        final c = Offset(fx * w, fy * h + 4);
        if (r >= 1.8) {
          canvas.drawPath(_sparkle(c, r * 1.8), star);
        } else {
          canvas.drawCircle(c, r, dot);
        }
        starsPainted++;
      }
    }

    final sun = paper.sun;
    if (sun != null) {
      // Low suns sit on the horizon below the bubble, half behind the hills.
      final c = paper.sunHigh ? Offset(endX(34), 16) : Offset(endX(64), h - 18);
      final r = paper.sunHigh ? 18.0 : 15.0;
      canvas.drawCircle(c.translate(1.5, 2), r, Paint()..color = _shadow);
      canvas.drawCircle(c, r, Paint()..color = sun);
    }

    // Two paper hills, each a little shadow on the layer behind it.
    final far = _hill(size, base: h - 20, amp: 9, phase: rtl ? .9 : .1);
    final near = _hill(size, base: h - 9, amp: 6, phase: rtl ? .25 : .7);
    canvas.drawPath(far.shift(const Offset(0, -2)), Paint()..color = _shadow);
    canvas.drawPath(far, Paint()..color = paper.farHill);
    canvas.drawPath(near.shift(const Offset(0, -2)), Paint()..color = _shadow);
    canvas.drawPath(near, Paint()..color = paper.nearHill);

    lanternsPainted = 0;
    if (ramadan && skyTakesRamadanSkin(time)) {
      _lanternString(canvas, size, sun: sun == null ? null : endX(64));
    }
  }

  /// The Ramadan string: five shallow swags of thread across the horizon,
  /// under the bubble, with a small paper lantern hanging from the low point
  /// of each — lit gold, a solid paper shadow, no glow. [sun] is the x of a low sun on the
  /// horizon; no lantern hangs in front of it (gold on gold reads as a blot).
  void _lanternString(Canvas canvas, Size size, {double? sun}) {
    final w = size.width, h = size.height;
    final dark = paper.sky.computeLuminance() < .2;
    // On a dark sky the thread is ivory paper; on maghrib's pale one, ink.
    final thread = dark ? const Color(0xFFEADBC0) : const Color(0xFF0D6A5A);
    final cap = dark ? const Color(0xFFEADBC0) : const Color(0xFF0F3D36);
    final shadow = dark ? const Color(0xFF062B26) : _shadow;

    final top = h - 31;
    const sag = 5.0;
    final swag = w / _lanterns.length;
    double ropeY(double x) {
      // Each swag a parabola, hung between two neighbouring tie points.
      final t = (x % swag) / swag;
      return top + sag * 4 * t * (1 - t);
    }

    final rope = Path()..moveTo(0, top);
    for (var i = 1; i <= 60; i++) {
      final x = w * i / 60;
      rope.lineTo(x, i % 12 == 0 ? top : ropeY(x));
    }
    canvas.drawPath(
      rope,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..strokeCap = StrokeCap.round
        ..color = thread,
    );

    final gold = Paint()..color = const Color(0xFFF7C548);
    for (final fx in _lanterns.take(kMaxSkyLanterns)) {
      final x = fx * w;
      if (sun != null && (x - sun).abs() < 26) continue;
      final y = ropeY(x);
      final body = _lantern(Offset(x, y + 3));
      canvas
        ..drawLine(
          Offset(x, y),
          Offset(x, y + 3),
          Paint()
            ..strokeWidth = 1
            ..color = thread,
        )
        ..drawPath(body.shift(const Offset(1, 1.5)), Paint()..color = shadow)
        ..drawPath(body, gold)
        ..drawRRect(
          RRect.fromRectAndRadius(
            Rect.fromCenter(center: Offset(x, y + 3.8), width: 6, height: 2),
            const Radius.circular(1),
          ),
          Paint()..color = cap,
        );
      lanternsPainted++;
    }
  }

  /// A small paper lantern hanging from [top]: a waisted body, wider in the
  /// middle, with a short point underneath.
  Path _lantern(Offset top) {
    final x = top.dx, y = top.dy;
    return Path()
      ..moveTo(x - 2.8, y + 1)
      ..lineTo(x + 2.8, y + 1)
      ..quadraticBezierTo(x + 5.6, y + 6.5, x + 3.1, y + 12)
      ..lineTo(x + 1, y + 12)
      ..lineTo(x, y + 14.4)
      ..lineTo(x - 1, y + 12)
      ..lineTo(x - 3.1, y + 12)
      ..quadraticBezierTo(x - 5.6, y + 6.5, x - 2.8, y + 1)
      ..close();
  }

  /// A soft rolling hill across the width: two bumps, closed at the bottom.
  Path _hill(
    Size size, {
    required double base,
    required double amp,
    required double phase,
  }) {
    final w = size.width;
    final p = Path()..moveTo(0, size.height);
    const steps = 24;
    for (var i = 0; i <= steps; i++) {
      final x = w * i / steps;
      final y = base - amp * math.sin((i / steps + phase) * math.pi * 2);
      p.lineTo(x, y);
    }
    return p
      ..lineTo(w, size.height)
      ..close();
  }

  /// A four-point paper star.
  Path _sparkle(Offset c, double r) {
    final k = r * .32;
    return Path()
      ..moveTo(c.dx, c.dy - r)
      ..quadraticBezierTo(c.dx + k * .3, c.dy - k * .3, c.dx + r, c.dy)
      ..quadraticBezierTo(c.dx + k * .3, c.dy + k * .3, c.dx, c.dy + r)
      ..quadraticBezierTo(c.dx - k * .3, c.dy + k * .3, c.dx - r, c.dy)
      ..quadraticBezierTo(c.dx - k * .3, c.dy - k * .3, c.dx, c.dy - r)
      ..close();
  }

  @override
  bool shouldRepaint(SkyPainter old) =>
      old.paper != paper ||
      old.time != time ||
      old.textDirection != textDirection ||
      old.ramadan != ramadan;
}
