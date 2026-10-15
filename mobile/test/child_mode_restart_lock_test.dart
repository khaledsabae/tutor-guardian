// A restart in the middle of child mode — or after its session ended — lands
// on the hand-back screen, never on the parent's app.
//
// restore() used to end child mode on every restart: the session id dies with
// the process, so it closed the lot and opened the parent's app — the
// assistant, settings, every child's profile — with no PIN. A child on «أعِد
// الجهاز إلى أهلك» only had to force-close the app and open it again. The same
// flip happened when the server stopped accepting the child's token (a 401
// cleared child mode), and one launch after the mission card's "I'm going".

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/handover/child_hand_back.dart';
import 'package:almorabbi/features/missions/child_mission_screen.dart';
import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/features/routine/screens/child_mode_lock_screen.dart';
import 'package:almorabbi/features/routine/screens/habit_child_mode_screen.dart';
import 'package:almorabbi/features/routine/services/child_mode_secure_storage.dart';
import 'package:almorabbi/features/routine/widgets/child_mode_gate.dart';
import 'package:almorabbi/features/routine/widgets/child_mode_shell.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart';

const _pin = '1234';
const _parentApp = 'PARENT APP';
const _waiting = 'WAITING';
const _returnLine = 'أعِد الجهاز إلى أهلك — شكرًا لك';

final Map<String, String> _secure = {};

/// The server as a restarted app meets it. [tokenAlive] false is a session
/// the server has already reaped: every child request is a 401.
class _Server extends TgClient {
  _Server({this.tokenAlive = false});

  final bool tokenAlive;
  final calls = <String>[];

  @override
  Future<Map<String, dynamic>> fetchChildTodayHabits({
    required String childToken,
  }) async {
    calls.add('today');
    if (!tokenAlive) throw TgClient.childSessionExpired;
    return {'child_id': 7, 'date': '2026-10-15', 'habits': [], 'events': []};
  }

  @override
  Future<Map<String, dynamic>> createChildHabitEvent({
    required String childToken,
    required Map<String, dynamic> body,
  }) async {
    calls.add('event');
    if (!tokenAlive) throw TgClient.childSessionExpired;
    return {'ok': true};
  }

  @override
  Future<Map<String, dynamic>> createChildSession(int childId,
      {String surface = 'habit'}) async {
    calls.add('session');
    return {'token': 'fresh', 'session_id': 99, 'surface': surface};
  }

  @override
  Future<void> endChildSession({
    required String childToken,
    required int sessionId,
    String reason = 'completed',
  }) async {
    calls.add('end:$sessionId:$reason');
  }

  @override
  Future<ChildMissionToday?> fetchChildMission(String childToken) async =>
      throw const TgApiError(503, 'down'); // "no mission today"
}

/// What the last run left on disk: child mode on, a token, a PIN.
Future<void> _childModeOnDisk({bool pin = true, int? childId = 7}) async {
  await saveChildToken('old-token');
  await setChildModeActive(true);
  if (pin) await setChildModePin(_pin);
  if (childId != null) {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(kChildModeChildIdKey, childId);
  }
}

ProviderContainer _launch(TgClient server) {
  final container = ProviderContainer(overrides: [
    tgClientProvider.overrideWithValue(server),
  ]);
  addTearDown(container.dispose);
  return container;
}

/// The app's root as main.dart builds it, with stand-ins for the parent's
/// app and the boot splash.
Future<ProviderContainer> _boot(WidgetTester t, TgClient server) async {
  final container = _launch(server);
  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(
      locale: Locale('ar'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: ChildModeGate(
        parentApp: Scaffold(body: Text(_parentApp)),
        waiting: Scaffold(body: Text(_waiting)),
      ),
    ),
  ));
  return container;
}

Future<void> _typePin(WidgetTester t, String pin) async {
  for (final d in pin.split('')) {
    await t.tap(find.text(d));
    await t.pump();
  }
  await t.pumpAndSettle();
}

Future<void> _openExit(WidgetTester t) async {
  await t.tap(find.byIcon(Icons.logout));
  await t.pumpAndSettle();
  await t.tap(find.text('خروج'));
  await t.pumpAndSettle();
}

