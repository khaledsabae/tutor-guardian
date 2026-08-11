/// A counter of "something worthwhile just happened", read by the navigation
/// observer to tell a finished task apart from a dead end.
///
/// Lives in its own file because `analytics.dart` raises the signal and
/// `nav_observer.dart` consumes it, and importing either from the other would
/// be circular.
library;

/// Bumped whenever the user completes something on the current screen.
///
/// `dead_end` classified an exit purely on "did this screen push another
/// named route", which made a leaf screen indistinguishable from a trap:
/// reading a lesson to the end, checking in a habit, finishing a game and
/// backing out all scored the same as opening a screen and finding nothing.
/// That is how 2,129 users — 66% of everyone — got labelled lost.
///
/// The count is deliberately global rather than per-screen. The observer
/// samples it on enter and on exit and asks only whether it moved, which
/// keeps every call site to a single line and needs no screen awareness at
/// the point where the good thing happened.
class EngagementSignal {
  EngagementSignal._();

  static int _count = 0;

  /// Current value. Compare two reads to learn whether anything happened
  /// between them.
  static int get count => _count;

  /// The user finished something real.
  static void mark() => _count++;
}
