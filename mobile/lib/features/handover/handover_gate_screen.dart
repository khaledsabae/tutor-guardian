/// «باب التسليم» — the one place a parent hands the device to a child.
///
/// It replaces a column of nine buttons under the habit list, four of which
/// opened a child surface, each behind its own hand-written age check — and
/// the other ways in (today's mission, the parent's day, the prayer card) had
/// checks of their own, or none: a 4-6 profile could still be sent to `habit`
/// and meet the server's `surface_not_allowed` as «فشل الدخول لوضع الطفل».
/// Now there is one button, and every way in opens this:
///
///  1. **What will {name} do?** Only the surfaces the child's band is allowed
///     (`child_surface.v1.yaml`, mirrored in [kChildSurfacePolicy]) and this
///     build can open. Under two — `prenatal-1` and the legacy `0-3` — nothing
///     is offered, and the screen says why.
///  2. **The PIN**, on the existing lock screen, which only checks it.
///  3. **The doors.** Two paper mashrabiya leaves swing open on «يا {name}،
///     دورك الآن» — a plain fade under reduced motion. This plays in *parent*
///     mode, before the child's session exists, so the moment of handing over
///     is never billed to the child's minutes (the old hand-over card ran
///     inside the session, on the child's clock).
///  4. **The session**, opened through [ChildModeNotifier.enter] with the same
///     PIN. A refusal that still gets through lands on a calm sentence here,
///     not on «فشل الدخول».
///
/// A caller that already knows the surface (today's mission, the prayer card)
/// passes it and skips step 1.
///
/// «ركن الطفل» ([kChildCornerSurface]) is listed first when the band allows
/// it. It is not a server surface: its session opens on the first part of
/// the corner the band allows (`story`), with [ChildModeState.cornerBand] set
/// so the child lands in `features/child_corner/` instead of a single screen.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_routes.dart';
import '../../core/motion.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_colors.dart';
import '../child_corner/corner_picks.dart';
import '../onboarding/providers/onboarding_providers.dart';
import '../program/data/story_models.dart' show contentLanguageFor;
import '../routine/providers/child_mode_providers.dart';
import '../routine/screens/child_mode_lock_screen.dart';
import 'child_surface_policy.dart';
import 'handover_doors.dart';

class HandoverGateScreen extends ConsumerStatefulWidget {
  const HandoverGateScreen({
    super.key,
    required this.childId,
    required this.childName,
    this.ageGroup,
    this.surface,
  });

  final int childId;
  final String childName;

  /// The profile's age group. Null when the caller could not tell; the gate
  /// then reads the active child's, and fails closed if that is another child.
  final String? ageGroup;

  /// Skip the choice and open this surface.
  final String? surface;

  /// The doors' swing — and the least time «دورك الآن» stays on screen before
  /// the session opens, reduced motion included.
  static const opening = Duration(milliseconds: 1200);

  @override
  ConsumerState<HandoverGateScreen> createState() => _HandoverGateScreenState();
}

enum _Phase {
  /// Choosing a surface.
  choosing,

  /// Doors closed, the PIN screen on top.
  waiting,

  /// Doors opening, then the session being opened. The device may already be
  /// in the child's hands, so back is held.
  opening,

  /// The server said no. Doors open on a calm sentence and a way back.
  refused,
}

