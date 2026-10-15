// How a child surface ends: on a screen that asks for the device back, with
// child mode still on — so the only way out is the parent's PIN.
//
// The licence's "I'm done" used to call exitWithoutPin(), which flipped the
// root to the parent's app: a child who finished the licence was handed the
// assistant, settings and every child's profile with no PIN in the way.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/handover/child_hand_back.dart';
import 'package:almorabbi/features/license/child_license_screen.dart';
import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/features/routine/screens/child_mode_lock_screen.dart';
import 'package:almorabbi/features/routine/screens/habit_child_mode_screen.dart';
import 'package:almorabbi/features/routine/services/child_mode_secure_storage.dart';
import 'package:almorabbi/features/routine/widgets/child_mode_shell.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart';

final Map<String, String> _secure = {};

class _FakeClient extends TgClient {
  final ended = <String>[];

  @override
  Future<Map<String, dynamic>> fetchChildLicense(String childToken) async =>
      {'scenario': null}; // every situation answered: the "done" screen

  @override
  Future<void> endChildSession({
    required String childToken,
    required int sessionId,
    String reason = 'completed',
  }) async {
    ended.add('$sessionId:$reason');
  }

  @override
  Future<Map<String, dynamic>> fetchChildTodayHabits({
    required String childToken,
  }) async =>
      {'child_id': 7, 'date': '2026-10-14', 'habits': [], 'events': []};
}

Future<ProviderContainer> _pump(
  WidgetTester t,
  ChildModeState state,
  _FakeClient client, {
  Locale locale = const Locale('ar'),
}) async {
  final container = ProviderContainer(overrides: [
    tgClientProvider.overrideWithValue(client),
  ]);
  addTearDown(container.dispose);
  container.read(childModeProvider.notifier).state = state;
  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const ChildModeShell(child: HabitChildModeScreen()),
    ),
  ));
  await t.pumpAndSettle();
  return container;
}

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    _secure.clear();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async {
        final key = call.arguments['key'] as String?;
        switch (call.method) {
          case 'read':
            return _secure[key];
          case 'write':
            _secure[key!] = call.arguments['value'] as String;
            return null;
          case 'delete':
            _secure.remove(key);
            return null;
          default:
            return null;
        }
      },
    );
    await saveChildToken('child-token');
    await setChildModeActive(true);
  });

  group('the licence\'s "I\'m done"', () {
    testWidgets(
        'closes the session but stays in child mode, and asks for the device '
        'back', (t) async {
      final client = _FakeClient();
      final container = await _pump(
        t,
        const ChildModeState(
            active: true, childId: 7, sessionId: 5, surface: 'license'),
        client,
      );
      expect(find.byType(ChildLicenseScreen), findsOneWidget);

      await t.tap(find.text('حسنًا، سأخرج'));
      await t.pumpAndSettle();

      // The session is closed — nothing is billed while the device waits…
      expect(client.ended, ['5:completed']);
      final state = container.read(childModeProvider);
      expect(state.sessionId, isNull);
      // …but this is still child mode, on screen and on disk. The old exit
      // ended here with the parent's app in the child's hands.
      expect(state.active, isTrue);
      expect(state.childId, 7);
      expect(await isChildModeActive(), isTrue);
      expect(find.byType(ChildHandBackScreen), findsOneWidget);
      expect(find.text('أعِد الجهاز إلى أهلك — شكرًا لك'), findsOneWidget);

      // The way out is the parent's: Exit, then the PIN.
      await t.tap(find.byIcon(Icons.logout));
      await t.pumpAndSettle();
      await t.tap(find.text('خروج'));
      await t.pumpAndSettle();
      final lock =
          t.widget<ChildModeLockScreen>(find.byType(ChildModeLockScreen));
      expect(lock.isExit, isTrue);
    });

    test('never leaves child mode without the PIN', () {
      final source = File('lib/features/license/child_license_screen.dart')
          .readAsStringSync()
          // Code only: the doc comment explains the old exit by name.
          .split('\n')
          .where((l) => !l.trimLeft().startsWith('//'))
          .join('\n');
      final leave = source.split('Future<void> _leave()')[1].split('\n  }')[0];
      expect(leave, isNot(contains('exitWithoutPin')));
      expect(leave, contains('endSession'));
    });
  });

  group('a session that ends under the child', () {
    for (final (code, text) in const [
      (kChildModeBudgetSpent, 'انتهت مدة اليوم'),
      (kChildModeOffline, 'انقطع الاتصال'),
    ]) {
      testWidgets('$code: the hand-back screen, not a live-looking checklist',
          (t) async {
        await _pump(
          t,
          ChildModeState(
            active: true,
            childId: 7,
            surface: 'habit',
            error: code,
            day: const HabitDay(
                childId: 7, date: '2026-10-14', habits: [], events: []),
          ),
          _FakeClient(),
        );
        expect(find.byType(ChildHandBackScreen), findsOneWidget);
        expect(find.textContaining(text), findsOneWidget);
        expect(find.text('أعِد الجهاز إلى أهلك — شكرًا لك'), findsOneWidget);
        // Child mode is still the frame around it.
        expect(find.byIcon(Icons.logout), findsOneWidget);
      });
    }

    testWidgets('English parity, neutral family wording', (t) async {
      await _pump(
        t,
        const ChildModeState(
          active: true,
          childId: 7,
          surface: 'habit',
          error: kChildModeBudgetSpent,
          day: HabitDay(childId: 7, date: '2026-10-14', habits: [], events: []),
        ),
        _FakeClient(),
        locale: const Locale('en'),
      );
      expect(
          find.text('Please hand the phone back to your family — thank you'),
          findsOneWidget);
    });

    testWidgets('a running session keeps its surface', (t) async {
      await _pump(
        t,
        const ChildModeState(
          active: true,
          childId: 7,
          sessionId: 9,
          surface: 'habit',
          day: HabitDay(childId: 7, date: '2026-10-14', habits: [], events: []),
        ),
        _FakeClient(),
      );
      expect(find.byType(ChildHandBackScreen), findsNothing);
      expect(find.text('ميزان العادات'), findsOneWidget);
    });
  });
}
