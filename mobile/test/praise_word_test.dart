/// «كلمة طيبة» — the note from parent to child.
///
/// The loop has three links and each is held here: the chips on the evening
/// screen ride the confirmation (and its outbox retries) as a `note`; the
/// child's card shows the note once, for three seconds, in the band's form;
/// and a note that was already seen never comes back.
library;

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/missions/mission_confirmations.dart';
import 'package:almorabbi/features/missions/pending_missions_screen.dart';
import 'package:almorabbi/features/missions/praise_header.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    MissionConfirmations.resetForTest();
  });

  group('the band decides the form', () {
    test('4-6 read a sticker and nothing else', () {
      expect(praiseDisplayFor('4-6'), PraiseDisplay.sticker);
    });

    test('7-12 get the sticker and the text', () {
      expect(praiseDisplayFor('7-9'), PraiseDisplay.stickerAndText);
      expect(praiseDisplayFor('10-12'), PraiseDisplay.stickerAndText);
    });

    test('13-18 get one text line, no sticker', () {
      expect(praiseDisplayFor('13-15'), PraiseDisplay.textOnly);
      expect(praiseDisplayFor('16-18'), PraiseDisplay.textOnly);
    });

    test('prenatal-3 and anything unreadable get nothing', () {
      expect(praiseDisplayFor('under-2'), PraiseDisplay.none);
      expect(praiseDisplayFor('2-3'), PraiseDisplay.none);
      expect(praiseDisplayFor(null), PraiseDisplay.none);
      expect(praiseDisplayFor('mystery'), PraiseDisplay.none);
    });
  });

  group('the header on the child card', () {
    Future<void> pumpBand(WidgetTester tester, String band,
        {void Function()? onGone}) async {
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: PraiseHeader(
            note: 'أحسنت',
            display: praiseDisplayFor(band),
            onGone: onGone,
          ),
        ),
      ));
      await tester.pumpAndSettle(const Duration(milliseconds: 400));
    }

    testWidgets('4-6: the sticker, and no sentence to decode', (tester) async {
      await pumpBand(tester, '4-6');
      expect(find.text('🌟'), findsOneWidget);
      expect(find.text('أحسنت'), findsNothing);
      expect(find.text('أهلك يقولون لك'), findsNothing);
    });

    testWidgets('7-9: the sticker and the text', (tester) async {
      await pumpBand(tester, '7-9');
      expect(find.text('🌟'), findsOneWidget);
      expect(find.text('أحسنت'), findsOneWidget);
      expect(find.text('أهلك يقولون لك'), findsOneWidget);
    });

    testWidgets('13-15: one text line, no sticker', (tester) async {
      await pumpBand(tester, '13-15');
      expect(find.text('🌟'), findsNothing);
      expect(find.text('أحسنت'), findsOneWidget);
    });

    testWidgets('gone in three seconds, by itself', (tester) async {
      var gone = false;
      await pumpBand(tester, '7-9', onGone: () => gone = true);
      await tester.pump(const Duration(seconds: 2));
      expect(gone, isFalse, reason: 'three seconds means three seconds');
      await tester.pump(const Duration(seconds: 1));
      expect(gone, isTrue);
    });

    testWidgets('the button under it was tappable the whole time',
        (tester) async {
      var pressed = 0;
      await tester.pumpWidget(MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: Column(
            children: [
              const PraiseHeader(
                  note: 'أحسنت', display: PraiseDisplay.stickerAndText),
              TextButton(onPressed: () => pressed++, child: const Text('اذهب')),
            ],
          ),
        ),
      ));
      await tester.tap(find.text('اذهب'));
      expect(pressed, 1, reason: 'the praise must never gate the main action');
    });
  });

  group('a note is shown once', () {
    test('the memory remembers which praise was delivered', () async {
      final prefs = await SharedPreferences.getInstance();
      expect(await PraiseMemory.alreadyShown(prefs, 41), isFalse);
      await PraiseMemory.markShown(prefs, 41);
      expect(await PraiseMemory.alreadyShown(prefs, 41), isTrue);
      expect(await PraiseMemory.alreadyShown(prefs, 42), isFalse,
          reason: 'a second child\'s praise is not spent by the first');
    });
  });

  group('the chips ride the evening batch', () {
    testWidgets('a chip becomes the note on every confirmed card',
        (tester) async {
      final client = _RecordingClient()
        ..pending = [
          _card(41, '7-9'),
          _card(42, '13-15'),
        ];
      await _openEvening(tester, client);
      await tester.tap(find.text('أحسنت'));
      await tester.pump();
      await tester.tap(find.text('أكّد الكل'));
      await tester.pumpAndSettle();

      expect(client.settled, hasLength(2));
      expect(client.settled[0]['note'], 'أحسنت');
      expect(client.settled[1]['note'], 'أحسنت');
    });

    testWidgets('the parent\'s own line joins the chip', (tester) async {
      final client = _RecordingClient()..pending = [_card(41, '7-9')];
      await _openEvening(tester, client);
      await tester.tap(find.text('بارك الله فيك'));
      await tester.enterText(
          find.byType(TextField), 'أدّيتها دون أن أذكّرك');
      await tester.tap(find.text('أكّد الكل'));
      await tester.pumpAndSettle();

      expect(client.settled.single['note'],
          'بارك الله فيك — أدّيتها دون أن أذكّرك');
    });

    testWidgets('no praise chosen means no note at all', (tester) async {
      final client = _RecordingClient()..pending = [_card(41, '7-9')];
      await _openEvening(tester, client);
      await tester.tap(find.text('أكّد الكل'));
      await tester.pumpAndSettle();

      expect(client.settled.single.containsKey('note'), isFalse);
    });

    testWidgets('a card marked "not yet" carries no kind word',
        (tester) async {
      final client = _RecordingClient()
        ..pending = [
          _card(41, '7-9'),
          _card(42, '7-9'),
        ];
      await _openEvening(tester, client);
      await tester.tap(find.text('أحسنت'));
      await tester.pump();
      // The second card is answered "not yet": a note there would reach the
      // child as a contradiction.
      await tester.tap(find.text('ليس بعد').last);
      await tester.tap(find.text('أكّد الكل'));
      await tester.pumpAndSettle();

      final withNote = client.settled.where((e) => e['confirmed'] == false);
      expect(withNote, hasLength(1));
      expect(withNote.single.containsKey('note'), isFalse);
      expect(client.settled.firstWhere((e) => e['mission_id'] == 41)['note'],
          'أحسنت');
    });
  });

  group('the note survives the outbox', () {
    test('a lost answer resends the note with the confirmation',
        () async {
      final client = _FlakyClient();
      await expectLater(
          MissionConfirmations.send(client, [
            {'mission_id': 41, 'confirmed': true, 'note': 'أحسنت'}
          ]),
          throwsA(isA<TgApiError>()));
      final waiting = await MissionConfirmations.outbox();
      expect(waiting.single['note'], 'أحسنت');

      client.fail = false;
      await MissionConfirmations.flush(client);
      expect(client.attempts.last.single['note'], 'أحسنت');
      expect(await MissionConfirmations.outbox(), isEmpty);
    });
  });
}

