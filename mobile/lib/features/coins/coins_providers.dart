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

  /// Redeem coins against a covenant — the only thing they buy, and it is
  /// handed over off the screen by a parent. Returns true on success.
  Future<bool> spendOnCovenant(int amount) async {
    final ok = await CoinsService.instance.spendOnCovenant(amount);
    if (ok) state = await CoinsService.instance.read();
    return ok;
  }

  /// Earn coins (e.g. from bedtime routine, or a game). Silently capped at
  /// the daily ceiling — the caller is not told it hit the cap, because the
  /// child does not need a number telling them they have run out of reward.
  Future<void> earn(int amount) async {
    await CoinsService.instance.earn(amount);
    state = await CoinsService.instance.read();
  }

  Future<void> refresh() async => _load();
}

final coinsProvider =
    StateNotifierProvider<CoinsNotifier, CoinsState>((ref) => CoinsNotifier());

/// Cosmetic badges the user owns from before they could no longer be bought.
final ownedBadgesProvider = FutureProvider<Set<String>>((ref) async {
  ref.watch(coinsProvider);
  return CoinsService.instance.ownedBadges();
});
