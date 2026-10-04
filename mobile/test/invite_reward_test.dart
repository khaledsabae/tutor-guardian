/// «أجرك الجاري» — the invite screen says only what is true.
///
/// The screen leads with how many families the parent's sharing reached, and
/// keeps the coins to one line. That line used to promise the server's
/// `reward_coins` (100 «لك ولصديقك») — a number this device never paid: the
/// client credits one badge reward each side, under the daily coin cap.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/coins/coins_service.dart';
import 'package:almorabbi/features/referral/invite_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart';

class _ReferralClient extends TgClient {
  @override
  Future<Map<String, dynamic>> getReferral() async => {
        'code': 'ABC234',
        'invited_count': 3,
        'reward_coins': 100, // the server's figure — never credited as such
        'share_url': 'https://play.google.com/store/apps/details?id=x',
      };

  @override
  Future<Map<String, dynamic>> getCommunityStats() async =>
      throw const TgApiError(503, 'offline');
}

void main() {
  testWidgets('the coin line shows what this device actually credits',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final client = _ReferralClient();
    TgClient.shared = client;
    addTearDown(() => TgClient.shared = null);

    await tester.pumpWidget(ProviderScope(
      overrides: [tgClientProvider.overrideWithValue(client)],
      child: const MaterialApp(
        locale: Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: InviteScreen(),
      ),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('وصل المربّي إلى 3 أسر بسببك'), findsOneWidget);
    final coins = find.textContaining('عملة لك');
    await tester.scrollUntilVisible(coins, 200,
        scrollable: find.byType(Scrollable).first);
    final line = tester.widget<Text>(coins).data!;
    expect(CoinsService.badgeReward, 50);
    expect(line, contains('${CoinsService.badgeReward} عملة لك'));
    expect(line, isNot(contains('100')));
    expect(line, contains('حدّ العملات اليومي'));
  });
}
