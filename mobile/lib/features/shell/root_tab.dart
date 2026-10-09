/// Bottom-navigation tab indices.
///
/// Lives in its own file so both the shell and the screens that ask it to
/// switch tabs can import it without a cycle.
///
/// These are a hard contract with [IndexedStack]: a stale index does not fail
/// loudly, it either opens the wrong screen or runs off the end of the stack.
/// Both have already happened here — two "ask the assistant" buttons spent a
/// release opening the infant feed/sleep tracker because they were hard-coded
/// to `3`. Never write the number; use these.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

// A one-shot request to bring a tab to the front, from anywhere (phase 1:
// شكر على كل نتيجة متابعة). The shell owns the index as private state, so
// without this a modal sheet could seed the assistant with a question but
// had no way to actually take the parent there. Set it, and the shell
// switches and clears it.
final rootTabRequestProvider = StateProvider<int?>((ref) => null);

abstract final class RootTab {
  static const today = 0;
  static const learn = 1;
  static const assistant = 2;
  static const more = 3;

  /// Number of destinations in the shell. Keep in sync with [RootScaffold]'s
  /// IndexedStack children — asserted by the shell's widget test.
  static const count = 4;
}

/// A tab the shell should land on, set by code that runs *before* the shell
/// exists. Onboarding's deferred "ask the mentor" arms it: the sample
/// question is tapped during onboarding, and the parent lands on the
/// assistant tab — question already seeding the chat — once onboarding
/// completes and [RootScaffold] mounts. Null means "no opinion".
final pendingRootTabProvider = StateProvider<int?>((ref) => null);

/// Reads and clears any pending tab. Call once when the shell mounts (the
/// value may predate it) and again from a listener, so both orderings —
/// armed before or after the shell exists — land on the tab exactly once.
int? takePendingRootTab(WidgetRef ref) {
  final pending = ref.read(pendingRootTabProvider);
  if (pending == null) return null;
  ref.read(pendingRootTabProvider.notifier).state = null;
  return pending;
}