class _HandoverGateScreenState extends ConsumerState<HandoverGateScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _doors;

  late _Phase _phase =
      widget.surface == null ? _Phase.choosing : _Phase.waiting;

  /// The doors are open and the session is on its way.
  bool _minting = false;

  String? _refusal;

  /// The day's time is spent: the refusal also points at something to do
  /// away from the screen, as the lock screen's did.
  bool _refusalIsBudget = false;

  @override
  void initState() {
    super.initState();
    _doors =
        AnimationController(vsync: this, duration: HandoverGateScreen.opening);
    final preset = widget.surface;
    if (preset != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _start(preset);
      });
    }
  }

  @override
  void dispose() {
    _doors.dispose();
    super.dispose();
  }

  /// The age group the policy is read against.
  String? get _ageGroup {
    if (widget.ageGroup != null) return widget.ageGroup;
    try {
      final active = ref.read(activeChildProfileProvider);
      return active?.id == widget.childId ? active?.ageGroup : null;
    } catch (_) {
      // Preferences not loaded yet: unknown, and unknown fails closed.
      return null;
    }
  }

  Future<void> _start(String surface) async {
    final l10n = AppLocalizations.of(context);
    final navigator = Navigator.of(context);
    final ageGroup = _ageGroup;

    // «ركن الطفل» is not a server surface: its session opens on the first
    // thing in it the band allows, and the corner moves it along from there.
    // It needs a known band — the corner shows only what that band may see —
    // so an unknown one is refused here rather than guessed.
    final corner = surface == kChildCornerSurface;
    final String? opening = corner
        ? childCornerOpeningSurface(
            ageGroup,
            withGame: ref.read(childCornerGameEnabledProvider),
          )
        : surface;
    if (opening == null) {
      _refuse(l10n.childModeSurfaceNotAllowed);
      return;
    }

    // A known band that the policy does not allow this surface: say so now,
    // before a PIN is asked for. An unknown band (a preset from a screen that
    // could not read the profile) goes on and lets the server decide.
    if (ageGroup != null && !childSurfaceAllowed(ageGroup, opening)) {
      _refuse(l10n.childModeSurfaceNotAllowed);
      return;
    }

    // Listening with the screen dark is played from the parent's side: there
    // is no session to open and no door to walk through.
    if (surface == 'screen_off') {
      if (widget.surface != null) {
        await navigator.pushReplacement(AppRoutes.screenOffPicker());
      } else {
        await navigator.push(AppRoutes.screenOffPicker());
      }
      return;
    }

    setState(() => _phase = _Phase.waiting);
    final pin = await navigator.push<String>(AppRoutes.childModeLock<String>(
      childId: widget.childId,
      childName: widget.childName,
      surface: opening,
      verifyOnly: true,
    ));
    if (!mounted) return;
    if (pin == null) {
      // The parent backed out of the PIN.
      if (widget.surface != null) {
        navigator.pop();
      } else {
        setState(() => _phase = _Phase.choosing);
      }
      return;
    }

    setState(() => _phase = _Phase.opening);
    await Future.wait<void>([
      _openDoors(),
      Future<void>.delayed(HandoverGateScreen.opening),
    ]);
    if (!mounted) return;

    setState(() => _minting = true);
    final ok = await ref.read(childModeProvider.notifier).enter(
          childId: widget.childId,
          pin: pin,
          surface: opening,
          cornerBand: corner ? childSurfaceBand(ageGroup) : null,
        );
    if (!mounted) return;
    if (ok) {
      // The child surface is the root widget; everything above it — this
      // gate and the screen that opened it — has to go.
      navigator.popUntil((route) => route.isFirst);
      return;
    }
    final code = ref.read(childModeProvider).error;
    _refuse(localizedChildModeError(code, l10n),
        budget: code == kChildModeBudgetSpent);
  }

  Future<void> _openDoors() async {
    try {
      await _doors.forward().orCancel;
    } on TickerCanceled {
      // Disposed mid-swing: the caller checks `mounted`.
    }
  }

  void _refuse(String message, {bool budget = false}) {
    _doors.value = 1;
    setState(() {
      _phase = _Phase.refused;
      _minting = false;
      _refusal = message;
      _refusalIsBudget = budget;
    });
  }

  void _back() {
    if (widget.surface != null) {
      Navigator.of(context).pop();
      return;
    }
    _doors.value = 0;
    setState(() {
      _phase = _Phase.choosing;
      _refusal = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: _phase != _Phase.opening,
      child: _phase == _Phase.choosing ? _choosing(context) : _doorway(context),
    );
  }

  Widget _doorway(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final ink = theme.textTheme.headlineSmall?.copyWith(
      color: PaperCut.ivory,
      fontWeight: FontWeight.w800,
      height: 1.5,
    );

    final Widget reveal;
    if (_phase == _Phase.refused) {
      reveal = Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const PaperStar(size: 40),
            const SizedBox(height: 16),
            Semantics(
              liveRegion: true,
              child: Text(
                _refusal ?? '',
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium
                    ?.copyWith(color: PaperCut.ivory, height: 1.6),
              ),
            ),
            const SizedBox(height: 24),
            if (_refusalIsBudget) ...[
              TextButton(
                style: TextButton.styleFrom(foregroundColor: PaperCut.ivory),
                onPressed: () => Navigator.of(context)
                    .push(AppRoutes.offscreenActivities()),
                child: Text(l10n.offscreenOpen),
              ),
              const SizedBox(height: 8),
            ],
            FilledButton(
              onPressed: _back,
              style: FilledButton.styleFrom(
                backgroundColor: PaperCut.ivory,
                foregroundColor: PaperCut.shadowOnEmerald,
                minimumSize: const Size(160, 52),
              ),
              child: Text(l10n.back),
            ),
          ],
        ),
      );
    } else {
      reveal = Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const PaperStar(size: 48),
            const SizedBox(height: 20),
            Semantics(
              liveRegion: true,
              child: Text(
                l10n.handoverYourTurn(widget.childName),
                textAlign: TextAlign.center,
                style: ink,
              ),
            ),
            const SizedBox(height: 24),
            // Room kept for it either way, so the name does not jump when the
            // session starts opening.
            SizedBox.square(
              dimension: 24,
              child: _minting
                  ? const CircularProgressIndicator(
                      strokeWidth: 2.5,
                      color: PaperCut.ivory,
                    )
                  : null,
            ),
          ],
        ),
      );
    }

    return Scaffold(
      backgroundColor: PaperCut.emerald,
      body: HandoverDoors(
        progress: _doors,
        reduceMotion: reduceMotion(context),
        // Scrollable so a 360 dp screen at 200% text still fits the refusal
        // and its button.
        reveal: SafeArea(child: SingleChildScrollView(child: reveal)),
      ),
    );
  }

  Widget _choosing(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final c = context.colors;
    final ageGroup = _ageGroup;
    final withGame = ref.read(childCornerGameEnabledProvider);
    final offered = [
      // The corner first: one calm place with an ending, rather than a list.
      if (childCornerOffered(ageGroup, withGame: withGame)) kChildCornerSurface,
      ...handoverSurfacesFor(ageGroup),
    ];
    // The same two checks the corner makes: the band has a game, and the
    // games' questions are in the language the child reads the app in.
    final cornerHasGame = childCornerActivitiesFor(ageGroup, withGame: withGame)
            .contains('game') &&
        cornerGamesSpeak(contentLanguageFor(Localizations.localeOf(context)));

    return Scaffold(
      appBar: AppBar(title: Text(l10n.handoverTitle)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          children: [
            // The doors, closed: what is about to happen, shown before it does.
            ClipRRect(
              borderRadius: BorderRadius.circular(24),
              child: SizedBox(
                height: 132,
                child: HandoverDoors(
                  progress: const AlwaysStoppedAnimation(0),
                  reduceMotion: true,
                  reveal: const SizedBox.shrink(),
                ),
              ),
            ),
            const SizedBox(height: 20),
            Text(
              l10n.handoverChoose(widget.childName),
              textAlign: TextAlign.center,
              style: theme.textTheme.titleLarge
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 6),
            Text(
              offered.isEmpty ? l10n.handoverNoSurface : l10n.handoverHint,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: c.textSecondary, height: 1.6),
            ),
            const SizedBox(height: 16),
            if (offered.isEmpty)
              Center(
                child: TextButton(
                  onPressed: () => Navigator.of(context).push(
                    AppRoutes.offscreenActivities(
                        band: childSurfaceBand(ageGroup)),
                  ),
                  child: Text(l10n.offscreenOpen),
                ),
              )
            else
              for (final surface in offered)
                _SurfaceTile(
                  surface: surface,
                  cornerHasGame: cornerHasGame,
                  onTap: () => _start(surface),
                ),
          ],
        ),
      ),
    );
  }
}

