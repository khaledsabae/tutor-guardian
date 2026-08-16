/// The child's day, on the «اليوم» tab.
///
/// The plan puts the parent panel in this tab (item 2.4). What shipped was a
/// button on the routine screen instead — two taps deeper than specified, and
/// down a path a parent only takes when they already intend to look. The
/// numbers this feature exists to produce were therefore invisible to anyone
/// not going looking for them.
///
/// A summary, not the panel: two rows and the mission's state, with the full
/// screen one tap away. Everything the panel says about *why* the two numbers
/// are never added lives there, where there is room to say it.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_routes.dart';
import '../../l10n/app_localizations.dart';
import '../../state/chat_notifier.dart' show tgClientProvider;
import '../program/providers/progress_providers.dart' show activeChildIdProvider;

class ChildDayCard extends ConsumerStatefulWidget {
  const ChildDayCard({super.key});

  @override
  ConsumerState<ChildDayCard> createState() => _ChildDayCardState();
}

class _ChildDayCardState extends ConsumerState<ChildDayCard> {
  Map<String, dynamic>? _day;
  bool _failed = false;
  int? _loadedFor;

  Future<void> _load(int childId) async {
    _loadedFor = childId;
    try {
      final day = await ref.read(tgClientProvider).fetchChildDay(childId);
      if (mounted) setState(() { _day = day; _failed = false; });
    } catch (_) {
      // The home tab must survive a backend that is down. A card that cannot
      // load hides; it does not put an error in the middle of the day.
      if (mounted) setState(() => _failed = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final childId = ref.watch(activeChildIdProvider);
    if (childId == null) return const SizedBox.shrink();
    if (_loadedFor != childId) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _loadedFor != childId) _load(childId);
      });
    }

    final day = _day;
    if (_failed || day == null) return const SizedBox.shrink();

    final screen = day['screen'] as Map<String, dynamic>? ?? const {};
    final listening = day['listening'] as Map<String, dynamic>? ?? const {};
    final mission = day['mission'] as Map<String, dynamic>?;
    final screenMin = ((screen['counted_seconds'] as int? ?? 0) / 60).round();
    final screenBudget = ((screen['budget_seconds'] as int? ?? 0) / 60).round();
    final audioMin = ((listening['counted_seconds'] as int? ?? 0) / 60).round();

    // Nothing happened today and nothing is pending: an empty card is noise on
    // the one screen that should stay calm.
    if (screenMin == 0 && audioMin == 0 && mission == null) {
      return const SizedBox.shrink();
    }

    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    return Card(
      elevation: 0,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () async {
          await Navigator.of(context).push(AppRoutes.parentDay());
          if (mounted) _load(childId);
        },
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l10n.parentDayWith('${day['child_name'] ?? ''}'),
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 10),
              // Two lines, never one sum — same rule as the panel.
              Text(l10n.parentDayScreenLine(screenMin, screenBudget),
                  style: theme.textTheme.bodyMedium),
              const SizedBox(height: 4),
              Text(l10n.parentDayAudioLine(audioMin),
                  style: theme.textTheme.bodyMedium
                      ?.copyWith(color: theme.colorScheme.outline)),
              if (mission != null) ...[
                const SizedBox(height: 8),
                Text(
                  mission['status'] == 'claimed'
                      ? l10n.parentDayMissionClaimed('${mission['title_ar']}')
                      : l10n.parentDayMissionAssigned('${mission['title_ar']}'),
                  style: theme.textTheme.bodyMedium,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
