/// «الاسم» — phase 2 of docs/NOOR_WAL_QANADIL_PLAN.md.
///
/// The child used to be created as «طفلي» and the name was never asked. Now
/// the creation wait asks it, optionally, with a title that follows the field
/// («درب طفلك» → «درب سارة»). Pinned here:
///   * the field is optional: a parent who ignores it is on Today the moment
///     the child exists — no extra wait, no extra request, «طفلي» stays;
///   * «لاحقًا» keeps the default;
///   * typing updates the title live;
///   * a name confirmed before the child exists, or after (the overlay holds
///     only a parent who was mid-name), is saved through the edit screen's
///     PATCH, and the on-disk profile — what Today greets — changes at once;
///   * a refused PATCH puts the server's name back;
///   * `child_added` fires exactly once, whatever happens to the name;
///   * the validation: trimmed, at most 30, not digits only, and the add/edit
///     forms' own rule underneath.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/analytics.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/onboarding/screens/onboarding_screen.dart';
import 'package:almorabbi/features/program/data/child_name.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart' show tgClientProvider;

const _question = 'ما اسم طفلك؟';
const _hint = 'مثلًا: سارة، أحمد، ليلى';
const _later = 'لاحقًا';
const _done = 'تمّ';
const _cta = 'ابدأ الرحلة';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late List<(String, Map<String, Object>?)> events;

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    events = [];
    Analytics.debugSink = (name, params) => events.add((name, params));
  });
  tearDown(() => Analytics.debugSink = null);

  int count(String name) => events.where((e) => e.$1 == name).length;
  Object? outcome() =>
      events.lastWhere((e) => e.$1 == 'onboarding_name').$2?['outcome'];

  /// Language → age → the value page, overlay not yet up.
  Future<({ProviderContainer container, List<bool> gate})> pumpToCta(
    WidgetTester tester,
    _FakeClient fake,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(overrides: [
      tgClientProvider.overrideWithValue(fake),
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ]);
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);
    // main.dart watches the gate from launch; so does this test, or a first
    // read after the prefs write would already say «done».
    final gate = <bool>[];
    container.listen<bool>(onboardingCompletedProvider, (_, v) => gate.add(v),
        fireImmediately: true);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: const Locale('ar'),
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: child!,
        ),
        home: const OnboardingScreen(),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('العربية'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('4–6 سنوات'));
    await tester.pumpAndSettle();
    return (container: container, gate: gate);
  }

  /// Tears the tree down so the overlay's line timer and the stars' delays
  /// never outlive the test.
  Future<void> finish(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 5));
  }

  /// pumpAndSettle never settles while the field has focus — its cursor
  /// blinks. Enough plain frames for the create → prefs → hold chain.
  Future<void> frames(WidgetTester tester) async {
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
  }

  String? storedName(ProviderContainer c) =>
      c.read(onboardingStorageProvider).activeChildName;

  testWidgets('the field is optional — ignoring it changes nothing',
      (tester) async {
    final fake = _FakeClient();
    final app = await pumpToCta(tester, fake);
    await tester.tap(find.text(_cta));
    await tester.pump();

    // The wait asks, without autofocus — a keyboard that opened by itself
    // would hold every parent here.
    expect(find.text(_question), findsOneWidget);
    expect(find.text(_hint), findsOneWidget);
    expect(find.text(_later), findsOneWidget);
    expect(find.text('درب طفلك'), findsOneWidget);
    expect(tester.testTextInput.isVisible, isFalse);

    // The child comes back: straight on, as before.
    fake.create.complete();
    await tester.pumpAndSettle();
    expect(app.gate.last, isTrue, reason: 'the shell takes over at once');
    expect(find.text(_question), findsNothing);
    expect(fake.createdNames, ['طفلي']);
    expect(fake.renames, isEmpty, reason: 'no name, no second request');
    expect(storedName(app.container), 'طفلي');
    expect(count('child_added'), 1);
    expect(outcome(), 'ignored');
    await finish(tester);
  });

  testWidgets('typing updates the title live', (tester) async {
    final fake = _FakeClient();
    await pumpToCta(tester, fake);
    await tester.tap(find.text(_cta));
    await tester.pump();

    await tester.enterText(find.byType(TextField), 'سارة');
    await tester.pump();
    expect(find.text('درب سارة'), findsOneWidget);
    expect(find.text('درب طفلك'), findsNothing);

    await tester.enterText(find.byType(TextField), '  ');
    await tester.pump();
    expect(find.text('درب طفلك'), findsOneWidget,
        reason: 'blank is no name — the default title comes back');

    await tester.tap(find.text(_later));
    fake.create.complete();
    await tester.pumpAndSettle();
    await finish(tester);
  });

  testWidgets('«لاحقًا» keeps the default name', (tester) async {
    final fake = _FakeClient();
    final app = await pumpToCta(tester, fake);
    await tester.tap(find.text(_cta));
    await tester.pump();

    await tester.enterText(find.byType(TextField), 'سارة');
    await tester.pump();
    await tester.tap(find.text(_later));
    await tester.pump();
    expect(find.text(_question), findsNothing, reason: 'the field is gone');
    expect(find.text('درب طفلك'), findsOneWidget);

    fake.create.complete();
    await tester.pumpAndSettle();
    expect(app.gate.last, isTrue);
    expect(fake.renames, isEmpty);
    expect(storedName(app.container), 'طفلي');
    expect(outcome(), 'later');
    await finish(tester);
  });

  testWidgets('a name typed while waiting is saved once the child exists',
      (tester) async {
    final fake = _FakeClient()..renameGate = Completer<void>();
    final app = await pumpToCta(tester, fake);
    await tester.tap(find.text(_cta));
    await tester.pump();

    // Still typing when the child comes back: the overlay holds them — the
    // lines all ticked — instead of yanking the field from under the keyboard.
    await tester.enterText(find.byType(TextField), '  سارة ');
    fake.create.complete();
    await frames(tester);
    expect(find.text(_question), findsOneWidget);
    expect(find.byIcon(Icons.check_circle_outline), findsNWidgets(2));
    expect(app.gate.last, isFalse, reason: 'held for the name');

    await tester.tap(find.text(_done));
    await tester.pumpAndSettle();
    // Today greets by name before the server has answered...
    expect(app.gate.last, isTrue);
    expect(storedName(app.container), 'سارة');
    expect(app.container.read(activeChildProfileProvider)?.name, 'سارة');
    // ...through the edit screen's own PATCH, trimmed.
    expect(fake.renames, [(1, 'سارة', '4-6')]);
    fake.renameGate!.complete();
    await tester.pumpAndSettle();
    expect(storedName(app.container), 'سارة');
    expect(count('child_added'), 1, reason: 'a rename is not a new child');
    expect(outcome(), 'named');
    await finish(tester);
  });

  testWidgets('a name confirmed before the child exists is saved without a '
      'hold', (tester) async {
    final fake = _FakeClient();
    final app = await pumpToCta(tester, fake);
    await tester.tap(find.text(_cta));
    await tester.pump();

    await tester.enterText(find.byType(TextField), 'ليلى');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();
    expect(find.text(_question), findsNothing, reason: 'answered');
    expect(find.text('درب ليلى'), findsOneWidget);

    fake.create.complete();
    await tester.pumpAndSettle();
    expect(app.gate.last, isTrue);
    expect(fake.renames, [(1, 'ليلى', '4-6')]);
    expect(storedName(app.container), 'ليلى');
    expect(count('child_added'), 1);
    await finish(tester);
  });

  testWidgets('a refused rename puts the server name back', (tester) async {
    final fake = _FakeClient()..renameFails = true;
    final app = await pumpToCta(tester, fake);
    await tester.tap(find.text(_cta));
    await tester.pump();
    await tester.enterText(find.byType(TextField), 'أحمد');
    await tester.tap(find.text(_done));
    fake.create.complete();
    await tester.pumpAndSettle();

    expect(fake.renames, hasLength(1));
    expect(storedName(app.container), 'طفلي',
        reason: 'Today must not greet a name the server never took');
    expect(app.gate.last, isTrue, reason: 'onboarding still finishes');
    await finish(tester);
  });

  testWidgets('a digits-only name is refused in place', (tester) async {
    final fake = _FakeClient();
    await pumpToCta(tester, fake);
    await tester.tap(find.text(_cta));
    await tester.pump();

    await tester.enterText(find.byType(TextField), '١٢٣');
    await tester.tap(find.text(_done));
    await tester.pump();
    expect(find.text('اكتب اسمًا لا أرقامًا'), findsOneWidget);
    expect(find.text(_question), findsOneWidget, reason: 'still asking');

    await tester.tap(find.text(_later));
    fake.create.complete();
    await tester.pumpAndSettle();
    expect(fake.renames, isEmpty);
    await finish(tester);
  });

  testWidgets('a name confirmed before a failed create goes into the retry',
      (tester) async {
    final fake = _FakeClient()..createFailures = 1;
    final app = await pumpToCta(tester, fake);
    await tester.tap(find.text(_cta));
    await tester.pump();
    await tester.enterText(find.byType(TextField), 'سارة');
    await tester.tap(find.text(_done));
    fake.create.complete();
    await tester.pumpAndSettle();
    expect(app.gate.last, isFalse, reason: 'the first create failed');

    await tester.tap(find.text(_cta));
    await tester.pumpAndSettle();
    // The first request left with the default before the name was typed.
    expect(fake.createdNames, ['طفلي', 'سارة']);
    expect(fake.renames, isEmpty, reason: 'the name rode in the create');
    expect(storedName(app.container), 'سارة');
    expect(count('child_added'), 1, reason: 'one child was created');
    await finish(tester);
  });

  group('validation', () {
    final l10n = lookupAppLocalizations(const Locale('ar'));

    test('the add/edit rule is unchanged', () {
      expect(childNameError(l10n, null), l10n.addChildNameRequired);
      expect(childNameError(l10n, '   '), l10n.addChildNameRequired);
      expect(childNameError(l10n, 'س' * 80), isNull);
      expect(childNameError(l10n, 'س' * 81), l10n.addChildNameTooLong);
    });

    test('onboarding trims, caps at 30, and refuses digits only', () {
      expect(onboardingNameError(l10n, '  سارة  '), isNull);
      expect(onboardingNameError(l10n, 'س' * 30), isNull);
      expect(onboardingNameError(l10n, 'س' * 31), l10n.onbNameTooLong);
      for (final digits in ['123', '١٢٣', '۱۲۳', '12 34']) {
        expect(onboardingNameError(l10n, digits), l10n.onbNameDigitsOnly,
            reason: digits);
      }
      expect(onboardingNameError(l10n, 'سارة 2'), isNull,
          reason: 'a digit in a name is not a digits-only name');
      expect(onboardingNameError(l10n, ''), l10n.addChildNameRequired);
    });

    test('the field caps input at the same length', () {
      expect(onboardingNameMaxLength, 30);
    });
  });
}

