/// «حصاد الجمعة» (نور والقناديل phase 3).
///
/// Noor says one line on the family's Friday — once, and only for a week with
/// lanterns — and the line stays put after it is recorded as seen, so its
/// chip can be tapped. The card is gathered on the phone from the week: the
/// lanterns light again one by one, the acts are summed up with the Arabic
/// plural each number takes, and it closes with a du'a picked by its id from
/// the guarded pack — the text is the pack's, character for character. The
/// shared image carries no child's name.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:screenshot/screenshot.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/core/clock.dart';
import 'package:almorabbi/features/adhkar/data/family_adhkar.dart';
import 'package:almorabbi/features/companion/widgets/noor_today_header.dart';
import 'package:almorabbi/features/lanterns/data/family_week.dart';
import 'package:almorabbi/features/lanterns/data/lantern_copy.dart';
import 'package:almorabbi/features/lanterns/widgets/friday_harvest.dart';
import 'package:almorabbi/features/lanterns/widgets/lantern_row.dart';
import 'package:almorabbi/features/share/shareable_moment_card.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';

import 'lantern_fakes.dart';
import 'memory_fakes.dart';

final _ar = lookupAppLocalizations(const Locale('ar'));
final _en = lookupAppLocalizations(const Locale('en'));

List<ParentingContent> _pack(String lang) => FamilyAdhkar.parse(
    File('assets/content/adhkar/family_adhkar.$lang.json').readAsStringSync());

FamilyWeek _week(Map<String, int> kinds) => FamilyWeek.fromJson(familyWeekJson(
      acts: [
        for (final MapEntry(key: kind, value: n) in kinds.entries)
          for (var i = 0; i < n; i++) act(kind, i % 5, hour: 8 + i % 10),
      ],
    ));

/// Every string a widget tree draws.
List<String> _texts(WidgetTester tester) => [
      for (final w in tester.widgetList<Text>(find.byType(Text)))
        w.data ?? w.textSpan?.toPlainText() ?? '',
      for (final w in tester.widgetList<RichText>(find.byType(RichText)))
        w.text.toPlainText(),
    ];

Future<void> _loadCairo(WidgetTester tester) => tester.runAsync(() async {
      for (final weight in [
        FontWeight.w400,
        FontWeight.w600,
        FontWeight.w700,
        FontWeight.w800,
      ]) {
        GoogleFonts.cairo(fontWeight: weight);
      }
      GoogleFonts.amiriQuran();
      await GoogleFonts.pendingFonts();
    });

Future<void> _pumpCard(WidgetTester tester, Widget card,
    {Locale locale = const Locale('ar')}) async {
  tester.view.physicalSize = const Size(360, 800) * 3.0;
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(MaterialApp(
    locale: locale,
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(body: card),
  ));
  await tester.pump();
}

