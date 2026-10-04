/// «مهمة الطفل» — the third of the three «اليوم» blocks.
///
/// What it shows is decided by the content banks, not by this widget:
///
///  * **4-6 · 7-9 · 10-12 · 13-15 · 16-18** have a mission bank
///    (`knowledge_base/curriculum/missions/`). If the child already opened
///    today's mission in child mode, the day's summary ([ChildDayCard]) shows
///    it — assigned, claimed and waiting on the parent, or confirmed. If not,
///    the block offers to open it: the mission is only ever minted by the
///    surface the child is holding (see `child_missions.today_mission`), so
///    the parent's screen can invite but never assign.
///    English titles exist for 7-9 and 13-15; the other bands fall back to the
///    Arabic text until their banks are translated.
///  * **prenatal-1 · 0-3 · 2-3** have no mission bank by design — under two
///    the child surface is refused outright. For them «the child's day» is the
///    sleep/feeding tracker, so the block opens that instead.
///  * No child yet: the block asks for one.
///
/// Whatever the server says — or if it says nothing (offline, older backend) —
/// the block always ends in an action.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../../parent_day/child_day_card.dart';
import '../../routine/screens/daily_routine_screen.dart' show habitTabLabel;
import 'today_section.dart';

/// Bands with a published mission bank. Keep in step with
/// `knowledge_base/curriculum/missions/missions_<band>.json`.
const Set<String> kMissionBands = {'4-6', '7-9', '10-12', '13-15', '16-18'};

class TodayChildBlock extends StatelessWidget {
  const TodayChildBlock({super.key, required this.profile});

  final ActiveChildProfile? profile;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final p = profile;

    if (p == null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TodaySectionHeader(emoji: '🧭', title: l10n.todayMissionTitleNoName),
          _ActionTile(
            body: l10n.todayAddChildBody,
            cta: l10n.addChild,
            icon: Icons.person_add_alt_1_rounded,
            onTap: () {
              unawaited(Analytics.todayBlockTapped('mission', 'add_child'));
              Navigator.of(context).push(AppRoutes.addChild());
            },
          ),
        ],
      );
    }

    final hasMissions = kMissionBands.contains(p.ageGroup);
    final Widget invite = hasMissions
        ? _ActionTile(
            body: l10n.todayMissionReady(p.name),
            cta: l10n.todayMissionOpen,
            icon: Icons.explore_outlined,
            onTap: () {
              unawaited(Analytics.todayBlockTapped('mission', 'child_mode'));
              Navigator.of(context).push(AppRoutes.childModeLock<void>(
                childId: p.id,
                childName: p.name,
                surface: 'mission',
              ));
            },
          )
        : _ActionTile(
            body: l10n.todayRoutineBody(p.name),
            cta: l10n.todayRoutineCta,
            icon: Icons.edit_calendar_outlined,
            caption: habitTabLabel(p.ageGroup, l10n),
            onTap: () {
              unawaited(Analytics.todayBlockTapped('mission', 'routine'));
              Navigator.of(context).push(AppRoutes.dailyRoutine());
            },
          );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TodaySectionHeader(
          emoji: hasMissions ? '🧭' : '🌱',
          title: hasMissions
              ? l10n.todayMissionTitle(p.name)
              : l10n.todayDayTitle(p.name),
        ),
        // The summary when there is a day to summarise; the invitation
        // otherwise (and while loading, and when the server is unreachable).
        // For a mission band the invitation also stays under a summary that
        // has screen or listening minutes but no mission yet — minutes are not
        // a mission, and hiding the hand-over behind them hid the block's
        // whole point.
        ChildDayCard(
          whenEmpty: invite,
          whenNoMission: hasMissions ? invite : null,
          onOpened: () =>
              unawaited(Analytics.todayBlockTapped('mission', 'open_day')),
        ),
      ],
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.body,
    required this.cta,
    required this.icon,
    required this.onTap,
    this.caption,
  });

  final String body;
  final String cta;
  final IconData icon;
  final VoidCallback onTap;

  /// Small label above the body (the tracker's own name for young bands).
  final String? caption;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Dt.surface,
      borderRadius: BorderRadius.circular(Dt.rCard),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (caption != null) ...[
              Text(
                caption!,
                style: TextStyle(
                  color: AppTheme.textMuted,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
            ],
            Text(
              body,
              style: TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 14,
                height: 1.6,
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.tonalIcon(
              onPressed: onTap,
              icon: Icon(icon, size: 20),
              label: Text(cta),
            ),
          ],
        ),
      ),
    );
  }
}
