/// «عيدكم مبارك» (NOOR_WAL_QANADIL_PLAN, phase 5): on the first open of Eid
/// al-Fitr, once a Hijri year, a quiet moment over «اليوم» — Noor happy under
/// a string of paper lanterns that light one after another, «عيدكم مبارك»,
/// and the way to the family's own «رمضان عائلتنا» card when the server has
/// it. No confetti, no sound, no count, no promise of reward. Under
/// reduce-motion every lantern is lit from the first frame and nothing moves.
///
/// *When* is the server's answer, not the phone's calendar: `/api/programs`
/// locates today in the family's season (their own sighting applied) and
/// says `eid` on the day itself, then `after` for the bridge weeks. The
/// moment may come on the first [kEidMomentDays] days of Eid — the days a
/// family says «عيدكم مبارك» — and never again that year.
///
/// Cut in the «ورق مقصوص» set (assets/svg/STYLE.md): the art's emerald card
/// in both themes, flat palette colours, solid offset paper shadows.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../core/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../../companion/providers/companion_providers.dart';
import '../../companion/widgets/noor_face.dart';
import '../../tour/tour_controller.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';

/// The days of Eid the moment may still come on (1 = the day itself).
const kEidMomentDays = 3;

/// How long the lanterns take to light, one after another.
const kEidLightDuration = Duration(milliseconds: 1600);

/// The once-a-year key in Noor's device memory (`CompanionMemory.seenKeys`).
String eidMomentKey(int hijriYear) => 'eid:$hijriYear';

/// Which day of Eid today is (1 = the day itself), from the server's own
/// answer — or null outside Eid, or when the server sends no season.
int? eidDayOf(ProgramsOverview overview) {
  final r = overview.ramadan;
  final season = r.season;
  if (season == null) return null;
  if (r.state == RamadanState.eid) return 1;
  if (r.state != RamadanState.after) return null;
  final today = overview.date;
  if (today == null) return null;
  // Calendar days, counted in UTC so a DST change cannot shave an hour off.
  DateTime day(DateTime d) => DateTime.utc(d.year, d.month, d.day);
  final n = day(today).difference(day(season.eidOn)).inDays + 1;
  return n >= 1 && n <= kEidMomentDays ? n : null;
}

/// The Hijri year whose Eid moment is due on this open, or null.
///
/// Noor's switches hold it like her lines: the server's kill switch, and
/// «وضع هادئ» (a moment that opens over the screen is more than a greeting).
/// Null too while the device memory or `/api/programs` is still loading.
final eidMomentDueProvider = Provider.autoDispose<int?>((ref) {
  if (!ref.watch(noorHeaderEnabledProvider)) return null;
  final memory = ref.watch(companionMemoryProvider).valueOrNull;
  if (memory == null || memory.quietMode) return null;
  final overview = ref.watch(programsOverviewProvider).valueOrNull;
  if (overview == null || eidDayOf(overview) == null) return null;
  final year = overview.ramadan.season!.hijriYear;
  return memory.seenKeys.contains(eidMomentKey(year)) ? null : year;
});

/// Sits around «اليوم» and opens the Eid moment when it is due — only while
/// Today is the tab on screen, its route on top, and no tour is up. Draws
/// nothing of its own.
class EidMomentGate extends ConsumerStatefulWidget {
  const EidMomentGate({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<EidMomentGate> createState() => _EidMomentGateState();
}

class _EidMomentGateState extends ConsumerState<EidMomentGate> {
  bool _shown = false;

  Future<void> _show(int year) async {
    if (!mounted) return;
    // Recorded before it shows: once means once, even if the app is closed
    // with the moment still up.
    unawaited(
      ref.read(companionMemoryProvider.notifier).markSeen(eidMomentKey(year)),
    );
    unawaited(Analytics.companionShown('eidMoment'));
    final recap =
        ref
            .read(programsOverviewProvider)
            .valueOrNull
            ?.ramadan
            .recapAvailable ??
        false;
    final open = await showEidMoment(context, recap: recap);
    if (!mounted) return;
    unawaited(
      Analytics.companionReply('eidMoment', open ? 'openRecap' : 'close'),
    );
    if (open) await Navigator.of(context).push(AppRoutes.ramadanRecap());
  }

  @override
  Widget build(BuildContext context) {
    final year = ref.watch(eidMomentDueProvider);
    final touring = ref.watch(tourControllerProvider).active;
    final onScreen =
        TickerMode.valuesOf(context).enabled &&
        (ModalRoute.of(context)?.isCurrent ?? true);
    if (year != null && !touring && onScreen && !_shown) {
      _shown = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => _show(year));
    }
    return widget.child;
  }
}

/// Shows the moment. Resolves true when the parent chose to open the
/// family's card. Under reduce-motion the dialog does not fade in either.
Future<bool> showEidMoment(BuildContext context, {required bool recap}) async {
  final open = await showDialog<bool>(
    context: context,
    animationStyle: reduceMotion(context) ? AnimationStyle.noAnimation : null,
    builder: (_) => EidMoment(recap: recap),
  );
  return open ?? false;
}

// The paper (assets/svg/STYLE.md).
const _kCard = Color(0xFF0F6B5C);
const _kCardShadow = Color(0xFF094A40);
const _kUnlit = Color(0xFF12806D);
const _kStarDecor = Color(0xFF13806C);
const _kIvory = Color(0xFFFBF1DE);
const _kIvoryEdge = Color(0xFFEADBC0);
const _kInk = Color(0xFF0F3D36);
const _kGold = Color(0xFFF7C548);

class EidMoment extends StatefulWidget {
  const EidMoment({super.key, required this.recap});

