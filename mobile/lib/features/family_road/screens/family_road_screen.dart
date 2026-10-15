/// «درب {الاسم}» — the family's paper road with the active child
/// (عالم الأسرة, the middle scenario Khaled approved on 2026-10-15).
///
/// It opens on what is ahead, not on what was done: the empty road is the
/// risk, because most families have done one lesson or none. Top to bottom:
///
///   * the sky of the hour (SkyBand — with the season's paper touch), where
///     the road comes from;
///   * «على الأفق»: up to four real gates, farthest first — Ramadan, seven
///     years old, a milestone, the next path — each with one button;
///   * «أنتم هنا»: Noor, and the path being resumed;
///   * «ما أضأتموه»: only what was done — this week's lit lanterns, finished
///     paths («اكتمل البدر»), earlier lit weeks, the family's own lit-week
///     total — and the road's start. Nothing unlit, no «فاتك», no numbers
///     to compare with anyone.
///
/// The road above «أنتم هنا» is plain paper; below it, walked, it is gold.
/// On opening, Noor hops onto «أنتم هنا» and the stops settle in once —
/// still under reduced motion.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../core/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/paper_lantern.dart';
import '../../companion/widgets/noor_face.dart';
import '../../companion/widgets/noor_presence.dart';
import '../../home/widgets/sky_band.dart';
import '../../home/widgets/today_road.dart' show RoadRailPainter;
import '../../lanterns/providers/lantern_providers.dart';
import '../../lanterns/widgets/week_acts_sheet.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../../program/data/models.dart';
import '../../program/providers/program_providers.dart';
import '../../programs/data/programs_models.dart';
import '../../programs/providers/programs_providers.dart';
import '../logic/horizon.dart';
import '../providers/family_road_providers.dart';
import '../widgets/gate_bits.dart';

class FamilyRoadScreen extends ConsumerStatefulWidget {
  const FamilyRoadScreen({super.key, this.from = 'unknown', this.now});

  /// Where it was opened from (GA4 `family_road_opened.from`).
  final String from;

  /// The sky's hour; tests pin it.
  final DateTime? now;

  @override
  ConsumerState<FamilyRoadScreen> createState() => _FamilyRoadScreenState();
}