void main() {
  setUp(() {
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
  });

  testWidgets('secure storage that never answers does not hold the launch',
      (t) async {
    t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) => Completer<Object?>().future,
    );
    await _boot(t, _Server());
    await t.pump();
    expect(find.text(_waiting), findsOneWidget);
    await t.pump(kChildModeRestoreTimeout + const Duration(milliseconds: 50));
    await t.pumpAndSettle();
    expect(find.text(_parentApp), findsOneWidget);
  });

  group('restore() after a restart', () {
    for (final alive in [false, true]) {
      final token = alive ? 'a token the server still accepts' : 'a dead token';
      test('child mode on disk, $token: still child mode, on the hand-back '
          'screen', () async {
        await _childModeOnDisk();
        final server = _Server(tokenAlive: alive);
        final container = _launch(server);

        await container.read(childModeProvider.notifier).restore();

        final state = container.read(childModeProvider);
        expect(state.active, isTrue,
            reason: 'a restart must not hand the parent\'s app to the child');
        expect(state.error, kChildModeHandedBack);
        expect(state.sessionId, isNull, reason: 'nothing runs unmetered');
        expect(state.childId, 7);
        expect(await isChildModeActive(), isTrue);
        // No round trip: it could only put a spinner in front of the screen,
        // and its 401 renewal opened a session nothing would close.
        expect(server.calls, isEmpty);
      });
    }

    test('nothing on disk: a parent\'s ordinary launch is untouched', () async {
      final server = _Server();
      final container = _launch(server);
      await container.read(childModeProvider.notifier).restore();
      expect(container.read(childModeProvider).active, isFalse);
      expect(container.read(childModeProvider).error, isNull);
      expect(server.calls, isEmpty);
    });

    test('no PIN on the device: nothing could open the lock, so it does not '
        'close', () async {
      await _childModeOnDisk(pin: false);
      final container = _launch(_Server());
      await container.read(childModeProvider.notifier).restore();
      expect(container.read(childModeProvider).active, isFalse);
      expect(await isChildModeActive(), isFalse);
    });

    test('a session opened in this launch is never stomped', () async {
      await _childModeOnDisk();
      final container = _launch(_Server());
      final notifier = container.read(childModeProvider.notifier);
      notifier.state =
          const ChildModeState(active: true, childId: 7, sessionId: 5);
      await notifier.restore();
      expect(container.read(childModeProvider).sessionId, 5);
      expect(container.read(childModeProvider).error, isNull);
    });

    test('the way out is the PIN — offline, with a dead token, without the '
        'child id', () async {
      await _childModeOnDisk(childId: null);
      final server = _Server();
      final container = _launch(server);
      final notifier = container.read(childModeProvider.notifier);
      await notifier.restore();
      expect(container.read(childModeProvider).active, isTrue);

      expect(await notifier.exit('0000'), isFalse);
      expect(container.read(childModeProvider).active, isTrue);

      expect(await notifier.exit(_pin), isTrue);
      expect(container.read(childModeProvider).active, isFalse);
      expect(await isChildModeActive(), isFalse);
      expect(await getChildToken(), isNull);
      expect(server.calls, isEmpty);
    });
  });

  group('the app\'s root after a restart', () {
    testWidgets('child mode on, session over: the parent\'s app never shows '
        'without the PIN — not even for a frame', (t) async {
      await _childModeOnDisk();
      await _boot(t, _Server());

      // Frame by frame through the boot, then settled.
      for (var i = 0; i < 5; i++) {
        expect(find.text(_parentApp), findsNothing, reason: 'frame $i');
        await t.pump(const Duration(milliseconds: 16));
      }
      await t.pumpAndSettle();
      expect(find.text(_parentApp), findsNothing);
      expect(find.byType(ChildHandBackScreen), findsOneWidget);
      expect(find.text(_returnLine), findsOneWidget);

      // Back does not leave it either.
      final popped = await t.binding.handlePopRoute();
      await t.pumpAndSettle();
      expect(popped, isTrue, reason: 'the hand-back screen swallows Back');
      expect(find.byType(ChildHandBackScreen), findsOneWidget);

      // Exit, a wrong PIN: still locked.
      await _openExit(t);
      expect(t.widget<ChildModeLockScreen>(find.byType(ChildModeLockScreen))
          .isExit, isTrue);
      await _typePin(t, '0000');
      expect(find.text('الرمز غير صحيح.'), findsOneWidget);
      expect(find.text(_parentApp), findsNothing);

      // The parent's PIN: the parent's app.
      await _typePin(t, _pin);
      expect(find.text(_parentApp), findsOneWidget);
      expect(find.byType(ChildHandBackScreen), findsNothing);
      expect(await isChildModeActive(), isFalse);
    });

    testWidgets('nothing on disk: the parent\'s app opens as before',
        (t) async {
      await _boot(t, _Server());
      await t.pumpAndSettle();
      expect(find.text(_parentApp), findsOneWidget);
      expect(find.byType(ChildModeShell), findsNothing);
    });
  });

  group('a token the server stopped accepting, mid-session', () {
    test('refresh: still child mode, waiting for the PIN', () async {
      await _childModeOnDisk();
      final container = _launch(_Server());
      final notifier = container.read(childModeProvider.notifier);
      notifier.state = const ChildModeState(
          active: true, childId: 7, sessionId: 5, surface: 'habit');

      await notifier.refresh();

      final state = container.read(childModeProvider);
      expect(state.active, isTrue);
      expect(state.error, kChildModeErrorSessionExpired);
      expect(state.sessionId, isNull);
      expect(await isChildModeActive(), isTrue);
    });

    test('a check-in: still child mode, waiting for the PIN', () async {
      await _childModeOnDisk();
      final container = _launch(_Server());
      final notifier = container.read(childModeProvider.notifier);
      notifier.state = const ChildModeState(
          active: true, childId: 7, sessionId: 5, surface: 'habit');

      final ok = await notifier.submit(
          const HabitItem(
              category: HabitCategory.worship, habitName: 'fajr'),
          'completed');

      expect(ok, isFalse);
      expect(container.read(childModeProvider).active, isTrue);
      expect(container.read(childModeProvider).error,
          kChildModeErrorSessionExpired);
      expect(await isChildModeActive(), isTrue);
    });

    testWidgets('renders the hand-back screen with Exit, not a spinner or '
        'the PIN pad in entry mode', (t) async {
      await _childModeOnDisk();
      final container = _launch(_Server());
      container.read(childModeProvider.notifier).state = const ChildModeState(
        active: true,
        childId: 7,
        surface: 'habit',
        error: kChildModeErrorSessionExpired,
      );
      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          locale: Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: ChildModeShell(child: HabitChildModeScreen()),
        ),
      ));
      await t.pumpAndSettle();
      expect(find.byType(ChildHandBackScreen), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.byType(ChildModeLockScreen), findsNothing);
      await _openExit(t);
      expect(t.widget<ChildModeLockScreen>(find.byType(ChildModeLockScreen))
          .isExit, isTrue);
    });
  });

  group('the mission card\'s "I\'m going"', () {
    testWidgets('closes the session and the app, but not child mode — the '
        'next launch is the hand-back screen', (t) async {
      await _childModeOnDisk();
      final systemCalls = <String>[];
      t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          SystemChannels.platform, (call) async {
        systemCalls.add(call.method);
        return null;
      });
      addTearDown(() => t.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null));

      final server = _Server(tokenAlive: true);
      final container = _launch(server);
      container.read(childModeProvider.notifier).state = const ChildModeState(
          active: true, childId: 7, sessionId: 5, surface: 'mission');
      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          locale: Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: ChildModeShell(child: HabitChildModeScreen()),
        ),
      ));
      await t.pumpAndSettle();
      expect(find.byType(ChildMissionScreen), findsOneWidget);

      await t.tap(find.text('حسنًا، سأخرج'));
      await t.pumpAndSettle();

      expect(server.calls, contains('end:5:completed'));
      expect(systemCalls, contains('SystemNavigator.pop'));
      expect(await isChildModeActive(), isTrue,
          reason: 'leaving child mode here opened the parent\'s app one '
              'launch later');

      // The next launch.
      final next = _launch(_Server());
      await next.read(childModeProvider.notifier).restore();
      expect(next.read(childModeProvider).active, isTrue);
      expect(next.read(childModeProvider).error, kChildModeHandedBack);
    });
  });
}
