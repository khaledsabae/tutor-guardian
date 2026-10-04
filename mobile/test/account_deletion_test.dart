/// Settings → Privacy: account deletion (MOBILE_API §10), erasing memory
/// (§9.6), and what the phone keeps after a deletion.
///
/// Account deletion, by effect on the (fake) server and the phone:
///   * paused (`deletion_paused_until`): when it ends, on the local clock,
///     why — and the e-mail path; no delete button;
///   * allowed: a checkbox, a final confirmation, the phone proven first, then
///     the deletion, then the phone cleared, then a page that only closes the
///     app;
///   * a pause answered at delete time, a proof that cannot complete, an older
///     server, a server error: each says what happened, and nothing on the
///     phone is cleared unless the server deleted.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/child_memory/data/local_wipe.dart';
import 'package:almorabbi/features/child_memory/data/memory_models.dart';
import 'package:almorabbi/features/child_memory/screens/account_deletion_screen.dart';
import 'package:almorabbi/features/child_memory/screens/privacy_screen.dart';
import 'package:almorabbi/features/child_memory/widgets/proof_views.dart';

import 'memory_fakes.dart';

class _Steps {
  int wipes = 0;
  bool linked = false;
  AccountDeletionSteps get steps => AccountDeletionSteps(
        wipeLocal: () async => wipes++,
        wasLinkedToGoogle: () async => linked,
      );
}

Future<_Steps> _pumpDeletion(WidgetTester tester, FakeMemoryServer server,
    {Duration? proofTimeout}) async {
  final steps = _Steps();
  await pumpMemoryApp(
    tester,
    const AccountDeletionScreen(),
    server: server,
    proof: proofTimeout == null
        ? null
        : proofFor(server, messageTimeout: proofTimeout),
    overrides: [accountDeletionStepsProvider.overrideWithValue(steps.steps)],
  );
  await settle(tester);
  return steps;
}

Future<void> _confirmDeletion(WidgetTester tester) async {
  final box = find.text('فهمت أن الحذف نهائي');
  await tester.scrollUntilVisible(box, 200,
      scrollable: find.byType(Scrollable).first);
  await tester.tap(box);
  await tester.pump();
  await tester.tap(find.widgetWithText(FilledButton, 'احذف حسابي'));
  await settle(tester);
  expect(find.text('حذف الحساب نهائيًا؟'), findsOneWidget);
  await tester.tap(find.widgetWithText(TextButton, 'احذف حسابي'));
}