/// createChild waits on [create] (and fails [createFailures] times first);
/// updateChild records the rename and can wait or refuse.
class _FakeClient extends TgClient {
  _FakeClient()
      : super.forTesting(
          baseUrl: 'http://x',
          httpClient: _IdleHttpClient(),
          storage: _MemStorage(),
        );

  final create = Completer<void>();
  int createFailures = 0;
  final createdNames = <String>[];

  Completer<void>? renameGate;
  bool renameFails = false;
  final renames = <(int, String?, String?)>[];

  @override
  Future<Map<String, dynamic>> createChild({
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
    String? birthMonth,
  }) async {
    createdNames.add(name);
    await create.future;
    if (createFailures > 0) {
      createFailures--;
      throw const TgApiError(500, 'boom');
    }
    return _child(name, ageGroup);
  }

  @override
  Future<Map<String, dynamic>> updateChild({
    required int childId,
    String? name,
    String? ageGroup,
    String? gender,
    String? avatarEmoji,
    String? birthMonth,
    bool clearBirthMonth = false,
  }) async {
    renames.add((childId, name, ageGroup));
    await renameGate?.future;
    if (renameFails) throw const TgApiError(503, 'down');
    return _child(name!, ageGroup!);
  }

  static Map<String, dynamic> _child(String name, String ageGroup) => {
        'id': 1,
        'name': name,
        'age_group': ageGroup,
        'gender': null,
        'avatar_emoji': null,
        'created_at': '2026-10-14T12:00:00',
        'updated_at': '2026-10-14T12:00:00',
      };
}

class _IdleHttpClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    throw StateError('unexpected network in test: ${request.url}');
  }
}

class _MemStorage implements FlutterSecureStorage {
  final Map<String, String> _store = {};

  @override
  Future<String?> read({
    required String key,
    Object? aOptions,
    Object? iOptions,
    Object? lOptions,
    Object? webOptions,
    Object? mOptions,
    Object? wOptions,
  }) async =>
      _store[key];

  @override
  Future<void> write({
    required String key,
    required String? value,
    Object? aOptions,
    Object? iOptions,
    Object? lOptions,
    Object? webOptions,
    Object? mOptions,
    Object? wOptions,
  }) async {
    if (value == null) {
      _store.remove(key);
    } else {
      _store[key] = value;
    }
  }

  @override
  Future<void> delete({
    required String key,
    Object? aOptions,
    Object? iOptions,
    Object? lOptions,
    Object? webOptions,
    Object? mOptions,
    Object? wOptions,
  }) async =>
      _store.remove(key);

  @override
  dynamic noSuchMethod(Invocation i) => super.noSuchMethod(i);
}
