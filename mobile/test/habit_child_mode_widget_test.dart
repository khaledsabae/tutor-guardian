import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/features/routine/screens/child_mode_lock_screen.dart';
import 'package:almorabbi/features/routine/screens/habit_child_mode_screen.dart';
import 'package:almorabbi/features/routine/services/child_mode_secure_storage.dart';
import 'package:almorabbi/state/chat_notifier.dart';

void main() {
  const fakeToken =
      'eyJhbG...TURE';

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async {
        final store = _FakeSecureStorage.store;
        switch (call.method) {
          case 'read':
            return store[call.arguments['key'] as String];
          case 'write':
            store[call.arguments['key'] as String] =
                call.arguments['value'] as String;
            return null;
          case 'delete':
            store.remove(call.arguments['key'] as String);
            return null;
          default:
            return null;
        }
      },
    );
  });

  tearDown(() {
    _FakeSecureStorage.store.clear();
  });

  group('HabitChildModeScreen', () {
    testWidgets('renders habit cards and marks completed via submit',
        (tester) async {
      final fake = _FakeTgClient()
        ..todayHabitsJson = {
          'child_id': 7,
          'date': '2026-07-07',
          'habits': [
            {
              'category': 'worship',
              'habit_name': 'صلاة الفجر',
              'source': 'default',
            },
          ],
          'events': [],
        }
        ..submitResult = true;

      final container = ProviderContainer(
        overrides: [tgClientProvider.overrideWithValue(fake)],
      );
      addTearDown(container.dispose);

      // Seed the secure storage with a token and enter the notifier.
      await saveChildToken(fakeToken);
      await setChildModeActive(true);
      container.read(childModeProvider.notifier).state =
          const ChildModeState(active: true, childId: 7);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            locale: Locale('ar'),
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: HabitChildModeScreen(),
          ),
        ),
      );
      await tester.pump();

      // The screen loads while day is null, so a spinner is expected first.
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Manually set the day so the list renders.
      container.read(childModeProvider.notifier).state = const ChildModeState(
        active: true,
        childId: 7,
        day: HabitDay(
          childId: 7,
          date: '2026-07-07',
          habits: [
            TodayHabitItem(
              category: HabitCategory.worship,
              habitName: 'صلاة الفجر',
              source: 'default',
            ),
          ],
          events: [],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('صلاة الفجر'), findsOneWidget);
      expect(find.text('تم'), findsOneWidget);

      // Submit as completed.
      await tester.tap(find.text('تم'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('تأكيد'));
      await tester.pumpAndSettle();

      expect(fake.submitBody, isNotNull);
      expect(fake.submitBody!['status'], 'completed');
      expect(fake.submitBody!['habit_name'], 'صلاة الفجر');
      expect(fake.submitBody!['device_timestamp'], isNotEmpty);
    });

    testWidgets('exit button redirects to ChildModeLockScreen',
        (tester) async {
      final fake = _FakeTgClient()
        ..todayHabitsJson = {
          'child_id': 7,
          'date': '2026-07-07',
          'habits': [],
          'events': [],
        };

      final container = ProviderContainer(
        overrides: [tgClientProvider.overrideWithValue(fake)],
      );
      addTearDown(container.dispose);

      await saveChildToken(fakeToken);
      await setChildModeActive(true);
      container.read(childModeProvider.notifier).state = const ChildModeState(
        active: true,
        childId: 7,
        day: HabitDay(childId: 7, date: '2026-07-07', habits: [], events: []),
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            locale: Locale('ar'),
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: HabitChildModeScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.logout));
      await tester.pumpAndSettle();
      await tester.tap(find.text('خروج'));
      await tester.pumpAndSettle();

      expect(find.byType(ChildModeLockScreen), findsOneWidget);
    });

    testWidgets('expired session renders the ExpiredGuard loading state',
        (tester) async {
      final fake = _FakeTgClient();

      final container = ProviderContainer(
        overrides: [tgClientProvider.overrideWithValue(fake)],
      );
      addTearDown(container.dispose);

      await saveChildToken(fakeToken);
      await setChildModeActive(true);
      container.read(childModeProvider.notifier).state = const ChildModeState(
        active: true,
        childId: 7,
        error: kChildModeErrorSessionExpired,
        day: HabitDay(childId: 7, date: '2026-07-07', habits: [], events: []),
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            locale: Locale('ar'),
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: HabitChildModeScreen(),
          ),
        ),
      );
      await tester.pump();

      // The screen should replace itself with the ExpiredGuard, which renders
      // a loading spinner while it redirects to the lock screen.
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('ميزان العادات'), findsNothing);
    });
  });
}

class _FakeSecureStorage {
  static final Map<String, String> store = {};
}

class _FakeTgClient extends TgClient {
  Map<String, dynamic> todayHabitsJson = {
    'child_id': 1,
    'date': '2026-07-07',
    'habits': [],
    'events': [],
  };
  bool submitResult = true;
  Map<String, dynamic>? submitBody;

  @override
  Future<Map<String, dynamic>> fetchChildTodayHabits({
    required String childToken,
  }) async =>
      todayHabitsJson;

  @override
  Future<Map<String, dynamic>> createChildHabitEvent({
    required String childToken,
    required Map<String, dynamic> body,
  }) async {
    submitBody = body;
    if (submitResult) return {'ok': true};
    throw const TgApiError(500, 'fail');
  }
}
