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
/// In the three quiet seasons («سماوات المواسم», عالم الأسرة) every sky of
/// the day carries one paper touch more, from the server's `hijri_season`,
/// all of it along the top edge — the bottom may hold the «على الأفق» strip:
/// Rajab hangs three small eight-point paper stars, Sha'ban strings paper
/// bunting overhead (the street getting ready), and the first days of Dhu
/// al-Hijjah send three small paper birds across the sky, with a row of
/// white tents on the far hill when nothing covers it. Never two at once,
/// never with the Ramadan string, and never a word.
///
/// Decoration only. Every word on it sits in Noor's bubble on the surface
/// colour, so the sky never carries text and its contrast never matters to
/// reading.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../programs/data/programs_models.dart' show HijriSeasonMonth;

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

/// Rajab's paper stars, Sha'ban's flags and Dhu al-Hijjah's tents: at most
/// this many marks of one season in one sky.
const kMaxSeasonMarks = 9;

/// Where Rajab's stars hang, as fractions of the width — clear of the sun's
/// corner at both ends.
const _rajabStarXs = <double>[.3, .5, .7];

/// Sha'ban's bunting: this many flags across the band.
const _shabanFlags = 9;

/// Dhu al-Hijjah's tents on the far hill, as fractions of the width.
const _hijjahTents = <double>[.16, .24, .32, .4];

