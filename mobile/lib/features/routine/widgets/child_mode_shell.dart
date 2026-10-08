/// The frame around every child surface (UX_UI_ROADMAP §4.3, E6).
///
/// The child surface used to look like the parent app with fewer buttons, so
/// a handed-over phone gave neither of them a clear cue. This frame:
///  * applies [AppTheme.child] — larger type, 56 dp targets, rounder cards;
///  * keeps one bar on top for the whole session: «وضع الطفل», the child's
///    name and avatar, the quiet time bar (never digits), and Exit, which
///    still goes through the parent PIN;
///  * opens with a short hand-over card showing the child's avatar, so the
///    moment the device changes hands is unmistakable. Reduced motion keeps
///    the card but drops the fade.
library;

import 'dart:async';

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

  /// How long the hand-over card stays before fading to the surface.
  static const handoffHold = Duration(milliseconds: 1100);
  static const fade = Duration(milliseconds: 300);

  @override
  ConsumerState<ChildModeShell> createState() => _ChildModeShellState();
}

class _ChildModeShellState extends ConsumerState<ChildModeShell> {
  bool _handoff = true;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer(ChildModeShell.handoffHold, () {
      if (mounted) setState(() => _handoff = false);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _askExit() async {
    final childId = ref.read(childModeProvider).childId;
    if (childId == null) return;
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
    final avatar = profile?.avatarEmoji ?? '🧒';
    final reduce = MediaQuery.maybeDisableAnimationsOf(context) ?? false;

    return Theme(
      data: theme,
      child: Builder(builder: (context) {
        final c = context.colors;
        return Stack(
          children: [
            Column(
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
                              ExcludeSemantics(
                                child: Text(avatar,
                                    style: const TextStyle(fontSize: 26)),
                              ),
                              const SizedBox(width: 10),
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
            ),
            IgnorePointer(
              ignoring: !_handoff,
              child: AnimatedOpacity(
                opacity: _handoff ? 1 : 0,
                duration: reduce ? Duration.zero : ChildModeShell.fade,
                child: _HandoffCard(avatar: avatar, name: name),
              ),
            ),
          ],
        );
      }),
    );
  }
}

class _HandoffCard extends StatelessWidget {
  const _HandoffCard({required this.avatar, required this.name});

  final String avatar;
  final String name;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    return Semantics(
      liveRegion: true,
      label: l10n.childModeHandoff(name),
      excludeSemantics: true,
      child: ColoredBox(
        color: c.primary,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(avatar, style: const TextStyle(fontSize: 96)),
              const SizedBox(height: 16),
              Text(
                l10n.childModeHandoff(name),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: c.onPrimary,
                      fontWeight: FontWeight.w800,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
