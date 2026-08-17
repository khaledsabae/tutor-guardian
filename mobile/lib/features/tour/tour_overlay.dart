/// The spotlight veil itself.
///
/// Lives in the root [Overlay] rather than inside `RootScaffold.body`, because
/// four of the five stops are nav-bar destinations and `body` cannot paint
/// over `bottomNavigationBar`.
///
/// RTL rule: every rectangle here comes from `RenderBox.localToGlobal`, and
/// the caption card is placed with [PositionedDirectional]. There is not one
/// hard-coded `left:`/`right:` in this file — mirroring is already baked into
/// the geometry the framework handed us.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/analytics.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/ui/bouncy_button.dart';
import '../../widgets/ui/noor_mascot.dart';
import '../onboarding/providers/onboarding_providers.dart';
import 'tour_controller.dart';
import 'tour_step.dart';

/// Gap between the cut-out and the caption card.
const _gap = 14.0;

/// Lets `RootScaffold` notice it is the top route again. The settings replay
/// row rewinds the stored version while a modal route covers the nav bar, so
/// the tour has to wait for that route to pop before it has anything to point
/// at. Registered in `MaterialApp.navigatorObservers`.
final tourRouteObserver = RouteObserver<ModalRoute<void>>();

/// Insert the tour into the root overlay and start it at step 0.
void showTour(BuildContext context, WidgetRef ref, List<TourStep> steps) {
  final overlay = Overlay.maybeOf(context, rootOverlay: true);
  if (overlay == null || steps.isEmpty) return;

  late final OverlayEntry entry;
  var removed = false;
  entry = OverlayEntry(
    builder: (_) => _TourBody(
      steps: steps,
      onClose: () {
        if (removed) return;
        removed = true;
        entry.remove();
      },
    ),
  );
  ref.read(tourControllerProvider.notifier).start(steps.length);
  overlay.insert(entry);
}

class _TourBody extends ConsumerStatefulWidget {
  const _TourBody({required this.steps, required this.onClose});

  final List<TourStep> steps;
  final VoidCallback onClose;

  @override
  ConsumerState<_TourBody> createState() => _TourBodyState();
}

class _TourBodyState extends ConsumerState<_TourBody> {
  /// Set while we are waiting a frame for a target to finish layout, so we
  /// schedule at most one retry per frame.
  bool _retrying = false;

  /// The target's rect in global coordinates, or null if it is not laid out
  /// yet. This is the ONLY source of position in the whole overlay.
  Rect? _rectOf(GlobalKey key) {
    final ctx = key.currentContext;
    if (ctx == null) return null;
    final box = ctx.findRenderObject() as RenderBox?;
    if (box == null || !box.attached || !box.hasSize) return null;
    return box.localToGlobal(Offset.zero) & box.size;
  }

  void _retryNextFrame() {
    if (_retrying) return;
    _retrying = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _retrying = false;
      if (mounted) setState(() {});
    });
  }

  /// Deliberately synchronous in its use of [ref]: the callers remove the
  /// overlay entry immediately afterwards, which disposes this state, and
  /// touching `ref` after that throws. SharedPreferences updates its in-memory
  /// cache before the platform write settles, so invalidating here already
  /// reads the new value.
  void _finish() {
    final storage = ref.read(onboardingStorageProvider);
    unawaited(storage.markTourSeen(kTourVersion));
    ref.invalidate(tourVersionProvider);
  }

  void _next() {
    final state = ref.read(tourControllerProvider);
    if (!state.active) return;
    unawaited(Analytics.tourStep(state.index, 'next'));
    final ended = ref.read(tourControllerProvider.notifier).next();
    if (!ended) return;
    unawaited(Analytics.tourCompleted());
    _finish();
    widget.onClose();
  }

  void _skip() {
    final state = ref.read(tourControllerProvider);
    if (!state.active) return;
    unawaited(Analytics.tourStep(state.index, 'skip'));
    unawaited(Analytics.tourSkipped(state.index));
    ref.read(tourControllerProvider.notifier).stop();
    _finish();
    widget.onClose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tourControllerProvider);
    final step = _currentStep(state);
    if (step == null) return const SizedBox.shrink();

    final rect = _rectOf(step.key);
    if (rect == null) {
      _retryNextFrame();
      return const SizedBox.shrink();
    }

    final screen = MediaQuery.sizeOf(context);
    final hole = RRect.fromRectAndRadius(
      rect.inflate(6),
      const Radius.circular(Dt.rCard),
    );
    // Target in the lower half → card sits above it, and vice versa, so the
    // card never lands off-screen or on top of what it is describing.
    final placeBelow = rect.center.dy < screen.height / 2;

    return Semantics(
      container: true,
      child: Stack(
        children: [
          _veil(hole),
          // Only `start`/`end` — never `left`/`right`.
          PositionedDirectional(
            start: Dt.pad,
            end: Dt.pad,
            top: placeBelow ? hole.bottom + _gap : null,
            bottom: placeBelow ? null : screen.height - hole.top + _gap,
            child: _TourCard(
              // Keyed by step so each spotlight re-plays the entrance fade
              // instead of the card silently swapping its text.
              key: ValueKey(state.index),
              step: step,
              progress: (state.index + 1) / state.total,
              isLast: state.isLast,
              onNext: _next,
              onSkip: _skip,
            ),
          ),
        ],
      ),
    );
  }

  /// The scrim. Tapping anywhere on it advances, so the whole screen is a
  /// "next" target — the veil is never a dead end.
  Widget _veil(RRect hole) {
    return Positioned.fill(
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: _next,
        child: CustomPaint(painter: _VeilPainter(hole)),
      ),
    );
  }

  /// The current step, or null when there is nothing to show.
  TourStep? _currentStep(TourState state) =>
      !state.active || state.index >= widget.steps.length
          ? null
          : widget.steps[state.index];
}

