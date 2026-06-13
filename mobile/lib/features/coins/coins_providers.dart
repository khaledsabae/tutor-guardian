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

  Future<void> refresh() async => _load();
}

final coinsProvider =
    StateNotifierProvider<CoinsNotifier, CoinsState>((ref) => CoinsNotifier());
