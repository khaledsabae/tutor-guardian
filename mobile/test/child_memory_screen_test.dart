/// «ما يعرفه المربّي عن <اسم>» (MOBILE_API §9.2–§9.3).
///
/// The parent's controls, each by effect on the (fake) server: facts by
/// category with the name swapped in on the device; a pending health note
/// confirmed; one fact edited (the words sent only when they changed),
/// rejected, deleted; a note added; everything about the child deleted; and
/// the switch — OFF works with no proof and through a pause. Then the states
/// in front of the facts: confirming the phone, a pause, a proof that cannot
/// complete, a server without memory. And the layout in English, dark, 200%.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/child_memory/screens/child_memory_screen.dart';
import 'package:almorabbi/features/child_memory/widgets/memory_errors.dart';
import 'package:almorabbi/features/child_memory/widgets/memory_switch_tile.dart';
import 'package:almorabbi/features/child_memory/widgets/proof_views.dart';

import 'memory_fakes.dart';

const _screen = ChildMemoryScreen(childId: 12, childName: 'أحمد');

FakeMemoryServer _serverWithFacts() => FakeMemoryServer()
  ..proven = true
  ..children = [childJson(12, 'أحمد'), childJson(30, 'ليلى')]
  ..facts[12] = [
    factJson(1, 12, category: 'temperament', fact: 'طفلي يخاف من الظلام'),
    factJson(2, 12,
        category: 'goal',
        fact: 'نريد أن يحفظ طفلي سورة الملك',
        source: 'parent_manual'),
    factJson(3, 12,
        category: 'health_note',
        fact: 'لدى طفلي حساسية من الفول السوداني',
        status: 'pending'),
    factJson(4, 12,
        category: 'temperament', fact: 'طفلي عنيد جدًا', status: 'rejected'),
    factJson(5, 12, category: 'challenge', fact: 'الطفل ب تغار من طفلي'),
  ];

Future<void> _openMenu(WidgetTester tester, String factText) async {
  final tile = find.ancestor(
      of: find.text(factText), matching: find.byType(Row)).first;
  await tester.tap(find.descendant(
      of: tile, matching: find.byIcon(Icons.more_vert_rounded)));
  await settle(tester);
}

