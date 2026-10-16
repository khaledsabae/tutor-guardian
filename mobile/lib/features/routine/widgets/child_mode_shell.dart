/// The frame around every child surface (UX_UI_ROADMAP §4.3, E6).
///
/// The child surface used to look like the parent app with fewer buttons, so
/// a handed-over phone gave neither of them a clear cue. This frame:
///  * applies [AppTheme.child] — larger type, 56 dp targets, rounder cards;
///  * keeps one bar on top for the whole session: «وضع الطفل», the child's
///    name and avatar, the quiet time bar (never digits), and Exit, which
///    still goes through the parent PIN;
///
/// It used to open with a 1.1-second hand-over card as well. That card ran
/// inside the session — on the child's clock, and swallowing their first taps.
/// The moment of handing over now belongs to the hand-over gate
/// (`features/handover/handover_gate_screen.dart`), whose doors open in parent
/// mode before the session exists; the frame shows the surface straight away.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_theme.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../providers/child_mode_providers.dart';
import 'quiet_time_bar.dart';

class ChildModeShell extends ConsumerStatefulWidget {
  const ChildModeShell({super.key, required this.child});

  final Widget child;

  /// The fade between the parent app and the child surface (main.dart).
  static const fade = Duration(milliseconds: 300);

  @override
  ConsumerState<ChildModeShell> createState() => _ChildModeShellState();
}

class _ChildModeShellState extends ConsumerState<ChildModeShell> {
  Future<void> _askExit() async {
    // The exit checks the PIN and nothing else, so it must not wait on the
    // child id: a restart can bring child mode back without one (the flag and
    // the id live in different stores), and an Exit that did nothing would
    // leave the device on the hand-back screen for good.
    final childId = ref.read(childModeProvider).childId ?? 0;
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.habitChildModeExitTitle),
        content: Text(l10n.habitChildModeExitConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n.habitChildModeExit),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await Navigator.of(context).push(
      AppRoutes.childModeLock<void>(
        childId: childId,
        childName: AppLocalizations.of(context).childFallbackName,
        isExit: true,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = AppTheme.child(Theme.of(context).brightness);
    // The name and avatar are a courtesy: if the profile cannot be read yet
    // (preferences still loading), fall back to the generic ones rather than
    // take down the child's whole surface.
    ActiveChildProfile? profile;
    try {
      profile = ref.watch(activeChildProfileProvider);
    } catch (_) {
      profile = null;
    }
    final l10n = AppLocalizations.of(context);
    final name = profile?.name ?? l10n.childFallbackName;
    final corner = ref.watch(childModeProvider.select((s) => s.corner));

    return Theme(
      data: theme,
      child: Builder(builder: (context) {
        final c = context.colors;
        return Column(
          children: [
            Material(
              color: c.primary,
              child: SafeArea(
                bottom: false,
                child: Padding(
                  padding: const EdgeInsetsDirectional.fromSTEB(16, 4, 4, 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Semantics(
                              header: true,
                              child: Text(
                                '${l10n.childMode} · $name',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: theme.textTheme.titleMedium
                                    ?.copyWith(
                                  color: c.onPrimary,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                          ),
                          Semantics(
                            container: true,
                            button: true,
                            label: l10n.a11yExitChildMode,
                            onTap: _askExit,
                            excludeSemantics: true,
                            child: IconButton(
                              tooltip: l10n.a11yExitChildMode,
                              icon: Icon(Icons.logout, color: c.onPrimary),
                              onPressed: _askExit,
                            ),
                          ),
                        ],
                      ),
                      // The corner draws its own clock — a paper candle in
                      // the scene — so the frame does not draw a second one.
                      if (!corner)
                        const Padding(
                          padding: EdgeInsetsDirectional.only(end: 12),
                          child: QuietTimeBar(),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            Expanded(
              child: MediaQuery.removePadding(
                context: context,
                removeTop: true,
                child: widget.child,
              ),
            ),
          ],
        );
      }),
    );
  }
}
