/// What shipped, told to the people who already had the app.
///
/// Why this exists rather than a push: the app's own numbers are 37,393 FCM
/// notifications to 1,567 users, 2.5% opened and 68% dismissed. A broadcast
/// asking people to do what Play already does for them spends that channel —
/// and the same channel carries the replies to their feedback. A card on the
/// screen they already opened costs nothing and reaches the people who are
/// actually here.
///
/// Two rules it must not break:
///
///  * **A fresh install never sees it.** "What's new" to someone who installed
///    ten seconds ago is a list of things they have no "old" to compare
///    against. The install/upgrade distinction is made by asking whether
///    onboarding was already completed — see [WhatsNewStore.shouldShow].
///  * **It appears once.** Dismissal is recorded against the build number, so
///    it does not come back on the next launch, and it does come back after the
///    next update.
library;

import 'package:shared_preferences/shared_preferences.dart';

import '../../onboarding/data/onboarding_storage.dart';

/// Builds whose notes are worth showing, newest first.
///
/// A build not listed here shows nothing at all — which is the right default
/// for a release with nothing a parent would notice. Keeping the list explicit
/// means a bugfix release does not interrupt anyone to say "we fixed something
/// you never saw".
const List<int> kWhatsNewBuilds = <int>[102];

/// The newest build with notes, or `null` when the list is empty.
int? get latestNotedBuild =>
    kWhatsNewBuilds.isEmpty ? null : kWhatsNewBuilds.first;

class WhatsNewStore {
  WhatsNewStore(this._prefs);

  /// The build whose card was last dismissed.
  static const String kLastSeenBuild = 'tg.whats_new.last_seen_build';

  final SharedPreferences _prefs;

  int? get lastSeenBuild => _prefs.getInt(kLastSeenBuild);

  Future<void> markSeen(int build) => _prefs.setInt(kLastSeenBuild, build);

  /// Whether to show the card for [currentBuild].
  ///
  /// [onboardingCompleted] is what separates an upgrade from a first install.
  /// It is read rather than inferred from a null [lastSeenBuild], because on
  /// the first release carrying this feature *every* device has a null value —
  /// an existing user of two months and someone who installed a minute ago look
  /// identical otherwise, and only one of them has anything new.
  bool shouldShow({
    required int currentBuild,
    required bool onboardingCompleted,
  }) {
    if (!onboardingCompleted) return false;
    if (!kWhatsNewBuilds.contains(currentBuild)) return false;
    final seen = lastSeenBuild;
    // `>=` not `==`: a user who somehow lands on an older build than the one
    // they dismissed should not be shown its notes again.
    if (seen != null && seen >= currentBuild) return false;
    return true;
  }

  /// Records the build without showing anything.
  ///
  /// Must run at startup, before onboarding completes — that window is the
  /// only place a first install is distinguishable from an upgrade. Called
  /// from the card instead, it could never fire: the card lives on HomeScreen,
  /// which a new user reaches only once onboarding is already marked complete.
  Future<void> seedForFreshInstall(int currentBuild) async {
    if (lastSeenBuild == null) await markSeen(currentBuild);
  }
}

/// Startup hook: silence the card for a device that has never onboarded.
///
/// A no-op for anyone who has onboarded — which is every upgrading user, and
/// is why the card appears for them on the very next launch after an update.
Future<void> seedWhatsNewForFreshInstall(
  SharedPreferences prefs,
  int currentBuild,
) async {
  if (onboardingCompletedFrom(prefs)) return;
  await WhatsNewStore(prefs).seedForFreshInstall(currentBuild);
}

/// Reads the onboarding flag the show/hide decision depends on.
bool onboardingCompletedFrom(SharedPreferences prefs) =>
    prefs.getBool(OnboardingStorage.keyOnboardingCompleted) ?? false;
