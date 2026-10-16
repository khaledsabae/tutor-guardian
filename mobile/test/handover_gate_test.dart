// «باب التسليم» (NOOR_WAL_QANADIL_PLAN phase 4): one gate for every hand-over.
//
// What has to hold:
//  * it offers only what the child's band allows (and nothing under two);
//  * the doors play in parent mode — the session, and so the child's minutes,
//    start only after them;
//  * reduced motion is a plain fade, and the doors are laid out physically,
//    so Arabic and English open the same way;
//  * a refusal that still gets through (`surface_not_allowed`) reads calm.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/app_routes.dart';
import 'package:almorabbi/features/handover/handover_doors.dart';
import 'package:almorabbi/features/handover/handover_gate_screen.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/features/routine/screens/child_mode_lock_screen.dart';
import 'package:almorabbi/features/routine/services/child_mode_secure_storage.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart';

final Map<String, String> _secure = {};

class _FakeClient extends TgClient {
  final sessions = <String>[];
  Object? refuseWith;

  @override
  Future<Map<String, dynamic>> createChildSession(int childId,
      {String surface = 'habit'}) async {
    sessions.add(surface);
    final refusal = refuseWith;
    if (refusal != null) throw refusal;
    // No session id: nothing heartbeats, so no timer outlives the test.
    return {'token': 'child-token', 'surface': surface};
  }
}

Future<ProviderContainer> _pump(
  WidgetTester t,
  Widget home, {
  _FakeClient? client,
  Locale locale = const Locale('en'),
  bool reduceMotion = false,
}) async {
  final container = ProviderContainer(overrides: [
    tgClientProvider.overrideWithValue(client ?? _FakeClient()),
  ]);
  addTearDown(container.dispose);
  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: reduceMotion),
        child: child!,
      ),
      home: home,
    ),
  ));
  return container;
}

/// A parent screen with one button that opens the gate — so the gate is not
/// the root, and closing it on success can be seen.
Widget _host({String? ageGroup, String? surface}) => Builder(
      builder: (context) => Scaffold(
        body: Center(
          child: TextButton(
            onPressed: () => Navigator.of(context).push(AppRoutes.handoverGate(
              childId: 7,
              childName: 'Yusuf',
              ageGroup: ageGroup,
              surface: surface,
            )),
            child: const Text('open gate'),
          ),
        ),
      ),
    );