  /// The server has the family's «رمضان عائلتنا» card: offer it.
  final bool recap;

  @override
  State<EidMoment> createState() => EidMomentState();
}

class EidMomentState extends State<EidMoment>
    with SingleTickerProviderStateMixin {
  late final AnimationController _light = AnimationController(
    vsync: this,
    duration: kEidLightDuration,
  );
  bool _started = false;

  /// How far the lighting has gone, 0 (all unlit) → 1 (all lit).
  @visibleForTesting
  double get lit => _light.value;

  /// Whether the lanterns are still lighting — pins the reduce-motion
  /// contract.
  @visibleForTesting
  bool get lighting => _light.isAnimating;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (reduceMotion(context)) {
      // Still: every lantern lit from the first frame.
      _light
        ..stop()
        ..value = 1;
    } else if (!_started) {
      _light.forward();
    }
    _started = true;
  }

  @override
  void dispose() {
    _light.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final art = math.min(232.0, MediaQuery.sizeOf(context).width * .6);
    return Dialog(
      key: const ValueKey('eid_moment'),
      backgroundColor: Colors.transparent,
      surfaceTintColor: Colors.transparent,
      shadowColor: Colors.transparent,
      elevation: 0,
      insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      child: Container(
        decoration: BoxDecoration(
          // The art's own card: emerald in both themes, like Noor's window.
          color: _kCard,
          borderRadius: BorderRadius.circular(28),
          boxShadow: const [
            BoxShadow(color: _kCardShadow, offset: Offset(4, 5)),
          ],
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ExcludeSemantics(
                child: SizedBox(
                  key: const ValueKey('eid_moment_art'),
                  width: art,
                  height: art * .92,
                  child: Stack(
                    children: [
                      Positioned.fill(
                        child: AnimatedBuilder(
                          animation: _light,
                          builder: (context, _) => CustomPaint(
                            painter: EidLanternsPainter(progress: _light.value),
                          ),
                        ),
                      ),
                      Align(
                        alignment: Alignment.bottomCenter,
                        child: NoorFace(
                          size: art * .78,
                          state: NoorFaceState.happy,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              Semantics(
                header: true,
                child: Text(
                  l10n.eidMomentTitle,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: _kIvory,
                    fontSize: 24,
                    fontWeight: FontWeight.w800,
                    height: 1.35,
                  ),
                ),
              ),
              const SizedBox(height: 6),
              Text(
                l10n.eidMomentBody,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: _kIvory.withValues(alpha: .92),
                  fontSize: 16,
                  height: 1.6,
                ),
              ),
              const SizedBox(height: 18),
              if (widget.recap) ...[
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    key: const ValueKey('eid_moment_recap'),
                    style: FilledButton.styleFrom(
                      backgroundColor: _kGold,
                      foregroundColor: _kInk,
                      minimumSize: const Size(0, 48),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                    onPressed: () => Navigator.of(context).pop(true),
                    child: Text(
                      l10n.ramadanRecapOpen,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                  ),
                ),
                const SizedBox(height: 4),
              ],
              TextButton(
                key: const ValueKey('eid_moment_close'),
                style: TextButton.styleFrom(
                  foregroundColor: _kIvory,
                  minimumSize: const Size(0, 48),
                ),
                onPressed: () => Navigator.of(context).pop(false),
                child: Text(l10n.close),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The lantern string over Noor: one thread swagged across the top of the
/// art, five paper lanterns hanging from it. Unlit they are emerald paper;
/// as [progress] runs a gold paper piece opens over each, from the middle
/// outwards — a room coming alight, not a firework.
class EidLanternsPainter extends CustomPainter {
  EidLanternsPainter({required this.progress});

  /// 0 → none lit, 1 → all lit.
  final double progress;

  /// Lanterns along the thread (fraction of the width) and how far each
  /// hangs below it, in the art's 240 grid.
  static const _lanterns = <(double, double)>[
    (.14, 8),
    (.32, 12),
    (.5, 14),
    (.68, 12),
    (.86, 8),
  ];

  /// The order they light in: the middle first, then outwards.
  static const _order = [2, 1, 3, 0, 4];

  /// Decorative eight-point stars on the card, clear of Noor and the string.
  static const _decor = <(double, double, double)>[
    (22, 118, 5),
    (218, 132, 4.5),
    (30, 186, 4),
  ];

  /// How lit lantern [i] is (0–1) at [progress]: one after another, each
  /// in a fifth of the time, the last one done at the end.
  static double litOf(int i, double progress) {
    final slot = _order.indexOf(i);
    return (progress * _order.length - slot).clamp(0.0, 1.0);
  }

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width / 240;
    canvas
      ..save()
      ..scale(s);
    final h = size.height / s;

    for (final (x, y, r) in _decor) {
      if (y + r > h) continue;
      canvas.drawPath(_star8(Offset(x, y), r), Paint()..color = _kStarDecor);
    }

    // The thread: one shallow swag from edge to edge.
    const top = 14.0, sag = 12.0;
    double threadY(double x) {
      final t = x / 240;
      return top + sag * 4 * t * (1 - t);
    }

    final thread = Path()..moveTo(6, threadY(6));
    for (var x = 6.0; x <= 234; x += 6) {
      thread.lineTo(x, threadY(x));
    }
    canvas.drawPath(
      thread.shift(const Offset(1, 1.5)),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round
        ..color = _kCardShadow,
    );
    canvas.drawPath(
      thread,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round
        ..color = _kIvoryEdge,
    );

    for (final (i, (fx, drop)) in _lanterns.indexed) {
      final x = fx * 240;
      final y = threadY(x);
      final at = Offset(x, y + drop);
      final body = _lantern(at);
      final glow = Curves.easeOutCubic.transform(litOf(i, progress));
      canvas
        ..drawLine(
          Offset(x, y),
          at,
          Paint()
            ..strokeWidth = 1.4
            ..color = _kIvoryEdge,
        )
        ..drawPath(
          body.shift(const Offset(1.5, 2)),
          Paint()..color = _kCardShadow,
        )
        ..drawPath(body, Paint()..color = _kUnlit);
      if (glow > 0) {
        // The gold piece opens from the lantern's middle until it covers it.
        final mid = at.translate(0, 11);
        canvas
          ..save()
          ..translate(mid.dx, mid.dy)
          ..scale(glow)
          ..translate(-mid.dx, -mid.dy)
          ..drawPath(body, Paint()..color = _kGold)
          ..restore();
      }
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: at.translate(0, 1.4), width: 10, height: 3),
          const Radius.circular(1.5),
        ),
        Paint()..color = _kIvoryEdge,
      );
    }
    canvas.restore();
  }

  /// A paper lantern hanging from [top]: a waisted body, widest in the
  /// middle, a cap above and a short point below.
  static Path _lantern(Offset top) {
    final x = top.dx, y = top.dy;
    return Path()
      ..moveTo(x - 4.5, y + 2)
      ..lineTo(x + 4.5, y + 2)
      ..quadraticBezierTo(x + 9.5, y + 11, x + 5, y + 20)
      ..lineTo(x + 1.6, y + 20)
      ..lineTo(x, y + 24)
      ..lineTo(x - 1.6, y + 20)
      ..lineTo(x - 5, y + 20)
      ..quadraticBezierTo(x - 9.5, y + 11, x - 4.5, y + 2)
      ..close();
  }

  /// An eight-point star (STYLE.md's decoration).
  static Path _star8(Offset c, double r) {
    final p = Path();
    for (var i = 0; i < 16; i++) {
      final rr = i.isEven ? r : r * .55;
      final a = i * math.pi / 8 - math.pi / 2;
      final pt = c + Offset(math.cos(a) * rr, math.sin(a) * rr);
      if (i == 0) {
        p.moveTo(pt.dx, pt.dy);
      } else {
        p.lineTo(pt.dx, pt.dy);
      }
    }
    return p..close();
  }

  @override
  bool shouldRepaint(EidLanternsPainter old) => old.progress != progress;
}
