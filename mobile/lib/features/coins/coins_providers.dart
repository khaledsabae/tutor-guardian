/// Riverpod wiring for the on-device coins ledger.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'coins_service.dart';

class CoinsNotifier extends StateNotifier<CoinsState> {
  CoinsNotifier()
      : super(const CoinsState(balance: 0, dailyStreak: 0, claimedToday: false)) {
    _load();
  }

  Future<void> _load() async {
    state = await CoinsService.instance.read();
  }

  /// Claim today's login reward (no-op if already claimed). Returns the
  /// coins granted this call so the UI can celebrate.
  Future<int> claimDaily() async {
    final next = await CoinsService.instance.claimDaily();
    state = next;
    return next.lastClaimReward;
  }

  /// Credit any newly-unlocked badges (idempotent).
  Future<void> creditBadges(Iterable<String> earnedBadgeIds) async {
    await CoinsService.instance.creditBadges(earnedBadgeIds);
    state = await CoinsService.instance.read();
  }

  /// Spend coins (e.g. to generate a story). Returns true on success.
  Future<bool> spend(int amount) async {
    final ok = await CoinsService.instance.spend(amount);
    if (ok) state = await CoinsService.instance.read();
    return ok;
  }

  /// Buy an exclusive cosmetic badge. Returns true if purchased.
  Future<bool> buyBadge(String badgeId, int cost) async {
    final ok = await CoinsService.instance.buyBadge(badgeId, cost);
    if (ok) state = await CoinsService.instance.read();
    return ok;
  }

  Future<void> refresh() async => _load();
}

final coinsProvider =
    StateNotifierProvider<CoinsNotifier, CoinsState>((ref) => CoinsNotifier());

/// The set of exclusive badge ids the user has purchased.
final ownedBadgesProvider = FutureProvider<Set<String>>((ref) async {
  // re-reads whenever the balance changes (a purchase mutates both)
  ref.watch(coinsProvider);
  return CoinsService.instance.ownedBadges();
});
