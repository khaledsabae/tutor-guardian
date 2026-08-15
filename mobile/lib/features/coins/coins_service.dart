/// Coins — a light, fully on-device reward currency.
///
/// Earned by: daily login (streak-aware), achievement badges, and small
/// in-app actions. Persisted in SharedPreferences (no backend, works offline).
///
/// The currency has exactly one sink: a covenant — a real reward a parent
/// hands over off the screen. It used to have three, and the other two were
/// the problem. Buying a story with coins made the reward for using the app
/// *more time in the app*, which is the loop this product exists to argue
/// against; buying cosmetic badges did the same in miniature. Both are gone,
/// and `spend` is private so that a fourth sink cannot be added by calling an
/// existing method — it has to come through [spendOnCovenant], which is a
/// name that has to be justified in review.
///
/// Two other behaviours changed for the same reason. Earning is capped per
/// day, so a game cannot be farmed into a coin pump. And the streak decays
/// instead of resetting: a broken streak that returns to zero is a punishment
/// the app hands a seven-year-old for a day their family was travelling.
library;

import 'package:shared_preferences/shared_preferences.dart';

class CoinsState {
  final int balance;
  final int dailyStreak;
  final bool claimedToday;
  final int lastClaimReward; // coins granted on the most recent claim

  /// Days the child showed up this calendar month, and how many that month
  /// could have held. The UI shows "24 of 31" rather than a streak that can
  /// break — a count that only goes up reads as an achievement, and a streak
  /// reads as something you are about to lose.
  final int activeDaysThisMonth;
  final int daysInThisMonth;

  /// Rest days left this month. Two days off do not cost the streak.
  final int restDaysLeft;

  /// Coins still earnable today. Zero is not an error state — it means the
  /// day's earning is done, which is the point.
  final int earnableToday;

  const CoinsState({
    required this.balance,
    required this.dailyStreak,
    required this.claimedToday,
    this.lastClaimReward = 0,
    this.activeDaysThisMonth = 0,
    this.daysInThisMonth = 30,
    this.restDaysLeft = CoinsService.restDaysPerMonth,
    this.earnableToday = CoinsService.dailyEarnCap,
  });
}

class CoinsService {
  CoinsService._();
  static final CoinsService instance = CoinsService._();

  static const _kBalance = 'coins.balance';
  static const _kLastClaim = 'coins.last_claim_date'; // yyyy-MM-dd
  static const _kStreak = 'coins.daily_streak';
  static const _kCreditedBadges = 'coins.credited_badges';
  static const _kOwnedBadges = 'coins.owned_exclusive_badges';
  static const _kRestDaysUsed = 'coins.rest_days_used';
  static const _kRestMonth = 'coins.rest_days_month'; // yyyy-MM
  static const _kActiveDays = 'coins.active_days_this_month';
  static const _kActiveMonth = 'coins.active_days_month'; // yyyy-MM
  static const _kEarnedToday = 'coins.earned_today';
  static const _kEarnedDate = 'coins.earned_today_date';

  static const dailyBase = 10;
  static const streakBonusCap = 20; // +2/day up to +20
  static const badgeReward = 50;
  static const referralReward = 100; // Doubled temporarily for growth push (was 50)

  /// Ceiling on coins earnable in one day from all sources except the daily
  /// login claim. Without it the four games are an unbounded mint, and the
  /// currency stops meaning anything a parent has to honour.
  static const dailyEarnCap = 60;

  /// Days per month that may be missed without the streak stepping back.
  static const restDaysPerMonth = 2;

  String _fmt(DateTime n) =>
      '${n.year}-${n.month.toString().padLeft(2, '0')}-${n.day.toString().padLeft(2, '0')}';

  String _today() => _fmt(DateTime.now());

  String _monthKey() {
    final n = DateTime.now();
    return '${n.year}-${n.month.toString().padLeft(2, '0')}';
  }

  int _daysInThisMonth() {
    final n = DateTime.now();
    return DateTime(n.year, n.month + 1, 0).day;
  }

  DateTime? _parse(String? value) {
    if (value == null) return null;
    return DateTime.tryParse(value);
  }

  /// Whole days between the last claim and today. Null when there is no last
  /// claim (a first-ever claim is not a gap).
  int? _daysSince(String? lastClaim) {
    final last = _parse(lastClaim);
    if (last == null) return null;
    final now = DateTime.now();
    final a = DateTime(last.year, last.month, last.day);
    final b = DateTime(now.year, now.month, now.day);
    return b.difference(a).inDays;
  }

  Future<int> _restDaysUsed(SharedPreferences p) async {
    if (p.getString(_kRestMonth) != _monthKey()) {
      await p.setString(_kRestMonth, _monthKey());
      await p.setInt(_kRestDaysUsed, 0);
      return 0;
    }
    return p.getInt(_kRestDaysUsed) ?? 0;
  }

  Future<int> _activeDays(SharedPreferences p) async {
    if (p.getString(_kActiveMonth) != _monthKey()) {
      await p.setString(_kActiveMonth, _monthKey());
      await p.setInt(_kActiveDays, 0);
      return 0;
    }
    return p.getInt(_kActiveDays) ?? 0;
  }

  Future<int> _earnedToday(SharedPreferences p) async {
    if (p.getString(_kEarnedDate) != _today()) {
      await p.setString(_kEarnedDate, _today());
      await p.setInt(_kEarnedToday, 0);
      return 0;
    }
    return p.getInt(_kEarnedToday) ?? 0;
  }