class _FamilyRoadScreenState extends ConsumerState<FamilyRoadScreen> {
  @override
  void initState() {
    super.initState();
    unawaited(Analytics.familyRoadOpened(widget.from));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final profile = ref.watch(activeChildProfileProvider);
    final name = realChildName(profile?.name);
    final gates = ref.watch(horizonGatesProvider);
    final here = ref.watch(roadHereProvider);
    final past = ref.watch(roadPastProvider);
    final overview = ref.watch(programsOverviewProvider).valueOrNull;
    final season = ref.watch(skySeasonProvider);
    final reduce = reduceMotion(context);

    // Farthest first: the eye starts at the horizon and walks down to «here».
    final ahead = gates.reversed.toList();
    final rows = <_RoadRow>[
      _RoadRow.label(l10n.familyRoadHorizon, key: const Key('road-horizon')),
      for (final (i, g) in ahead.indexed)
        _RoadRow(
          key: ValueKey('gate-${g.kind.wire}'),
          station: PaperGate(near: i == ahead.length - 1),
          child: _GateCard(gate: g, name: name),
        ),
      _RoadRow(
        key: const Key('road-here'),
        station: _hop(
          const NoorPresence(size: 36, face: NoorFaceState.happy),
          reduce,
        ),
        stationSize: 52,
        child: _HereCard(here: here),
        walkedOut: !past.isEmpty,
      ),
      if (!past.isEmpty) ...[
        _RoadRow.label(
          l10n.familyRoadLit,
          walked: true,
          key: const Key('road-lit'),
        ),
        if (past.weekLanterns > 0)
          _RoadRow(
            key: const Key('road-week'),
            walked: true,
            station: const PaperLantern(lit: true, height: 26),
            child: _LanternsCard(
              title: l10n.familyRoadThisWeek,
              lit: past.weekLanterns,
              onTap: () {
                final week = ref.read(familyWeekProvider).valueOrNull;
                if (week != null) showWeekActsSheet(context, week);
              },
            ),
          ),
        for (final title in past.fullMoonTitles.take(3))
          _RoadRow(
            walked: true,
            station: const _FullMoon(),
            child: _PastCard(text: l10n.familyRoadFullMoon(title)),
          ),
        if (past.earlierLitWeeks > 0)
          _RoadRow(
            key: const Key('road-before'),
            walked: true,
            station: const PaperLantern(lit: true, height: 26),
            child: _LanternsCard(
              title: l10n.familyRoadBefore,
              lit: past.earlierLitWeeks,
            ),
          ),
        if (past.showsTotal)
          _RoadRow(
            walked: true,
            station: const _Dot(),
            child: _PastCard(
              text: l10n.familyRoadSinceStart(past.litWeeksTotal),
            ),
          ),
        _RoadRow(
          key: const Key('road-start'),
          walked: true,
          walkedOut: false,
          station: const _Dot(start: true),
          child: _PastCard(text: l10n.familyRoadStart, quiet: true),
        ),
      ],
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(
          name == null ? l10n.familyRoadTitleNoName : l10n.familyRoadTitle(name),
        ),
      ),
      // Built whole, not lazily: the road is a dozen rows at most, and the
      // stops settle in together on opening — a row built later on scroll
      // must not fade in after the parent has already reached it.
      body: SingleChildScrollView(
        key: const Key('family-road-list'),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
          // The horizon the road comes from: the hour's sky with the
          // season's touch — decoration only, no text on it.
          ExcludeSemantics(
            child: SkyBand(
              now: widget.now,
              ramadan: overview?.ramadan.state == RamadanState.ramadan,
              season: season,
              child: const SizedBox(height: 44),
            ),
          ),
          for (final (i, row) in rows.indexed)
            _settle(
              _RoadRowView(
                row: row,
                first: i == 0,
                last: i == rows.length - 1,
                bendLeft: i.isEven,
                walkedIn: i > 0 && rows[i - 1].walkedOutResolved,
              ),
              i,
              reduce,
            ),
          ],
        ),
      ),
    );
  }

  /// Noor's hop onto «أنتم هنا»: once, on opening; still under reduced motion.
  Widget _hop(Widget noor, bool reduce) => reduce
      ? noor
      : noor.animate().moveY(
          begin: -18,
          curve: Curves.easeOutBack,
          duration: Dt.slow,
        );

  /// The stops settle in once, a beat apart.
  Widget _settle(Widget w, int i, bool reduce) => reduce
      ? w
      : w
            .animate(delay: Dt.stagger * i.clamp(0, Dt.maxStaggeredItems))
            .fadeIn(duration: Dt.base);
}

// ── The road ────────────────────────────────────────────────────────────────

const double _kRail = 48;
const double _kGap = 10;
const double _kStationY = 22;

class _RoadRow {
  const _RoadRow({
    this.key,
    required this.child,
    this.station,
    this.stationSize = 40,
    this.walked = false,
    this.walkedOut,
  }) : label = null;

  const _RoadRow.label(String this.label, {this.walked = false, this.key})
    : child = null,
      station = null,
      stationSize = 0,
      walkedOut = null;

  final Key? key;
  final Widget? child;
  final String? label;
  final Widget? station;
  final double stationSize;

  /// Below «أنتم هنا»: the road here was walked — gold.
  final bool walked;

  /// The road out of this row, when it differs from [walked].
  final bool? walkedOut;

  bool get walkedOutResolved => walkedOut ?? walked;
}

class _RoadRowView extends StatelessWidget {
  const _RoadRowView({
    required this.row,
    required this.first,
    required this.last,
    required this.bendLeft,
    required this.walkedIn,
  });

  final _RoadRow row;
  final bool first, last, bendLeft, walkedIn;

