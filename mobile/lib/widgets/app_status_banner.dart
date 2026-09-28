/// One app-wide status line for "you are offline" and "this is a saved copy"
/// (UX_UI_ROADMAP E2).
///
/// Offline used to be signalled only inside the chat, and the curriculum's
/// offline cache served yesterday's copy without a word. This sits above every
/// route (it is installed in `MaterialApp.builder`), takes the status-bar inset
/// itself while shown, and disappears when there is nothing to say.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/program/data/curriculum_cache.dart';
import '../l10n/app_localizations.dart';
import '../state/connectivity_provider.dart';
import '../theme/app_colors.dart';

class AppStatusBanner extends ConsumerWidget {
  const AppStatusBanner({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final online = ref
        .watch(connectivityProvider)
        .maybeWhen(data: (v) => v, orElse: () => true);
    return ValueListenableBuilder<DateTime?>(
      valueListenable: CurriculumCache.servedStaleAt,
      builder: (context, savedAt, _) {
        final message = statusMessage(context, online: online, savedAt: savedAt);
        if (message == null) return child;
        final c = context.colors;
        return Column(
          children: [
            Material(
              color: c.warningBg,
              child: SafeArea(
                bottom: false,
                child: Semantics(
                  liveRegion: true,
                  container: true,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 6),
                    child: Row(
                      children: [
                        Icon(online ? Icons.history : Icons.wifi_off,
                            size: 16, color: c.warningFg),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            message,
                            style: TextStyle(
                              color: c.warningFg,
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            // The banner owns the top inset while it is shown, so app bars
            // below do not pad for a status bar that is no longer above them.
            Expanded(
              child: MediaQuery.removePadding(
                context: context,
                removeTop: true,
                child: child,
              ),
            ),
          ],
        );
      },
    );
  }

  /// The line to show, or null for none. Public for tests.
  static String? statusMessage(
    BuildContext context, {
    required bool online,
    DateTime? savedAt,
  }) {
    final l10n = AppLocalizations.of(context);
    final when = savedAt == null ? null : _formatSavedAt(context, savedAt);
    if (!online) {
      return when == null ? l10n.appOfflineBanner : l10n.appOfflineSavedCopy(when);
    }
    return when == null ? null : l10n.appSavedCopy(when);
  }

  static String _formatSavedAt(BuildContext context, DateTime savedAt) {
    final m = MaterialLocalizations.of(context);
    final local = savedAt.toLocal();
    final now = DateTime.now();
    final time = m.formatTimeOfDay(TimeOfDay.fromDateTime(local));
    final sameDay = local.year == now.year &&
        local.month == now.month &&
        local.day == now.day;
    return sameDay ? time : '${m.formatShortDate(local)} $time';
  }
}