void main() {
  testWidgets('paused: when it ends, why, and the e-mail path — no button',
      (tester) async {
    final until = DateTime.now().toUtc().add(const Duration(hours: 50));
    final server = FakeMemoryServer()..deletionPausedUntil = until;
    await _pumpDeletion(tester, server);

    final context = tester.element(find.byType(AccountDeletionScreen));
    expect(find.text('متوقّف مؤقتًا حتى ${formatLocalDateTime(context, until)}'),
        findsOneWidget);
    expect(find.textContaining('يتوقّف الحذف 72 ساعة'), findsOneWidget);
    expect(find.text('وإن احتجت الحذف قبل ذلك فراسلنا على support@alsaba.cloud.'),
        findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'احذف حسابي'), findsNothing);
    // What a deletion would remove is still explained.
    expect(find.text('ملفات أطفالك وتقدّمهم وأدواتهم'), findsOneWidget);
    expect(server.calls, ['GET /api/device-proof']);
  });

  testWidgets('allowed: checkbox, confirmation, proof, deletion, phone cleared',
      (tester) async {
    final server = FakeMemoryServer(); // unproven: the proof runs first
    final steps = await _pumpDeletion(tester, server);

    // Nothing happens before the parent says they understand.
    expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, 'احذف حسابي'))
            .onPressed,
        isNull);
    await _confirmDeletion(tester);
    await settle(tester);

    final proofDone = server.calls.indexOf('POST /api/device-proof/complete');
    final deleted = server.calls.indexOf('DELETE /api/privacy/account?confirm=true');
    expect(proofDone, greaterThanOrEqualTo(0));
    expect(deleted, greaterThan(proofDone), reason: 'proven before deleting');
    expect(steps.wipes, 1);
    expect(find.text('حُذف حسابك'), findsOneWidget);
    expect(find.text('أغلق التطبيق'), findsOneWidget);
    // Nothing left to go back to, once the page transition is over.
    await tester.pump(const Duration(seconds: 1));
    expect(find.byType(AccountDeletionScreen), findsNothing);
  });

  testWidgets('a pause answered at delete time: shown, nothing cleared',
      (tester) async {
    final server = FakeMemoryServer()..proven = true;
    final steps = await _pumpDeletion(tester, server);
    // The token changed between opening the screen and pressing delete.
    server.deletionPausedUntil =
        DateTime.now().toUtc().add(const Duration(hours: 72));
    await _confirmDeletion(tester);
    await settle(tester);
    expect(find.textContaining('متوقّف مؤقتًا حتى'), findsOneWidget);
    expect(steps.wipes, 0);
  });

  testWidgets('a proof that cannot complete: why, the address, nothing deleted',
      (tester) async {
    final server = FakeMemoryServer()..deliverCodes = false;
    final steps = await _pumpDeletion(tester, server,
        proofTimeout: const Duration(seconds: 20));
    await _confirmDeletion(tester);
    await tester.pump();
    expect(find.text('نتأكّد أن هذا هاتفك…'), findsOneWidget);
    await tester.pump(const Duration(seconds: 21));
    await tester.pump(const Duration(seconds: 21));
    await settle(tester);
    expect(find.text('تعذّر التأكد من هاتفك'), findsOneWidget);
    expect(find.textContaining('support@alsaba.cloud'), findsWidgets);
    expect(server.calls.where((c) => c.startsWith('DELETE')), isEmpty);
    expect(steps.wipes, 0);
    // «إعادة المحاولة» goes back to the decision, not straight to deleting.
    await tester.tap(find.text('إعادة المحاولة'));
    await settle(tester);
    expect(find.text('فهمت أن الحذف نهائي'), findsOneWidget);
  });

  testWidgets('today\'s production server: the e-mail path and the page',
      (tester) async {
    final server = FakeMemoryServer()..memorySupported = false;
    final steps = await _pumpDeletion(tester, server);
    expect(
        find.text(
            'الحذف من داخل التطبيق غير متاح الآن. يمكنك طلبه بالبريد، وننفّذه خلال 30 يومًا.'),
        findsOneWidget);
    expect(find.text('راسلنا بالبريد'), findsOneWidget);
    expect(find.text('افتح صفحة الحذف'), findsOneWidget);
    expect(steps.wipes, 0);
    expect(deleteAccountPageUri.path, '/delete-account');
  });

  testWidgets('a server error: nothing was deleted, try again',
      (tester) async {
    final server = FakeMemoryServer()
      ..proven = true
      ..deletionError = const TgApiError(500, 'boom');
    final steps = await _pumpDeletion(tester, server);
    await _confirmDeletion(tester);
    await settle(tester);
    expect(find.text('لم يُحذف شيء. حاول مرة أخرى بعد قليل.'), findsOneWidget);
    expect(steps.wipes, 0);
  });

  testWidgets('the result names other phones, and an unconfirmed Google link',
      (tester) async {
    final server = FakeMemoryServer()
      ..proven = true
      ..deletionResult = {
        'devices': 3,
        'signed_in': false,
        'deleted': {'child_profiles': 3},
        'deleted_at': '2026-10-04T18:40:00Z',
      };
    final steps = _Steps()..linked = true;
    await pumpMemoryApp(tester, const AccountDeletionScreen(),
        server: server,
        overrides: [accountDeletionStepsProvider.overrideWithValue(steps.steps)]);
    await settle(tester);
    await _confirmDeletion(tester);
    await settle(tester);
    expect(find.textContaining('(العدد: 2)'), findsOneWidget);
    expect(find.textContaining('دون تحقق لم تُحذف'), findsOneWidget);
  });

  testWidgets('the deleted page: back and the button both close the app',
      (tester) async {
    var closes = 0;
    await pumpMemoryApp(
      tester,
      AccountDeletedScreen(
        result: const AccountDeletionResult(devices: 1, signedIn: false),
        wasLinkedToGoogle: false,
        closeApp: () async => closes++,
      ),
      server: FakeMemoryServer(),
    );
    await tester.tap(find.text('أغلق التطبيق'));
    await tester.pump();
    expect(closes, 1);
    final popped = await tester.binding.handlePopRoute();
    await tester.pump();
    expect(popped, isTrue);
    expect(closes, 2);
    expect(find.text('حُذف حسابك'), findsOneWidget);
  });

  group('privacy screen', () {
    testWidgets('memory controls, then the account, then the policy',
        (tester) async {
      final server = FakeMemoryServer()
        ..proven = true
        ..children = [childJson(12, 'أحمد'), childJson(30, 'ليلى')];
      await pumpMemoryApp(tester, const PrivacyScreen(), server: server);
      await settle(tester);
      expect(find.text('ذاكرة المربّي'), findsOneWidget);
      expect(find.text('تذكّر ما أشاركه'), findsOneWidget);
      expect(find.text('ما يعرفه المربّي عن أحمد'), findsOneWidget);
      expect(find.text('ما يعرفه المربّي عن ليلى'), findsOneWidget);

      await tester.tap(find.text('امسح ذاكرة كل أطفالك'));
      await settle(tester);
      await tester.tap(find.widgetWithText(TextButton, 'حذف'));
      await settle(tester);
      expect(server.calls, contains('DELETE /api/privacy/memory'));
      expect(find.text('مُسحت الذاكرة.'), findsOneWidget);

      await tester.scrollUntilVisible(find.text('سياسة الخصوصية'), 200,
          scrollable: find.byType(Scrollable).first);
      expect(find.text('حذف الحساب'), findsOneWidget);
      expect(find.text('طلب الحذف دون التطبيق'), findsOneWidget);
    });

    testWidgets('erasing proves first when the session is not proven',
        (tester) async {
      final server = FakeMemoryServer();
      await pumpMemoryApp(tester, const PrivacyScreen(), server: server);
      await settle(tester);
      await tester.tap(find.text('امسح ذاكرة كل أطفالك'));
      await settle(tester);
      await tester.tap(find.widgetWithText(TextButton, 'حذف'));
      await settle(tester);
      expect(server.proven, isTrue);
      // Refused, proven, sent once more (§9.0: prove once, retry once).
      expect(server.calls.where((c) => c == 'DELETE /api/privacy/memory'),
          hasLength(2));
      expect(server.calls.lastIndexOf('DELETE /api/privacy/memory'),
          greaterThan(server.calls.indexOf('POST /api/device-proof/complete')));
      expect(find.text('مُسحت الذاكرة.'), findsOneWidget);
    });

    testWidgets('an older server: no memory section, deletion still offered',
        (tester) async {
      final server = FakeMemoryServer()..memorySupported = false;
      await pumpMemoryApp(tester, const PrivacyScreen(), server: server);
      await settle(tester);
      expect(find.text('ذاكرة المربّي'), findsNothing);
      expect(find.text('امسح ذاكرة كل أطفالك'), findsNothing);
      expect(find.text('حذف الحساب'), findsOneWidget);
    });

    testWidgets('English, dark, 200%: lays out cleanly', (tester) async {
      final server = FakeMemoryServer()
        ..children = [childJson(12, 'أحمد')];
      await pumpMemoryApp(tester, const PrivacyScreen(),
          server: server,
          locale: const Locale('en'),
          dark: true,
          textScale: 2.0,
          phone: const Size(320, 640));
      await settle(tester);
      for (final t in [
        'Remember what I share',
        'What Almorabbi knows about أحمد',
        'Erase memory for all your children',
        'Delete Account',
        'Privacy Policy',
      ]) {
        await tester.scrollUntilVisible(find.text(t), 200,
            scrollable: find.byType(Scrollable).first);
        await tester.pump();
        expect(tester.takeException(), isNull, reason: t);
      }
    });
  });

  group('what the phone keeps after a deletion', () {
    test('only the settings that say nothing about the family', () async {
      SharedPreferences.setMockInitialValues({
        'tg.ui_language': 'en',
        'tg.theme_mode': 'dark',
        'cached_minimum_build_number': 106,
        'tg_device_id_backup': 'fresh-id',
        'tg.analytics.once.onboarding_done': true,
        'tg.onboarding.completed': true,
        'tg.active_child_id': 12,
        'tg.active_child_name': 'أحمد',
        'identity.linked': true,
        'chat_snapshot': '{"messages": []}',
        'narration.index': '{}',
      });
      final prefs = await SharedPreferences.getInstance();
      await clearPreferencesForFreshStart(prefs);
      expect(prefs.getKeys(), {
        'tg.ui_language',
        'tg.theme_mode',
        'cached_minimum_build_number',
        'tg_device_id_backup',
        'tg.analytics.once.onboarding_done',
      });
      expect(prefs.getString('tg.ui_language'), 'en');
      expect(prefs.getInt('cached_minimum_build_number'), 106);
      expect(prefs.getBool('tg.analytics.once.onboarding_done'), isTrue);
    });

    test('a folder is emptied, not removed', () async {
      final dir = await Directory.systemTemp.createTemp('wt-memui-wipe');
      addTearDown(() => dir.delete(recursive: true));
      await File('${dir.path}/a.m4a').writeAsString('voice');
      await Directory('${dir.path}/narrations').create();
      await File('${dir.path}/narrations/b.m4a').writeAsString('voice');
      await emptyDirectory(dir);
      expect(await dir.exists(), isTrue);
      expect(await dir.list().toList(), isEmpty);
    });
  });
}
