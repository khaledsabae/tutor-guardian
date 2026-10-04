/// «المتابعة» on Today — plan §1.2, the loop that brings a parent back.
///
/// Shows one due follow-up (the active child's first, else the oldest of any
/// child, named), with the four answers right on the card: one tap opens the
/// sheet with that answer chosen and an optional note. "Don't ask about this"
/// dismisses without opening anything.
///
/// Hides itself while loading, on any failure, on an older server, and for a
/// session that is not proven yet (the launch's background proof brings it in
/// when it lands — this card never starts a challenge).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../data/memory_models.dart';
import '../data/placeholder_names.dart';
import '../providers/memory_providers.dart';
import 'followup_sheet.dart';
import 'memory_errors.dart';

class TodayFollowupCard extends ConsumerStatefulWidget {
  const TodayFollowupCard({super.key, required this.activeChildId});

  final int? activeChildId;

  @override
  ConsumerState<TodayFollowupCard> createState() => _TodayFollowupCardState();
}

class _TodayFollowupCardState extends ConsumerState<TodayFollowupCard> {
  late final AppLifecycleListener _lifecycle;
  DateTime _lastLook = DateTime.now();
  bool _dismissing = false;

  @override
  void initState() {
    super.initState();
    // A follow-up falls due while the app sleeps (the push goes out at 19:00
    // family time); a parent who comes back by the launcher, not the push,
    // must still see it. At most one look a minute.
    _lifecycle = AppLifecycleListener(onResume: () {
      final now = DateTime.now();
      if (now.difference(_lastLook) < const Duration(minutes: 1)) return;
      _lastLook = now;
      ref.invalidate(dueFollowupsProvider);
    });
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  Followup? _pick(List<Followup> due) {
    if (due.isEmpty) return null;
    final active = widget.activeChildId;
    for (final f in due) {
      if (f.childId == active) return f;
    }
    return due.first;
  }

  Future<void> _dismiss(Followup f) async {
    if (_dismissing) return;
    setState(() => _dismissing = true);
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context);
    // Held before the await: the card may be gone when the answer comes.
    final container = ProviderScope.containerOf(context, listen: false);
    unawaited(Analytics.todayBlockTapped('loop', 'followup_dismiss'));
    try {
      await container.read(memoryRepositoryProvider).dismiss(f.id);
      messenger.showSnackBar(SnackBar(content: Text(l10n.followupDismissed)));
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(describeActionFailure(context, e))));
      }
    } finally {
      container.invalidate(dueFollowupsProvider);
      if (mounted) setState(() => _dismissing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final due = ref.watch(dueFollowupsProvider).valueOrNull;
    final f = due == null ? null : _pick(due);
    if (f == null) return const SizedBox.shrink();

    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final name = ref.watch(childNameProvider(f.childId));
    final strategy = renderMemoryText(f.strategy,
        childName: name, family: ref.watch(familyMembersProvider));

    void open(String? outcome) {
      unawaited(Analytics.todayBlockTapped('loop', 'followup_answer'));
      unawaited(showFollowupSheet(
        context,
        followupId: f.id,
        source: FollowupSource.today,
        initial: f,
        preselected: outcome,
      ));
    }

    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Material(
        color: colors.surface,
        borderRadius: BorderRadius.circular(Dt.rCard),
        child: InkWell(
          borderRadius: BorderRadius.circular(Dt.rCard),
          onTap: () => open(null),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(Dt.rCard),
              border: Border.all(
                  color: colors.primary.withValues(alpha: colors.isDark ? .35 : .22)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Icon(Icons.replay_circle_filled_outlined,
                        color: colors.primary, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        name == null
                            ? l10n.followupTitle
                            : l10n.followupTitleFor(name),
                        style: TextStyle(
                          color: colors.primary,
                          fontWeight: FontWeight.w800,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  l10n.followupQuestion(strategy),
                  textDirection: ContentDirectionality.resolve(
                      text: strategy, fallback: Directionality.of(context)),
                  style: TextStyle(
                    color: colors.ink,
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final o in FollowupOutcome.all)
                      ActionChip(
                        label: Text(outcomeLabel(l10n, o)),
                        onPressed: () => open(o),
                      ),
                  ],
                ),
                Align(
                  alignment: AlignmentDirectional.centerEnd,
                  child: TextButton(
                    onPressed: _dismissing ? null : () => _dismiss(f),
                    child: Text(l10n.followupDismiss),
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
