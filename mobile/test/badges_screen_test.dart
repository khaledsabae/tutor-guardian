/// The Badges screen, as parents see it.
///
/// Every tile had a fixed height (`GridView.count`'s aspect ratio), so it
/// could not grow with its text: it overflowed on a 360dp phone at normal
/// size, and at 200% text the descriptions were cut off.
library;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/program/screens/badges_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

LessonProgress _done(String lesson, String path) => LessonProgress(
      lessonId: lesson,
      pathId: path,
      status: ProgressStatus.completed,
    );

/// Earns first_step 🌱, five_lessons, week_streak and path_explorer; leaves
/// ten_lessons and month_streak locked 🔒, so both tile states render.
final _bundle = ChildProgressBundle(
  childId: 1,
  lessons: [
    _done('l1', 'p1'),
    _done('l2', 'p1'),
    _done('l3', 'p2'),
    _done('l4', 'p2'),
    _done('l5', 'p3'),
  ],
  streakDays: 7,
);

Future<void> _pumpBadges(WidgetTester tester, Locale locale,
    {double textScale = 1.0}) async {
  // A 360dp phone: the narrow end of what parents actually hold.
  tester.view.physicalSize = const Size(360, 800) * 3.0;
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(ProviderScope(
    overrides: [
      activeChildIdProvider.overrideWith((_) => 1),
      childProgressProvider.overrideWith((ref, childId) async => _bundle),
    ],
    child: MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context)
            .copyWith(textScaler: TextScaler.linear(textScale)),
        child: child!,
      ),
      home: const BadgesScreen(),
    ),
  ));
  await tester.pumpAndSettle();
}

void main() {
  for (final locale in AppLocalizations.supportedLocales) {
    testWidgets(
        'at 200% text the badge tiles grow instead of clipping '
        '(${locale.languageCode})', (tester) async {
      await _pumpBadges(tester, locale, textScale: 2.0);

      expect(tester.takeException(), isNull); // a RenderFlex overflow
      expect(find.text('🌱'), findsOneWidget); // the tiles did render
      expect(find.text('🔒'), findsNWidgets(2));
      // The app bar title is one line by design; nothing below it is cut.
      final appBar = tester
          .renderObjectList<RenderParagraph>(find.descendant(
              of: find.byType(AppBar), matching: find.byType(RichText)))
          .toSet();
      final cut = [
        for (final p
            in tester.renderObjectList<RenderParagraph>(find.byType(RichText)))
          if (!appBar.contains(p) && p.didExceedMaxLines) p.text.toPlainText(),
      ];
      expect(cut, isEmpty);
    });
  }
}
