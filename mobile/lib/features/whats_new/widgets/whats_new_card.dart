/// The «الجديد في التحديث» card.
///
/// Renders nothing at all until every condition in [WhatsNewStore.shouldShow]
/// is met, so a fresh install, a build with no notes, and a user who already
/// dismissed it all get an empty box rather than a special case at the call
/// site.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../../l10n/app_localizations.dart';
import '../../../main.dart' show packageInfoProvider;
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../data/whats_new.dart';

class WhatsNewCard extends ConsumerStatefulWidget {
  const WhatsNewCard({super.key});

  @override
  ConsumerState<WhatsNewCard> createState() => _WhatsNewCardState();
}

class _WhatsNewCardState extends ConsumerState<WhatsNewCard> {
  /// Set once the user dismisses, so the card goes immediately rather than on
  /// the next rebuild after the write lands.
  bool _dismissed = false;

  @override
  Widget build(BuildContext context) {
    if (_dismissed) return const SizedBox.shrink();

    final prefs = ref.watch(sharedPreferencesProvider).valueOrNull;
    final PackageInfo? info = ref.watch(packageInfoProvider).valueOrNull;
    if (prefs == null || info == null) return const SizedBox.shrink();

    final build = int.tryParse(info.buildNumber);
    if (build == null) return const SizedBox.shrink();

    final store = WhatsNewStore(prefs);
    // Seeding a fresh install deliberately does NOT happen here. This widget
    // lives on HomeScreen, which a first-run user only reaches *after*
    // finishing onboarding — by which time `onboardingCompleted` is already
    // true and they look exactly like someone who just updated. The seed runs
    // at startup instead; see `seedWhatsNewForFreshInstall` in main.dart.
    if (!store.shouldShow(
      currentBuild: build,
      onboardingCompleted: onboardingCompletedFrom(prefs),
    )) {
      return const SizedBox.shrink();
    }

    final l10n = AppLocalizations.of(context);
    final items = <String>[
      l10n.whatsNew102Tafsir,
      l10n.whatsNew102Adhkar,
      l10n.whatsNew102Wird,
      l10n.whatsNew102Timing,
    ];

    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
        decoration: BoxDecoration(
          color: AppTheme.primary.withValues(alpha: .07),
          borderRadius: BorderRadius.circular(Dt.rCard),
          border: Border.all(color: AppTheme.primary.withValues(alpha: .18)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text('✨', style: TextStyle(fontSize: 16)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    l10n.whatsNewTitle,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                      color: AppTheme.primary,
                    ),
                  ),
                ),
                // A real close affordance, not a "got it" button buried at the
                // bottom of four lines the user may not want to read.
                IconButton(
                  tooltip: l10n.close,
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  icon: Icon(Icons.close_rounded,
                      size: 18, color: AppTheme.textSecondary),
                  onPressed: () {
                    setState(() => _dismissed = true);
                    store.markSeen(build);
                  },
                ),
              ],
            ),
            const SizedBox(height: 10),
            ...items.map(
              (t) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsetsDirectional.only(top: 6, end: 8),
                      child: Container(
                        width: 5,
                        height: 5,
                        decoration: BoxDecoration(
                          color: AppTheme.primary,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                    Expanded(
                      child: Text(
                        t,
                        style: TextStyle(
                          fontSize: 13.5,
                          height: 1.6,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
