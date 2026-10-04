/// Two layout promises on screens this branch touched, checked as numbers:
///
///  * «المزيد» tiles grow with the text. They sat in a GridView with a fixed
///    childAspectRatio, which fixes every tile's height — at 200% a two-line
///    label was clipped to its first line.
///  * The journey card's "open" chevron points forward in Arabic.
///    Icons.chevron_left mirrors itself under RTL, so it pointed back at the
///    screen edge; DirectionalChevron picks the glyph explicitly.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/hub/data/hub_catalog.dart';
import 'package:almorabbi/features/hub/widgets/hub_group_card.dart';
import 'package:almorabbi/features/journey/widgets/child_journey_card.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/widgets/ui/directional_chevron.dart';

Widget _app(Widget child, {double textScale = 1.0, Locale locale = const Locale('en')}) =>
    MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, c) => MediaQuery(
        data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(textScale)),
        child: c!,
      ),
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

void main() {
  testWidgets('hub tiles grow with 200% text instead of clipping', (tester) async {
    tester.view.physicalSize = const Size(960, 2400);
    tester.view.devicePixelRatio = 3.0; // 320dp wide
    addTearDown(tester.view.reset);
    final group = kHubGroups.firstWhere((g) => g.id == 'help');
    final label = lookupAppLocalizations(const Locale('en')).feedbackTitle;

    Future<double> tileHeight(double scale) async {
      await tester.pumpWidget(
          _app(HubGroupCard(group: group, ageGroup: '7-9'), textScale: scale));
      await tester.pump();
      expect(tester.takeException(), isNull);
      final tile = find.ancestor(of: find.text(label), matching: find.byType(Material)).first;
      return tester.getSize(tile).height;
    }

    final normal = await tileHeight(1.0);
    final large = await tileHeight(2.0);
    expect(large, greaterThan(normal * 1.5));
    // The label's own box fits inside its tile — nothing cut off.
    final text = tester.getRect(find.text(label));
    final tile = tester.getRect(
        find.ancestor(of: find.text(label), matching: find.byType(Material)).first);
    expect(text.bottom, lessThanOrEqualTo(tile.bottom));
  });

  testWidgets('the journey card chevron points forward in Arabic', (tester) async {
    SharedPreferences.setMockInitialValues({
      OnboardingStorage.keyActiveChildId: 1,
      OnboardingStorage.keyActiveChildName: 'سارة',
      OnboardingStorage.keyActiveChildAgeGroup: '7-9',
      OnboardingStorage.keyOnboardingCompleted: true,
    });
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(overrides: [
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ]);
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);

    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: _app(const ChildJourneyCard(), locale: const Locale('ar')),
    ));
    await tester.pump();
    expect(find.byType(DirectionalChevron), findsOneWidget);
    final icon = tester.widget<Icon>(find.descendant(
        of: find.byType(DirectionalChevron), matching: find.byType(Icon)));
    // Forward is leftwards in Arabic, drawn unmirrored.
    expect(icon.icon, Icons.chevron_left);
    expect(icon.textDirection, TextDirection.ltr);
    expect(
        find.byWidgetPredicate((w) =>
            w is Icon && w.icon == Icons.chevron_right),
        findsNothing);
  });

  test('the invite keys this branch replaced are gone from both locales', () {
    // inviteTitle / inviteCodeUsed lost their last caller when the screen
    // became «أجرك الجاري»; an orphaned key is a string nobody will update.
    for (final file in ['lib/l10n/app_ar.arb', 'lib/l10n/app_en.arb']) {
      final arb = File(file).readAsStringSync();
      expect(arb, isNot(contains('"inviteTitle"')), reason: file);
      expect(arb, isNot(contains('"inviteCodeUsed"')), reason: file);
    }
  });
}