class _SurfaceTile extends StatelessWidget {
  const _SurfaceTile({
    required this.surface,
    required this.onTap,
    this.cornerHasGame = false,
  });

  final String surface;
  final VoidCallback onTap;

  /// The corner's line names a game only when the band has one.
  final bool cornerHasGame;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final (icon, title, body) = switch (surface) {
      kChildCornerSurface => (
          Icons.auto_stories_outlined,
          l10n.childCornerTileTitle,
          cornerHasGame
              ? l10n.childCornerTileBody
              : l10n.childCornerTileBodyNoGame,
        ),
      'habit' => (
          Icons.checklist_rounded,
          l10n.habitChildModeTitle,
          l10n.handoverHabitBody,
        ),
      'mission' => (
          Icons.explore_outlined,
          l10n.missionOpenForChild,
          l10n.handoverMissionBody,
        ),
      'license' => (
          Icons.shield_outlined,
          l10n.licenseOpenForChild,
          l10n.handoverLicenseBody,
        ),
      _ => (
          Icons.nightlight_outlined,
          l10n.screenOffOpen,
          l10n.handoverScreenOffBody,
        ),
    };
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        key: ValueKey('handover_$surface'),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        leading: Icon(icon, color: c.primary),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(body),
        trailing: Icon(Icons.chevron_right, color: c.textSecondary),
        onTap: onTap,
      ),
    );
  }
}
