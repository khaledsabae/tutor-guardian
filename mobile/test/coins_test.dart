/// The coin economy has one sink and two ceilings, and each of these tests
/// pins one of the things that used to be true and should not be again.
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:almorabbi/features/coins/coins_service.dart';
import 'package:almorabbi/features/coins/covenant_service.dart';

String _day(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('earning', () {
    test('a fresh ledger starts empty', () async {
      final state = await CoinsService.instance.read();
      expect(state.balance, 0);
      expect(state.earnableToday, CoinsService.dailyEarnCap);
    });

    test('earning stops at the daily ceiling', () async {
      // The four games used to write the balance key directly, outside every
      // rule in this class. Uncapped, a game is a coin mint.
      await CoinsService.instance.earn(50);
      await CoinsService.instance.earn(50);
      final state = await CoinsService.instance.read();
      expect(state.balance, CoinsService.dailyEarnCap);
      expect(state.earnableToday, 0);
    });

    test('the ceiling lifts the next day', () async {
      await CoinsService.instance.earn(CoinsService.dailyEarnCap);
      SharedPreferences.setMockInitialValues({
        'coins.balance': CoinsService.dailyEarnCap,
        'coins.earned_today': CoinsService.dailyEarnCap,
        'coins.earned_today_date': _day(DateTime.now().subtract(const Duration(days: 1))),
      });
      final balance = await CoinsService.instance.earn(10);
      expect(balance, CoinsService.dailyEarnCap + 10);
    });

    test('badges credit through the same capped path', () async {
      await CoinsService.instance.creditBadges(['a', 'b', 'c']);
      final state = await CoinsService.instance.read();
      expect(state.balance, lessThanOrEqualTo(CoinsService.dailyEarnCap));
    });

    test('a badge is only ever credited once', () async {
      await CoinsService.instance.creditBadges(['a']);
      final first = (await CoinsService.instance.read()).balance;
      await CoinsService.instance.creditBadges(['a']);
      expect((await CoinsService.instance.read()).balance, first);
    });
  });

  group('the one sink', () {
    test('coins are spent on a covenant and nothing else', () async {
      await CoinsService.instance.earn(50);
      expect(await CoinsService.instance.spendOnCovenant(30), isTrue);
      expect((await CoinsService.instance.read()).balance, 20);
    });

    test('spending more than the balance fails and changes nothing', () async {
      await CoinsService.instance.earn(10);
      expect(await CoinsService.instance.spendOnCovenant(40), isFalse);
      expect((await CoinsService.instance.read()).balance, 10);
    });

    test('stories cost nothing at all', () async {
      // The 50-coin story gate is gone: there is no story price to read.
      // ignore: unnecessary_type_check
      expect(CoinsService.dailyEarnCap is int, isTrue);
    });
  });

  group('the streak steps back, never to zero', () {
    test('consecutive days grow it', () async {
      SharedPreferences.setMockInitialValues({
        'coins.daily_streak': 5,
        'coins.last_claim_date': _day(DateTime.now().subtract(const Duration(days: 1))),
      });
      final state = await CoinsService.instance.claimDaily();
      expect(state.dailyStreak, 6);
    });

    test('a missed day is covered by a rest day', () async {
      SharedPreferences.setMockInitialValues({
        'coins.daily_streak': 10,
        'coins.last_claim_date': _day(DateTime.now().subtract(const Duration(days: 2))),
      });
      final state = await CoinsService.instance.claimDaily();
      expect(state.dailyStreak, 11);
      expect(state.restDaysLeft, CoinsService.restDaysPerMonth - 1);
    });

    test('past the rest days it decays rather than resetting', () async {
      SharedPreferences.setMockInitialValues({
        'coins.daily_streak': 20,
        'coins.last_claim_date': _day(DateTime.now().subtract(const Duration(days: 6))),
      });
      final state = await CoinsService.instance.claimDaily();
      // Five days missed, two forgiven, three charged.
      expect(state.dailyStreak, 17);
    });

    test('a long absence floors at one and never zero', () async {
      SharedPreferences.setMockInitialValues({
        'coins.daily_streak': 3,
        'coins.last_claim_date': _day(DateTime.now().subtract(const Duration(days: 300))),
      });
      final state = await CoinsService.instance.claimDaily();
      expect(state.dailyStreak, 1);
      expect(state.dailyStreak, isNot(0));
    });

    test('claiming twice in a day is a no-op', () async {
      final first = await CoinsService.instance.claimDaily();
      final second = await CoinsService.instance.claimDaily();
      expect(second.balance, first.balance);
      expect(second.claimedToday, isTrue);
    });

    test('the month count is what the UI shows instead of a streak', () async {
      final state = await CoinsService.instance.claimDaily();
      expect(state.activeDaysThisMonth, 1);
      expect(state.daysInThisMonth, greaterThanOrEqualTo(28));
    });
  });

  group('covenants', () {
    test('each child keeps their own rewards', () async {
      await CovenantService.instance.add(1, 'رحلة', 100);
      final one = await CovenantService.instance.load(1);
      final two = await CovenantService.instance.load(2);
      expect(one.where((c) => c.title == 'رحلة'), isNotEmpty);
      expect(two.where((c) => c.title == 'رحلة'), isEmpty);
    });

    test('the old shared list is adopted rather than dropped', () async {
      SharedPreferences.setMockInitialValues({
        'covenant.list':
            '[{"id":"old_1","title":"مكافأة قديمة","cost":40,"isRedeemed":false,"isDelivered":false,"redeemedAt":null}]',
      });
      final adopted = await CovenantService.instance.load(7);
      expect(adopted.single.title, 'مكافأة قديمة');
    });

    test('redeeming twice is refused', () async {
      await CovenantService.instance.add(1, 'مثلجات', 30);
      final id = (await CovenantService.instance.load(1)).last.id;
      expect(await CovenantService.instance.redeem(1, id), isTrue);
      expect(await CovenantService.instance.redeem(1, id), isFalse);
    });

    test('a reward redeemed and not delivered goes overdue', () async {
      final old = DateTime.now().subtract(const Duration(days: 9)).toIso8601String();
      SharedPreferences.setMockInitialValues({
        'covenant.list.1':
            '[{"id":"c1","title":"حديقة","cost":100,"isRedeemed":true,"isDelivered":false,"redeemedAt":"$old"}]',
      });
      final overdue = await CovenantService.instance.overdueDeliveries(1);
      expect(overdue, hasLength(1));
    });

    test('a delivered reward is never overdue', () async {
      final old = DateTime.now().subtract(const Duration(days: 30)).toIso8601String();
      SharedPreferences.setMockInitialValues({
        'covenant.list.1':
            '[{"id":"c1","title":"حديقة","cost":100,"isRedeemed":true,"isDelivered":true,"redeemedAt":"$old"}]',
      });
      expect(await CovenantService.instance.overdueDeliveries(1), isEmpty);
      expect(await CovenantService.instance.deliveredThisMonth(1), 0);
    });

    test('this month\'s deliveries are what a parent is shown', () async {
      final now = DateTime.now().toIso8601String();
      SharedPreferences.setMockInitialValues({
        'covenant.list.1':
            '[{"id":"c1","title":"حديقة","cost":100,"isRedeemed":true,"isDelivered":true,"redeemedAt":"$now"}]',
      });
      expect(await CovenantService.instance.deliveredThisMonth(1), 1);
    });
  });
}
