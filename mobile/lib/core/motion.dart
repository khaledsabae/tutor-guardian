/// Reduce-motion support (UX_UI_ROADMAP §5).
///
/// With the system "remove animations" setting on, Flutter already runs every
/// AnimationController at 5% of its duration, so one-shot entrances collapse
/// to a frame on their own. Loops are the problem: a pulse or shimmer that
/// repeats at 20× speed turns into rapid flicker, the opposite of what the
/// setting asks for. Every looping animation goes through here instead.
library;

import 'package:flutter/widgets.dart';

/// Whether the user asked the system for less motion.
bool reduceMotion(BuildContext context) =>
    MediaQuery.maybeDisableAnimationsOf(context) ?? false;

/// An `onPlay` for flutter_animate that loops only when motion is allowed.
/// With reduced motion the effect plays once and rests on its end state.
void Function(AnimationController) loopUnlessReduced(
  BuildContext context, {
  bool reverse = false,
  int? count,
}) {
  final reduce = reduceMotion(context);
  return (controller) {
    if (!reduce) controller.repeat(reverse: reverse, count: count);
  };
}

/// Start or stop a hand-driven looping controller to match the setting.
/// Call from `didChangeDependencies`, which also runs when it changes.
void syncLoop(
  BuildContext context,
  AnimationController controller, {
  bool reverse = false,
  double restValue = 0,
}) {
  if (reduceMotion(context)) {
    controller
      ..stop()
      ..value = restValue;
  } else if (!controller.isAnimating) {
    controller.repeat(reverse: reverse);
  }
}