void main() {
  testWidgets('facts by category, with the names put back on the device',
      (tester) async {
    final server = _serverWithFacts();
    await pumpMemoryApp(tester, _screen, server: server);
    await settle(tester);

    expect(find.text('ما يعرفه المربّي عن أحمد'), findsOneWidget);
    expect(find.text('أحمد يخاف من الظلام'), findsOneWidget);
    expect(find.text('الطبع'), findsOneWidget);
    // «الطفل ب» is the second child by profile id: ليلى.
    expect(find.text('ليلى تغار من أحمد'), findsOneWidget);
    // A rejected fact is kept on the server only so it is not learned
    // again — never shown.
    expect(find.text('أحمد عنيد جدًا'), findsNothing);
    // The pending health note waits for a yes/no, outside the categories.
    expect(find.text('هل هذا صحيح؟'), findsOneWidget);
    expect(find.text('لدى أحمد حساسية من الفول السوداني'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('ما لا يحفظه المربّي أبدًا'), 300,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('ما لا يحفظه المربّي أبدًا'), findsOneWidget);
    expect(server.calls.where((c) => c.contains('device-proof')), isEmpty);
  });

  testWidgets('a pending health note is confirmed with one tap',
      (tester) async {
    final server = _serverWithFacts();
    await pumpMemoryApp(tester, _screen, server: server);
    await settle(tester);

    await tester.tap(find.text('نعم، صحيح'));
    await settle(tester);
    expect(server.calls, contains('PATCH /api/children/12/memory/3'));
    expect(server.lastPatch, {'status': 'active'});
    // Reloaded: now an active fact under its category.
    expect(find.text('هل هذا صحيح؟'), findsNothing);
    expect(find.text('ملاحظات صحية'), findsOneWidget);
  });

  testWidgets('edit sends the words only when the parent changed them',
      (tester) async {
    final server = _serverWithFacts();
    await pumpMemoryApp(tester, _screen, server: server);
    await settle(tester);

    // 1. Only the category changes: the swapped-in name is never sent back.
    await _openMenu(tester, 'أحمد يخاف من الظلام');
    await tester.tap(find.text('تعديل').last);
    await settle(tester);
    expect(find.text('تعديل المعلومة'), findsOneWidget);
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await settle(tester);
    await tester.tap(find.text('التحديات').last);
    await settle(tester);
    await tester.tap(find.text('حفظ'));
    await settle(tester);
    expect(server.lastPatch, {'category': 'challenge'});

    // 2. New words go back as typed (the server re-redacts names).
    await _openMenu(tester, 'أحمد يخاف من الظلام');
    await tester.tap(find.text('تعديل').last);
    await settle(tester);
    await tester.enterText(find.byType(TextField), 'أحمد يخاف من الظلام قليلًا');
    await tester.pump();
    await tester.tap(find.text('حفظ'));
    await settle(tester);
    expect(server.lastPatch, {'fact': 'أحمد يخاف من الظلام قليلًا'});
  });

  testWidgets('reject and delete one fact', (tester) async {
    final server = _serverWithFacts();
    await pumpMemoryApp(tester, _screen, server: server);
    await settle(tester);

    await _openMenu(tester, 'أحمد يخاف من الظلام');
    await tester.tap(find.text('ليس صحيحًا').last);
    await settle(tester);
    expect(server.lastPatch, {'status': 'rejected'});
    expect(find.text('لن يتعلّم المربّي هذه المعلومة مرة أخرى.'), findsOneWidget);
    expect(find.text('أحمد يخاف من الظلام'), findsNothing);

    await _openMenu(tester, 'نريد أن يحفظ أحمد سورة الملك');
    await tester.tap(find.text('حذف').last);
    await settle(tester);
    expect(find.text('حذف هذه المعلومة؟'), findsOneWidget);
    await tester.tap(find.widgetWithText(TextButton, 'حذف'));
    await settle(tester);
    expect(server.calls, contains('DELETE /api/children/12/memory/2'));
    expect(find.text('نريد أن يحفظ أحمد سورة الملك'), findsNothing);
  });

  testWidgets('add a note; something memory never keeps is refused gently',
      (tester) async {
    final server = _serverWithFacts();
    await pumpMemoryApp(tester, _screen, server: server);
    await settle(tester);

    await tester.scrollUntilVisible(find.text('أضف معلومة'), 300,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text('أضف معلومة'));
    await settle(tester);
    await tester.enterText(find.byType(TextField), 'يحب القصص قبل النوم');
    await tester.pump(); // the frame that enables «حفظ»
    await tester.tap(find.text('حفظ'));
    await settle(tester);
    expect(server.calls, contains('POST /api/children/12/memory'));
    expect(server.facts[12]!.first['fact'], 'يحب القصص قبل النوم');

    server.addError = coded(422, 'sensitive', message: 'هذه المعلومة مما لا يحفظه');
    await tester.scrollUntilVisible(find.text('أضف معلومة'), 300,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text('أضف معلومة'));
    await settle(tester);
    await tester.enterText(find.byType(TextField), 'يأخذ دواء كذا');
    await tester.pump();
    await tester.tap(find.text('حفظ'));
    await settle(tester);
    expect(
        find.text(
            'هذه المعلومة مما لا يحفظه المربّي، مثل الأدوية أو الأمور الحساسة، فلم نحفظها.'),
        findsOneWidget);
  });

  testWidgets('delete everything about the child, after a confirmation',
      (tester) async {
    final server = _serverWithFacts();
    await pumpMemoryApp(tester, _screen, server: server);
    await settle(tester);

    final forget = find.text('احذف كل ما يعرفه المربّي عن أحمد');
    await tester.scrollUntilVisible(forget, 300,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(forget);
    await settle(tester);
    await tester.tap(find.widgetWithText(TextButton, 'حذف'));
    await settle(tester);
    expect(server.calls, contains('DELETE /api/children/12/memory'));
    expect(find.text('لا يعرف المربّي شيئًا عن أحمد بعد'), findsOneWidget);
  });

  testWidgets('memory OFF needs no proof — even during a pause',
      (tester) async {
    final until = DateTime.now().toUtc().add(const Duration(hours: 70));
    final server = _serverWithFacts()
      ..proven = false
      ..cooldownUntil = until;
    await pumpMemoryApp(tester, _screen, server: server);
    await settle(tester);

    // The pause is explained, with when it ends…
    expect(find.textContaining('متوقّف مؤقتًا حتى'), findsOneWidget);
    // …and the switch is still there.
    expect(find.byType(MemorySwitchTile), findsOneWidget);
    expect(find.textContaining('مفعّل لكل أطفالك'), findsOneWidget);

    await tester.tap(find.byType(Switch));
    await settle(tester);
    expect(server.calls, contains('PUT /api/children/memory/settings enabled=false'));
    expect(server.enabled, isFalse);
    expect(server.starts, 0, reason: 'switching off never runs a challenge');
    expect(find.textContaining('متوقّف لكل أطفالك'), findsOneWidget);
  });

  testWidgets('an unproven session is confirmed first, then the facts appear',
      (tester) async {
    final server = _serverWithFacts()
      ..proven = false
      ..deliverCodes = false;
    await pumpMemoryApp(tester, _screen, server: server);
    await settle(tester);

    expect(find.text('نتأكّد أن هذا هاتفك…'), findsOneWidget);
    expect(server.starts, 1);

    server.sendPendingCode(); // FCM delivers the silent code
    await settle(tester);
    expect(server.proven, isTrue);
    expect(find.text('أحمد يخاف من الظلام'), findsOneWidget);
  });

  testWidgets('a proof that cannot complete: why, the address, a retry',
      (tester) async {
    final server = _serverWithFacts()
      ..proven = false
      ..deliverCodes = false;
    final proof = proofFor(server, messageTimeout: const Duration(seconds: 20));
    await pumpMemoryApp(tester, _screen, server: server, proof: proof);
    await settle(tester);
    expect(find.text('نتأكّد أن هذا هاتفك…'), findsOneWidget);

    // Two waits of 20 s, then the failure (§9.0.1: start once more, no more).
    await tester.pump(const Duration(seconds: 21));
    await tester.pump(const Duration(seconds: 21));
    await settle(tester);
    expect(server.starts, 2);
    expect(find.text('تعذّر التأكد من هاتفك'), findsOneWidget);
    expect(find.textContaining('support@alsaba.cloud'), findsOneWidget);
    expect(find.byType(MemorySwitchTile), findsOneWidget);

    // Retry, and this time the code comes.
    server.deliverCodes = true;
    await tester.tap(find.text('إعادة المحاولة'));
    await settle(tester);
    expect(server.proven, isTrue);
    expect(find.text('أحمد يخاف من الظلام'), findsOneWidget);
  });

  testWidgets('a server without memory says it is not available yet',
      (tester) async {
    final server = FakeMemoryServer()..memorySupported = false;
    await pumpMemoryApp(tester, _screen, server: server);
    await settle(tester);
    expect(find.text('هذه الميزة غير متاحة بعد، وستظهر هنا حين تصبح جاهزة.'),
        findsOneWidget);
    expect(server.starts, 0);
  });

  testWidgets('English, dark, 200% text: lays out cleanly, content keeps its '
      'own direction', (tester) async {
    final server = _serverWithFacts()
      ..facts[12]!.add(factJson(9, 12,
          category: 'school', fact: 'My child likes maths', lang: 'en'));
    await pumpMemoryApp(tester, _screen,
        server: server,
        locale: const Locale('en'),
        dark: true,
        textScale: 2.0);
    await settle(tester);
    expect(tester.takeException(), isNull);
    expect(find.text('What Almorabbi knows about أحمد'), findsOneWidget);

    for (final text in [
      'Remember what I share',
      'أحمد يخاف من الظلام',
      'أحمد likes maths',
      'Add a note',
      'What Almorabbi never keeps',
    ]) {
      await tester.scrollUntilVisible(find.text(text), 300,
          scrollable: find.byType(Scrollable).first);
      await tester.pump();
      expect(tester.takeException(), isNull, reason: text);
    }
    // The chrome is LTR; each fact reads in its own direction.
    expect(Directionality.of(tester.element(find.text('What Almorabbi knows about أحمد'))),
        TextDirection.ltr);
    await tester.scrollUntilVisible(find.text('أحمد يخاف من الظلام'), -300,
        scrollable: find.byType(Scrollable).first);
    expect(tester.widget<Text>(find.text('أحمد يخاف من الظلام')).textDirection,
        TextDirection.rtl);
    await tester.scrollUntilVisible(find.text('أحمد likes maths'), 300,
        scrollable: find.byType(Scrollable).first);
    expect(tester.widget<Text>(find.text('أحمد likes maths')).textDirection,
        TextDirection.ltr);
  });

  testWidgets('a paused delete or reset says until when, on the local clock',
      (tester) async {
    // describeActionFailure is what the child-delete and reset snackbars show.
    final until = DateTime.utc(2026, 10, 7, 18, 30);
    final e = TgApiError(403, 'لحماية بيانات أسرتك تُتاح هذه الخطوة لاحقًا.',
        code: 'device_proof_cooldown',
        details: {'available_at': until.toIso8601String()});
    late String text;
    late String when;
    await pumpMemoryApp(
      tester,
      Builder(builder: (context) {
        text = describeActionFailure(context, e);
        when = formatLocalDateTime(context, until);
        return const SizedBox();
      }),
      server: FakeMemoryServer(),
    );
    expect(text, startsWith('متوقّف مؤقتًا حتى $when'));
    expect(text, contains('لحماية بيانات أسرتك'));
    // Local time, not UTC: the hour shown is the device's own.
    final local = until.toLocal();
    expect(when, contains('${local.minute}'.padLeft(2, '0')));
  });
}
