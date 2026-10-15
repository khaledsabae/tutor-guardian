/// «قناديل الأسبوع» under ① on «اليوم» (نور والقناديل, phase 3).
///
/// Only the lanterns this week has lit — one per local day with a parenting
/// act, seven at most — and one dashed lantern after them, the one the next
/// step lights. Never an unlit day, never a count of what is left.
///
/// A lantern this phone has not shown yet lights in 350ms with one success
/// tap (no glow under reduced motion); the phone remembers how many it has
/// shown, so opening «اليوم» again does not replay it. A tap opens the week's
/// acts. Renders nothing while loading, on any failure, and on an older
/// server (`/api/family/week` → 404): ① is never disturbed by it.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/haptics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../data/family_week.dart';
import '../providers/lantern_providers.dart';
import 'lantern_row.dart';
import 'week_acts_sheet.dart';

class WeekLanternString extends ConsumerStatefulWidget {
  const WeekLanternString({super.key});

  @override
  ConsumerState<WeekLanternString> createState() => _WeekLanternStringState();
}

class _WeekLanternStringState extends ConsumerState<WeekLanternString> {
  late final AppLifecycleListener _lifecycle;

  /// On screen: this tab in front and no route over «اليوم». A lantern only
  /// lights where it can be seen; the moment waits for the parent's return.
  bool _visible = false;
  DateTime _askedAt = DateTime.now();

  String? _week;

  /// Lanterns lit from the first frame this week (already seen before).
  int? _from;

  /// Lanterns acknowledged as seen: the tap fired, the phone remembers them.
  int _ack = 0;
  bool _ackPending = false;

  @override
  void initState() {
    super.initState();
    _lifecycle = AppLifecycleListener(onResume: _ask);
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  void _ask() {
    if (!mounted) return;
    _askedAt = DateTime.now();
    ref.invalidate(familyWeekProvider);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final visible =
        TickerMode.valuesOf(context).enabled &&
        (ModalRoute.isCurrentOf(context) ?? true);
    // Back on «اليوم» after a lesson, a chat or a mission: a lantern may have
    // lit meanwhile. Not more than twice a minute.
    if (visible &&
        !_visible &&
        DateTime.now().difference(_askedAt) > const Duration(seconds: 30)) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _ask());
    }
    _visible = visible;
  }

  /// New lanterns are on screen: one success tap for all of them, and the
  /// phone remembers them so they do not light again.
  void _acknowledge(FamilyWeek week, int total) {
    _ackPending = false;
    if (!mounted || total <= _ack) return;
    _ack = total;
    unawaited(Haptics.success());
    unawaited(Analytics.lanternLit(total));
    unawaited(
      ref.read(lanternSeenStoreProvider)?.setSeen(week.weekKey, total) ??
          Future.value(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final week = ref.watch(familyWeekProvider).valueOrNull;
    if (week == null) return const SizedBox.shrink();
    final store = ref.watch(lanternSeenStoreProvider);
    // The phone's record decides which lanterns are new; until it is read
    // (a moment at launch) there is nothing to draw honestly.
    if (store == null) return const SizedBox.shrink();
    final total = week.lanterns;

    if (_week != week.weekKey) {
      _week = week.weekKey;
      _from = null;
    }
    if (_from == null) {
      _from = store.seenFor(week.weekKey).clamp(0, total);
      _ack = _from!;
    }
    if (total < _ack) {
      // Acts were erased (memory, a child, the account): remember fewer, so
      // the next real lantern still lights.
      _ack = total;
      unawaited(store.setSeen(week.weekKey, total));
    }
    final from = _from!;
    if (_visible && total > _ack && !_ackPending) {
      _ackPending = true;
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => _acknowledge(week, total),
      );
    }

    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: Semantics(
        button: true,
        label: l10n.weekLanternsTitle,
        value: total == 0 ? l10n.weekLanternsHint : l10n.weekLanternsLitDays(total),
        hint: l10n.weekLanternsOpenHint,
        excludeSemantics: true,
        child: Material(
          color: colors.surface,
          borderRadius: BorderRadius.circular(Dt.rCard),
          child: InkWell(
            borderRadius: BorderRadius.circular(Dt.rCard),
            onTap: () {
              Haptics.selection();
              unawaited(Analytics.todayBlockTapped('loop', 'lanterns'));
              showWeekActsSheet(context, week);
            },
            child: Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(Dt.rCard),
                border: Border.all(color: colors.track),
              ),
              padding: const EdgeInsetsDirectional.fromSTEB(14, 10, 8, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          l10n.weekLanternsTitle,
                          style: TextStyle(
                            color: colors.textSecondary,
                            fontWeight: FontWeight.w700,
                            fontSize: 12.5,
                          ),
                        ),
                      ),
                      DirectionalChevron(color: colors.inkSoft),
                    ],
                  ),
                  const SizedBox(height: 8),
                  LanternRow(
                    key: ValueKey('week-${week.weekKey}'),
                    count: total,
                    litFrom: from,
                    lighting: _visible,
                    showNext: total < 7,
                    nextLabel: l10n.weekLanternNext,
                  ),
                  if (total == 0) ...[
                    const SizedBox(height: 6),
                    Text(
                      l10n.weekLanternsHint,
                      style: TextStyle(
                        color: colors.inkSoft,
                        fontSize: 12.5,
                        height: 1.5,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
