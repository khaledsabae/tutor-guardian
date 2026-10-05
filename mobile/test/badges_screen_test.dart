/// The Badges screen, as parents see it.
///
/// * Every tile had a fixed height (`GridView.count`'s aspect ratio), so it
///   could not grow with its text: it overflowed on a 360dp phone at normal
///   size, and at 200% text the descriptions were cut off.
/// * It spoke Arabic to English readers. Each badge carried its Arabic title
///   and description as plain strings in `badges.dart`, and the screen showed
///   them, an Arabic share line and an Arabic screen-reader label whatever
///   the app language. The words are now looked up by badge id in the ARB
///   files. The ids must not move: the coins ledger credits each badge once,
///   by id.
library;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/badges.dart';
import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/program/screens/badges_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

/// Arabic, Arabic Supplement, Arabic Extended-A/B and both presentation-form
/// blocks — a pre-shaped glyph pasted from somewhere still counts.
final _arabicScript = RegExp(r'[\u0600-\u06FF\u0750-\u077F\u0870-\u089F'
    r'\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFC]');

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

/// Everything the screen paints, plus every label it hands a screen reader.
List<String> _screenStrings(WidgetTester tester) => [
      for (final t in tester.widgetList<RichText>(find.byType(RichText)))
        t.text.toPlainText(),
      for (final s in tester.widgetList<Semantics>(find.byType(Semantics)))
        ?s.properties.label,
    ];

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

  testWidgets('English readers see no Arabic on the Badges screen',
      (tester) async {
    await _pumpBadges(tester, const Locale('en'));

    expect(_screenStrings(tester).where(_arabicScript.hasMatch), isEmpty);
    // And the tiles really rendered, so the check above is not vacuous.
    for (final title in const [
      'First step',
      'Five lessons',
      'Ten lessons',
      'Week streak',
      'Month streak',
      'Path explorer',
    ]) {
      expect(find.text(title), findsOneWidget, reason: title);
    }
  });

  testWidgets('Arabic readers keep the original badge wording', (tester) async {
    await _pumpBadges(tester, const Locale('ar'));

    const wording = {
      'أول خطوة': 'أكملت أول درس — بداية الطريق',
      'خمسة دروس': 'أكملت 5 دروس — استمرّ',
      'عشرة دروس': 'أكملت 10 دروس — ما شاء الله',
      'أسبوع متواصل': '7 أيام متتالية من التعلّم',
      'سلسلة شهر': '30 يوماً متتالية — التزام رائع',
      'مستكشف المسارات': 'دروس مكتملة في 3 مسارات مختلفة',
    };
    for (final MapEntry(key: title, value: description) in wording.entries) {
      expect(find.text(title), findsOneWidget, reason: title);
      expect(find.text(description), findsOneWidget, reason: description);
    }
  });

  group('badge words are looked up by id', () {
    test('the ids the coins ledger credits are unchanged', () {
      expect(computeBadges(null).map((b) => b.id), [
        'first_step',
        'five_lessons',
        'ten_lessons',
        'week_streak',
        'month_streak',
        'path_explorer',
      ]);
    });

    test('every badge has its own words in every app language', () {
      for (final locale in AppLocalizations.supportedLocales) {
        final l10n = lookupAppLocalizations(locale);
        final badges = computeBadges(null);
        for (final badge in badges) {
          final where = '${badge.id} (${locale.languageCode})';
          // An id with no entry falls back to the bare id.
          expect(badge.title(l10n), isNot(badge.id), reason: where);
          expect(badge.description(l10n), isNotEmpty, reason: where);
          expect(badge.shareMessage(l10n), contains(badge.title(l10n)),
              reason: where);
        }
        final titles = badges.map((b) => b.title(l10n)).toList();
        expect(titles.toSet(), hasLength(titles.length),
            reason: 'two badges share a title in ${locale.languageCode}');
      }
    });

    test('the share line and card label follow the app language', () {
      final en = lookupAppLocalizations(const Locale('en'));
      for (final badge in computeBadges(null)) {
        expect(_arabicScript.hasMatch(badge.shareMessage(en)), isFalse,
            reason: badge.id);
      }
      expect(_arabicScript.hasMatch(en.badgeShareEyebrow), isFalse);

      final ar = lookupAppLocalizations(const Locale('ar'));
      expect(
        computeBadges(null).first.shareMessage(ar),
        'ما شاء الله 🌟 وصلت لإنجاز «أول خطوة» في رحلتي التربوية مع «المربّي» 🤍',
      );
      expect(ar.badgeShareEyebrow, 'إنجاز جديد');
    });
  });
}
