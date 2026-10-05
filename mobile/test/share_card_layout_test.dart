/// Where a shared card puts its words, and which way they read.
///
/// Two faults every shared card had, both seen only in a captured PNG:
///
/// * Short content sat at the start edge, not on the centre line.
///   [ShareCardFrame] left its content to the Stack's defaults — loose,
///   top-start — so the Column was only as wide as its widest line. A long
///   body wraps, fills the width and hides it; a quiz result shows it.
/// * Arabic read left to right. The capture (screenshot's captureFromWidget)
///   wraps a card in `Directionality(ltr)` and nothing else, so «» and the
///   emoji of the install hint landed on the wrong side, and a quiz score
///   read «نقطة 50 / 40».
///
/// Layout and direction are read off a card pumped under the capture's own
/// left-to-right Directionality, in the bundled Cairo. In the test font the
/// lines come out wider: a quiz result or a first surah then fills the card,
/// and their geometry tests passed against the old frame. A pumped tree also
/// has a View and a MediaQuery, which the capture has not, so only the real
/// capture at the end proves the cards still render where they are shared
/// from.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:screenshot/screenshot.dart';

import 'package:almorabbi/features/journey/screens/child_journey_screen.dart';
import 'package:almorabbi/features/journey/screens/quran_memorization_screen.dart';
import 'package:almorabbi/features/program/screens/path_detail_screen.dart';
import 'package:almorabbi/features/program/widgets/coach_tip_card.dart';
import 'package:almorabbi/features/programs/data/programs_models.dart';
import 'package:almorabbi/features/programs/widgets/ramadan_recap_card.dart';
import 'package:almorabbi/features/share/shareable_moment_card.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';

final _en = lookupAppLocalizations(const Locale('en'));
final _ar = lookupAppLocalizations(const Locale('ar'));

/// `--dart-define=SHARE_CARD_PNG=/tmp/cards-` writes each real capture to
/// `/tmp/cards-<name>.png`, to look at.
const _pngPrefix = String.fromEnvironment('SHARE_CARD_PNG');

/// The shortest card the app shares: every line is narrower than the card.
ShareableMomentCard _quiz(AppLocalizations l10n) => ShareableMomentCard(
  emoji: '🏆',
  eyebrow: l10n.quizResultTitle,
  headline: l10n.quizScorePoints(40, 50),
  body: l10n.quizPraiseExcellent,
  icon: Icons.quiz_outlined,
);

const _longTip =
    'اقرأ لطفلك قصة قصيرة كل ليلة قبل النوم، ثم اسأله في الصباح عمّا أعجبه '
    'فيها؛ فهذا يقوّي ذاكرته ولغته ويقرّبه منك، ويجعل القراءة عادةً يحبّها لا '
    'واجبًا يهرب منه.';

const _longDescription =
    'Seven small steps to meet anger with patience: name the feeling, wait '
    'before you speak, and show your child every day that a calm voice is '
    'stronger than a loud one.';

const _arabicNote = 'صلّت معنا في المسجد لأول مرة 🤍';

const _arabicRecap = RecapCard(
  headline: 'رمضان عائلتنا ١٤٤٨',
  lines: ['تحديات العائلة: ١٢', 'أيام الصيام: ٢٧'],
  closing: 'تقبّل الله منا ومنكم',
);

const _englishRecap = RecapCard(
  headline: "Our Family's Ramadan 1448",
  lines: ['Family challenges: 12', 'Days of fasting: 27'],
  closing: 'May Allah accept from us and from you',
);

/// Loads the bundled Cairo weights the cards use. Runs for real, not in the
/// test's fake time; a font that is already loaded costs nothing.
Future<void> _loadCairo(WidgetTester tester) => tester.runAsync(() async {
  for (final weight in [
    FontWeight.w400,
    FontWeight.w600,
    FontWeight.w700,
    FontWeight.w800,
  ]) {
    GoogleFonts.cairo(fontWeight: weight);
  }
  await GoogleFonts.pendingFonts();
});