Map<String, dynamic> _card(int id, String band) => {
      'mission_id': id,
      'child_id': 7,
      'child_name': 'أحمد',
      'title_ar': 'مهمة',
      'estimated_minutes': 20,
      'coins': 0,
      'age_band': band,
    };

Future<void> _openEvening(WidgetTester tester, TgClient client) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [tgClientProvider.overrideWithValue(client)],
    child: MaterialApp(
      locale: const Locale('ar'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: Center(
          child: Builder(
            builder: (context) => FilledButton(
              onPressed: () => Navigator.of(context).push<bool>(
                  MaterialPageRoute(
                      builder: (_) => const PendingMissionsScreen())),
              child: const Text('افتح'),
            ),
          ),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('افتح'));
  await tester.pumpAndSettle();
}

class _RecordingClient extends TgClient {
  List<Map<String, dynamic>> pending = [];
  final List<Map<String, dynamic>> settled = [];

  @override
  Future<List<Map<String, dynamic>>> fetchPendingMissions() async => pending;

  @override
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(
      List<Map<String, dynamic>> items) async {
    settled.addAll(items.map((e) => Map<String, dynamic>.from(e)));
    return (settled: items.length, coins: const <Map<String, dynamic>>[]);
  }
}

class _FlakyClient extends TgClient {
  bool fail = true;
  final List<List<Map<String, dynamic>>> attempts = [];

  @override
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(
      List<Map<String, dynamic>> items) async {
    attempts.add(items.map((e) => Map<String, dynamic>.from(e)).toList());
    if (fail) throw const TgApiError(503, 'unreachable');
    return (settled: items.length, coins: const <Map<String, dynamic>>[]);
  }
}