  @override
  Widget build(BuildContext context) {
    final paper = RoadRailPainter.paperFor(Theme.of(context).brightness);
    final label = row.label;
    final content = label != null
        ? Padding(
            padding: const EdgeInsets.only(top: 14, bottom: 10),
            child: Semantics(
              header: true,
              child: Text(
                label,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: context.colors.textSecondary,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          )
        : Padding(padding: const EdgeInsets.only(bottom: 14), child: row.child);
    return Stack(
      key: row.key,
      children: [
        PositionedDirectional(
          start: 0,
          top: 0,
          bottom: 0,
          width: _kRail,
          child: CustomPaint(
            painter: FamilyRoadRailPainter(
              // The road comes down from the sky above the first row.
              first: false,
              last: last,
              station: label == null,
              walkedIn: walkedIn,
              walkedOut: row.walkedOutResolved,
              bendLeft: bendLeft,
              paper: paper,
              textDirection: Directionality.of(context),
            ),
          ),
        ),
        if (row.station != null)
          PositionedDirectional(
            start: 0,
            top: _kStationY - row.stationSize / 2,
            width: _kRail,
            height: row.stationSize,
            child: Center(child: row.station),
          ),
        Padding(
          padding: const EdgeInsetsDirectional.only(start: _kRail + _kGap),
          child: content,
        ),
      ],
    );
  }
}

/// The road through one row: in from the top to the station, out from the
/// station to the bottom, in a winding S wider than «درب اليوم»'s — this is
/// the long road. Walked road is gold; the shared paper strip of
/// [RoadRailPainter.paintStrip] cuts both roads from the same paper.
class FamilyRoadRailPainter extends CustomPainter {
  FamilyRoadRailPainter({
    required this.first,
    required this.last,
    required this.station,
    required this.walkedIn,
    required this.walkedOut,
    required this.bendLeft,
    required this.paper,
    required this.textDirection,
  });

  final bool first, last, station, walkedIn, walkedOut, bendLeft;
  final Color paper;
  final TextDirection textDirection;

  static const width = 10.0;

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final y = station ? _kStationY : size.height / 2;
    // One soft S per row, out of the station; the way in is straight, so
    // the road winds once between two stops instead of wriggling.
    final s = (bendLeft ? -1 : 1) * 11.0;
    if (!first) {
      RoadRailPainter.paintStrip(
        canvas,
        Path()
          ..moveTo(cx, 0)
          ..lineTo(cx, y),
        walked: walkedIn,
        paper: paper,
        width: width,
      );
    }
    if (!last) {
      final l = size.height - y;
      RoadRailPainter.paintStrip(
        canvas,
        Path()
          ..moveTo(cx, y)
          ..cubicTo(
            cx + s,
            y + l * .35,
            cx - s,
            y + l * .65,
            cx,
            size.height,
          ),
        walked: walkedOut,
        paper: paper,
        width: width,
      );
    }
  }

  @override
  bool shouldRepaint(FamilyRoadRailPainter old) =>
      old.first != first ||
      old.last != last ||
      old.station != station ||
      old.walkedIn != walkedIn ||
      old.walkedOut != walkedOut ||
      old.bendLeft != bendLeft ||
      old.paper != paper ||
      old.textDirection != textDirection;
}

// ── The stops ───────────────────────────────────────────────────────────────

BoxDecoration _card(BuildContext context, {bool strong = false}) {
  final c = context.colors;
  return BoxDecoration(
    color: c.surface,
    borderRadius: BorderRadius.circular(18),
    border: Border.all(
      color: c.primary.withValues(alpha: strong ? .5 : .18),
      width: strong ? 1.5 : 1,
    ),
  );
}

class _GateCard extends ConsumerWidget {
  const _GateCard({required this.gate, this.name});

