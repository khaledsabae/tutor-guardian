/// Coins — a light, fully on-device reward currency.
///
/// Earned by: daily login (streak-aware) + each achievement badge unlocked.
/// Persisted in SharedPreferences (no backend, works offline). A `spend()`
/// path exists for future redeemables; nothing consumes coins yet, so the
/// store screen presents balance + how-to-earn rather than fake purchases.
library;

import 'package:shared_preferences/shared_preferences.dart';

class CoinsState {
  final int balance;
  final int dailyStreak;
  final bool claimedToday;
  final int lastClaimReward; // coins granted on the most recent claim

  const CoinsState({
    required this.balance,
    required this.dailyStreak,
    required this.claimedToday,
    this.lastClaimReward = 0,
  });
}

class CoinsService {
  CoinsService._();
  static final CoinsService instance = CoinsService._();

  static const _kBalance = 'coins.balance';
  static const _kLastClaim = 'coins.last_claim_date'; // yyyy-MM-dd
  static const _kStreak = 'coins.daily_streak';
  static const _kCreditedBadges = 'coins.credited_badges';

  static const dailyBase = 10;
  static const streakBonusCap = 20; // +2/day up to +20
  static const badgeReward = 50;

  String _today() {
    final n = DateTime.now();
    return '${n.year}-${n.month.toString().padLeft(2, '0')}-${n.day.toString().padLeft(2, '0')}';
  }

  String _yesterday() {
    final n = DateTime.now().subtract(const Duration(days: 1));
    return '${n.year}-${n.month.toString().padLeft(2, '0')}-${n.day.toString().padLeft(2, '0')}';
  }

  Future<CoinsState> read() async {
    final p = await SharedPreferences.getInstance();
    return CoinsState(
      balance: p.getInt(_kBalance) ?? 0,
      dailyStreak: p.getInt(_kStreak) ?? 0,
      claimedToday: p.getString(_kLastClaim) == _today(),
    );
  }

  /// Claim the daily login reward exactly once per calendar day.
  /// Consecutive days grow the streak (and the bonus); a missed day resets it.
  Future<CoinsState> claimDaily() async {
    final p = await SharedPreferences.getInstance();
    final last = p.getString(_kLastClaim);
    final today = _today();
    if (last == today) {
      return read(); // already claimed
    }
    final prevStreak = p.getInt(_kStreak) ?? 0;
    final streak = (last == _yesterday()) ? prevStreak + 1 : 1;
    final bonus = ((streak - 1) * 2).clamp(0, streakBonusCap);
    final reward = dailyBase + bonus;
    final balance = (p.getInt(_kBalance) ?? 0) + reward;

    await p.setInt(_kBalance, balance);
    await p.setInt(_kStreak, streak);
    await p.setString(_kLastClaim, today);
    return CoinsState(
      balance: balance,
      dailyStreak: streak,
      claimedToday: true,
      lastClaimReward: reward,
    );
  }

  /// Credit coins for any newly-earned badges (idempotent — each badge id
  /// is rewarded once, ever). Returns the new balance.
  Future<int> creditBadges(Iterable<String> earnedBadgeIds) async {
    final p = await SharedPreferences.getInstance();
    final credited = (p.getStringList(_kCreditedBadges) ?? <String>[]).toSet();
    var balance = p.getInt(_kBalance) ?? 0;
    var changed = false;
    for (final id in earnedBadgeIds) {
      if (!credited.contains(id)) {
        credited.add(id);
        balance += badgeReward;
        changed = true;
      }
    }
    if (changed) {
      await p.setInt(_kBalance, balance);
      await p.setStringList(_kCreditedBadges, credited.toList());
    }
    return balance;
  }

  /// Deduct coins for a future redeemable. Returns true on success.
  Future<bool> spend(int amount) async {
    final p = await SharedPreferences.getInstance();
    final balance = p.getInt(_kBalance) ?? 0;
    if (amount <= 0 || balance < amount) return false;
    await p.setInt(_kBalance, balance - amount);
    return true;
  }
}
