// §6.4 — PrideInviteCard: the referral ask fires only at pride moments
// (≥7-day streak), once per 7-day tier, and dismissal persists.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/referral/pride_invite_card.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

Widget _wrap(Widget child) => MaterialApp(
      locale: const Locale('ar'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('hidden below a 7-day streak', (tester) async {
    await tester.pumpWidget(_wrap(const PrideInviteCard(streakDays: 6)));
    await tester.pumpAndSettle();
    expect(find.text('ادعُ صديقًا'), findsNothing);
  });

  testWidgets('shows at 7 days with the sadaqa framing', (tester) async {
    await tester.pumpWidget(_wrap(const PrideInviteCard(streakDays: 7)));
    await tester.pumpAndSettle();
    expect(find.text('ادعُ صديقًا'), findsOneWidget);
    expect(find.textContaining('صدقة جارية'), findsOneWidget);
    expect(find.textContaining('7'), findsOneWidget);
  });

  testWidgets('dismiss persists — same tier stays hidden', (tester) async {
    await tester.pumpWidget(_wrap(const PrideInviteCard(streakDays: 7)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('لاحقًا'));
    await tester.pumpAndSettle();
    expect(find.text('ادعُ صديقًا'), findsNothing);

    // Rebuild fresh (new widget state, same prefs) at streak 10 — same
    // 7-day tier, must stay hidden.
    await tester.pumpWidget(_wrap(const SizedBox()));
    await tester.pumpWidget(_wrap(const PrideInviteCard(streakDays: 10)));
    await tester.pumpAndSettle();
    expect(find.text('ادعُ صديقًا'), findsNothing);
  });

  testWidgets('reappears at the next 7-day tier', (tester) async {
    SharedPreferences.setMockInitialValues({PrideInviteCard.prefsKey: 7});
    await tester.pumpWidget(_wrap(const PrideInviteCard(streakDays: 14)));
    await tester.pumpAndSettle();
    expect(find.text('ادعُ صديقًا'), findsOneWidget);
  });

  testWidgets('tiers are monotonic — a rebuilt streak stays quiet',
      (tester) async {
    // Acted at 14, streak broke, climbed back to 7: 7 ~/ 7 == 1 is not
    // greater than 14 ~/ 7 == 2, so the card stays hidden until 21.
    SharedPreferences.setMockInitialValues({PrideInviteCard.prefsKey: 14});
    await tester.pumpWidget(_wrap(const PrideInviteCard(streakDays: 7)));
    await tester.pumpAndSettle();
    expect(find.text('ادعُ صديقًا'), findsNothing);
  });
}