void main() {
  group('the summary speaks Arabic numbers properly', () {
    test('one, two, a few, many, a hundred', () {
      String lessons(int n) => harvestSummary(_ar, _week({'lesson': n}));
      expect(lessons(1), 'درس واحد');
      expect(lessons(2), 'درسان');
      expect(lessons(3), '3 دروس');
      expect(lessons(10), '10 دروس');
      expect(lessons(11), '11 درسًا');
      expect(lessons(99), '99 درسًا');
      expect(lessons(100), '100 درس');
    });

    test('by kind, in a fixed order, joined with the Arabic comma', () {
      final week = _week({'mission': 1, 'question': 2, 'lesson': 3});
      expect(harvestSummary(_ar, week), '3 دروس، سؤالان، مهمة واحدة');
      expect(harvestSummary(_en, week), '3 lessons, 2 questions, 1 mission');
      final all = _week({
        'challenge': 1,
        'habit': 2,
        'plan_tick': 3,
        'followup': 1,
        'stargazing': 1,
      });
      expect(harvestSummary(_ar, all),
          'متابعة واحدة، 3 خطوات من الخطة، عادتان، تحدٍّ واحد، خطوة تربوية أخرى');
    });
  });

  group("the du'a is the pack's, by id", () {
    for (final lang in ['ar', 'en']) {
      test('$lang pack: $kHarvestDuaId is a verse with its source', () {
        final dua = harvestDua(_pack(lang))!;
        expect(dua.id, kHarvestDuaId);
        expect(dua.kind, 'verse');
        expect(dua.source, isNotEmpty);
        // Scripture is not translated: the English pack carries it in Arabic.
        expect(dua.text, harvestDua(_pack('ar'))!.text);
      });
    }

    testWidgets('the card shows exactly that text, after the lead-in', (
      tester,
    ) async {
      final dua = harvestDua(_pack('ar'))!;
      await _pumpCard(
          tester, FridayHarvestCard(week: _week({'lesson': 1}), dua: dua));
      await tester.pump(const Duration(seconds: 3));
      expect(find.text('ونختم الأسبوع بدعاء من القرآن الكريم:'), findsOneWidget);
      expect(find.text(dua.text), findsOneWidget);
      expect(find.text(dua.source), findsOneWidget);
    });

    testWidgets('no pack loaded: the card ends without a du\'a', (
      tester,
    ) async {
      await _pumpCard(
          tester, FridayHarvestCard(week: _week({'lesson': 1}), dua: null));
      await tester.pump(const Duration(seconds: 3));
      expect(find.text('ونختم الأسبوع بدعاء من القرآن الكريم:'), findsNothing);
      expect(find.byType(HarvestDuaText), findsNothing);
    });
  });

  testWidgets('the card replays the week’s lanterns, one after another', (
    tester,
  ) async {
    await _pumpCard(
        tester,
        FridayHarvestCard(
            week: _week({'lesson': 3, 'question': 2}),
            dua: harvestDua(_pack('ar'))));
    final row = tester.state<LanternRowState>(find.byType(LanternRow));
    expect(row.shown, 0);
    await tester.pump(const Duration(milliseconds: 300));
    expect(row.shown, 1);
    await tester.pump(const Duration(milliseconds: 300));
    expect(row.shown, 2);
    await tester.pump(const Duration(seconds: 3));
    expect(row.shown, 3, reason: 'three days with acts');
    expect(find.text('حصاد الأسبوع'), findsOneWidget);
    expect(find.text('من نور'), findsOneWidget);
    expect(find.text('في أسبوعكم: 3 دروس، سؤالان'), findsOneWidget);
    expect(find.text('شارك الحصاد'), findsOneWidget);
  });

  testWidgets('English card, 200% text: lays out, the verse stays Arabic', (
    tester,
  ) async {
    final dua = harvestDua(_pack('en'))!;
    tester.view.physicalSize = const Size(320, 640) * 3.0;
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('en'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context)
            .copyWith(textScaler: const TextScaler.linear(2)),
        child: child!,
      ),
      home: Scaffold(
          body: FridayHarvestCard(
              week: _week({'lesson': 1, 'mission': 2}), dua: dua)),
    ));
    await tester.pump(const Duration(seconds: 3));
    expect(tester.takeException(), isNull);
    expect(find.text("The week's harvest"), findsOneWidget);
    await tester.scrollUntilVisible(
        find.text('Your week: 1 lesson, 2 missions'), 200,
        scrollable: find.byType(Scrollable).first);
    await tester.scrollUntilVisible(find.text(dua.text), 200,
        scrollable: find.byType(Scrollable).first);
    expect(tester.takeException(), isNull);
  });

  group('the shared image', () {
    // A week whose curriculum titles and child ids are all present — none of
    // it may reach the image or its message.
    final week = FamilyWeek.fromJson(familyWeekJson(acts: [
      act('lesson', 0, title: 'سارة والنوم'),
      act('mission', 1, title: 'مهمة سارة'),
      act('question', 2),
    ]));

    test('the message is the summary, with no name and no title', () {
      final share = harvestShare(_ar, week);
      expect(share.message, 'قناديل أسبوعنا: درس واحد، سؤال واحد، مهمة واحدة');
      expect(share.message, isNot(contains('سارة')));
    });

    testWidgets('the card draws no name, no title — counts and the du\'a', (
      tester,
    ) async {
      await _loadCairo(tester);
      AppL10n.current = _ar;
      addTearDown(() => AppL10n.current = _ar);
      tester.view.physicalSize = ShareableMomentCard.size;
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final dua = harvestDua(_pack('ar'))!;
      await tester.pumpWidget(Directionality(
          textDirection: TextDirection.ltr,
          child: harvestShare(_ar, week, dua: dua).card));
      expect(tester.takeException(), isNull);
      final texts = _texts(tester).join('\n');
      expect(texts, isNot(contains('سارة')));
      expect(texts, contains('درس واحد، سؤال واحد، مهمة واحدة'));
      expect(texts, contains(dua.text));
      expect(texts, contains('حصاد أسبوعنا'));
    });

    testWidgets('a real capture renders (no error box), 1080×1080', (
      tester,
    ) async {
      await _loadCairo(tester);
      for (final l10n in [_ar, _en]) {
        AppL10n.current = l10n;
        addTearDown(() => AppL10n.current = _ar);
        final card = harvestShare(l10n, week, dua: harvestDua(_pack('ar'))).card;
        final png = (await tester.runAsync(
          () => ScreenshotController().captureFromWidget(
            card,
            targetSize: ShareableMomentCard.size,
            delay: const Duration(milliseconds: 400),
          ),
        ))!;
        expect(tester.takeException(), isNull, reason: l10n.localeName);
        final image = (await tester.runAsync(() => decodeImageFromList(png)))!;
        addTearDown(image.dispose);
        expect(Size(image.width.toDouble(), image.height.toDouble()),
            ShareableMomentCard.size);
        // A captured error box is a few KB; a real card is far larger.
        expect(png.length, greaterThan(60 * 1024), reason: l10n.localeName);
        const out = String.fromEnvironment('HARVEST_PNG');
        if (out.isNotEmpty) {
          File('$out${l10n.localeName}.png').writeAsBytesSync(png);
        }
      }
    });
  });

  group("Noor's Friday line on «اليوم»", () {
    DateTime friday() =>
        mondayOf(DateTime.now()).add(const Duration(days: 4, hours: 9));

    testWidgets('speaks, stays after it is recorded, and opens the card', (
      tester,
    ) async {
      final server = FakeMemoryServer()
        ..familyWeek = familyWeekJson(acts: [
          act('lesson', 0),
          act('lesson', 1),
          act('question', 1),
        ]);
      await pumpMemoryApp(
        tester,
        const Scaffold(body: NoorTodayHeader(fallback: Text('FALLBACK'))),
        server: server,
        overrides: [clockProvider.overrideWithValue(friday)],
      );
      await settle(tester, 10);
      const line = 'جمعة مباركة. جمعتُ لكم قناديل هذا الأسبوع في بطاقة صغيرة.';
      expect(find.text(line), findsOneWidget);
      // Recorded on the phone as seen — so it never comes back on the next
      // open — and still here in this one.
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('noor.seen.v1'), contains('harvest:'));
      await settle(tester, 10);
      expect(find.text(line), findsOneWidget);

      await tester.tap(find.text('افتح البطاقة'));
      await settle(tester, 10);
      expect(find.text('حصاد الأسبوع'), findsOneWidget);
      expect(find.text('في أسبوعكم: درسان، سؤال واحد'), findsOneWidget);
      await tester.pump(const Duration(seconds: 3));
    });

    testWidgets('no lanterns this week (or an older server): the greeting', (
      tester,
    ) async {
      final server = FakeMemoryServer(); // /api/family/week → 404
      await pumpMemoryApp(
        tester,
        const Scaffold(body: NoorTodayHeader(fallback: Text('FALLBACK'))),
        server: server,
        overrides: [clockProvider.overrideWithValue(friday)],
      );
      await settle(tester, 10);
      expect(find.textContaining('جمعة مباركة'), findsNothing);
      expect(find.text('افتح البطاقة'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  });
}