/// Pumps [card] at the size it is captured at, under [ambient] — left to
/// right, as the capture has it, unless a test says otherwise — with the app
/// in [l10n]'s language.
Future<void> _pump(
  WidgetTester tester,
  Widget card,
  AppLocalizations l10n, {
  TextDirection ambient = TextDirection.ltr,
}) async {
  await _loadCairo(tester);
  AppL10n.current = l10n;
  addTearDown(() => AppL10n.current = _ar);
  tester.view.physicalSize = ShareableMomentCard.size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(Directionality(textDirection: ambient, child: card));
  expect(tester.takeException(), isNull);
}

/// The horizontal centre of every run of text on the pumped card — emoji and
/// icon included — and of the QR.
Map<String, double> _centres(WidgetTester tester) {
  double centreOf(RenderBox box) =>
      box.localToGlobal(box.size.center(Offset.zero)).dx;
  return {
    for (final p in tester.renderObjectList<RenderParagraph>(
      find.byType(RichText),
    ))
      p.text.toPlainText(): centreOf(p),
    'QR': centreOf(tester.renderObject<RenderBox>(find.byType(QrImageView))),
  };
}

/// The direction [text] is laid out in on the pumped card.
TextDirection _directionOf(WidgetTester tester, String text) =>
    tester.renderObject<RenderParagraph>(find.text(text)).textDirection;

