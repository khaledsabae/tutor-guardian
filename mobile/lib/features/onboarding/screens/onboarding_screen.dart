/// Onboarding screen — first-launch flow, redesigned for <90s to first value.
///
/// Two swipeable pages (age question → instant value):
///   1. One question only: «كم عمر طفلك؟» — age chips. Picking one advances.
///   2. Instant value: a curated, age-specific parenting tip (fully local,
///      renders with zero network) + a preview of the age-tailored path and
///      a sample mentor question, then a single CTA.
///
/// Everything else (child name, avatar, gender) is deferred to
/// [EditChildScreen] — the CTA creates the child with a localized default
/// name so the funnel has exactly one required decision.
///
/// On submit:
///   * POST /api/children (via `createChildProvider`)
///   * Persist id + name + age_group to [OnboardingStorage]
///   * Set [onboardingCompletedProvider] = true
///   * Set [activeChildIdProvider] (in progress_providers) = new id
///   * Pop the route — the root scaffold takes over.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../models/enums.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../program/providers/progress_providers.dart';
import '../data/onboarding_storage.dart';
import '../providers/onboarding_providers.dart';
import 'update_splash_screen.dart' show updateSplashVersion;

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _pageController = PageController();
  int _page = 0;
  String? _ageGroup;

  static const _pageCount = 3;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _goTo(int page) {
    _pageController.animateToPage(
      page,
      duration: Dt.base,
      curve: Curves.easeOutCubic,
    );
  }

  void _pickAge(String wire) {
    setState(() => _ageGroup = wire);
    _goTo(2);
  }

  Future<void> _submit() async {
    final ageGroup = _ageGroup;
    if (ageGroup == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).onbSelectAge)),
      );
      _goTo(1);
      return;
    }
    final defaultName = AppLocalizations.of(context).onbDefaultChildName;
    try {
      // Make sure prefs are hydrated before anything reads
      // onboardingStorageProvider (requireValue would throw during boot).
      await ref.read(sharedPreferencesProvider.future);
      final child = await ref
          .read(createChildProvider.notifier)
          .create(name: defaultName, ageGroup: ageGroup)
          // Guard against a hung backend — surface a clear error instead
          // of leaving the user on a blank/loading screen indefinitely.
          .timeout(const Duration(seconds: 45));
      // Persist locally and flip the gate.
      final storage = ref.read(onboardingStorageProvider);
      await storage.setActiveChild(
        id: child.id,
        name: child.name,
        ageGroup: child.ageGroup,
      );
      await ref.read(onboardingStorageProvider).markOnboardingCompleted();
      // A fresh install is not an update. `lastSeenVersion` defaults to null,
      // and main.dart gates the what's-new splash on `!= updateSplashVersion`
      // — so without this line every brand-new user is handed a changelog for
      // a version they have never run, wedged between onboarding and the home
      // screen, at the exact moment they most need orientation. 3,297 devices
      // registered a child; 1,283 ever opened a lesson. This sits on that path.
      await storage.markUpdateSeen(updateSplashVersion);
      unawaited(Analytics.onboardingDone());
      // Flip the gate LAST: main.dart rebuilds and swaps OnboardingScreen →
      // RootScaffold. Only pop if this screen was actually pushed onto a
      // navigator; popping the ROOT route (first-run onboarding) leaves a
      // black frame until the rebuild settles — the cause of the first-run
      // black screen on real devices.
      if (mounted && Navigator.of(context).canPop()) {
        Navigator.of(context).pop(true);
      }
      if (mounted) {
        await ref.read(onboardingCompletedProvider.notifier).markCompleted();
      }
    } on TimeoutException {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppLocalizations.of(context).onbServerSlow),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppLocalizations.of(context).onbChildError('$e')),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final createState = ref.watch(createChildProvider);
    final busy = createState.isLoading;
    final isLastPage = _page == _pageCount - 1;

    return PopScope(
      canPop: false, // onboarding is mandatory
      child: Stack(
        children: [
          Scaffold(
            body: SafeArea(
              child: Column(
                children: [
                  Expanded(
                    child: PageView(
                      controller: _pageController,
                      onPageChanged: (i) => setState(() => _page = i),
                      children: [
                        _LanguageSelectionPage(
                          onChoose: (lang) {
                            ref.read(appLocaleProvider.notifier).setLocale(lang);
                            _goTo(1);
                          },
                        ),
                        _AgeQuestionPage(
                          selected: _ageGroup,
                          onPick: _pickAge,
                        ),
                        _InstantValuePage(
                          ageGroup: _ageGroup,
                          onChangeAge: () => _goTo(1),
                        ),
                      ],
                    ),
                  ),
                  // ── Dots + CTA ──
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
                    child: Column(
                      children: [
                        Directionality(
                          textDirection: TextDirection.ltr,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              for (var i = 0; i < _pageCount; i++)
                                AnimatedContainer(
                                  duration: Dt.fast,
                                  margin:
                                      const EdgeInsets.symmetric(horizontal: 3),
                                  width: _page == i ? 24 : 8,
                                  height: 8,
                                  decoration: BoxDecoration(
                                    color: _page == i
                                        ? AppTheme.primary
                                        : Dt.track,
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        // The CTA only appears on the value page — page 1's
                        // only action is the age chips themselves.
                        if (isLastPage) ...[
                          const SizedBox(height: 16),
                          BouncyButton(
                            label: busy
                                ? AppLocalizations.of(context).onbSaving
                                : AppLocalizations.of(context).onbStartJourney,
                            icon: busy
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : null,
                            onTap: busy ? null : _submit,
                          ),
                          const SizedBox(height: 10),
                          Text(
                            AppLocalizations.of(context).onbDeferredHint,
                            textAlign: TextAlign.center,
                            style: Theme.of(context)
                                .textTheme
                                .bodySmall
                                ?.copyWith(color: AppTheme.textMuted),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          // Full-screen loading overlay — keeps the wait from ever
          // looking like a frozen/black screen (child creation can be
          // slow on first cold backend hit).
          if (busy)
            Positioned.fill(
              child: AbsorbPointer(
                child: ColoredBox(
                  color: Colors.black.withValues(alpha: 0.55),
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.all(28),
                      decoration: BoxDecoration(
                        color: AppTheme.surface,
                        borderRadius: BorderRadius.circular(Dt.rSheet),
                      ),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text('👶', style: TextStyle(fontSize: 44)),
                          const SizedBox(height: 16),
                          const CircularProgressIndicator(),
                          const SizedBox(height: 16),
                          Text(
                            AppLocalizations.of(context).onbPreparing,
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Page 1 — brand line + free badge + the single onboarding question.
class _AgeQuestionPage extends StatelessWidget {
  const _AgeQuestionPage({required this.selected, required this.onPick});

  final String? selected;
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.all(28),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Image.asset(
              'assets/images/generated/mascot_reading.webp',
              height: 120,
              fit: BoxFit.contain,
              errorBuilder: (_, _, _) => const Text(
                '🌙',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 64),
              ),
            ).animate().fadeIn(duration: Dt.base).scale(
                  begin: const Offset(.9, .9),
                  curve: Curves.easeOutBack,
                ),
            const SizedBox(height: 12),
            Text(
              l10n.onbWelcome,
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .headlineSmall
                  ?.copyWith(fontWeight: FontWeight.w800),
            ).animate(delay: 100.ms).fadeIn(duration: Dt.base),
            const SizedBox(height: 10),
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: Dt.primary.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(Dt.rCard),
                border: Border.all(color: Dt.primary.withValues(alpha: 0.25)),
              ),
              child: Text(
                '${l10n.onbFreeTitle} — ${l10n.onbFreeDesc}',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Dt.primaryDeep,
                  fontWeight: FontWeight.w700,
                  height: 1.5,
                  fontSize: 13,
                ),
              ),
            ).animate(delay: 200.ms).fadeIn(duration: Dt.base),
            const SizedBox(height: 28),
            Text(
              l10n.onbAgeQuestion,
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w800),
            ).animate(delay: 300.ms).fadeIn(duration: Dt.base).slideY(begin: .15),
            const SizedBox(height: 6),
            Text(
              l10n.onbAgeQuestionSub,
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: AppTheme.textSecondary),
            ).animate(delay: 380.ms).fadeIn(duration: Dt.base),
            const SizedBox(height: 16),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 8,
              runSpacing: 8,
              children: AgeGroup.values
                  .where((a) => a != AgeGroup.unspecified)
                  .map((a) => _AgeChip(
                        label: a.label(l10n),
                        selected: selected == a.wire,
                        onTap: () => onPick(a.wire),
                      ))
                  .toList(),
            ).animate(delay: 450.ms).fadeIn(duration: Dt.base).slideY(begin: .1),
          ],
        ),
      ),
    );
  }
}

/// Page 2 — the "wow" moment: an instant, fully-local personalized tip for
/// the chosen age plus a preview of what's inside. No network, no waiting.
class _InstantValuePage extends StatelessWidget {
  const _InstantValuePage({required this.ageGroup, required this.onChangeAge});

  final String? ageGroup;
  final VoidCallback onChangeAge;

  /// Curated, age-specific first tip. Local by design: the first value
  /// moment must never wait on a cold backend.
  String _tipFor(AppLocalizations l10n) {
    switch (ageGroup) {
      case 'prenatal-1':
        return l10n.onbTip_prenatal;
      case '2-3':
        return l10n.onbTip_2to3;
      case '4-6':
        return l10n.onbTip_4to6;
      case '7-9':
        return l10n.onbTip_7to9;
      case '10-12':
        return l10n.onbTip_10to12;
      case '13-15':
        return l10n.onbTip_13to15;
      case '16-18':
        return l10n.onbTip_16to18;
      default:
        return l10n.onbTip_4to6;
    }
  }

  /// Sample mentor question for this age — mirrors the age→pain-question
  /// mapping used by the chat empty state (topics match the backend's
  /// curated topic seeds so the first real answer lands grounded).
  String _sampleQuestionFor(AppLocalizations l10n) {
    switch (ageGroup) {
      case 'prenatal-1':
        return l10n.chatQ_sleep;
      case '2-3':
        return l10n.chatQ_stubborn;
      case '4-6':
        return l10n.chatQ_pray5;
      case '7-9':
        return l10n.chatQ_study;
      case '10-12':
        return l10n.chatQ_gaming;
      case '13-15':
        return l10n.chatQ_socialMedia;
      case '16-18':
        return l10n.chatQ_talkOlder;
      default:
        return l10n.chatQ_tantrums;
    }
  }

  String? _ageLabel(AppLocalizations l10n) {
    for (final a in AgeGroup.values) {
      if (a.wire == ageGroup) return a.label(l10n);
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final ageLabel = _ageLabel(l10n);
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 8),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              l10n.onbFirstTipTitle,
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w800),
            ).animate().fadeIn(duration: Dt.base),
            if (ageLabel != null) ...[
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      l10n.onbTipForAge(ageLabel),
                      style: const TextStyle(
                        color: Dt.primaryDeep,
                        fontWeight: FontWeight.w700,
                        fontSize: 13,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: onChangeAge,
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      minimumSize: const Size(0, 32),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    child: Text(
                      l10n.onbChangeAge,
                      style: const TextStyle(fontSize: 13),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 16),
            // ── The tip itself ──
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(20),
                boxShadow: Dt.cardShadow,
                border:
                    Border.all(color: Dt.primary.withValues(alpha: 0.20)),
              ),
              child: Column(
                children: [
                  const Text('💡', style: TextStyle(fontSize: 40)),
                  const SizedBox(height: 12),
                  Text(
                    _tipFor(l10n),
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          height: 1.8,
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ],
              ),
            )
                .animate(delay: 150.ms)
                .fadeIn(duration: Dt.base)
                .scale(begin: const Offset(.95, .95), curve: Curves.easeOutBack),
            const SizedBox(height: 24),
            // ── What's waiting inside ──
            Text(
              l10n.onbReadyForYou,
              style: Theme.of(context)
                  .textTheme
                  .titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700),
            ).animate(delay: 300.ms).fadeIn(duration: Dt.base),
            const SizedBox(height: 10),
            _PreviewRow(emoji: '🛤️', text: l10n.onbReadyPath)
                .animate(delay: 380.ms)
                .fadeIn(duration: Dt.base)
                .slideY(begin: .15),
            const SizedBox(height: 10),
            _PreviewRow(
              emoji: '💬',
              text: l10n.onbReadyChat,
              subText: '«${_sampleQuestionFor(l10n)}»',
            )
                .animate(delay: 460.ms)
                .fadeIn(duration: Dt.base)
                .slideY(begin: .15),
          ],
        ),
      ),
    );
  }
}

