// UX-4 (UX_UI_ROADMAP §4.3): the child theme and the child-mode frame.

import 'package:flutter/material.dart';
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

  testWidgets('frame: hand-over card first, then the surface under a '
      'persistent child-mode bar', (t) async {
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
    expect(find.textContaining('This is your time'), findsOneWidget);

    await t.pump(ChildModeShell.handoffHold);
    await t.pump(ChildModeShell.fade);
    final card = t.widget<AnimatedOpacity>(find.ancestor(
      of: find.textContaining('This is your time'),
      matching: find.byType(AnimatedOpacity),
    ));
    expect(card.opacity, 0);
    expect(find.textContaining('Child Mode'), findsOneWidget);
    expect(find.byTooltip('Exit'), findsOneWidget);
    expect(find.text('surface'), findsOneWidget);
    // The surface inherits the child theme.
    final ctx = t.element(find.text('surface'));
    expect(Theme.of(ctx).textTheme.bodyMedium!.fontSize,
        Typography.material2021().englishLike.bodyMedium!.fontSize! + 2);
  });
}
