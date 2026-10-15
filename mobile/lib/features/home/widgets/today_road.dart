/// «درب اليوم» (plan phase 2): the day's three stops — ① خطوة ابنك، ② اسأل
/// المربّي، ③ مهمة الطفل — as three stations on one short paper road down the
/// start edge of «اليوم».
///
/// The content and its order are untouched; the road only frames it. A stop
/// reached today lights its station gold and the road behind it; Noor sits on
/// the next station (and hops there when one is reached). When all three are
/// reached Noor rests, happy, on the last one.
///
/// Each section header inside a stop drops its own glyph ([TodayRoadScope]):
/// the station carries it, so the eye meets one mark per stop, not two.
library;

import 'package:flutter/material.dart';

import '../../../core/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/brand_glyph.dart';
import '../../companion/widgets/noor_face.dart';
import '../../companion/widgets/noor_presence.dart';

/// Tells a [TodaySectionHeader] it stands on the road and must not draw its
/// own glyph.
class TodayRoadScope extends InheritedWidget {
  const TodayRoadScope({super.key, required super.child});

  static bool of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<TodayRoadScope>() != null;

  @override
  bool updateShouldNotify(TodayRoadScope oldWidget) => false;
}

/// One stop of the road: its station glyph, whether it was reached today,
/// and the content beside it.
class RoadStop {
  const RoadStop({
    required this.icon,
    required this.reached,
    required this.child,
  });

  final BrandIcon icon;
  final bool reached;
  final Widget child;
}

const double _kRail = 34;
const double _kGap = 8;

/// The station's centre from the top of its stop: level with the header's
/// first line.
const double _kStationY = 13;

class TodayRoad extends StatelessWidget {
  const TodayRoad({super.key, required this.stops, this.spacing = 24});

  final List<RoadStop> stops;

  /// The space between two stops — the road runs through it.
  final double spacing;

  /// Where Noor stands: the first stop not yet reached, else the last.
  int get noorAt {
    final i = stops.indexWhere((s) => !s.reached);
    return i == -1 ? stops.length - 1 : i;
  }

  @override
  Widget build(BuildContext context) {
    final at = noorAt;
    return TodayRoadScope(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var i = 0; i < stops.length; i++)
            _StopRow(
              index: i,
              stop: stops[i],
              first: i == 0,
              last: i == stops.length - 1,
              // The road into this stop is walked when the one before it was
              // reached; the road out when this one was.
              walkedIn: i > 0 && stops[i - 1].reached,
              walkedOut: stops[i].reached,
              noorHere: i == at,
              allReached: stops.every((s) => s.reached),
              spacing: i == stops.length - 1 ? 0 : spacing,
            ),
        ],
      ),
    );
  }
}

class _StopRow extends StatelessWidget {
  const _StopRow({
    required this.index,
    required this.stop,
    required this.first,
    required this.last,
    required this.walkedIn,
    required this.walkedOut,
    required this.noorHere,
    required this.allReached,
    required this.spacing,
  });

  final int index;
  final RoadStop stop;
  final bool first, last, walkedIn, walkedOut, noorHere, allReached;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return Stack(

      children: [
        PositionedDirectional(
          start: 0,
          top: 0,
          bottom: 0,
          width: _kRail,
          child: CustomPaint(
            painter: RoadRailPainter(
              first: first,
              last: last,
              walkedIn: walkedIn,
              walkedOut: walkedOut,
              bendLeft: index.isEven,
              paper: RoadRailPainter.paperFor(Theme.of(context).brightness),

            ),
          ),
        ),
        PositionedDirectional(
          start: 0,
          top: _kStationY - 18,
          width: _kRail,
          height: 36,
          child: Center(
            child: _Station(
              icon: stop.icon,
              reached: stop.reached,
              noorHere: noorHere,
              allReached: allReached,
            ),
          ),
        ),
        Padding(
          padding: EdgeInsetsDirectional.only(
            start: _kRail + _kGap,
            bottom: spacing,
          ),
          child: stop.child,
        ),
      ],
    );
  }
}

class _Station extends StatelessWidget {
  const _Station({
    required this.icon,
    required this.reached,
    required this.noorHere,
    required this.allReached,
  });

