/// Every share sheet, as the people a parent shares with receive it.
///
/// With the app in English, each share still went out in Arabic: the install
/// line under every message (ShareService), the brand line and install hint
/// on every card (ShareCardBrandFooter), and the messages and card labels of
/// the path, milestone, first-surah, coach-tip and infographic shares. The
/// path message also sent a literal backslash-n where a line break was meant.
///
/// A card is captured off-tree (ShareService → captureFromWidget) under a
/// left-to-right Directionality and no Localizations, so card chrome reads
/// [AppL10n.current], which the app keeps in step with its language —
/// `AppLocalizations.of(context)` throws there.
/// [_cardLines] reads a card's words without Localizations above it; the
/// real capture runs in the last widget test, through the share button.
///
/// Only the app's own words follow the language. Content — a path's title, a
/// tip, a milestone, a child's name, a surah's name — travels as served. The
/// du'as on the Arabic shares are religious text: English leaves them out
/// rather than offer a translation as if it were a quote.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/journey/screens/child_journey_screen.dart';
import 'package:almorabbi/features/journey/screens/quran_memorization_screen.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/data/models.dart';
import 'package:almorabbi/features/program/providers/program_providers.dart';
import 'package:almorabbi/features/program/screens/path_detail_screen.dart';
import 'package:almorabbi/features/program/widgets/coach_tip_card.dart';
import 'package:almorabbi/features/programs/data/programs_models.dart';
import 'package:almorabbi/features/programs/widgets/ramadan_recap_card.dart';
import 'package:almorabbi/features/share/share_service.dart';
import 'package:almorabbi/features/share/shareable_moment_card.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';

/// Arabic, Arabic Supplement, Arabic Extended-A/B and both presentation-form
/// blocks — the same net as test/badges_screen_test.dart.
final _arabicScript = RegExp(
  r'[\u0600-\u06FF\u0750-\u077F\u0870-\u089F'
  r'\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFC]',
);

final _en = lookupAppLocalizations(const Locale('en'));
final _ar = lookupAppLocalizations(const Locale('ar'));

Iterable<String> _arabicIn(Iterable<String> words) =>
    words.where(_arabicScript.hasMatch);

/// Builds [card] as the capture tree has it — left-to-right, with no
/// Localizations above it — with the app in [l10n]'s language, and returns
/// every line it paints.
Future<List<String>> _cardLines(
  WidgetTester tester,
  Widget card,
  AppLocalizations l10n,
) async {
  AppL10n.current = l10n;
  addTearDown(() => AppL10n.current = _ar);
  tester.view.physicalSize = ShareableMomentCard.size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    Directionality(textDirection: TextDirection.ltr, child: card),
  );
  expect(tester.takeException(), isNull);
  return [
    for (final t in tester.widgetList<RichText>(find.byType(RichText)))
      t.text.toPlainText(),
  ];
}

/// Everything one moment sends: the text under the image, and the card.
Future<List<String>> _sent(
  WidgetTester tester,
  MomentShare share,
  AppLocalizations l10n,
) async => [
  ShareService.shareText(share.message, l10n),
  ...await _cardLines(tester, share.card, l10n),
];

const _servedTip = 'Read to your child tonight.';

class _ServedTip extends CoachTipNotifier {
  @override
  Future<CoachTip> build(int childId) async => CoachTip(
    id: 1,
    text: _servedTip,
    domain: 'development',
    childId: childId,
    date: '2026-10-05',
  );
}

/// Quoted string literals on code lines — comments may stay Arabic.
final _literal = RegExp(
  r"'(?:[^'\\]|\\.)*'"
  '|'
  r'"(?:[^"\\]|\\.)*"',
);