class _PreviewRow extends StatelessWidget {
  const _PreviewRow({required this.emoji, required this.text, this.subText});

  final String emoji;
  final String text;
  final String? subText;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: Dt.cardShadow,
      ),
      child: Row(
        children: [
          Text(emoji, style: const TextStyle(fontSize: 28)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  text,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                    height: 1.5,
                  ),
                ),
                if (subText != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    subText!,
                    style: const TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 13,
                      height: 1.5,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AgeChip extends StatelessWidget {
  const _AgeChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: AppTheme.primary,
      labelStyle: TextStyle(
        color: selected ? Colors.white : AppTheme.textPrimary,
        fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
      ),
      side: BorderSide(
        color: selected ? AppTheme.primary : const Color(0xFFD0D5DD),
      ),
    );
  }
}

class _LanguageSelectionPage extends StatelessWidget {
  const _LanguageSelectionPage({required this.onChoose});

  final ValueChanged<String> onChoose;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(28),
      child: Center(
        child: SingleChildScrollView(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                '🌍',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 64),
              ).animate().fadeIn(duration: Dt.base).scale(
                    begin: const Offset(.9, .9),
                    curve: Curves.easeOutBack,
                  ),
              const SizedBox(height: 24),
              const Text(
                'اختر لغة التطبيق',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimary,
                ),
              ).animate(delay: 100.ms).fadeIn(duration: Dt.base),
              const Text(
                'Choose App Language',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textSecondary,
                ),
              ).animate(delay: 150.ms).fadeIn(duration: Dt.base),
              const SizedBox(height: 36),
              BouncyButton(
                label: 'العربية',
                color: AppTheme.primary,
                onTap: () => onChoose('ar'),
              ).animate(delay: 200.ms).fadeIn(duration: Dt.base),
              const SizedBox(height: 16),
              BouncyButton(
                label: 'English',
                color: AppTheme.accent,
                onTap: () => onChoose('en'),
              ).animate(delay: 250.ms).fadeIn(duration: Dt.base),
            ],
          ),
        ),
      ),
    );
  }
}


// Note: we don't import `progress_providers.dart` from the form code
// — the create call is the only side effect. The exports come
// through [progress_providers.dart] when the user lands on
// PathsScreen, so the existing `activeChildIdProvider` picks up the
// new id transparently.
