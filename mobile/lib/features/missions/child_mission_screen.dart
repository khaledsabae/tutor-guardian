/// The mission card — sixty seconds of screen that buys fifteen minutes away
/// from it.
///
/// This is rule 1 of the constitution made literal: the screen is a medium,
/// not a destination, so the primary button does not navigate anywhere. It
/// closes the app. Everything about the layout is subordinate to that — one
/// instruction, no scroll, no second thing to look at, and no path onward.
///
/// The backend for this shipped complete and tested (bank of twelve, 21-day
/// no-repeat, batched confirmation, evening digest) with no screen calling it.
/// A child was assigned a mission every single day and was never shown one.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/tg_client.dart';
import '../../l10n/app_localizations.dart';
import '../../state/chat_notifier.dart';
import '../routine/providers/child_mode_providers.dart';
import '../routine/services/child_mode_secure_storage.dart';
import '../routine/widgets/quiet_time_bar.dart';

class ChildMissionScreen extends ConsumerStatefulWidget {
  const ChildMissionScreen({super.key});

  @override
  ConsumerState<ChildMissionScreen> createState() => _ChildMissionScreenState();
}

class _ChildMissionScreenState extends ConsumerState<ChildMissionScreen> {
  Map<String, dynamic>? _mission;
  bool _loading = true;
  bool _claiming = false;

  /// Set when the bank has nothing for this child's band. Not an error: only
  /// 7-9 has a mission bank today, and every other band lands here normally.
  bool _empty = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final token = await getChildToken();
    if (token == null) {
      if (mounted) setState(() { _loading = false; _empty = true; });
      return;
    }
    try {
      final card = await ref.read(tgClientProvider).fetchChildMission(token);
      if (!mounted) return;
      setState(() {
        _mission = card;
        _empty = card == null;
        _loading = false;
      });
    } on TgApiError {
      // A child does not get an error dialog. An unreachable server looks
      // exactly like a day with no mission, which is a state they already
      // understand.
      if (mounted) setState(() { _loading = false; _empty = true; });
    }
  }

  /// "I'm going" — and the app actually goes away.
  ///
  /// Returning to a menu would make this a navigation choice among others.
  /// The session is closed first so the server stops billing the surface, and
  /// so the parent's dashboard shows a finished session rather than one that
  /// timed out.
  Future<void> _understood() async {
    await ref.read(childModeProvider.notifier).endSession(reason: 'completed');
    await SystemNavigator.pop();
  }

  Future<void> _claim() async {
    final card = _mission;
    final token = await getChildToken();
    if (card == null || token == null || _claiming) return;
    setState(() => _claiming = true);
    try {
      await ref.read(tgClientProvider).claimChildMission(
            childToken: token,
            missionId: card['mission_id'] as int,
          );
    } on TgApiError {
      // Swallowed on purpose. The child said they did the thing; telling them
      // the network disagreed teaches them the app is the authority on their
      // own afternoon. The card expires quietly after 48h either way.
    }
    if (!mounted) return;
    setState(() {
      _claiming = false;
      _mission = {...card, 'status': 'claimed'};
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);

    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    if (_empty || _mission == null) {
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('🌙', style: theme.textTheme.displayMedium),
                  const SizedBox(height: 16),
                  Text(
                    l10n.missionNoneToday,
                    textAlign: TextAlign.center,
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: _understood,
                    child: Text(l10n.missionLeave),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    final card = _mission!;
    final claimed = card['status'] == 'claimed' || card['status'] == 'confirmed';

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // The candle, not a countdown. This surface is budgeted at three
              // minutes; the child should feel it shortening, not read it.
              const QuietTimeBar(),
              const Spacer(),
              Text('🧭', style: theme.textTheme.displayLarge,
                  textAlign: TextAlign.center),
              const SizedBox(height: 12),
              Text(
                l10n.missionTodayLabel,
                textAlign: TextAlign.center,
                style: theme.textTheme.labelLarge
                    ?.copyWith(color: theme.colorScheme.outline),
              ),
              const SizedBox(height: 8),
              Text(
                card['title_ar'] as String? ?? '',
                textAlign: TextAlign.center,
                style: theme.textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 16),
              Text(
                card['instruction_ar'] as String? ?? '',
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium?.copyWith(height: 1.6),
              ),
              if (card['needs_outdoors'] == true) ...[
                const SizedBox(height: 12),
                Text(
                  l10n.missionOutdoorsHint,
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: theme.colorScheme.outline),
                ),
              ],
              const Spacer(),
              if (claimed)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(
                    l10n.missionClaimedNote,
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodyMedium
                        ?.copyWith(color: theme.colorScheme.outline),
                  ),
                ),
              FilledButton(
                onPressed: _understood,
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(64),
                  textStyle: theme.textTheme.titleMedium,
                ),
                child: Text(l10n.missionUnderstoodGoing),
              ),
              const SizedBox(height: 8),
              // Deliberately the smaller of the two. Finishing is reported
              // later, from wherever the child actually was; the button that
              // matters right now is the one that ends the screen.
              TextButton(
                onPressed: claimed || _claiming ? null : _claim,
                child: Text(claimed ? l10n.missionAlreadyDone : l10n.missionDone),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