Future<void> _typePin(WidgetTester t) async {
  for (final d in ['2', '5', '8', '0']) {
    await t.tap(find.text(d));
    await t.pump();
  }
  // The PIN check reads secure storage: let it land.
  await t.pump(const Duration(milliseconds: 50));
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
          case 'containsKey':
            return _secure.containsKey(key);
          default:
            return null;
        }
      },
    );
  });

  group('offers only what the band allows', () {
    Future<void> open(WidgetTester t, String ageGroup,
        {Locale locale = const Locale('en')}) async {
      // Tall enough that every tile is built: the list is lazy, and with
      // «ركن الطفل» on top the last tile falls below the default 600 dp.
      // Reaching them on a short screen is the scroll test's job below.
      t.view.physicalSize = const Size(800, 1400) * t.view.devicePixelRatio;
      addTearDown(t.view.reset);
      await _pump(
        t,
        HandoverGateScreen(childId: 7, childName: 'Yusuf', ageGroup: ageGroup),
        locale: locale,
      );
      await t.pump();
    }

    Set<String> offered() => {
          for (final s in ['habit', 'mission', 'license', 'screen_off'])
            if (find.byKey(ValueKey('handover_$s')).evaluate().isNotEmpty) s,
        };

    for (final (band, expected) in const [
      ('2-3', {'screen_off'}),
      ('4-6', {'mission', 'screen_off'}),
      ('7-9', {'habit', 'mission', 'screen_off'}),
      ('10-12', {'habit', 'mission', 'license', 'screen_off'}),
      ('13-15', {'habit', 'mission', 'license', 'screen_off'}),
      ('16-18', {'habit', 'mission', 'screen_off'}),
    ]) {
      testWidgets('$band → $expected', (t) async {
        await open(t, band);
        expect(offered(), expected);
        expect(find.text('What will Yusuf do now?'), findsOneWidget);
      });
    }

    for (final age in ['prenatal-1', '0-3']) {
      testWidgets('$age: nothing to hand over, and the screen says why',
          (t) async {
        await open(t, age, locale: const Locale('ar'));
        expect(offered(), isEmpty);
        expect(find.textContaining('في هذا السن لا نسلّم الجهاز للطفل'),
            findsOneWidget);
        // Pointed somewhere, not a dead end.
        expect(find.text('بدائل بلا شاشة'), findsOneWidget);
      });
    }
  });

  testWidgets(
      'the doors open in parent mode; the session is opened only after them',
      (t) async {
    await setChildModePin('2580');
    final client = _FakeClient();
    final container =
        await _pump(t, _host(ageGroup: '7-9', surface: 'mission'), client: client);

    await t.tap(find.text('open gate'));
    await t.pumpAndSettle();
    // A preset surface skips the choice: straight to the PIN, which only checks.
    final lock = t.widget<ChildModeLockScreen>(find.byType(ChildModeLockScreen));
    expect(lock.verifyOnly, isTrue);
    expect(lock.surface, 'mission');

    await _typePin(t);
    await t.pump(const Duration(milliseconds: 400));

    // The doors are opening onto the child's name — and nothing is open yet.
    expect(find.byType(HandoverDoors), findsOneWidget);
    expect(find.text("Yusuf, it's your turn"), findsOneWidget);
    expect(client.sessions, isEmpty,
        reason: 'the hand-over moment must not be billed to the child');
    expect(container.read(childModeProvider).active, isFalse);

    // Back is held while the device may already be in the child's hands.
    await t.binding.handlePopRoute();
    await t.pump();
    expect(find.byType(HandoverGateScreen), findsOneWidget);
    expect(client.sessions, isEmpty);

    // The doors finish (1.2 s); only then is the session opened.
    await t.pump(HandoverGateScreen.opening);
    await t.pump();
    await t.pump(const Duration(milliseconds: 50));
    expect(client.sessions, ['mission']);
    expect(container.read(childModeProvider).active, isTrue);
    expect(container.read(childModeProvider).surface, 'mission');

    // Everything above the root goes: the child surface is the root widget.
    await t.pumpAndSettle();
    expect(find.byType(HandoverGateScreen), findsNothing);
    expect(find.text('open gate'), findsOneWidget);
  });

  testWidgets('backing out of the PIN opens nothing', (t) async {
    await setChildModePin('2580');
    final client = _FakeClient();
    await _pump(t, _host(ageGroup: '7-9'), client: client);
    await t.tap(find.text('open gate'));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const ValueKey('handover_habit')));
    await t.pumpAndSettle();
    expect(find.byType(ChildModeLockScreen), findsOneWidget);

    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('handover_habit')), findsOneWidget);
    expect(client.sessions, isEmpty);
  });

  testWidgets('a known band is refused calmly before any PIN (4-6 → habit)',
      (t) async {
    final client = _FakeClient();
    await _pump(t, _host(ageGroup: '4-6', surface: 'habit'), client: client);
    await t.tap(find.text('open gate'));
    await t.pumpAndSettle();
    expect(find.byType(ChildModeLockScreen), findsNothing);
    expect(find.text('This activity isn\'t for this age. Please choose another one.'),
        findsOneWidget);
    expect(client.sessions, isEmpty);

    await t.tap(find.text('Back'));
    await t.pumpAndSettle();
    expect(find.text('open gate'), findsOneWidget);
  });

  testWidgets(
      'surface_not_allowed from the server reads calm, not «failed to enter»',
      (t) async {
    await setChildModePin('2580');
    final client = _FakeClient()
      ..refuseWith = const TgApiError(403, 'HTTP 403',
          code: 'surface_not_allowed', details: {'error': 'surface_not_allowed'});
    // No age group, and no active profile to read one from: the gate cannot
    // filter, so the server decides — and refuses.
    final container =
        await _pump(t, _host(surface: 'habit'), client: client, locale: const Locale('ar'));
    await t.tap(find.text('open gate'));
    await t.pumpAndSettle();
    await _typePin(t);
    await t.pump(HandoverGateScreen.opening);
    await t.pumpAndSettle();

    expect(client.sessions, ['habit']);
    expect(container.read(childModeProvider).error, kChildModeSurfaceNotAllowed);
    expect(find.text('هذا النشاط ليس لهذا العمر. اختر نشاطًا آخر.'), findsOneWidget);
    expect(find.text('فشل الدخول لوضع الطفل.'), findsNothing);
    expect(container.read(childModeProvider).active, isFalse);
  });

  testWidgets('screen-off is played from the parent side: no PIN, no session',
      (t) async {
    final client = _FakeClient();
    await _pump(
      t,
      const HandoverGateScreen(childId: 7, childName: 'Yusuf', ageGroup: '2-3'),
      client: client,
    );
    await t.pump();
    await t.tap(find.byKey(const ValueKey('handover_screen_off')));
    await t.pump();
    await t.pump(const Duration(milliseconds: 500));
    expect(find.byType(ChildModeLockScreen), findsNothing);
    expect(client.sessions, isEmpty);
  });

  group('360 dp at 200% text', () {
    Future<void> small(WidgetTester t, Widget home) async {
      t.view.physicalSize = const Size(360, 640);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.reset);
      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(_FakeClient()),
      ]);
      addTearDown(container.dispose);
      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          locale: const Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: const TextScaler.linear(2)),
            child: child!,
          ),
          home: home,
        ),
      ));
      await t.pumpAndSettle();
    }

    testWidgets('the choice fits (it scrolls), every tile reachable', (t) async {
      await small(t,
          const HandoverGateScreen(childId: 7, childName: 'يوسف', ageGroup: '13-15'));
      expect(t.takeException(), isNull);
      await t.scrollUntilVisible(
          find.byKey(const ValueKey('handover_screen_off')), 200);
      expect(find.byKey(const ValueKey('handover_screen_off')), findsOneWidget);
    });

    testWidgets('a refusal and its way back fit', (t) async {
      await small(
          t,
          const HandoverGateScreen(
              childId: 7, childName: 'يوسف', ageGroup: '4-6', surface: 'habit'));
      expect(t.takeException(), isNull);
      expect(find.text('رجوع'), findsOneWidget);
    });
  });

  group('the doors', () {
    Future<void> doors(WidgetTester t, double value,
        {required bool reduce, TextDirection dir = TextDirection.ltr}) async {
      await t.pumpWidget(Directionality(
        textDirection: dir,
        child: SizedBox(
          width: 360,
          height: 640,
          child: HandoverDoors(
            progress: AlwaysStoppedAnimation(value),
            reduceMotion: reduce,
            reveal: const Text('behind'),
          ),
        ),
      ));
    }

    Finder transforms() => find.descendant(
        of: find.byType(HandoverDoors), matching: find.byType(Transform));

    double revealOpacity(WidgetTester t) => t
        .widget<FadeTransition>(find.ancestor(
            of: find.text('behind'), matching: find.byType(FadeTransition)))
        .opacity
        .value;

    testWidgets('closed: the reveal is hidden, so nothing peeks through',
        (t) async {
      await doors(t, 0, reduce: false);
      expect(revealOpacity(t), 0);
      expect(transforms(), findsNothing);
    });

    testWidgets('moving: the two leaves swing on their hinges', (t) async {
      await doors(t, 0.5, reduce: false);
      expect(transforms(), findsNWidgets(2));
    });

    testWidgets('reduced motion: no swing, a plain fade', (t) async {
      await doors(t, 0.5, reduce: true);
      expect(transforms(), findsNothing);
      final fade = t.widget<Opacity>(find.descendant(
          of: find.byType(HandoverDoors), matching: find.byType(Opacity)));
      expect(fade.opacity, closeTo(0.5, 0.2));
      expect(revealOpacity(t), closeTo(0.5, 0.01));
    });

    testWidgets('open: the leaves are gone and the reveal is fully shown',
        (t) async {
      await doors(t, 1, reduce: false);
      expect(revealOpacity(t), 1);
      expect(find.descendant(
              of: find.byType(HandoverDoors), matching: find.byType(Opacity)),
          findsNothing);
    });

    for (final dir in TextDirection.values) {
      testWidgets('laid out physically ($dir): hinges stay left and right',
          (t) async {
        await doors(t, 0.5, reduce: false, dir: dir);
        final hinges = t
            .widgetList<Transform>(transforms())
            .map((w) => w.alignment)
            .toSet();
        expect(hinges, {Alignment.centerLeft, Alignment.centerRight});
        final leaves = t
            .widgetList<Positioned>(find.descendant(
                of: find.byType(HandoverDoors),
                matching: find.byType(Positioned)))
            .toList();
        expect(leaves.map((p) => p.left).whereType<double>(), [0]);
        expect(leaves.map((p) => p.right).whereType<double>(), [0]);
      });
    }
  });
}