  Future<CoinsState> _snapshot(SharedPreferences p, {int lastClaimReward = 0}) async {
    return CoinsState(
      balance: p.getInt(_kBalance) ?? 0,
      dailyStreak: p.getInt(_kStreak) ?? 0,
      claimedToday: p.getString(_kLastClaim) == _today(),
      lastClaimReward: lastClaimReward,
      activeDaysThisMonth: await _activeDays(p),
      daysInThisMonth: _daysInThisMonth(),
      restDaysLeft: (restDaysPerMonth - await _restDaysUsed(p)).clamp(0, restDaysPerMonth),
      earnableToday: (dailyEarnCap - await _earnedToday(p)).clamp(0, dailyEarnCap),
    );
  }

  Future<CoinsState> read() async {
    return _snapshot(await SharedPreferences.getInstance());
  }

  /// Claim the daily login reward exactly once per calendar day.
  ///
  /// A missed day is spent from the month's two rest days if any remain. When
  /// they are gone the streak steps back by the days missed rather than
  /// collapsing — it can reach 1, never 0. Coming back after a fortnight away
  /// should feel like resuming, not like starting over.
  Future<CoinsState> claimDaily() async {
    final p = await SharedPreferences.getInstance();
    final last = p.getString(_kLastClaim);
    final today = _today();
    if (last == today) {
      return _snapshot(p); // already claimed
    }

    final prevStreak = p.getInt(_kStreak) ?? 0;
    final gap = _daysSince(last);
    int streak;
    if (gap == null) {
      streak = 1; // first ever claim
    } else if (gap <= 1) {
      streak = prevStreak + 1;
    } else {
      final missed = gap - 1;
      final used = await _restDaysUsed(p);
      final coverable = (restDaysPerMonth - used).clamp(0, restDaysPerMonth);
      if (missed <= coverable) {
        await p.setInt(_kRestDaysUsed, used + missed);
        streak = prevStreak + 1;
      } else {
        final uncovered = missed - coverable;
        if (coverable > 0) await p.setInt(_kRestDaysUsed, used + coverable);
        streak = (prevStreak - uncovered).clamp(1, 1 << 30);
      }
    }

    final bonus = ((streak - 1) * 2).clamp(0, streakBonusCap);
    final reward = dailyBase + bonus;

    await p.setInt(_kBalance, (p.getInt(_kBalance) ?? 0) + reward);
    await p.setInt(_kStreak, streak);
    await p.setString(_kLastClaim, today);
    await p.setInt(_kActiveDays, await _activeDays(p) + 1);

    return _snapshot(p, lastClaimReward: reward);
  }

  /// Credit coins for any newly-earned badges (idempotent — each badge id
  /// is rewarded once, ever). Returns the new balance.
  ///
  /// Badges are unlocked by doing something, never bought. That is the whole
  /// distinction: a badge you earned is a record, a badge you bought is a
  /// purchase, and only one of them means anything a month later.
  Future<int> creditBadges(Iterable<String> earnedBadgeIds) async {
    final p = await SharedPreferences.getInstance();
    final credited = (p.getStringList(_kCreditedBadges) ?? <String>[]).toSet();
    final fresh = earnedBadgeIds.where((id) => !credited.contains(id)).toList();
    if (fresh.isEmpty) return p.getInt(_kBalance) ?? 0;
    credited.addAll(fresh);
    await p.setStringList(_kCreditedBadges, credited.toList());
    return earn(badgeReward * fresh.length);
  }

  /// The one sink. Deducts [amount] for a covenant the parent has agreed to
  /// hand over in the real world. Returns true when the balance covered it.
  Future<bool> spendOnCovenant(int amount) => _spend(amount);

  Future<bool> _spend(int amount) async {
    final p = await SharedPreferences.getInstance();
    final balance = p.getInt(_kBalance) ?? 0;
    if (amount <= 0 || balance < amount) return false;
    await p.setInt(_kBalance, balance - amount);
    return true;
  }

  /// Cosmetic badges the user owns.
  ///
  /// Nothing writes to this any more — buying them is gone. It is still read
  /// so that anyone who bought one before keeps it; deleting their purchase
  /// to make a point about extrinsic motivation would be its own kind of rude.
  Future<Set<String>> ownedBadges() async {
    final p = await SharedPreferences.getInstance();
    return (p.getStringList(_kOwnedBadges) ?? const <String>[]).toSet();
  }

  /// Add coins, up to the daily ceiling. Returns the new balance.
  ///
  /// Everything that credits coins goes through here — including the games,
  /// which used to write the balance key directly and so were outside every
  /// limit this class imposes.
  Future<int> earn(int amount) async {
    final p = await SharedPreferences.getInstance();
    if (amount <= 0) return p.getInt(_kBalance) ?? 0;
    final earned = await _earnedToday(p);
    final room = (dailyEarnCap - earned).clamp(0, dailyEarnCap);
    final granted = amount < room ? amount : room;
    if (granted <= 0) return p.getInt(_kBalance) ?? 0;
    await p.setInt(_kEarnedToday, earned + granted);
    final balance = (p.getInt(_kBalance) ?? 0) + granted;
    await p.setInt(_kBalance, balance);
    return balance;
  }
}
