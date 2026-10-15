/// Who holds the device, decided before anything of the parent's is built.
///
/// The root of the app under the boot checks (main.dart). While child mode is
/// on it is the child surface, in its frame; otherwise the parent's app — but
/// only once [childModeRestoreProvider] has looked at what the last run left
/// on disk. Until then it is [waiting], so a restart in the middle of a child
/// session never shows the parent's app, not even for a frame.
///
/// Entering and leaving child mode is a fade-through (UX_UI_ROADMAP §4.3):
/// the parent app and the child surface never cut hard into each other.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/child_mode_providers.dart';
import '../screens/habit_child_mode_screen.dart';
import 'child_mode_shell.dart';

class ChildModeGate extends ConsumerWidget {
  const ChildModeGate({
    super.key,
    required this.parentApp,
    required this.waiting,
  });

  /// The parent's app. Built only when no child has the device.
  final Widget parentApp;

  /// Shown while the last run's child mode is still being looked up.
  final Widget waiting;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final active = ref.watch(childModeProvider.select((s) => s.active));
    final restoring = ref.watch(childModeRestoreProvider).isLoading;
    return AnimatedSwitcher(
      duration: ChildModeShell.fade,
      child: KeyedSubtree(
        key: ValueKey<bool>(active),
        child: active
            ? const ChildModeShell(child: HabitChildModeScreen())
            : restoring
                ? waiting
                : parentApp,
      ),
    );
  }
}
