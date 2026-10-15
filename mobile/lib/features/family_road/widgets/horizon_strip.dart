/// «على الأفق» — one slim line on Today's hills naming the nearest gate of
/// «درب {الاسم}» («رمضان بعد ١١٦ يومًا»، «سنّ السابعة بعد ٤ أشهر»); a tap
/// opens the road (عالم الأسرة, the study's first experiment).
///
/// It lies in the sky band's bottom margin, on the hills, so ① moves down by
/// little more than the line itself. It is not there without a dated gate
/// (the next path is ① already), and the server can hide it on every build
/// (`/api/app-config` → `horizon_strip_enabled`). Words sit on the surface
/// colour, like Noor's bubble — never on the sky.
///
/// Measured: `horizon_strip_shown` once a day, `horizon_strip_tapped`, and
/// the tap is remembered for `horizon_to_action_48h`.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../core/horizon_attribution.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../logic/horizon.dart';
import 'gate_bits.dart';

class HorizonStrip extends ConsumerStatefulWidget {
  const HorizonStrip({super.key, required this.gate});

  final HorizonGate gate;

  /// Where the once-a-day impression is remembered.
  static const shownDayKey = 'tg.horizon.strip_shown_day';

  @override
  ConsumerState<HorizonStrip> createState() => _HorizonStripState();
}

class _HorizonStripState extends ConsumerState<HorizonStrip> {
  @override
  void initState() {
    super.initState();
    unawaited(_markShown());
  }

  Future<void> _markShown() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final now = DateTime.now();
      final day = '${now.year}-${now.month}-${now.day}';
      if (prefs.getString(HorizonStrip.shownDayKey) == day) return;
      await prefs.setString(HorizonStrip.shownDayKey, day);
      await Analytics.horizonStripShown(widget.gate.kind.wire);
    } catch (_) {
      // analytics must never affect UX
    }
  }

  void _open() {
    unawaited(Analytics.horizonStripTapped(widget.gate.kind.wire));
    unawaited(HorizonAttribution.recordTap('strip'));
    Navigator.of(context).push(AppRoutes.familyRoad(from: 'today_strip'));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final g = widget.gate;
    final name = realChildName(ref.watch(activeChildProfileProvider)?.name);
    final when = gateWhen(l10n, g);
    final what = when == null
        ? gateTitle(l10n, g, name: name)
        : '${gateTitle(l10n, g, name: name)} $when';
    // Its own node (container): without it the label merged into the sky
    // band's node, and a tap on that node's centre — what TalkBack and
    // Maestro do — landed on Noor's bubble (CI run 38754954265).
    return Semantics(
      container: true,
      button: true,
      hint: l10n.horizonStripHint,
      child: Material(
        key: const Key('horizon-strip'),
        color: c.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: c.primary.withValues(alpha: .18)),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: _open,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Padding(
              padding: const EdgeInsetsDirectional.fromSTEB(10, 6, 8, 6),
              child: Row(
                children: [
                  PaperGate(size: 22, near: true),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text.rich(
                      TextSpan(
                        children: [
                          TextSpan(
                            text: '${l10n.familyRoadHorizon}: ',
                            style: TextStyle(
                              color: c.primary,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          TextSpan(text: what),
                        ],
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: c.ink,
                        fontWeight: FontWeight.w600,
                        height: 1.3,
                      ),
                    ),
                  ),
                  const SizedBox(width: 4),
                  DirectionalChevron(size: 18, color: c.textSecondary),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