/// Full-screen scrim with the target punched out via [PathFillType.evenOdd].
class _VeilPainter extends CustomPainter {
  const _VeilPainter(this.hole);

  final RRect hole;

  @override
  void paint(Canvas canvas, Size size) {
    final path = Path()
      ..fillType = PathFillType.evenOdd
      ..addRect(Offset.zero & size)
      ..addRRect(hole);
    canvas.drawPath(path, Paint()..color = Colors.black54);
  }

  @override
  bool shouldRepaint(_VeilPainter old) => old.hole != hole;
}

class _TourCard extends StatelessWidget {
  const _TourCard({
    super.key,
    required this.step,
    required this.progress,
    required this.isLast,
    required this.onNext,
    required this.onSkip,
  });

  final TourStep step;

  /// 0..1 — how far through the tour this step is.
  final double progress;
  final bool isLast;
  final VoidCallback onNext;
  final VoidCallback onSkip;

  /// Step meter. `AlignmentDirectional` keeps it filling from the
  /// reading-start edge in both directions.
  Widget _meter() {
    return ClipRRect(
      borderRadius: BorderRadius.circular(Dt.rChip),
      child: Container(
        height: 5,
        color: Dt.track,
        child: FractionallySizedBox(
          alignment: AlignmentDirectional.centerStart,
          widthFactor: progress.clamp(0.0, 1.0),
          child: DecoratedBox(
            decoration: BoxDecoration(gradient: Dt.primaryGradient),
          ),
        ),
      ),
    );
  }

  Widget _copy(AppLocalizations l10n) {
    final title = step.title?.call(l10n);
    return Row(
      children: [
        const NoorMascot(size: 44),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (title != null)
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    color: Dt.ink,
                  ),
                ),
              const SizedBox(height: 4),
              Text(
                step.caption(l10n),
                style: TextStyle(
                  fontSize: 14,
                  height: 1.4,
                  color: Dt.inkSoft,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _actions(AppLocalizations l10n) {
    return Row(
      children: [
        // Skip stays a quiet text target: a second BouncyButton here would
        // give the exit the same weight as the thing we want people to do.
        BouncyTap(
          onTap: onSkip,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
            child: Text(
              l10n.tourSkip,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: Dt.inkSoft,
              ),
            ),
          ),
        ),
        const Spacer(),
        BouncyButton(
          label: isLast ? l10n.tourDone : l10n.tourNext,
          expanded: false,
          onTap: onNext,
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Material(
      color: Colors.transparent,
      child: Container(
        padding: const EdgeInsets.all(Dt.pad),
        decoration: BoxDecoration(
          color: Dt.surface,
          borderRadius: BorderRadius.circular(Dt.rSheet),
          boxShadow: Dt.softShadow(Dt.primaryDeep, alpha: .3),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _meter(),
            const SizedBox(height: Dt.pad),
            _copy(l10n),
            const SizedBox(height: Dt.pad),
            _actions(l10n),
          ],
        ),
      ).animate().fadeIn(duration: Dt.base).slideY(begin: .06, end: 0),
    );
  }
}
