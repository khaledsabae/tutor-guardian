/// The way into «درب {الاسم}» from the Learn tab: one quiet row at the top of
/// the paths list (it scrolls away with them; it never pins).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import 'gate_bits.dart';

class FamilyRoadEntry extends ConsumerWidget {
  const FamilyRoadEntry({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(activeChildProfileProvider);
    if (profile == null) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final t = Theme.of(context).textTheme;
    final name = realChildName(profile.name);
    return Material(
      key: const Key('family-road-entry'),
      color: c.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: c.primary.withValues(alpha: .18)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: () => Navigator.of(
          context,
        ).push(AppRoutes.familyRoad(from: 'learn_tab')),
        child: Padding(
          padding: const EdgeInsetsDirectional.fromSTEB(14, 12, 10, 12),
          child: Row(
            children: [
              const PaperGate(size: 30, near: true),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name == null
                          ? l10n.familyRoadTitleNoName
                          : l10n.familyRoadEntryTitle(name),
                      style: t.titleSmall?.copyWith(
                        color: c.ink,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    Text(
                      l10n.familyRoadEntryBody,
                      style: t.bodySmall?.copyWith(
                        color: c.textSecondary,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
              DirectionalChevron(size: 18, color: c.textSecondary),
            ],
          ),
        ),
      ),
    );
  }
}