void main() {
  group('the text under a shared image', () {
    test('ends with the install line in the app language', () {
      expect(
        ShareService.shareText('Look 🤍', _en, referralCode: 'R1'),
        'Look 🤍\n\n📲 Al-Murabbi — free, for the sake of Allah:\n'
        'https://tg-api.alsaba.cloud/go?ref=R1',
      );
    });

    test('keeps the Arabic install line word for word', () {
      expect(
        ShareService.shareText('ما شاء الله', _ar),
        'ما شاء الله\n\n📲 «المربّي» مجانًا لوجه الله:\n'
        'https://tg-api.alsaba.cloud/go',
      );
    });

    test('adds nothing to a message that brings its own link', () {
      expect(
        ShareService.shareText(
          'Ours: https://x.test',
          _en,
          appendInstallLink: false,
        ),
        'Ours: https://x.test',
      );
    });
  });

  group('the footer every card carries', () {
    testWidgets('speaks English to English readers', (tester) async {
      final lines = await _cardLines(
        tester,
        const ShareableMomentCard(
          emoji: '🌟',
          eyebrow: 'New achievement',
          headline: 'Five lessons',
        ),
        _en,
      );
      expect(_arabicIn(lines), isEmpty);
      expect(
        lines,
        containsAll([
          'Al-Murabbi — your partner on the parenting journey',
          '📲 Free, for the sake of Allah — scan the code or search for '
              '“Al-Murabbi”',
        ]),
      );
    });

    testWidgets('keeps its Arabic word for word', (tester) async {
      final lines = await _cardLines(
        tester,
        const ShareableMomentCard(
          emoji: '🌟',
          eyebrow: 'إنجاز جديد',
          headline: 'خمسة دروس',
        ),
        _ar,
      );
      expect(
        lines,
        containsAll([
          'المربّي — شريكك في رحلة التربية',
          '📲 مجانًا لوجه الله — امسح الكود أو ابحث: «المربّي»',
        ]),
      );
    });

    testWidgets('on the Ramadan recap card too', (tester) async {
      final lines = await _cardLines(
        tester,
        const RamadanRecapShareCard(
          card: RecapCard(
            headline: "Our Family's Ramadan 1448",
            lines: ['Family challenges: 12'],
            closing: 'May Allah accept from us and from you',
          ),
        ),
        _en,
      );
      expect(lines, contains('Family challenges: 12'));
      expect(_arabicIn(lines), isEmpty);
    });
  });

  group('each moment, shared in English', () {
    testWidgets('a finished path', (tester) async {
      final share = pathCompletionShare(
        _en,
        title: 'Patience',
        description: 'Seven small steps',
      );
      final sent = await _sent(tester, share, _en);
      expect(sent.first, contains('Patience'));
      expect(sent.first, isNot(contains(r'\n')));
      expect(_arabicIn(sent), isEmpty);
    });

    testWidgets("a journey milestone, with no du'a", (tester) async {
      final share = milestoneShare(
        _en,
        childName: 'Sara',
        emoji: '🕌',
        title: 'First prayer',
        note: '',
      );
      final sent = await _sent(tester, share, _en);
      expect(sent.first, contains('First prayer'));
      expect(_arabicIn(sent), isEmpty);
      expect(share.card.body?.trim() ?? '', isEmpty);
    });

    testWidgets("a first surah, with no du'a", (tester) async {
      // The surah's name is content — it comes from an Arabic-only list, as
      // the Quran does; what is checked here is the app's words around it.
      final share = firstSurahShare(_en, childName: 'Sara', surah: 'Al-Ikhlas');
      final sent = await _sent(tester, share, _en);
      expect(sent.first, contains('Al-Ikhlas'));
      expect(_arabicIn(sent), isEmpty);
      expect(share.card.body?.trim() ?? '', isEmpty);
    });

    testWidgets("today's coach tip", (tester) async {
      final share = coachTipShare(_en, _servedTip);
      final sent = await _sent(tester, share, _en);
      expect(sent.first, contains(_servedTip));
      expect(_arabicIn(sent), isEmpty);
    });

    test('an infographic', () {
      expect(_arabicIn([_en.shareInfographicText]), isEmpty);
    });
  });

  group('the Arabic wording is unchanged', () {
    test('a finished path — with a real line break now', () {
      final share = pathCompletionShare(
        _ar,
        title: 'الصبر',
        description: 'سبع خطوات صغيرة',
      );
      expect(
        share.message,
        'ما شاء الله 🤍 أتممت مسار «الصبر» في «المربّي»!\n'
        'كل خطوة في تربية أولادك صدقة جارية:',
      );
      expect(share.card.eyebrow, 'مسار مكتمل');
      expect(share.card.headline, 'الصبر');
      expect(share.card.body, 'سبع خطوات صغيرة');
    });

    test('a journey milestone', () {
      final share = milestoneShare(
        _ar,
        childName: 'سارة',
        emoji: '🕌',
        title: 'أول صلاة',
        note: '',
      );
      expect(
        share.message,
        'ما شاء الله 🤍 سجّلت محطة جديدة في رحلة سارة:\n'
        '«أول صلاة»\nاللهم بارك له واجعله من الصالحين.',
      );
      expect(share.card.eyebrow, 'محطة في رحلة سارة');
      expect(share.card.headline, 'أول صلاة');
      expect(share.card.body, 'اللهم بارك له واجعله قرة عين لوالديه 🤍');
      // The parent's own note, when there is one, takes the du'a's place.
      final noted = milestoneShare(
        _ar,
        childName: 'سارة',
        emoji: '🕌',
        title: 'أول صلاة',
        note: 'في المسجد',
      );
      expect(noted.card.body, 'في المسجد');
    });

    test('a first surah', () {
      final share = firstSurahShare(_ar, childName: 'سارة', surah: 'الإخلاص');
      expect(
        share.message,
        'ما شاء الله 📖 سارة حفظ أول سورة — سورة الإخلاص 🌟\n'
        'اللهم اجعله من أهل القرآن وخاصته.',
      );
      expect(share.card.eyebrow, 'محطة قرآنية لـ سارة');
      expect(share.card.headline, 'حفظ أول سورة — سورة الإخلاص');
      expect(share.card.body, 'اللهم اجعله من أهل القرآن وخاصّتك يا رب 🤍');
    });

    test("today's coach tip", () {
      final share = coachTipShare(_ar, 'اقرأ لطفلك قبل النوم');
      expect(
        share.message,
        'نصيحة اليوم في تربية أبنائنا 🌱\n\nاقرأ لطفلك قبل النوم\n\n'
        'انشرها تكن صدقة جارية لكل أب وأم:',
      );
      expect(share.card.eyebrow, 'نصيحة اليوم');
      expect(share.card.headline, 'وقفة في تربية أبنائنا');
      expect(share.card.body, 'اقرأ لطفلك قبل النوم');
    });

    test('an infographic', () {
      expect(_ar.shareInfographicText, 'إنفوجراف من تطبيق المربّي 🌿');
    });
  });

  testWidgets('tapping share on the coach tip sends English and the image', (
    tester,
  ) async {
    final sent = <Map<Object?, Object?>>[];
    const channel = MethodChannel('dev.fluttercommunity.plus/share');
    final messenger = tester.binding.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(channel, (call) async {
      sent.add(call.arguments as Map<Object?, Object?>);
      return null;
    });
    addTearDown(() => messenger.setMockMethodCallHandler(channel, null));
    addTearDown(() => AppL10n.current = _ar);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          activeChildProfileProvider.overrideWith(
            (ref) =>
                const ActiveChildProfile(id: 7, name: 'Sara', ageGroup: '4-6'),
          ),
          coachTipProvider.overrideWith(_ServedTip.new),
        ],
        child: MaterialApp(
          locale: const Locale('en'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          // What TutorGuardianApp's builder does; the off-tree card reads it.
          builder: (context, child) {
            AppL10n.current = AppLocalizations.of(context);
            return child!;
          },
          home: const Scaffold(body: CoachTipCard()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.runAsync(() async {
      await tester.tap(find.byIcon(Icons.ios_share));
      // The capture waits a second for the card's images before painting.
      for (var i = 0; i < 100 && sent.isEmpty; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 50));
      }
    });
    await tester.pumpAndSettle();

    expect(sent, hasLength(1));
    final text = sent.single['text']! as String;
    expect(text, contains(_servedTip));
    expect(text, endsWith('https://tg-api.alsaba.cloud/go'));
    expect(_arabicIn([text]), isEmpty);
    final image = File((sent.single['paths']! as List).single as String);
    addTearDown(() => image.parent.deleteSync(recursive: true));
    expect(image.lengthSync(), greaterThan(0));
  });

  test('no share surface spells its words out in Arabic', () {
    const files = [
      'lib/features/share/share_service.dart',
      'lib/features/share/shareable_moment_card.dart',
      'lib/features/program/widgets/coach_tip_card.dart',
      'lib/features/program/screens/infographic_screen.dart',
      'lib/features/journey/screens/child_journey_screen.dart',
    ];
    for (final path in files) {
      final arabic = [
        for (final line in File(path).readAsLinesSync())
          if (!line.trimLeft().startsWith('//'))
            for (final m in _literal.allMatches(line))
              if (_arabicScript.hasMatch(m[0]!)) m[0]!,
      ];
      expect(arabic, isEmpty, reason: path);
    }
  });
}
