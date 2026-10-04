/// «جرّبت النصيحة؟ نفعت؟» — the follow-up on Today and behind the
/// `/followup/{id}` push (MOBILE_API §9.4).
///
/// Pinned by effect on the (fake) server: the card shows the active child's
/// due follow-up first, between ① and ② on Today; an answer is one tap plus
/// an optional note, and the card is gone afterwards; "don't ask" dismisses;
/// a dropped note is said gently; the card never starts a proof and hides on
/// an unproven session or an older server, appearing once a proof lands; the
/// deep link shows a closed follow-up's result instead of buttons.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/deeplink/deep_link_handler.dart';
import 'package:almorabbi/features/home/widgets/today_loop_cards.dart';
import 'package:almorabbi/features/child_memory/widgets/followup_sheet.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/screens/home_screen.dart';

import 'memory_fakes.dart';

const _ahmad =
    ActiveChildProfile(id: 12, name: 'أحمد', ageGroup: '7-9', avatarEmoji: '🧒');

Widget _today() => Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [TodayLoopCards(profile: _ahmad)],
      ),
    );

FakeMemoryServer _server() => FakeMemoryServer()
  ..proven = true
  ..children = [childJson(12, 'أحمد'), childJson(30, 'ليلى')]
  ..due = [
    followupJson(8, 30, strategy: 'ركن هادئ لطفلي حين يغضب الطفل أ'),
    followupJson(7, 12),
  ];

/// A button that opens the sheet the way the deep link does.
Widget _deepLinkHome(int id) => Scaffold(
      body: Builder(
        builder: (context) => Center(
          child: TextButton(
            onPressed: () => showFollowupSheet(context,
                followupId: id, source: FollowupSource.push),
            child: const Text('open'),
          ),
        ),
      ),
    );