void main() {
  group('every line sits on the centre line of the card', () {
    final cards = <String, (Widget, AppLocalizations)>{
      'a quiz result, in Arabic': (_quiz(_ar), _ar),
      'a quiz result, in English': (_quiz(_en), _en),
      'a first surah': (
        firstSurahShare(_ar, childName: 'سارة', surah: 'الإخلاص').card,
        _ar,
      ),
      'a long tip, which wraps': (coachTipShare(_ar, _longTip).card, _ar),
      'the Ramadan recap': (
        const RamadanRecapShareCard(card: _arabicRecap),
        _ar,
      ),
    };
    for (final MapEntry(key: name, value: (card, l10n)) in cards.entries) {
      // Left to right is the capture; right to left is an Arabic app showing
      // a card in its own tree (the Ramadan preview).
      for (final ambient in TextDirection.values) {
        testWidgets('$name, under ${ambient.name}', (tester) async {
          await _pump(tester, card, l10n, ambient: ambient);
          final centres = _centres(tester);
          expect(centres.length, greaterThanOrEqualTo(7), reason: '$centres');
          for (final MapEntry(key: line, value: x) in centres.entries) {
            expect(
              x,
              closeTo(ShareableMomentCard.size.width / 2, 0.5),
              reason: line,
            );
          }
        });
      }
    }
  });

  group('each line reads in the direction of its own words', () {
    testWidgets('an Arabic card from an Arabic app reads right to left', (
      tester,
    ) async {
      await _pump(tester, _quiz(_ar), _ar);
      for (final line in [
        _ar.quizResultTitle,
        _ar.quizScorePoints(40, 50),
        _ar.quizPraiseExcellent,
        _ar.shareCardBrandLine,
        _ar.shareCardInstallHint,
      ]) {
        expect(_directionOf(tester, line), TextDirection.rtl, reason: line);
      }
    });

    testWidgets('an English card from an English app, left to right', (
      tester,
    ) async {
      // Inside a right-to-left tree: the card decides, not what is around it.
      await _pump(tester, _quiz(_en), _en, ambient: TextDirection.rtl);
      for (final line in [
        _en.quizResultTitle,
        _en.quizScorePoints(40, 50),
        _en.quizPraiseExcellent,
        _en.shareCardBrandLine,
        _en.shareCardInstallHint,
      ]) {
        expect(_directionOf(tester, line), TextDirection.ltr, reason: line);
      }
    });

    testWidgets("a parent's Arabic note under an English app", (tester) async {
      final card = milestoneShare(
        _en,
        childName: 'Sara',
        emoji: '🕌',
        title: 'First prayer',
        note: _arabicNote,
      ).card;
      await _pump(tester, card, _en);
      expect(_directionOf(tester, _arabicNote), TextDirection.rtl);
      expect(_directionOf(tester, 'First prayer'), TextDirection.ltr);
      // The app's own words stay in the app's direction.
      expect(_directionOf(tester, card.eyebrow), TextDirection.ltr);
      expect(_directionOf(tester, _en.shareCardInstallHint), TextDirection.ltr);
    });

    testWidgets('a label is the app\'s words, whatever name is in it', (
      tester,
    ) async {
      // More Latin letters than Arabic: counting letters would call this
      // line English. It is the app's Arabic with a name in it.
      final card = firstSurahShare(
        _ar,
        childName: 'Abdulrahman Alexander',
        surah: 'الإخلاص',
      ).card;
      await _pump(tester, card, _ar);
      expect(_directionOf(tester, card.eyebrow), TextDirection.rtl);
    });

    testWidgets('a line with no letters reads in the app\'s direction', (
      tester,
    ) async {
      const score = '40 / 50';
      await _pump(
        tester,
        ShareableMomentCard(
          emoji: '🏆',
          eyebrow: _ar.quizResultTitle,
          headline: score,
        ),
        _ar,
      );
      expect(_directionOf(tester, score), TextDirection.rtl);
    });

    testWidgets('the Ramadan footer follows the app, its content the card', (
      tester,
    ) async {
      await _pump(tester, const RamadanRecapShareCard(card: _arabicRecap), _en);
      expect(_directionOf(tester, _arabicRecap.headline), TextDirection.rtl);
      expect(_directionOf(tester, _en.shareCardInstallHint), TextDirection.ltr);
      expect(_directionOf(tester, _en.shareCardBrandLine), TextDirection.ltr);
    });
  });

  group('the real capture', () {
    // No View, no MediaQuery, no Localizations: only a left-to-right
    // Directionality. A failure there does not throw — the error box is
    // captured and shared — so the exception is the signal.
    final cards = <String, (Widget, AppLocalizations)>{
      'quiz-ar': (_quiz(_ar), _ar),
      'quiz-en': (_quiz(_en), _en),
      'first-surah-ar': (
        firstSurahShare(_ar, childName: 'سارة', surah: 'الإخلاص').card,
        _ar,
      ),
      'first-surah-en': (
        firstSurahShare(_en, childName: 'Sara', surah: 'الإخلاص').card,
        _en,
      ),
      'milestone-en-arabic-note': (
        milestoneShare(
          _en,
          childName: 'Sara',
          emoji: '🕌',
          title: 'First prayer',
          note: _arabicNote,
        ).card,
        _en,
      ),
      'coach-tip-long-ar': (coachTipShare(_ar, _longTip).card, _ar),
      'path-long-en': (
        pathCompletionShare(
          _en,
          title: 'Patience',
          description: _longDescription,
        ).card,
        _en,
      ),
      'ramadan-ar': (const RamadanRecapShareCard(card: _arabicRecap), _ar),
      'ramadan-en': (const RamadanRecapShareCard(card: _englishRecap), _en),
    };
    for (final MapEntry(key: name, value: (card, l10n)) in cards.entries) {
      testWidgets(name, (tester) async {
        await _loadCairo(tester);
        AppL10n.current = l10n;
        addTearDown(() => AppL10n.current = _ar);
        final png = (await tester.runAsync(
          () => ScreenshotController().captureFromWidget(
            card,
            targetSize: ShareableMomentCard.size,
            // Long enough for the background art to decode and repaint.
            delay: const Duration(milliseconds: 400),
          ),
        ))!;
        expect(tester.takeException(), isNull);
        final image = (await tester.runAsync(() => decodeImageFromList(png)))!;
        addTearDown(image.dispose);
        expect(
          Size(image.width.toDouble(), image.height.toDouble()),
          ShareableMomentCard.size,
        );
        if (_pngPrefix.isNotEmpty) {
          File('$_pngPrefix$name.png').writeAsBytesSync(png);
        }
      });
    }
  });
}
