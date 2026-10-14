// UX-4 (UX_UI_ROADMAP §4.3): the child theme and the child-mode frame.

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';

import 'package:almorabbi/features/routine/widgets/child_mode_shell.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/theme/app_theme.dart';
import 'package:almorabbi/theme/design_tokens.dart';

void main() {
  testWidgets('child theme: +2 sp type, 56 dp targets, rounder cards',
      (t) async {
    final geometry = Typography.material2021().englishLike;
    final child = AppTheme.child(Brightness.light);
    expect(child.textTheme.bodyMedium!.fontSize,
        geometry.bodyMedium!.fontSize! + 2);
    expect(child.textTheme.titleLarge!.fontSize,
        geometry.titleLarge!.fontSize! + 2);
    expect(child.textTheme.headlineSmall!.fontSize,
        geometry.headlineSmall!.fontSize! + 2);
    final size = child.elevatedButtonTheme.style!.minimumSize!.resolve({})!;
    expect(size.height, Dt.minTouchChild);
    expect(child.iconButtonTheme.style!.minimumSize!.resolve({})!.width,
        Dt.minTouchChild);
    final shape = child.cardTheme.shape! as RoundedRectangleBorder;
    expect((shape.borderRadius as BorderRadius).topLeft.x, Dt.rCard + 8);
    expect(AppTheme.child(Brightness.dark).brightness, Brightness.dark);
  });

  for (final locale in const [Locale('ar'), Locale('en')]) {
    testWidgets('child mode exit is localized and avatar is decorative (${locale.languageCode})', (t) async {
      final semantics = t.ensureSemantics();
      try {
        SharedPreferences.setMockInitialValues({});
        final prefs = await SharedPreferences.getInstance();
        final container = ProviderContainer(overrides: [
          sharedPreferencesProvider.overrideWith((_) async => prefs),
        ]);
        addTearDown(container.dispose);
        await container.read(sharedPreferencesProvider.future);
        await t.pumpWidget(UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            locale: locale,
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: const ChildModeShell(child: Scaffold(body: Text('surface'))),
          ),
        ));
        await t.pump();
        final exit = find.bySemanticsLabel(locale.languageCode == 'ar'
            ? 'الخروج من وضع الطفل' : 'Exit child mode');
        expect(exit, findsOneWidget);
        expect(t.getSemantics(exit).getSemanticsData().hasAction(SemanticsAction.tap), isTrue);
        expect(t.getSize(find.byTooltip(locale.languageCode == 'ar'
            ? 'الخروج من وضع الطفل' : 'Exit child mode')).height, greaterThanOrEqualTo(56));
        expect(find.bySemanticsLabel(RegExp('👶')), findsNothing);
      } finally {
        semantics.dispose();
      }
    });
  }

  testWidgets('frame: the surface straight away under a persistent '
      'child-mode bar — no hand-over card on the child\'s clock', (t) async {
    // The app only enters child mode once preferences are loaded; so here.
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(overrides: [
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ]);
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);
    await t.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: const Locale('en'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const ChildModeShell(child: Scaffold(body: Text('surface'))),
      ),
    ));
    await t.pump();
    // The hand-over card used to cover the surface for 1.1 s here, inside the
    // session and on the child's minutes. The gate's doors do that job now,
    // in parent mode, before the session exists.
    expect(find.textContaining('This is your time'), findsNothing);
    expect(find.text('surface').hitTestable(), findsOneWidget);
    expect(find.textContaining('Child Mode'), findsOneWidget);
    expect(find.byTooltip('Exit child mode'), findsOneWidget);
    expect(find.text('surface'), findsOneWidget);
    // The surface inherits the child theme.
    final ctx = t.element(find.text('surface'));
    expect(Theme.of(ctx).textTheme.bodyMedium!.fontSize,
        Typography.material2021().englishLike.bodyMedium!.fontSize! + 2);
  });
}
