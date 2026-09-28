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
import 'package:almorabbi/widgets/ui/loading_view.dart';
import 'package:almorabbi/features/routine/widgets/child_mode_shell.dart';

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

      // The screen loads while day is null: a skeleton, not a bare spinner (E3).
      expect(find.byType(LoadingView), findsOneWidget);

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

      // Submit as completed: one tap, no confirmation dialog (UX-3, G3).
      await tester.tap(find.text('تم'));
      await tester.pump();
      expect(find.text('تأكيد'), findsNothing);
      // Shown as logged at once, but held for the undo window.
      expect(find.text('تم التسجيل'), findsOneWidget);
      expect(fake.submitBody, isNull);

      await tester.pump(ChildModeNotifier.undoWindow);
      await tester.pumpAndSettle();

      expect(fake.submitBody, isNotNull);
      expect(fake.submitBody!['status'], 'completed');
      expect(fake.submitBody!['habit_name'], 'صلاة الفجر');
      expect(fake.submitBody!['device_timestamp'], isNotEmpty);
    });

    Future<ProviderContainer> pumpWithHabit(
      WidgetTester tester,
      _FakeTgClient fake, {
      HabitStreak streak = const HabitStreak(),
    }) async {
      final container = ProviderContainer(
        overrides: [tgClientProvider.overrideWithValue(fake)],
      );
      addTearDown(container.dispose);
      await saveChildToken(fakeToken);
      await setChildModeActive(true);
      container.read(childModeProvider.notifier).state = ChildModeState(
        active: true,
        childId: 7,
        day: HabitDay(
          childId: 7,
          date: '2026-07-07',
          habits: const [
            TodayHabitItem(
              category: HabitCategory.worship,
              habitName: 'صلاة الفجر',
              source: 'default',
            ),
          ],
          events: const [],
          streak: streak,
        ),
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
      return container;
    }

    testWidgets('Undo inside the window means nothing is ever sent',
        (tester) async {
      final fake = _FakeTgClient();
      await pumpWithHabit(tester, fake);

      await tester.tap(find.text('تم'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500)); // snackbar in
      await tester.tap(find.text('تراجع'));
      await tester.pump();

      expect(find.text('تم التسجيل'), findsNothing,
          reason: 'the card offers the buttons again');
      await tester.pump(ChildModeNotifier.undoWindow * 2);
      await tester.pumpAndSettle();
      expect(fake.submitBody, isNull);
    });

    testWidgets('crossing a streak milestone celebrates, once', (tester) async {
      final fake = _FakeTgClient();
      final container = await pumpWithHabit(
        tester,
        fake,
        streak: const HabitStreak(days: 2),
      );
      expect(find.text('يومان متتاليان'), findsOneWidget);

      await tester.tap(find.text('تم'));
      await tester.pump(ChildModeNotifier.undoWindow);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));

      expect(find.text('ثلاثة أيام من المواظبة!'), findsOneWidget);
      expect(container.read(childModeProvider).day!.streak.days, 3);
    });

    test('a second stage of the same habit is a no-op', () {
      final n = ChildModeNotifier(_FakeTgClient());
      const item = HabitItem(category: HabitCategory.worship, habitName: 'x');
      expect(n.stage(item, 'completed'), isNotNull);
      expect(n.stage(item, 'completed'), isNull);
      n.undo('x');
      n.dispose();
    });

    testWidgets('a staged log is sent when the session ends early',
        (tester) async {
      final fake = _FakeTgClient();
      final container = await pumpWithHabit(tester, fake);

      await tester.tap(find.text('تم'));
      await tester.pump();
      await container.read(childModeProvider.notifier).flushStaged();
      expect(fake.submitBody?['habit_name'], 'صلاة الفجر');
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
            // Exit lives in the child-mode frame now (UX-4), above every
            // child surface rather than in one screen's app bar.
            home: ChildModeShell(child: HabitChildModeScreen()),
          ),
        ),
      );
      // Past the hand-over card, which covers the surface while it shows.
      await tester.pump(ChildModeShell.handoffHold);
      await tester.pumpAndSettle();
      expect(find.textContaining('وضع الطفل'), findsOneWidget);

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
