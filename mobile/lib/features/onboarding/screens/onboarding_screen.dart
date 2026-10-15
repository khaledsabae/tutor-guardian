/// Onboarding screen — first-launch flow, redesigned for <90s to first value.
///
/// Two swipeable pages (age question → instant value):
///   1. One question only: «كم عمر طفلك؟» — age chips. Picking one advances.
///   2. Instant value: a curated, age-specific parenting tip (fully local,
///      renders with zero network) + a preview of the age-tailored path and
///      a sample mentor question, then a single CTA.
///
/// Everything else (avatar, gender) is deferred to [EditChildScreen] — the
/// CTA creates the child with a localized default name so the funnel has
/// exactly one required decision. The name is asked, optionally, *while* the
/// child is being created (see [_WaitingOverlay]): the wait gets a personal
/// touch, and the funnel gets no new step.
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
import '../../../core/haptics.dart';
import '../../../features/companion/widgets/noor_presence.dart';
import '../../../features/shell/root_tab.dart';
import '../../../l10n/app_localizations.dart';
import '../../../models/enums.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/brand_glyph.dart';
import '../../../widgets/ui/night_sky.dart';
import '../../program/data/child_name.dart';
import '../../program/data/progress_models.dart' show ChildProfile;
import '../../program/providers/progress_providers.dart';
import '../../program/providers/settings_providers.dart'
    show updateChildProvider;
import '../../program/providers/program_providers.dart'
    show pendingChatQuestionProvider;
