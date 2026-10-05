/// Two screens that said what was not true.
///
/// * The family agreement said it was "available for ages 7–9 only" after the
///   13–15 clause bank shipped, and every line of its chrome was Arabic for
///   English readers too (the clauses themselves already came in the UI
///   language).
/// * The coins screen listed a story and exclusive badges under «استبدل
///   عملاتك». Coins buy one thing — the covenant; stories are free and badges
///   are earned by doing.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/agreement/agreement_screen.dart';
import 'package:almorabbi/features/coins/coins_screen.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart'
    show activeChildIdProvider;
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart';

class _NoBankClient extends TgClient {
  @override
  Future<Map<String, dynamic>?> fetchAgreement(int childId) async => null;

  @override
  Future<Map<String, dynamic>> fetchSuggestedClauses(int childId) async =>
      {'pairs': <Map<String, dynamic>>[]};
}

Future<void> _pump(WidgetTester tester, Widget home, Locale locale,
    {List<Override> overrides = const []}) async {
  await tester.pumpWidget(ProviderScope(
    overrides: overrides,
    child: MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: home,
    ),
  ));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('an age with no clause bank is told both bands that have one',
      (tester) async {
    final client = _NoBankClient();
    await _pump(tester, const AgreementScreen(), const Locale('ar'), overrides: [
      tgClientProvider.overrideWithValue(client),
      activeChildIdProvider.overrideWith((_) => 7),
    ]);
    expect(find.textContaining('٧–٩ و١٣–١٥'), findsOneWidget);
    expect(find.textContaining('فقط'), findsNothing);
  });

  testWidgets('English readers get the agreement screen in English',
      (tester) async {
    final client = _NoBankClient();
    await _pump(tester, const AgreementScreen(), const Locale('en'), overrides: [
      tgClientProvider.overrideWithValue(client),
      activeChildIdProvider.overrideWith((_) => 7),
    ]);
    expect(find.text('Family agreement'), findsOneWidget);
    expect(find.textContaining('ages 7–9 and 13–15'), findsOneWidget);
    expect(find.textContaining('الميثاق'), findsNothing);
  });

  testWidgets('with no child chosen, the screen says so (worded in build)',
      (tester) async {
    await _pump(tester, const AgreementScreen(), const Locale('en'), overrides: [
      tgClientProvider.overrideWithValue(_NoBankClient()),
    ]);
    expect(find.text('Choose a child first.'), findsOneWidget);
  });

  testWidgets('coins buy only the covenant; story and badges cost nothing',
      (tester) async {
    await _pump(tester, const CoinsScreen(), const Locale('ar'));
    final spend = find.text('اصرف عملاتك 🎁');
    final free = find.text('وفي التطبيق أيضًا — بلا عملات');
    await tester.scrollUntilVisible(spend, 200,
        scrollable: find.byType(Scrollable).first);
    expect(spend, findsOneWidget);
    await tester.scrollUntilVisible(free, 200,
        scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    expect(free, findsOneWidget);
    // The story and the badges sit under «بلا عملات», not under «اصرف».
    final freeY = tester.getTopLeft(free).dy;
    expect(tester.getTopLeft(find.text('قصة مخصصة لطفلك')).dy, greaterThan(freeY));
    expect(tester.getTopLeft(find.text('شارات حصرية')).dy, greaterThan(freeY));
    expect(tester.getTopLeft(find.text('عهد المكافآت الواقعية')).dy, lessThan(freeY));
    expect(find.text('شارات تُفتح بالإنجاز، لا بالعملات'), findsOneWidget);
    // Let the entrance animations' timers run out before the tree goes.
    await tester.pump(const Duration(seconds: 2));
  });
}
