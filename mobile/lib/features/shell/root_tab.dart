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

abstract final class RootTab {
  static const today = 0;
  static const learn = 1;
  static const assistant = 2;
  static const more = 3;

  /// Number of destinations in the shell. Keep in sync with [RootScaffold]'s
  /// IndexedStack children — asserted by the shell's widget test.
  static const count = 4;
}