/// Dhu al-Hijjah's birds: (x as a fraction of the width, y, size), toward the
/// middle of the band, clear of the sun's corner.
const _hijjahBirds = <(double, double, double)>[
  (.42, 8, 6),
  (.5, 12, 5),
  (.58, 7, 5.5),
];

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
    this.season,
    this.footer,
  });

  final Widget child;

  /// The server's `hijri_season`, when today is in one of the three — every
  /// sky of the day takes its quiet paper touch. Ignored in Ramadan.
  final HijriSeasonMonth? season;

  /// A slim line laid on the hills under [child] («على الأفق»). It takes the
  /// band's bottom margin, so the band grows by little more than the line.
  final Widget? footer;

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
          season: ramadan ? null : season,
        ),
        child: footer == null
            ? Padding(
                padding: const EdgeInsets.fromLTRB(12, 18, 12, 34),
                child: child,
              )
            : Padding(
                padding: const EdgeInsets.fromLTRB(12, 18, 12, 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [child, const SizedBox(height: 12), footer!],
                ),
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
    this.season,
  });

  final SkyPaper paper;
  final SkyTime time;
  final TextDirection textDirection;
  final bool ramadan;
  final HijriSeasonMonth? season;

  /// Season marks painted on the last [paint] (stars, flags or tents) — the
  /// test holds «one season at a time, never in Ramadan».
  int seasonMarksPainted = 0;

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

    seasonMarksPainted = 0;
    final season = ramadan ? null : this.season;
    if (season == HijriSeasonMonth.rajab) {
      _rajabStars(canvas, size);
    }

    // Two paper hills, each a little shadow on the layer behind it.
    final farPhase = rtl ? .9 : .1;
    final far = _hill(size, base: h - 20, amp: 9, phase: farPhase);
    final near = _hill(size, base: h - 9, amp: 6, phase: rtl ? .25 : .7);
    canvas.drawPath(far.shift(const Offset(0, -2)), Paint()..color = _shadow);
    canvas.drawPath(far, Paint()..color = paper.farHill);
    if (season == HijriSeasonMonth.dhulHijjah) {
      // On the far hill, in front of it and behind the near one.
      _tents(canvas, size, farPhase: farPhase, rtl: rtl);
    }
    canvas.drawPath(near.shift(const Offset(0, -2)), Paint()..color = _shadow);
    canvas.drawPath(near, Paint()..color = paper.nearHill);

    if (season == HijriSeasonMonth.shaban) {
      _bunting(canvas, size, sun: sun != null && paper.sunHigh ? endX(34) : null);
    }
    if (season == HijriSeasonMonth.dhulHijjah) {
      _birds(canvas, size, rtl: rtl);
    }

    lanternsPainted = 0;
    if (ramadan && skyTakesRamadanSkin(time)) {
      _lanternString(canvas, size, sun: sun == null ? null : endX(64));
    }
  }

  bool get _darkSky => paper.sky.computeLuminance() < .2;

  /// Rajab: three small eight-point paper stars on short threads from the
  /// top edge, above the bubble — ivory on a dark sky, emerald on a pale one.
  void _rajabStars(Canvas canvas, Size size) {
    final w = size.width;
    final dark = _darkSky;
    final fill = Paint()
      ..color = dark ? const Color(0xFFFBF1DE) : const Color(0xFF12806D);
    final shade = Paint()
      ..color = dark ? const Color(0xFF062B26) : _shadow;
    final thread = Paint()
      ..strokeWidth = 1
      ..color = dark ? const Color(0xFFEADBC0) : const Color(0xFF0D6A5A);
    for (final (i, fx) in _rajabStarXs.indexed) {
      if (seasonMarksPainted >= kMaxSeasonMarks) break;
      final x = fx * w;
      // The middle star hangs a little lower: a garland, not a ruler.
      final cy = i == 1 ? 11.0 : 9.0;
      canvas.drawLine(Offset(x, 0), Offset(x, cy - 5), thread);
      final star = _eightPoint(Offset(x, cy), 5.2);
      canvas
        ..drawPath(star.shift(const Offset(1, 1.4)), shade)
        ..drawPath(star, fill);
      seasonMarksPainted++;
    }
  }

  /// Sha'ban: paper bunting on a thread hung overhead along the top edge —
  /// small flags, ivory and coral (emerald and coral on a pale sky), no glow,
  /// none in front of a high sun.
  void _bunting(Canvas canvas, Size size, {double? sun}) {
    final w = size.width;
    final dark = _darkSky;
    const swags = 3;
    const sag = 5.0;
    final span = w / swags;
    double ropeY(double x) {
      final t = (x % span) / span;
      return 1 + sag * 4 * t * (1 - t);
    }

    final rope = Path()..moveTo(0, 1);
    for (var i = 1; i <= 60; i++) {
      final x = w * i / 60;
      rope.lineTo(x, i % 20 == 0 ? 1 : ropeY(x));
    }
    canvas.drawPath(
      rope,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.1
        ..color = dark ? const Color(0xFFEADBC0) : const Color(0xFF0D6A5A),
    );
    final a = Paint()
      ..color = dark ? const Color(0xFFFBF1DE) : const Color(0xFF12806D);
    final b = Paint()..color = const Color(0xFFF4A492);
    final shade = Paint()..color = dark ? const Color(0xFF062B26) : _shadow;
    for (var i = 0; i < _shabanFlags; i++) {
      if (seasonMarksPainted >= kMaxSeasonMarks) break;
      final x = w * (i + .5) / _shabanFlags;
      if (sun != null && (x - sun).abs() < 30) continue;
      final y = ropeY(x);
      final flag = Path()
        ..moveTo(x - 5, y)
        ..lineTo(x + 5, y)
        ..lineTo(x, y + 9)
        ..close();
      canvas
        ..drawPath(flag.shift(const Offset(1, 1.4)), shade)
        ..drawPath(flag, i.isEven ? a : b);
      seasonMarksPainted++;
    }
  }

  /// Dhu al-Hijjah: three small paper birds high in the sky, flying away
  /// from Noor's side — travellers, not a flock.
  void _birds(Canvas canvas, Size size, {required bool rtl}) {
    final w = size.width;
    final dark = _darkSky;
    final fill = Paint()
      ..color = dark ? const Color(0xFFFBF1DE) : const Color(0xFF0D6A5A);
    final shade = Paint()..color = dark ? const Color(0xFF062B26) : _shadow;
    for (final (fx, y, r) in _hijjahBirds) {
      if (seasonMarksPainted >= kMaxSeasonMarks) break;
      final x = (rtl ? 1 - fx : fx) * w;
      // Two paper wings meeting at the body, the tips raised.
      final bird = Path()
        ..moveTo(x - r, y - r * .45)
        ..quadraticBezierTo(x - r * .45, y - r * .2, x, y + r * .25)
        ..quadraticBezierTo(x + r * .45, y - r * .2, x + r, y - r * .45)
        ..quadraticBezierTo(x + r * .4, y + r * .15, x, y + r * .6)
        ..quadraticBezierTo(x - r * .4, y + r * .15, x - r, y - r * .45)
        ..close();
      canvas
        ..drawPath(bird.shift(const Offset(1, 1.2)), shade)
        ..drawPath(bird, fill);
      seasonMarksPainted++;
    }
  }

  /// Dhu al-Hijjah: a row of small white paper tents standing on the far
  /// hill, toward Noor's side (the sun keeps the far corner).
  void _tents(
    Canvas canvas,
    Size size, {
    required double farPhase,
    required bool rtl,
  }) {
    final w = size.width, h = size.height;
    double hillY(double x) =>
        h - 20 - 9 * math.sin((x / w + farPhase) * math.pi * 2);
    final cloth = Paint()..color = const Color(0xFFFBF1DE);
    final shade = Paint()..color = _darkSky ? const Color(0xFF062B26) : _shadow;
    final door = Paint()..color = const Color(0xFFD9C7A7);
    for (final fx in _hijjahTents) {
      if (seasonMarksPainted >= kMaxSeasonMarks) break;
      final x = (rtl ? 1 - fx : fx) * w;
      final base = hillY(x) + 2;
      final tent = Path()
        ..moveTo(x - 7, base)
        ..lineTo(x, base - 10)
        ..lineTo(x + 7, base)
        ..close();
      final flap = Path()
        ..moveTo(x - 1.6, base)
        ..lineTo(x, base - 5)
        ..lineTo(x + 1.6, base)
        ..close();
      canvas
        ..drawPath(tent.shift(const Offset(1, 1.4)), shade)
        ..drawPath(tent, cloth)
        ..drawPath(flap, door);
      seasonMarksPainted++;
    }
  }

  /// The eight-point star of STYLE.md: two squares, one turned 45°.
  Path _eightPoint(Offset c, double r) {
    final p = Path();
    for (var i = 0; i < 16; i++) {
      final a = -math.pi / 2 + i * math.pi / 8;
      final rr = i.isEven ? r : r * .62;
      final pt = Offset(c.dx + rr * math.cos(a), c.dy + rr * math.sin(a));
      i == 0 ? p.moveTo(pt.dx, pt.dy) : p.lineTo(pt.dx, pt.dy);
    }
    return p..close();
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
      old.ramadan != ramadan ||
      old.season != season;
}
