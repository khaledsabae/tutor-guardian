/// What a gate says and where it goes — shared by «درب {الاسم}» and the
/// «على الأفق» strip on Today, so the two never word a gate differently.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../core/horizon_attribution.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../child_memory/data/placeholder_names.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../../program/providers/program_providers.dart';
import '../../program/providers/settings_providers.dart';
import '../../programs/providers/programs_providers.dart';
import '../logic/horizon.dart';

/// The child's name to say, or null while it is still the default «طفلي».
String? realChildName(String? name) =>
    name == null || name.trim().isEmpty || isDefaultChildName(name)
    ? null
    : name;

String gateTitle(AppLocalizations l10n, HorizonGate g, {String? name}) =>
    switch (g.kind) {
      GateKind.nextPath => g.title ?? l10n.gateNextPath,
      GateKind.milestoneDue =>
        g.title ?? l10n.gateMilestoneFallback(name ?? l10n.childFallbackName),
      GateKind.milestone =>
        g.title ?? l10n.gateMilestoneFallback(name ?? l10n.childFallbackName),
      GateKind.ramadan || GateKind.ramadanNow => l10n.gateRamadan,
      GateKind.ageSeven => l10n.gateAgeSeven,
      GateKind.birthMonth => l10n.gateBirthMonth(
        name ?? l10n.childFallbackName,
      ),
    };

/// The when-line, or null for an undated gate.
String? gateWhen(AppLocalizations l10n, HorizonGate g) => switch (g.kind) {
  GateKind.milestoneDue => l10n.gateMilestoneDue,
  GateKind.ramadanNow => l10n.gateRamadanDay(g.ramadanDay ?? 1),
  GateKind.ramadan => l10n.gateInDays(g.days ?? 0),
  GateKind.ageSeven || GateKind.milestone =>
    (g.days ?? 0) < 60 && g.days != null
        ? l10n.gateInDays(g.days!)
        : l10n.gateInMonths((g.months ?? 1).clamp(1, 999)),
  GateKind.nextPath || GateKind.birthMonth => null,
};

/// A small label over the title, or null.
String? gateEyebrow(AppLocalizations l10n, HorizonGate g) =>
    g.kind == GateKind.nextPath && g.title != null ? l10n.gateNextPath : null;

/// A short line under the gate, or null.
String? gateNote(AppLocalizations l10n, HorizonGate g) => switch (g.kind) {
  GateKind.ageSeven => l10n.gateAgeSevenNote,
  GateKind.birthMonth => l10n.gateBirthMonthNote,
  _ => null,
};

String gateAction(AppLocalizations l10n, HorizonGate g) => switch (g.kind) {
  GateKind.nextPath => l10n.gateOpenPath,
  GateKind.milestoneDue || GateKind.milestone => l10n.gateReadMilestone,
  GateKind.ramadan || GateKind.ramadanNow => l10n.noorChipRamadan,
  GateKind.ageSeven => l10n.noorChipPrayerJourney,
  GateKind.birthMonth => l10n.noorChipAddBirthMonth,
};

/// Follow a gate to its one act. Logs `horizon_gate_tapped` and remembers
/// the tap for `horizon_to_action_48h`.
Future<void> openGate(
  BuildContext context,
  WidgetRef ref,
  HorizonGate g,
) async {
  final child = ref.read(activeChildProfileProvider);
  if (child == null) return;
  unawaited(Analytics.horizonGateTapped(g.kind.wire));
  unawaited(HorizonAttribution.recordTap(g.kind.wire));
  final nav = Navigator.of(context);
  switch (g.kind) {
    case GateKind.nextPath:
      await nav.push(
        AppRoutes.pathDetail(g.pathId!, ref.read(selectedAgeGroupProvider)),
      );
    case GateKind.milestoneDue:
    case GateKind.milestone:
      final key = g.milestoneKey;
      await nav.push(
        key == null
            ? AppRoutes.milestones(child.id)
            : AppRoutes.milestoneDetail(child.id, key),
      );
    case GateKind.ramadan:
    case GateKind.ramadanNow:
      await nav.push(AppRoutes.ramadan(child.id));
    case GateKind.ageSeven:
      final mine = ref
          .read(programsOverviewProvider)
          .valueOrNull
          ?.forChild(child.id);
      await nav.push(
        mine?.prayer.eligibleTrack != null
            ? AppRoutes.prayerJourney(child.id)
            : AppRoutes.milestones(child.id),
      );
      ref.invalidate(programsOverviewProvider);
    case GateKind.birthMonth:
      final full = ref
          .read(childrenListProvider)
          .valueOrNull
          ?.children
          .where((c) => c.id == child.id)
          .firstOrNull;
      if (full != null) {
        await nav.push(AppRoutes.editChild(full));
        ref.invalidate(programsOverviewProvider);
        ref.invalidate(childrenListProvider);
      }
  }
}


/// A paper gate («بوابة»), drawn in code from the «ورق مقصوص» palette: an
/// emerald arch with its solid offset shadow and the ivory light through it.
class PaperGate extends StatelessWidget {
  const PaperGate({super.key, this.size = 30, this.near = false});

  /// The gate's height; it is four fifths as wide.
  final double size;

  /// The nearest gate keeps a small gold star over its arch.
  final bool near;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return ExcludeSemantics(
      child: SizedBox(
        width: size * .8,
        height: size,
        child: CustomPaint(
          painter: PaperGatePainter(
            arch: c.paperEmerald,
            light: c.paperIvory,
            shadow: c.paperShadow,
            star: near ? c.paperGold : null,
          ),
        ),
      ),
    );
  }
}

class PaperGatePainter extends CustomPainter {
  const PaperGatePainter({
    required this.arch,
    required this.light,
    required this.shadow,
    this.star,
  });

  final Color arch, light, shadow;
  final Color? star;

  Path _archPath(Rect r) {
    final rad = r.width / 2;
    return Path()
      ..moveTo(r.left, r.bottom)
      ..lineTo(r.left, r.top + rad)
      ..arcToPoint(
        Offset(r.right, r.top + rad),
        radius: Radius.circular(rad),
      )
      ..lineTo(r.right, r.bottom)
      ..close();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final top = star == null ? 0.0 : h * .14;
    final outer = Rect.fromLTRB(0, top, w - 1.5, h - 2);
    final inner = Rect.fromLTRB(
      w * .24,
      top + h * .2,
      w - 1.5 - w * .24,
      h - 2,
    );
    final o = _archPath(outer);
    canvas
      ..drawPath(o.shift(const Offset(1.5, 2)), Paint()..color = shadow)
      ..drawPath(o, Paint()..color = arch)
      ..drawPath(_archPath(inner), Paint()..color = light);
    final s = star;
    if (s != null) {
      final cx = (w - 1.5) / 2, r = h * .08;
      final p = Path()
        ..moveTo(cx, 0)
        ..lineTo(cx + r * .35, r * .65)
        ..lineTo(cx + r, r)
        ..lineTo(cx + r * .35, r * 1.35)
        ..lineTo(cx, r * 2)
        ..lineTo(cx - r * .35, r * 1.35)
        ..lineTo(cx - r, r)
        ..lineTo(cx - r * .35, r * .65)
        ..close();
      canvas.drawPath(p, Paint()..color = s);
    }
  }

  @override
  bool shouldRepaint(PaperGatePainter old) =>
      old.arch != arch ||
      old.light != light ||
      old.shadow != shadow ||
      old.star != star;
}
