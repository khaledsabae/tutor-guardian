/// Phase 8-B — shows the active child (emoji + name) in the PathsScreen
/// AppBar. Tap → opens [ChildrenListScreen] to switch / add a child.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../screens/children_list_screen.dart';

class ActiveChildChip extends ConsumerWidget {
  const ActiveChildChip({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(activeChildProfileProvider);
    final l10n = AppLocalizations.of(context);
    void chooseChild() => Navigator.of(context).push(AppRoutes.childrenList());
    return Semantics(
      container: true,
      button: true,
      // The chip opens the children list — it doesn't select anyone — so
      // the label names who is active now and says what a tap does.
      label: profile != null
          ? l10n.a11yCurrentChild(profile.name)
          : l10n.a11yChooseAChild,
      onTap: chooseChild,
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        // 48dp lives on the hit area, not on the pill: the visible pill keeps
        // its compact app-bar size and sits centred in the larger target.
        child: ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
          child: InkWell(
            borderRadius: BorderRadius.circular(20),
            excludeFromSemantics: true,
            onTap: chooseChild,
            child: Center(
              widthFactor: 1,
              heightFactor: 1,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 5,
                ),
                decoration: BoxDecoration(
                  color: Theme.of(context).brightness == Brightness.dark
                      ? Colors.white.withValues(alpha: 0.12)
                      : AppTheme.primary.withValues(alpha: 0.08),
                  border: Border.all(
                    color: AppTheme.primary.withValues(alpha: 0.25),
                    width: 1,
                  ),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      profile?.avatarEmoji ?? '👶',
                      style: const TextStyle(fontSize: 16),
                    ),
                    const SizedBox(width: 5),
                    if (profile != null) ...[
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 80),
                        child: Text(
                          profile.name,
                          style: TextStyle(
                            color:
                                Theme.of(context).brightness == Brightness.dark
                                ? Colors.white
                                : AppTheme.primaryDark,
                            fontWeight: FontWeight.w700,
                            fontSize: 13,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 2),
                      Icon(
                        Icons.unfold_more,
                        size: 14,
                        color: Theme.of(context).brightness == Brightness.dark
                            ? Colors.white70
                            : AppTheme.primaryDark,
                      ),
                    ] else
                      Text(
                        AppLocalizations.of(context).activeChildLabel,
                        style: TextStyle(
                          color: Theme.of(context).brightness == Brightness.dark
                              ? Colors.white
                              : AppTheme.primaryDark,
                          fontWeight: FontWeight.w700,
                          fontSize: 13,
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