  final BrandIcon icon;
  final bool reached, noorHere, allReached;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final Widget face;
    final String key;
    if (noorHere) {
      key = allReached ? 'noor-rest' : 'noor';
      face = NoorPresence(
        size: 36,
        face: allReached ? NoorFaceState.happy : NoorFaceState.awake,
      );
    } else if (reached) {
      key = 'lit';
      face = _Disc(
        color: const Color(0xFFF7C548),
        child: const Icon(
          Icons.check_rounded,
          size: 18,
          color: Color(0xFF0F3D36),
        ),
      );
    } else {
      key = 'ahead';
      face = _Disc(
        color: dark ? const Color(0xFF1F4A43) : const Color(0xFFFBF1DE),
        edge: dark ? null : const Color(0xFFD9C7A7),
        // The «quiet» paper (BrandGlyph: a muted colour asks for 45%).
        child: BrandGlyph(icon, size: 16, color: colors.textSecondary),
      );
    }
    final reduce = reduceMotion(context);
    return Semantics(
      label: reached ? l10n.todayRoadReached : null,
      child: AnimatedSwitcher(
        duration: reduce ? Duration.zero : const Duration(milliseconds: 420),
        switchInCurve: Curves.easeOutBack,
        switchOutCurve: Curves.easeIn,
        transitionBuilder: (child, a) =>
            ScaleTransition(scale: a, child: child),
        child: KeyedSubtree(key: ValueKey(key), child: face),
      ),
    );
  }
}

class _Disc extends StatelessWidget {
  const _Disc({required this.color, required this.child, this.edge});

  final Color color;
  final Widget child;

  /// A paper edge, for a cream disc on a cream page.
  final Color? edge;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 28,
      height: 28,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color,
        border: edge == null ? null : Border.all(color: edge!, width: 1.5),
        // A cut-paper drop: flat, offset, no blur (assets/svg/STYLE.md).
        boxShadow: const [
          BoxShadow(color: Color(0x330F3D36), offset: Offset(1.5, 2)),
        ],
      ),
      child: child,
    );
  }
}

/// The paper strip through one stop: in from the top to the station, and out
/// from the station down to the next stop, in a soft S. Walked road is gold.
class RoadRailPainter extends CustomPainter {
  RoadRailPainter({
    required this.first,
    required this.last,
    required this.walkedIn,
    required this.walkedOut,
    required this.bendLeft,
    required this.paper,
  });

  final bool first, last, walkedIn, walkedOut, bendLeft;
  final Color paper;

  static const gold = Color(0xFFF7C548);
  static const _shadow = Color(0x260F3D36);
  static const _width = 7.0;

  /// The unwalked paper of the road on a page of [brightness].
  static Color paperFor(Brightness brightness) => brightness == Brightness.dark
      ? const Color(0xFF1F4A43)
      : const Color(0xFFD9C7A7);

  /// One strip of paper road along [path]: a flat offset shadow, then the
  /// strip — gold where it was walked. Shared with «درب المسار» so both roads
  /// are cut from the same paper; the shadow's offset grows with [width].
  static void paintStrip(
    Canvas canvas,
    Path path, {
    required bool walked,
    required Color paper,
    double width = _width,
  }) {
    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = width
      ..strokeCap = StrokeCap.round;
    final k = width / _width;
    canvas.drawPath(
      path.shift(Offset(1.5 * k, 2 * k)),
      stroke..color = _shadow,
    );
    canvas.drawPath(path, stroke..color = walked ? gold : paper);
  }


  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    if (!first) {
      _strip(
        canvas,
        Path()
          ..moveTo(cx, 0)
          ..lineTo(cx, _kStationY),
        walkedIn,
      );
    }
    if (!last) {
      final from = Offset(cx, _kStationY);
      final to = Offset(cx, size.height);
      final l = to.dy - from.dy;
      final a = (bendLeft ? -1 : 1) * 9.0;
      _strip(
        canvas,
        Path()
          ..moveTo(from.dx, from.dy)
          ..cubicTo(
            cx + a,
            from.dy + l * .35,
            cx - a,
            from.dy + l * .65,
            to.dx,
            to.dy,
          ),
        walkedOut,
      );
    }
  }

  void _strip(Canvas canvas, Path path, bool walked) =>
      paintStrip(canvas, path, walked: walked, paper: paper);


  @override
  bool shouldRepaint(RoadRailPainter old) =>
      old.first != first ||
      old.last != last ||
      old.walkedIn != walkedIn ||
      old.walkedOut != walkedOut ||
      old.bendLeft != bendLeft ||
      old.paper != paper;
}
