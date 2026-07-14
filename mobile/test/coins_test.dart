import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/coins/coins_providers.dart';
import 'package:almorabbi/features/coins/coins_service.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({
      'coins.balance': 10,
    });
  });

  test('CoinsService.earn adds coins to balance', () async {
    final balance1 = await CoinsService.instance.earn(5);
    expect(balance1, 15);

    final state = await CoinsService.instance.read();
    expect(state.balance, 15);

    final balance2 = await CoinsService.instance.earn(10);
    expect(balance2, 25);
  });

  test('CoinsNotifier.earn updates riverpod state', () async {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    // Initial load
    await container.read(coinsProvider.notifier).refresh();
    expect(container.read(coinsProvider).balance, 10);

    // Earn coins via riverpod
    await container.read(coinsProvider.notifier).earn(15);
    expect(container.read(coinsProvider).balance, 25);

    // Verify service has the updated balance
    final state = await CoinsService.instance.read();
    expect(state.balance, 25);
  });
}