void main() {
  testWidgets('the active child\'s due follow-up, with the name put back',
      (tester) async {
    final server = _server();
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);

    expect(find.text('متابعة مع أحمد'), findsOneWidget);
    expect(find.text('هل جرّبت: روتين نوم ثابت مع قصة قبل النوم لأحمد؟'),
        findsOneWidget);
    for (final label in ['نجحت', 'نجحت جزئيًا', 'لم تنجح', 'لم أجرّب بعد']) {
      expect(find.text(label), findsOneWidget);
    }
    expect(server.calls.firstWhere((c) => c.contains('followups/due')),
        'GET /api/children/followups/due tz=${DateTime.now().timeZoneOffset.inMinutes}');
  });

  testWidgets('another child\'s follow-up when the active one has none',
      (tester) async {
    final server = _server()..due.removeWhere((d) => d['child_id'] == 12);
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    expect(find.text('متابعة مع ليلى'), findsOneWidget);
    // Her own placeholder is «طفلي»; her brother keeps his letter («الطفل أ»:
    // the first profile by id).
    expect(find.text('هل جرّبت: ركن هادئ لليلى حين يغضب أحمد؟'), findsOneWidget);
  });

  testWidgets('one tap, an optional note, a thank-you — and the card is gone',
      (tester) async {
    final server = _server();
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);

    await tester.tap(find.text('لم تنجح'));
    await settle(tester);
    // The sheet opens with that answer already chosen.
    final chip = tester.widget<ChoiceChip>(
        find.widgetWithText(ChoiceChip, 'لم تنجح'));
    expect(chip.selected, isTrue);
    await tester.enterText(find.byType(TextField), 'بكى كثيرًا في الليلة الأولى');
    await tester.pump();
    await tester.tap(find.text('إرسال'));
    await settle(tester);

    expect(server.calls, contains(
        'POST /api/children/followups/7/answer outcome=didnt_work '
        'note=بكى كثيرًا في الليلة الأولى'));
    expect(find.text('شكرًا لك 🤍'), findsOneWidget);
    expect(
        find.text(
            'لا بأس، فلكل طفل طريقه. لن يكرّر المربّي هذه النصيحة، وسيقترح بديلًا.'),
        findsOneWidget);

    await tester.tap(find.text('تم'));
    await settle(tester);
    expect(find.text('متابعة مع أحمد'), findsNothing,
        reason: 'answered: the due list was asked again');
    expect(find.text('متابعة مع ليلى'), findsOneWidget);
  });

  testWidgets('a note memory never keeps is dropped, and the parent is told',
      (tester) async {
    final server = _server()..noteDropped = true;
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    await tester.tap(find.text('نجحت').first);
    await settle(tester);
    await tester.tap(find.text('إرسال'));
    await settle(tester);
    expect(find.text('حُفظت إجابتك، ولم نحفظ ملاحظتك لأنها مما لا يحفظه المربّي.'),
        findsOneWidget);
    expect(find.text('الحمد لله! سيتذكّر المربّي أن هذا نفع.'), findsOneWidget);
  });

  testWidgets('"don\'t ask about this" dismisses it from the card',
      (tester) async {
    final server = _server();
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    await tester.tap(find.text('لا تسألني عن هذا'));
    await settle(tester);
    expect(server.calls, contains('POST /api/children/followups/7/dismiss'));
    expect(find.text('لن نسألك عن هذا مرة أخرى.'), findsOneWidget);
    expect(find.text('متابعة مع أحمد'), findsNothing);
  });

  testWidgets('unproven: hidden, no challenge started — until a proof lands',
      (tester) async {
    final server = _server()..proven = false;
    final proof = proofFor(server);
    await pumpMemoryApp(tester, _today(), server: server, proof: proof);
    await settle(tester);
    expect(find.text('متابعة مع أحمد'), findsNothing);
    expect(server.starts, 0, reason: 'a Today card never starts a challenge');

    // The launch's background proof lands…
    await proof.prove();
    await settle(tester);
    // …and the card comes in without anyone asking.
    expect(find.text('متابعة مع أحمد'), findsOneWidget);
  });

  testWidgets('today\'s production server: nothing at all', (tester) async {
    final server = FakeMemoryServer()..memorySupported = false;
    await pumpMemoryApp(tester, _today(), server: server);
    await settle(tester);
    expect(find.byType(Card), findsNothing);
    expect(find.text('متابعة'), findsNothing);
    expect(find.text('خطة أحمد هذا الأسبوع'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('on Today the loop sits between ① and ②', (tester) async {
    final server = _HomeServer()..proven = true;
    server.due = [followupJson(7, 12)];
    server.plans[12] = planJson(12);
    await pumpMemoryApp(
        tester, HomeScreen(onGoToTab: (_) {}), server: server);
    await settle(tester);

    double top(Finder f) => tester.getTopLeft(f).dy;
    final step = find.text('خطوة اليوم مع أحمد');
    final followup = find.text('متابعة مع أحمد');
    final plan = find.text('خطة أحمد هذا الأسبوع');
    final ask = find.text('اسأل المربّي');
    await tester.scrollUntilVisible(ask, 200,
        scrollable: find.byType(Scrollable).first);
    for (final f in [followup, plan, ask]) {
      expect(f, findsOneWidget);
    }
    expect(top(followup), lessThan(top(plan)));
    expect(top(plan), lessThan(top(ask)));
    if (step.evaluate().isNotEmpty) expect(top(step), lessThan(top(followup)));
  });

  group('the /followup/{id} deep link', () {
    test('parses only follow-up links', () {
      expect(DeepLinkHandler.followupIdFromPath('/followup/7'), 7);
      expect(DeepLinkHandler.followupIdFromPath('/followup/123/'), 123);
      expect(DeepLinkHandler.followupIdFromPath('/followup/abc'), isNull);
      expect(DeepLinkHandler.followupIdFromPath('/followups/7'), isNull);
      expect(DeepLinkHandler.followupIdFromPath('/l/7'), isNull);
    });

    testWidgets('a pending one asks; the answer is sent', (tester) async {
      final server = _server()..followups[7] = followupJson(7, 12);
      await pumpMemoryApp(tester, _deepLinkHome(7), server: server);
      await tester.tap(find.text('open'));
      await settle(tester);
      expect(server.calls, contains('GET /api/children/followups/7'));
      expect(find.text('هل جرّبت: روتين نوم ثابت مع قصة قبل النوم لأحمد؟'),
          findsOneWidget);
      // Nothing chosen yet: «إرسال» waits for an answer.
      expect(
          tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'إرسال'))
              .onPressed,
          isNull);
      await tester.tap(find.text('نجحت جزئيًا'));
      await tester.pump();
      await tester.tap(find.text('إرسال'));
      await settle(tester);
      expect(server.calls,
          contains('POST /api/children/followups/7/answer outcome=partly note=-'));
      expect(find.text('خطوة طيبة. سيبني المربّي على ما نجح منها.'),
          findsOneWidget);
    });

    testWidgets('an answered one shows its result, not the buttons',
        (tester) async {
      final server = _server()
        ..followups[7] =
            followupJson(7, 12, status: 'answered', outcome: 'worked');
      await pumpMemoryApp(tester, _deepLinkHome(7), server: server);
      await tester.tap(find.text('open'));
      await settle(tester);
      expect(find.text('أجبت: نجحت'), findsOneWidget);
      expect(find.byType(ChoiceChip), findsNothing);
    });

    testWidgets('answered elsewhere meanwhile: the result, no error',
        (tester) async {
      final server = _server()..followups[7] = followupJson(7, 12);
      await pumpMemoryApp(tester, _deepLinkHome(7), server: server);
      await tester.tap(find.text('open'));
      await settle(tester);
      // Another phone answers while this sheet is open.
      server.followups[7]!
        ..['status'] = 'answered'
        ..['outcome'] = 'didnt_try';
      await tester.tap(find.text('نجحت'));
      await tester.pump();
      await tester.tap(find.text('إرسال'));
      await settle(tester);
      expect(find.text('أجبت: لم أجرّب بعد'), findsOneWidget);
    });

    testWidgets('a follow-up that no longer exists says so', (tester) async {
      final server = _server();
      await pumpMemoryApp(tester, _deepLinkHome(99), server: server);
      await tester.tap(find.text('open'));
      await settle(tester);
      expect(find.text('لم نجد هذه المتابعة.'), findsOneWidget);
    });

    testWidgets('an unproven session is confirmed first', (tester) async {
      final server = _server()
        ..proven = false
        ..deliverCodes = false
        ..followups[7] = followupJson(7, 12);
      await pumpMemoryApp(tester, _deepLinkHome(7), server: server);
      await tester.tap(find.text('open'));
      await settle(tester);
      expect(find.text('نتأكّد أن هذا هاتفك…'), findsOneWidget);
      server.sendPendingCode();
      await settle(tester);
      expect(find.byType(ChoiceChip), findsNWidgets(4));
    });
  });

  testWidgets('English, dark, 200%: card and sheet lay out cleanly',
      (tester) async {
    final server = _server()
      ..due = [
        followupJson(7, 12,
            strategy: 'A fixed bedtime routine with a story for my child',
            lang: 'en'),
      ];
    await pumpMemoryApp(tester, _today(),
        server: server,
        locale: const Locale('en'),
        dark: true,
        textScale: 2.0,
        phone: const Size(320, 640));
    await settle(tester);
    expect(tester.takeException(), isNull);
    expect(find.text('Follow-up with أحمد'), findsOneWidget);
    expect(
        find.text('Did you try: A fixed bedtime routine with a story for أحمد?'),
        findsOneWidget);
    await tester.tap(find.text("Didn't work"));
    await settle(tester);
    expect(tester.takeException(), isNull);
    expect(find.text('Optional note: what happened?'), findsOneWidget);
  });
}

/// The memory fake, plus what the rest of Today reads (as the existing Today
/// test does: everything else fails fast, the way an unreachable server does).
class _HomeServer extends FakeMemoryServer {
  @override
  Future<Map<String, dynamic>> getChildProgress(int childId,
          {String? pathId}) async =>
      {'child_id': childId, 'lessons': []};

  @override
  Future<Map<String, dynamic>> getPathsList(
          {String? ageGroup, String? domain}) async =>
      throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> getNextLesson(String ageGroup,
          {int? childId}) async =>
      throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> getCoachTip(int childId) async =>
      throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> getCommunityStats() async =>
      throw const TgApiError(503, 'offline');

  @override
  Future<Map<String, dynamic>> fetchChildDay(int childId) =>
      Completer<Map<String, dynamic>>().future; // stays loading
}