import '../data/onboarding_storage.dart';
import '../providers/onboarding_providers.dart';
import 'update_splash_screen.dart' show updateSplashVersion;
import '../../../widgets/ui/error_retry_view.dart';
import '../../../widgets/ui/art_image.dart';
import '../widgets/welcome_hero.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _pageController = PageController();
  int _page = 0;
  String? _ageGroup;

  /// The parent tapped the sample question on the value page: after the
  /// child is created, the shell should land on the assistant tab with the
  /// question already seeding the chat (Phase 1 «التطبيق يصحو»).
  bool _askAfterOnboard = false;

  static const _pageCount = 3;

  // ── The name, asked on the creation wait (plan phase 2, «الاسم») ──────
  // Owned here, not by the overlay: a failed create takes the overlay down
  // and a retry brings it back, and what the parent typed must survive that.
  final _nameController = TextEditingController();
  final _nameFocus = FocusNode();

  /// «لاحقًا»: the field is gone and the default name stays.
  bool _nameDeclined = false;

  /// A name the parent confirmed — trimmed and valid.
  String? _confirmedName;
  String? _nameError;

  /// From the CTA until the shell takes over, or the create fails: the
  /// overlay's lifetime. Not `createChildProvider.isLoading` alone — the child
  /// exists a few awaits before the gate flips, and a parent mid-name must not
  /// see the overlay (and the keyboard) blink out in between.
  bool _creating = false;

  /// The child exists; the overlay may still be up for the name.
  bool _created = false;

  /// Completed by «تمّ» / «لاحقًا» while a parent who was mid-name when the
  /// child came back is held. A parent who never touched the field is never
  /// held.
  Completer<void>? _nameHold;

  bool get _nameEngaged =>
      _nameFocus.hasFocus || _nameController.text.trim().isNotEmpty;

  @override
  void dispose() {
    _pageController.dispose();
    _nameController.dispose();
    _nameFocus.dispose();
    super.dispose();
  }

  void _confirmName() {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      _declineName();
      return;
    }
    final error = onboardingNameError(AppLocalizations.of(context), name);
    setState(() {
      _nameError = error;
      if (error == null) _confirmedName = name;
    });
    if (error != null) return;
    _nameFocus.unfocus();
    _releaseNameHold();
  }

  void _declineName() {
    _nameController.clear();
    _nameFocus.unfocus();
    setState(() {
      _nameDeclined = true;
      _confirmedName = null;
      _nameError = null;
    });
    _releaseNameHold();
  }

  void _releaseNameHold() {
    final hold = _nameHold;
    if (hold != null && !hold.isCompleted) hold.complete();
  }

  /// After the child exists: wait for a parent who is mid-name, then save
  /// what they confirmed. Ignoring the field costs nothing — no wait at all.
  ///
  /// Never throws: the child exists by now, and an error reaching `_submit`
  /// would read as a failed create — and a retry would make a second child.
  Future<void> _settleName(ChildProfile child) async {
    try {
      if (_confirmedName == null && !_nameDeclined && _nameEngaged) {
        final hold = _nameHold = Completer<void>();
        await hold.future;
        if (!mounted) return;
      }
      final name = _confirmedName;
      unawaited(
        Analytics.onboardingName(
          name != null ? 'named' : (_nameDeclined ? 'later' : 'ignored'),
        ),
      );
      if (name == null || name == child.name) return;
      // Today greets by the new name at once: the on-disk profile changes
      // now, and the server learns it through the edit screen's own PATCH in
      // the background, so a slow network never holds the parent here.
      final container = ProviderScope.containerOf(context, listen: false);
      final storage = container.read(onboardingStorageProvider);
      await storage.setActiveChild(
        id: child.id,
        name: name,
        ageGroup: child.ageGroup,
      );
      container.invalidate(activeChildProfileProvider);
      unawaited(_saveNameOnServer(container, child, name));
    } catch (_) {
      // The default name stays; Settings can still change it.
    }
  }

  /// Outlives this screen (the gate flips right after), so it runs on the
  /// container, never on `ref`. If the server refuses, the name goes back to
  /// what the server has: a greeting that disagrees with Settings is worse
  /// than «طفلي», which the parent can still change there.
  static Future<void> _saveNameOnServer(
    ProviderContainer container,
    ChildProfile child,
    String name,
  ) async {
    // The notifier is autoDispose; keep it alive for the length of the call.
    final keepAlive = container.listen(updateChildProvider, (_, _) {});
    try {
      await container
          .read(updateChildProvider.notifier)
          .call(childId: child.id, name: name, ageGroup: child.ageGroup);
    } catch (_) {
      final storage = container.read(onboardingStorageProvider);
      if (storage.activeChildId == child.id &&
          storage.activeChildName == name) {
        await storage.setActiveChild(
          id: child.id,
          name: child.name,
          ageGroup: child.ageGroup,
        );
        container.invalidate(activeChildProfileProvider);
      }
    } finally {
      keepAlive.close();
    }
  }

  void _goTo(int page) {
    if (_pageController.hasClients) {
      _pageController.animateToPage(
        page,
        duration: Dt.base,
        curve: Curves.easeOutCubic,
      );
    }
    setState(() => _page = page);
  }

  void _pickAge(String wire) {
    // The one decision onboarding asks for — it deserves a tick of
    // acknowledgement (semantic haptics: a choice was made).
    unawaited(Haptics.selection());
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
    // A name confirmed during an attempt that failed goes straight into this
    // one — no second request needed for it.
    final name =
        _confirmedName ?? AppLocalizations.of(context).onbDefaultChildName;
    setState(() {
      _creating = true;
      _created = false;
    });
    try {
      // Make sure prefs are hydrated before anything reads
      // onboardingStorageProvider (requireValue would throw during boot).
      await ref.read(sharedPreferencesProvider.future);
      final child = await ref
          .read(createChildProvider.notifier)
          .create(name: name, ageGroup: ageGroup)
          // Guard against a hung backend — surface a clear error instead
          // of leaving the user on a blank/loading screen indefinitely.
          .timeout(const Duration(seconds: 45));
      if (mounted) setState(() => _created = true);
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
      if (!mounted) return;
      await _settleName(child);
      // The deferred ask, armed on the value page: seed the question and the
      // target tab BEFORE the gate flips, because the shell (and ChatScreen
      // inside it) mounts on the next build. ChatScreen consumes a question
      // that predates it; the shell reads the pending tab on mount.
      if (_askAfterOnboard && mounted) {
        ref.read(pendingChatQuestionProvider.notifier).state =
            sampleQuestionFor(AppLocalizations.of(context), ageGroup);
        ref.read(pendingRootTabProvider.notifier).state = RootTab.assistant;
      }
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
      // Same frame as main.dart's swap to the shell, so nothing blinks; it
      // only shows where this screen outlives the gate (tests, a pushed
      // onboarding).
      if (mounted) setState(() => _creating = false);
    } on TimeoutException {
      if (mounted) setState(() => _creating = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppLocalizations.of(context).onbServerSlow),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    } catch (e) {
      if (mounted) setState(() => _creating = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              AppLocalizations.of(
                context,
              ).onbChildError(describeFailure(AppLocalizations.of(context), e)),
            ),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final createState = ref.watch(createChildProvider);
    // Creating, or created and on the way to the shell (perhaps held by the
    // name — see _settleName).
    final busy = createState.isLoading || _creating;
    final isLastPage = _page == _pageCount - 1;
    final showCta = isLastPage || (_page == 1 && _ageGroup != null);

    return PopScope(
      canPop: false, // onboarding is mandatory
      child: Stack(
        children: [
          // The night sky behind the whole first-run flow — the app's night
          // identity from the very first frame. TwinklingStars holds itself
          // still under reduceMotion (night_sky.dart setStill).
          Positioned.fill(child: ColoredBox(color: AppTheme.background)),
          const Positioned.fill(child: TwinklingStars(count: 28)),
          Scaffold(
            backgroundColor: Colors.transparent,
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
                            ref
                                .read(appLocaleProvider.notifier)
                                .setLocale(lang);
                            _goTo(1);
                          },
                        ),
                        _AgeQuestionPage(selected: _ageGroup, onPick: _pickAge),
                        _InstantValuePage(
                          ageGroup: _ageGroup,
                          onChangeAge: () => _goTo(1),
                          askArmed: _askAfterOnboard,
                          onAskSample: () =>
                              setState(() => _askAfterOnboard = true),
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
                                  margin: const EdgeInsets.symmetric(
                                    horizontal: 3,
                                  ),
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
                        // The CTA appears on the value page, or on the age page once an age is picked
                        if (showCta) ...[
                          const SizedBox(height: 16),
                          BouncyButton(
                            label: busy
                                ? AppLocalizations.of(context).onbSaving
                                : AppLocalizations.of(context).onbStartJourney,
                            icon: busy
                                ? SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Dt.surface,
                                    ),
                                  )
                                : null,
                            onTap: busy ? null : _submit,
                          ),
                          const SizedBox(height: 10),
                          Text(
                            AppLocalizations.of(context).onbDeferredHint,
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.bodySmall
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
          // slow on first cold backend hit). The scrim is opaque to taps
          // (ColoredBox), so nothing behind it can be pressed; only the
          // card's name field and its two buttons take input.
          if (busy)
            Positioned.fill(
              child: ColoredBox(
                color: Colors.black.withValues(alpha: 0.55),
                // The overlay sits beside the Scaffold, not in it; the name
                // field needs a Material above it.
                child: Material(
                  type: MaterialType.transparency,
                  child: SafeArea(
                    child: Padding(
                      // Lift the card above the keyboard the name field opens.
                      padding: EdgeInsets.only(
                        bottom: MediaQuery.viewInsetsOf(context).bottom,
                      ),
                      child: Center(
                        child: SingleChildScrollView(
                          padding: const EdgeInsets.all(20),
                          child: _WaitingOverlay(
                            lines: [
                              AppLocalizations.of(context).onbPreparingStep1,
                              AppLocalizations.of(context).onbPreparingStep2,
                            ],
                            created: _created,
                            nameController: _nameController,
                            nameFocus: _nameFocus,
                            askName: !_nameDeclined && _confirmedName == null,
                            nameError: _nameError,
                            onNameDone: _confirmName,
                            onNameLater: _declineName,
                          ),
                        ),
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

/// The child-creation wait, told as progressive work instead of a bare
/// spinner: Noor in a calm halo above status lines that appear one by one
/// while the create call is in flight. The overlay's lifetime is bounded by
/// `_submit`'s existing 45s timeout — this widget only ever adds lines,
/// never decides when to stop.
///
/// It also asks the child's name — optionally («الاسم», plan phase 2). The
/// title follows the field as the parent types («درب طفلك» → «درب سارة»).
/// Nothing here waits for an answer: a parent who ignores the field is on
/// Today the moment the child exists, exactly as before. Only a parent who
/// is mid-name when it does ([created]) is held, with the lines all ticked,
/// until «تمّ» or «لاحقًا».
class _WaitingOverlay extends StatefulWidget {
  const _WaitingOverlay({
    required this.lines,
    required this.created,
    required this.nameController,
    required this.nameFocus,
    required this.askName,
    required this.nameError,
    required this.onNameDone,
    required this.onNameLater,
  });

  final List<String> lines;

  /// The child exists; the overlay is only still up for the name.
  final bool created;
  final TextEditingController nameController;
  final FocusNode nameFocus;

  /// False once the parent confirmed a name or chose «لاحقًا».
  final bool askName;
  final String? nameError;
  final VoidCallback onNameDone;
  final VoidCallback onNameLater;

  @override
  State<_WaitingOverlay> createState() => _WaitingOverlayState();
}

class _WaitingOverlayState extends State<_WaitingOverlay> {
  /// How many lines are visible. Starts at the first; a timer reveals the
  /// rest so a slow backend reads as work happening, not a freeze.
  int _revealed = 1;
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    if (widget.lines.length > 1) {
      _ticker = Timer.periodic(_revealInterval, (_) {
        if (!mounted || _revealed >= widget.lines.length) return;
        setState(() => _revealed++);
      });
    }
  }

  /// Generous on purpose: the second line promises lesson-picking, which
  /// the backend genuinely does after the child row exists.
  static const _revealInterval = Duration(seconds: 4);

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    // Once the child exists every line is true, whatever the timer reached.
    final shown = widget.created ? widget.lines.length : _revealed;
    final done = widget.created ? shown : shown - 1;
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(Dt.rSheet),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          NoorPresence(size: 84, semanticLabel: l10n.noorName),
          const SizedBox(height: 14),
          // The live title: the field's text as the parent types it.
          ValueListenableBuilder<TextEditingValue>(
            valueListenable: widget.nameController,
            builder: (context, value, _) {
              final name = value.text.trim();
              return Text(
                name.isEmpty
                    ? l10n.onbNameTitleDefault
                    : l10n.onbNameTitle(name),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimary,
                ),
              );
            },
          ),
          const SizedBox(height: 14),
          for (var i = 0; i < shown; i++) ...[
            if (i > 0) const SizedBox(height: 8),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  // Every visible line except the last is done; the last one
                  // is the work in progress — until the child exists.
                  i < done
                      ? Icons.check_circle_outline
                      : Icons.radio_button_checked,
                  size: 18,
                  color: i < done ? AppTheme.primary : AppTheme.textSecondary,
                ),
                const SizedBox(width: 8),
                Flexible(
                  child: Text(
                    widget.lines[i],
                    overflow: TextOverflow.ellipsis,
                    maxLines: 2,
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
          ],
          if (widget.askName) ...[
            const SizedBox(height: 22),
            _NameField(
              controller: widget.nameController,
              focusNode: widget.nameFocus,
              error: widget.nameError,
              onDone: widget.onNameDone,
              onLater: widget.onNameLater,
            ),
          ],
        ],
      ),
    );
  }
}

/// «ما اسم طفلك؟» — one optional line and its two ways out. Never autofocused:
/// a keyboard that opens by itself would hold every parent on this overlay.
class _NameField extends StatelessWidget {
  const _NameField({
    required this.controller,
    required this.focusNode,
    required this.error,
    required this.onDone,
    required this.onLater,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final String? error;
  final VoidCallback onDone;
  final VoidCallback onLater;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return SizedBox(
      width: 320,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            l10n.onbNameQuestion,
            style: TextStyle(
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: controller,
            focusNode: focusNode,
            maxLength: onboardingNameMaxLength,
            textInputAction: TextInputAction.done,
            textCapitalization: TextCapitalization.words,
            onSubmitted: (_) => onDone(),
            decoration: InputDecoration(
              hintText: l10n.onbNameHint,
              errorText: error,
              // The cap is enforced as they type; a running count would only
              // turn a name into a form.
              counterText: '',
              prefixIcon: const Icon(Icons.person_outline),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              TextButton(
                onPressed: onLater,
                child: Text(
                  l10n.onbNameLater,
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ),
              const Spacer(),
              BouncyButton(
                label: l10n.onbNameDone,
                expanded: false,
                onTap: onDone,
              ),
            ],
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
            Center(
                  child: Container(
                    width: 120,
                    height: 120,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      // The art's own emerald, like every Noor window.
                      color: kNoorWindowGround,
                      // A solid gold paper ring: a translucent orange over the
                      // emerald read as olive.
                      border: Border.all(
                        color: const Color(0xFFF7C548),
                        width: 3,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: const Color(
                            0xFFF7C548,
                          ).withValues(alpha: 0.25),
                          blurRadius: 18,
                          spreadRadius: 2,
                        ),
                      ],
                    ),
                    child: ClipOval(
                      child: Padding(
                        padding: const EdgeInsets.all(6),
                        child: ArtImage(
                          'assets/svg/noor/noor_reading.svg',
                          fallback: (_) => const Center(
                            child: BrandGlyph(BrandIcon.crescent, size: 64),
                          ),
                        ),
                      ),
                    ),
                  ),
                )
                .animate()
                .fadeIn(duration: Dt.base)
                .scale(begin: const Offset(.9, .9), curve: Curves.easeOutBack),
            const SizedBox(height: 12),
            Text(
              l10n.onbWelcome,
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
            ).animate(delay: 100.ms).fadeIn(duration: Dt.base),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: Dt.primary.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(Dt.rCard),
                border: Border.all(color: Dt.primary.withValues(alpha: 0.25)),
              ),
              child: Text(
                '${l10n.onbFreeTitle} — ${l10n.onbFreeDesc}',
                textAlign: TextAlign.center,
                style: TextStyle(
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
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                )
                .animate(delay: 300.ms)
                .fadeIn(duration: Dt.base)
                .slideY(begin: .15),
            const SizedBox(height: 6),
            Text(
              l10n.onbAgeQuestionSub,
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: AppTheme.textSecondary),
            ).animate(delay: 380.ms).fadeIn(duration: Dt.base),
            const SizedBox(height: 16),
            Wrap(
                  alignment: WrapAlignment.center,
                  spacing: 8,
                  runSpacing: 8,
                  children: AgeGroup.values
                      .where((a) => a != AgeGroup.unspecified)
                      .map(
                        (a) => _AgeChip(
                          label: a.label(l10n),
                          selected: selected == a.wire,
                          onTap: () => onPick(a.wire),
                        ),
                      )
                      .toList(),
                )
                .animate(delay: 450.ms)
                .fadeIn(duration: Dt.base)
                .slideY(begin: .1),
          ],
        ),
      ),
    );
  }
}

/// Sample mentor question for an age band — mirrors the age→pain-question
/// mapping used by the chat empty state (topics match the backend's curated
/// topic seeds so the first real answer lands grounded). Top-level because
/// two places need the identical string: the value page shows it, and
/// `_submit` seeds it into the chat when the parent asked for it.
String sampleQuestionFor(AppLocalizations l10n, String? ageGroup) {
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

/// Page 2 — the "wow" moment: an instant, fully-local personalized tip for
/// the chosen age plus a preview of what's inside. No network, no waiting.
class _InstantValuePage extends StatelessWidget {
  const _InstantValuePage({
    required this.ageGroup,
    required this.onChangeAge,
    required this.askArmed,
    required this.onAskSample,
  });

  final String? ageGroup;
  final VoidCallback onChangeAge;

  /// Whether the parent tapped the sample question (arming the deferred
  /// ask), and the tap handler that arms it.
  final bool askArmed;
  final VoidCallback onAskSample;

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
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
            ).animate().fadeIn(duration: Dt.base),
            if (ageLabel != null) ...[
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      l10n.onbTipForAge(ageLabel),
                      style: TextStyle(
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
                    border: Border.all(
                      color: Dt.primary.withValues(alpha: 0.20),
                    ),
                  ),
                  child: Column(
                    children: [
                      NoorPresence(size: 64, semanticLabel: l10n.noorName),
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
                .scale(
                  begin: const Offset(.95, .95),
                  curve: Curves.easeOutBack,
                ),
            const SizedBox(height: 24),
            // ── What's waiting inside ──
            Text(
              l10n.onbReadyForYou,
              style: Theme.of(
                context,
              ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
            ).animate(delay: 300.ms).fadeIn(duration: Dt.base),
            const SizedBox(height: 10),
            _PreviewRow(icon: BrandIcon.path, text: l10n.onbReadyPath)
                .animate(delay: 380.ms)
                .fadeIn(duration: Dt.base)
                .slideY(begin: .15),
            const SizedBox(height: 10),
            // The sample question is a real button: tapping it arms a
            // deferred ask — after onboarding, the shell lands on the
            // assistant tab with this question already seeding the chat.
            _SampleQuestionRow(
                  label: l10n.onbReadyChat,
                  question: '«${sampleQuestionFor(l10n, ageGroup)}»',
                  armed: askArmed,
                  armedHint: l10n.onbAskSampleArmed,
                  hint: l10n.onbAskSampleHint,
                  onTap: onAskSample,
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
  const _PreviewRow({required this.icon, required this.text});

  final BrandIcon icon;
  final String text;

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
          BrandGlyph(icon, size: 30, color: context.colors.primary),
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
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The sample mentor question, as a button. Tapping arms the deferred ask:
/// after the child is created, the assistant tab opens with this question
/// already sent to the mentor.
class _SampleQuestionRow extends StatelessWidget {
  const _SampleQuestionRow({
    required this.label,
    required this.question,
    required this.armed,
    required this.armedHint,
    required this.hint,
    required this.onTap,
  });

  final String label;
  final String question;
  final bool armed;
  final String armedHint;
  final String hint;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return BouncyTap(
      onTap: () {
        unawaited(Haptics.selection());
        onTap();
      },
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          boxShadow: Dt.cardShadow,
          border: Border.all(
            color: armed
                ? AppTheme.primary.withValues(alpha: 0.6)
                : Colors.transparent,
            width: 1.5,
          ),
        ),
        child: Row(
          children: [
            BrandGlyph(
              BrandIcon.speechBubble,
              size: 30,
              color: context.colors.primary,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    question,
                    style: TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 13,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Icon(
                        armed ? Icons.check_circle : Icons.touch_app_outlined,
                        size: 16,
                        color: armed ? AppTheme.primary : AppTheme.textMuted,
                      ),
                      const SizedBox(width: 4),
                      Flexible(
                        child: Text(
                          armed ? armedHint : hint,
                          style: TextStyle(
                            color: armed ? Dt.primaryDeep : AppTheme.textMuted,
                            fontSize: 12,
                            fontWeight: armed
                                ? FontWeight.w700
                                : FontWeight.w500,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
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
        color: selected ? AppTheme.primary : context.colors.track,
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
              SizedBox(
                    height: 140,
                    child: Center(
                      child: WelcomeHero(
                        // The hero is bundled; if it is ever missing the
                        // layout keeps a drawn anchor instead of collapsing
                        // (a globe: this is the language page).
                        fallback: (_) => const Center(
                          child: BrandGlyph(BrandIcon.globe, size: 64),
                        ),
                      ),
                    ),
                  )
                  .animate()
                  .fadeIn(duration: Dt.base)
                  .scale(
                    begin: const Offset(.9, .9),
                    curve: Curves.easeOutBack,
                  ),
              const SizedBox(height: 24),
              Text(
                'اختر لغة التطبيق',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimary,
                ),
              ).animate(delay: 100.ms).fadeIn(duration: Dt.base),
              Text(
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
