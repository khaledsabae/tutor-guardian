/// The child's last screen: the session is over, and the device goes back.
///
/// Every child surface used to end differently. The mission card closes the
/// app; the licence called `exitWithoutPin`, which put the *parent's* app —
/// chat, settings, every child's profile — in the child's hands with no PIN;
/// and a habit session that ran out of time left the checklist on screen with
/// a dead token, where the next tap's 401 cleared child mode and did the same.
///
/// This is where they end instead. The session is closed, so nothing is
/// billed while the device waits; child mode is still on, so the only way out
/// is the frame's Exit, behind the parent's PIN. And the screen says what to
/// do next, in family words — «أهلك», never one parent.
///
/// A restart lands here too. Child mode outlives the process, so a child who
/// force-closes the app on this screen — or anywhere in a session — opens it
/// again to this screen, not to the parent's app (`ChildModeNotifier.restore`).
library;

import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../../theme/app_colors.dart';
import '../../widgets/ui/brand_glyph.dart';

/// «أعِد الجهاز إلى أهلك — شكرًا لك».
class ChildReturnLine extends StatelessWidget {
  const ChildReturnLine({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Text(
      AppLocalizations.of(context).childReturnDevice,
      textAlign: TextAlign.center,
      style: theme.textTheme.titleMedium?.copyWith(
        color: context.colors.primary,
        fontWeight: FontWeight.w800,
        height: 1.6,
      ),
    );
  }
}

class ChildHandBackScreen extends StatelessWidget {
  const ChildHandBackScreen({super.key, this.message});

  /// Why it ended — the day's time, a lost connection, a finished level.
  /// Null when the return line is the whole story.
  final String? message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return PopScope(
      // Back would close the app from the root, and the next launch opens the
      // parent's app with no PIN. The device goes back by hand, not by gesture.
      canPop: false,
      child: Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  ExcludeSemantics(
                    child: GlyphHero(
                      BrandIcon.fullMoon,
                      size: 64,
                      color: context.colors.primary,
                      background: context.colors.primary.withValues(alpha: .08),
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (message != null) ...[
                    Text(
                      message!,
                      textAlign: TextAlign.center,
                      style: theme.textTheme.titleMedium?.copyWith(height: 1.6),
                    ),
                    const SizedBox(height: 16),
                  ],
                  const ChildReturnLine(),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