  final HorizonGate gate;
  final String? name;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final t = Theme.of(context).textTheme;
    final eyebrow = gateEyebrow(l10n, gate);
    final when = gateWhen(l10n, gate);
    final note = gateNote(l10n, gate);
    return Container(
      decoration: _card(context),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: () => openGate(context, ref, gate),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (eyebrow != null)
                  Text(
                    eyebrow,
                    style: t.labelMedium?.copyWith(
                      color: c.textSecondary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(
                        text: gateTitle(l10n, gate, name: name),
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      if (when != null) TextSpan(text: ' $when'),
                    ],
                  ),
                  style: t.titleSmall?.copyWith(color: c.ink, height: 1.4),
                ),
                if (note != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      note,
                      style: t.bodySmall?.copyWith(
                        color: c.textSecondary,
                        height: 1.4,
                      ),
                    ),
                  ),
                Align(
                  alignment: AlignmentDirectional.centerEnd,
                  child: TextButton(
                    onPressed: () => openGate(context, ref, gate),
                    child: Text(gateAction(l10n, gate)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _HereCard extends ConsumerWidget {
  const _HereCard({required this.here});

  final ({CurriculumPath path, int done})? here;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final t = Theme.of(context).textTheme;
    final h = here;
    return Container(
      decoration: _card(context, strong: true),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l10n.familyRoadHere,
            style: t.titleMedium?.copyWith(
              color: c.primary,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            h == null
                ? l10n.familyRoadHereHint
                : l10n.familyRoadHereResume(
                    h.path.title,
                    h.done,
                    h.path.lessonIds.length,
                  ),
            style: t.bodyMedium?.copyWith(color: c.ink, height: 1.45),
          ),
          if (h != null)
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: FilledButton(
                key: const Key('road-continue'),
                onPressed: () => Navigator.of(context).push(
                  AppRoutes.pathDetail(
                    h.path.id,
                    ref.read(selectedAgeGroupProvider),
                  ),
                ),
                child: Text(l10n.familyRoadContinue),
              ),
            ),
        ],
      ),
    );
  }
}

class _LanternsCard extends StatelessWidget {
  const _LanternsCard({required this.title, required this.lit, this.onTap});

  final String title;
  final int lit;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final t = Theme.of(context).textTheme;
    final c = context.colors;
    final body = Padding(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: t.titleSmall?.copyWith(
              color: c.ink,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          // Lit lanterns only — an unlit day or week is never drawn.
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (var i = 0; i < lit.clamp(0, 8); i++)
                const PaperLantern(lit: true, height: 30),
            ],
          ),
        ],
      ),
    );
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: c.surfaceAlt,
        borderRadius: BorderRadius.circular(18),
      ),
      child: onTap == null
          ? body
          : Material(
              type: MaterialType.transparency,
              child: InkWell(
                borderRadius: BorderRadius.circular(18),
                onTap: onTap,
                child: Semantics(
                  container: true,
                  button: true,
                  hint: l10n.familyRoadOpenWeek,
                  child: body,
                ),
              ),
            ),
    );
  }
}

class _PastCard extends StatelessWidget {
  const _PastCard({required this.text, this.quiet = false});

  final String text;
  final bool quiet;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Text(
        text,
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: quiet ? c.textSecondary : c.ink,
          fontWeight: quiet ? FontWeight.w500 : FontWeight.w700,
          height: 1.4,
        ),
      ),
    );
  }
}

/// «اكتمل البدر»: a full paper moon with its solid shadow.
class _FullMoon extends StatelessWidget {
  const _FullMoon();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      width: 24,
      height: 24,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: c.paperIvory,
        border: Border.all(color: c.paperGold, width: 2),
        boxShadow: [BoxShadow(color: c.paperShadow, offset: const Offset(1.5, 2))],
      ),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({this.start = false});

  final bool start;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final d = start ? 16.0 : 12.0;
    return Container(
      width: d,
      height: d,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        // Emerald paper on the gold of the walked road.
        color: start ? c.paperShadow : c.paperEmerald,
        boxShadow: [BoxShadow(color: c.paperShadow, offset: const Offset(1, 1.5))],
      ),
    );
  }
}
