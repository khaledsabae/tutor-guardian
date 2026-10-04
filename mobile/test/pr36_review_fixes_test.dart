/// PR #36 review — one group per item, each by effect.
///
///  1. After an account deletion the app really ends (finishAndRemoveTask),
///     with exit(0) only as the fallback.
///  2. Edits never send back a name the app inserted; the limit is on the
///     stored form.
///  3. A phone signed in with Google is linked again from the proven session
///     before the deletion; a kept Google record is said, not hidden.
///  4. A lost answer is not "nothing was deleted": the old token tells, no
///     session is minted meanwhile, and the next launch finishes the job.
///  5. Memory off pauses the follow-up loop.
///  6. No link opens a parent screen — /followup included — over child mode;
///     it waits, and opens when the parent leaves (PR #34's hold).
///  7. Only the launch registration may raise the permission dialog.
///  8. A sibling letter that resolves to the child itself is not shown as
///     the child's own name.
///  9. Only FastAPI's bare 404 hides a feature; deleting a child refreshes
///     what was keyed by it.
/// 10. The parent's voice recordings are excluded from backup where they
///     really are.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/app_closer.dart';
import 'package:almorabbi/features/child_memory/data/local_wipe.dart';
import 'package:almorabbi/features/child_memory/data/memory_models.dart';
import 'package:almorabbi/features/child_memory/data/pending_deletion.dart';
import 'package:almorabbi/features/child_memory/data/placeholder_names.dart';
import 'package:almorabbi/features/child_memory/screens/account_deletion_screen.dart';
import 'package:almorabbi/features/child_memory/screens/child_memory_screen.dart';
import 'package:almorabbi/features/child_memory/widgets/followup_sheet.dart';
import 'package:almorabbi/features/child_memory/widgets/memory_switch_tile.dart';
import 'package:almorabbi/features/deeplink/deep_link_handler.dart';
import 'package:almorabbi/features/home/widgets/today_loop_cards.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/settings_providers.dart';
import 'package:almorabbi/features/push/push_service.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/features/screen_off/narration_store.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';
import 'package:almorabbi/state/chat_notifier.dart';

import 'memory_fakes.dart';

class _MemStorage implements FlutterSecureStorage {
  final Map<String, String> store = {};

  @override
  Future<String?> read({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async =>
      store[key];

  @override
  Future<void> write({
    required String key,
    required String? value,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    if (value == null) {
      store.remove(key);
    } else {
      store[key] = value;
    }
  }

  @override
  Future<void> delete({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    store.remove(key);
  }

  @override
  Future<void> deleteAll({
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    store.clear();
  }

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

http.Response _json(Object body, [int status = 200]) => http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

/// A client over a scripted server, holding the session `s1`/`tok1` of the
/// device `dev-old`. [seen] records `METHOD path` for every request.
({TgClient client, List<String> seen, _MemStorage storage}) _client(
    Future<http.Response> Function(http.Request req) answer) {
  final seen = <String>[];
  final storage = _MemStorage()
    ..store['tg_device_id'] = 'dev-old'
    ..store['tg_session_id'] = 's1'
    ..store['tg_token'] = 'tok1';
  final client = TgClient.forTesting(
    baseUrl: 'http://api.test',
    storage: storage,
    httpClient: MockClient((req) async {
      seen.add('${req.method} ${req.url.path}');
      return answer(req);
    }),
  );
  return (client: client, seen: seen, storage: storage);
}

class _ActiveChildMode extends ChildModeNotifier {
  _ActiveChildMode(super.client) {
    state = const ChildModeState(active: true, childId: 12);
  }
  void leave() => state = const ChildModeState();
}

const _ahmad =
    ActiveChildProfile(id: 12, name: 'أحمد', ageGroup: '7-9', avatarEmoji: '🧒');

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    AppL10n.current = lookupAppLocalizations(const Locale('ar'));
  });

  // ── 1 ──────────────────────────────────────────────────────────────────
  group('1 · after a deletion the app really ends', () {
    testWidgets('it asks the activity to finish and remove its task',
        (tester) async {
      final calls = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          appChannel, (call) async {
        calls.add(call.method);
        return true;
      });
      addTearDown(() => tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(appChannel, null));
      int? exited;
      await closeAppForFreshStart(exitProcess: (code) => exited = code);
      expect(calls, ['finishAndRemoveTask']);
      expect(exited, isNull, reason: 'the activity ends; no exit needed');
    });

    testWidgets('no channel (iOS, an old build), an error, or no reply: exit(0)',
        (tester) async {
      addTearDown(() => tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(appChannel, null));
      int? exited;

      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          appChannel, (call) async => throw MissingPluginException());
      await closeAppForFreshStart(exitProcess: (code) => exited = code);
      expect(exited, 0, reason: 'no native side → the fallback');

      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          appChannel, (call) async => throw PlatformException(code: 'x'));
      exited = null;
      await closeAppForFreshStart(exitProcess: (code) => exited = code);
      expect(exited, 0);

      // A reply that never comes is bounded too.
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          appChannel, (call) => Completer<Object?>().future);
      exited = null;
      final closing = closeAppForFreshStart(
          exitProcess: (code) => exited = code,
          timeout: const Duration(seconds: 3));
      await tester.pump(const Duration(seconds: 4));
      await closing;
      expect(exited, 0);
    });

    testWidgets('the deleted page closes through it by default',
        (tester) async {
      final calls = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          appChannel, (call) async {
        calls.add(call.method);
        return true;
      });
      addTearDown(() => tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(appChannel, null));
      await pumpMemoryApp(
        tester,
        const AccountDeletedScreen(
          result: AccountDeletionResult(devices: 1, signedIn: false),
          wasLinkedToGoogle: false,
        ),
        server: FakeMemoryServer(),
      );
      await tester.tap(find.text('أغلق التطبيق'));
      await tester.pump();
      expect(calls, ['finishAndRemoveTask']);
    });

    // Source, deliberately: no host test runs the Android activity.
    test('MainActivity finishes the task on that channel, engine not cached',
        () {
      final kt = File(
              'android/app/src/main/kotlin/com/alsaba/almorabbi/MainActivity.kt')
          .readAsStringSync();
      expect(kt, contains('const val APP_CHANNEL = "${appChannel.name}"'));
      expect(kt, contains('"finishAndRemoveTask" ->'));
      expect(kt, contains('finishAndRemoveTask()'));
      expect(kt, contains('super.configureFlutterEngine(flutterEngine)'),
          reason: 'the plugins must still be registered');
      for (final cached in [
        'FlutterEngineCache',
        'provideFlutterEngine',
        'getCachedEngineId',
        'shouldDestroyEngineWithHost',
      ]) {
        expect(kt.contains(cached), isFalse,
            reason: 'a cached engine would survive the activity: $cached');
      }
    });
  });

  // ── 2 ──────────────────────────────────────────────────────────────────
  group('2 · names the app inserted never go back', () {
    final family = [
      const FamilyMember(id: 12, name: 'أحمد'),
      const FamilyMember(id: 30, name: 'نور'),
    ];

    test('the reviewer\'s case: a sibling whose name is also a word', () {
      final r = renderMemory('طفلي يضرب الطفل ب حين يغضب',
          childName: 'أحمد', family: family, subjectId: 12);
      expect(r.text, 'أحمد يضرب نور حين يغضب');
      expect(r.restore(r.text), 'طفلي يضرب الطفل ب حين يغضب');
      expect(r.restore('أحمد يضرب نور حين يغضب كثيرًا'),
          'طفلي يضرب الطفل ب حين يغضب كثيرًا');
      expect(r.restore('أحيانًا أحمد يضرب نور'),
          'أحيانًا طفلي يضرب الطفل ب');
    });

    test('«ل» + sibling, and an English placeholder keeps its case', () {
      final r = renderMemory('أعطِ للطفل ب وقتًا مع طفلي',
          childName: 'أحمد', family: family, subjectId: 12);
      expect(r.text, 'أعطِ لنور وقتًا مع أحمد');
      expect(r.restore('أعطِ لنور وقتًا أطول مع أحمد'),
          'أعطِ للطفل ب وقتًا أطول مع طفلي');
      final en = renderMemory('My child is shy; my child reads well',
          childName: 'Sara', lang: 'en');
      expect(en.restore('Sara is shy; Sara reads very well'),
          'My child is shy; my child reads very well');
    });

    test('only what the app inserted: a word that was there stays', () {
      // «آية» the child, and «آية» the verse — only the first was inserted.
      final r = renderMemory('طفلي تحفظ آية الكرسي', childName: 'آية');
      expect(r.text, 'آية تحفظ آية الكرسي');
      expect(r.restore('آية تحفظ آية الكرسي كل ليلة'),
          'طفلي تحفظ آية الكرسي كل ليلة');
    });

    test('a removed or altered name is not restored', () {
      final r = renderMemory('طفلي يخاف من الظلام', childName: 'أحمد');
      expect(r.restore('يخاف من الظلام'), 'يخاف من الظلام');
      // A letter glued on makes it another word.
      expect(r.restore('أحمدي يخاف من الظلام'), 'أحمدي يخاف من الظلام');
    });

    test('separate edits around the names are all followed', () {
      final r = renderMemory('طفلي يغار من الطفل ب عند اللعب',
          childName: 'أحمد', family: family, subjectId: 12);
      expect(r.restore('كثيرًا ما أحمد يغار من نور عند اللعب بالكرة'),
          'كثيرًا ما طفلي يغار من الطفل ب عند اللعب بالكرة');
    });

    testWidgets('editing a sibling fact sends the placeholders',
        (tester) async {
      final server = FakeMemoryServer()
        ..proven = true
        ..children = [childJson(12, 'أحمد'), childJson(30, 'نور')]
        ..facts[12] = [
          factJson(1, 12,
              category: 'challenge', fact: 'طفلي يضرب الطفل ب حين يغضب'),
        ];
      await pumpMemoryApp(
          tester, const ChildMemoryScreen(childId: 12, childName: 'أحمد'),
          server: server);
      await settle(tester);
      expect(find.text('أحمد يضرب نور حين يغضب'), findsOneWidget);
      await tester.tap(find.byIcon(Icons.more_vert_rounded));
      await settle(tester);
      await tester.tap(find.text('تعديل').last);
      await settle(tester);
      await tester.enterText(
          find.byType(TextField), 'أحمد يضرب نور حين يغضب ويتعب');
      await tester.pump();
      await tester.tap(find.text('حفظ'));
      await settle(tester);
      expect(server.lastPatch, {'fact': 'طفلي يضرب الطفل ب حين يغضب ويتعب'});
    });

    testWidgets('the limit is on the stored form, not the shown one',
        (tester) async {
      // «عبدالرحمن» shows 9 characters where «طفلي» stores 4: a fact at 158
      // stored characters shows 163 and must still be saveable.
      final stored = 'طفلي ${'ا' * 153}';
      expect(stored.length, 158);
      final server = FakeMemoryServer()
        ..proven = true
        ..facts[12] = [factJson(1, 12, fact: stored)];
      await pumpMemoryApp(
          tester, const ChildMemoryScreen(childId: 12, childName: 'عبدالرحمن'),
          server: server);
      await settle(tester);
      await tester.tap(find.byIcon(Icons.more_vert_rounded));
      await settle(tester);
      await tester.tap(find.text('تعديل').last);
      await settle(tester);
      FilledButton save() =>
          tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'حفظ'));
      expect(find.text('158/160'), findsOneWidget);
      expect(save().onPressed, isNotNull);

      await tester.enterText(find.byType(TextField), 'عبدالرحمن ${'ا' * 156}');
      await tester.pump();
      expect(find.text('161/160'), findsOneWidget);
      expect(save().onPressed, isNull);
    });
  });

  // ── 3 ──────────────────────────────────────────────────────────────────
  group('3 · a Google sign-in is confirmed before the deletion', () {
    Future<void> confirm(WidgetTester tester) async {
      final box = find.text('فهمت أن الحذف نهائي');
      await tester.scrollUntilVisible(box, 200,
          scrollable: find.byType(Scrollable).first);
      await tester.tap(box);
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'احذف حسابي'));
      await settle(tester);
      await tester.tap(find.widgetWithText(TextButton, 'احذف حسابي'));
      await settle(tester);
    }

    AccountDeletionSteps steps(FakeMemoryServer server,
            {required bool linked, List<int>? wipes}) =>
        AccountDeletionSteps(
          wipeLocal: () async => wipes?.add(1),
          wasLinkedToGoogle: () async => linked,
          relinkGoogle: () async {
            server.calls.add('RELINK from the proven session');
            return true;
          },
        );

    testWidgets('linked: proof, then the re-link, then the deletion',
        (tester) async {
      final server = FakeMemoryServer()
        ..deletionResult = {
          'devices': 2,
          'signed_in': true,
          'deleted': {'parent_identities': 1, 'user_backups': 1},
          'deleted_at': '2026-10-04T18:40:00Z',
        };
      await pumpMemoryApp(tester, const AccountDeletionScreen(),
          server: server,
          overrides: [
            accountDeletionStepsProvider
                .overrideWithValue(steps(server, linked: true)),
          ]);
      await settle(tester);
      await confirm(tester);
      final proven = server.calls.indexOf('POST /api/device-proof/complete');
      final relinked = server.calls.indexOf('RELINK from the proven session');
      final deleted =
          server.calls.indexOf('DELETE /api/privacy/account?confirm=true');
      expect(proven, greaterThanOrEqualTo(0));
      expect(relinked, greaterThan(proven));
      expect(deleted, greaterThan(relinked));
      expect(find.text('حُذف حسابك'), findsOneWidget);
      expect(find.textContaining('أبقينا سجلّ حسابك'), findsNothing,
          reason: 'signed_in: the record went with it');
    });

    testWidgets('not linked: no re-link', (tester) async {
      final server = FakeMemoryServer();
      await pumpMemoryApp(tester, const AccountDeletionScreen(),
          server: server,
          overrides: [
            accountDeletionStepsProvider
                .overrideWithValue(steps(server, linked: false)),
          ]);
      await settle(tester);
      await confirm(tester);
      expect(server.calls.where((c) => c.startsWith('RELINK')), isEmpty);
    });

    testWidgets('still not signed in after it: the page says what was kept',
        (tester) async {
      final server = FakeMemoryServer(); // signed_in: false by default
      await pumpMemoryApp(tester, const AccountDeletionScreen(),
          server: server,
          overrides: [
            accountDeletionStepsProvider
                .overrideWithValue(steps(server, linked: true)),
          ]);
      await settle(tester);
      await confirm(tester);
      expect(
          find.text(
              'أبقينا سجلّ حسابك في Google ونسخه الاحتياطية، لأن ربط هذا الهاتف به لم يُتحقَّق منه. لحذفها — ومعها أي هاتف آخر مرتبط به — راسلنا على support@alsaba.cloud.'),
          findsOneWidget);
    });
  });

  // ── 4 ──────────────────────────────────────────────────────────────────
  group('4 · a lost answer is settled, not guessed', () {
    Future<http.Response> Function(http.Request) server({
      required Future<http.Response> Function() delete,
      required Future<http.Response> Function() probe,
    }) =>
        (req) async {
          if (req.method == 'DELETE') return delete();
          if (req.method == 'GET' && req.url.path == '/api/children') {
            return probe();
          }
          if (req.method == 'POST' && req.url.path == '/api/chat/sessions') {
            return _json({'session_id': 's2', 'token': 'tok2'}, 201);
          }
          return _json({'detail': 'Not Found'}, 404);
        };

    test('the connection dropped, the old token is refused: it was deleted',
        () async {
      final c = _client(server(
        delete: () async => throw http.ClientException('connection reset'),
        probe: () async => _json({'detail': 'invalid token'}, 401),
      ));
      final body = await c.client.deleteAccount();
      expect(AccountDeletionResult.fromJson(body).scopeKnown, isFalse);
      expect(c.storage.store['tg_device_id'], isNot('dev-old'));
      expect(c.storage.store.containsKey('tg_token'), isFalse);
      expect(await c.client.accountDeletionState(), kAccountDeletionConfirmed);
    });

    test('an edge 502, the old token still works: nothing was deleted',
        () async {
      final c = _client(server(
        delete: () async => http.Response('<html>Bad gateway</html>', 502),
        probe: () async => _json({'children': []}),
      ));
      await expectLater(
          c.client.deleteAccount(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'account_not_deleted')));
      expect(c.storage.store['tg_device_id'], 'dev-old');
      expect(c.storage.store['tg_token'], 'tok1');
      expect(await c.client.accountDeletionState(), isNull);
    });

    test('no answer either way: unconfirmed, recorded, identity kept',
        () async {
      final c = _client(server(
        delete: () async => http.Response('', 524),
        probe: () async => throw http.ClientException('offline'),
      ));
      await expectLater(
          c.client.deleteAccount(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'account_deletion_unconfirmed')));
      expect(await c.client.accountDeletionState(), kAccountDeletionRequested);
      expect(c.storage.store['tg_device_id'], 'dev-old');
    });

    test('a refusal (a pause) deleted nothing and leaves nothing recorded',
        () async {
      final c = _client(server(
        delete: () async => _json({
          'detail': {
            'code': 'device_proof_cooldown',
            'message': 'm',
            'available_at': '2026-10-07T18:30:00Z',
          }
        }, 403),
        probe: () async => fail('a refusal needs no probe'),
      ));
      await expectLater(c.client.deleteAccount(), throwsA(isA<TgApiError>()));
      expect(await c.client.accountDeletionState(), isNull);
      expect(c.seen.where((s) => s == 'GET /api/children'), isEmpty);
    });

    test('while unsettled no session is minted for the possibly erased id',
        () async {
      SharedPreferences.setMockInitialValues(
          {kAccountDeletionKey: kAccountDeletionRequested});
      final c = _client(
          (req) async => req.url.path == '/api/chat/sessions'
              ? _json({'session_id': 's2', 'token': 'tok2'}, 201)
              : _json({'detail': 'invalid token'}, 401));
      await expectLater(
          c.client.getMemorySettings(), throwsA(isA<TgApiError>()));
      await expectLater(
          c.client.createSession(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'account_deletion_unconfirmed')));
      expect(c.seen.where((s) => s == 'POST /api/chat/sessions'), isEmpty);
      expect(c.storage.store['tg_device_id'], 'dev-old');
      // And the old token is kept: it is the only way left to ask the server
      // whether the account is gone (recovery would clear it before minting).
      expect(c.storage.store['tg_token'], 'tok1');
    });

    group('the next launch finishes it', () {
      test('requested, token refused: new device, phone cleared', () async {
        final s = FakeMemoryServer()
          ..deletionStateValue = kAccountDeletionRequested
          ..probeAnswer = true;
        var wiped = 0;
        expect(await completePendingAccountDeletion(
            client: s, wipe: () async => wiped++), isTrue);
        expect(s.startOvers, 1);
        expect(wiped, 1);
      });

      test('requested, token still works: nothing to finish', () async {
        final s = FakeMemoryServer()
          ..deletionStateValue = kAccountDeletionRequested
          ..probeAnswer = false;
        var wiped = 0;
        expect(await completePendingAccountDeletion(
            client: s, wipe: () async => wiped++), isFalse);
        expect(s.deletionStateValue, isNull);
        expect(wiped, 0);
      });

      test('requested, no answer: kept for the next launch', () async {
        final s = FakeMemoryServer()
          ..deletionStateValue = kAccountDeletionRequested
          ..probeAnswer = null;
        var wiped = 0;
        expect(await completePendingAccountDeletion(
            client: s, wipe: () async => wiped++), isFalse);
        expect(s.deletionStateValue, kAccountDeletionRequested);
        expect(wiped, 0);
      });

      test('confirmed but the wipe was cut short: wiped, no network',
          () async {
        final s = FakeMemoryServer()
          ..deletionStateValue = kAccountDeletionConfirmed;
        var wiped = 0;
        expect(await completePendingAccountDeletion(
            client: s, wipe: () async => wiped++), isTrue);
        expect(wiped, 1);
        expect(s.calls, isEmpty);
      });

      test('nothing recorded: nothing done, nothing asked', () async {
        final s = FakeMemoryServer();
        expect(await completePendingAccountDeletion(client: s), isFalse);
        expect(s.calls, isEmpty);
      });

      test('the record survives the clear and is removed by the wipe last',
          () async {
        SharedPreferences.setMockInitialValues({
          kAccountDeletionKey: kAccountDeletionConfirmed,
          'tg.onboarding.completed': true,
        });
        final prefs = await SharedPreferences.getInstance();
        await clearPreferencesForFreshStart(prefs);
        expect(prefs.getString(kAccountDeletionKey), kAccountDeletionConfirmed);
        expect(prefs.containsKey('tg.onboarding.completed'), isFalse);
      });
    });

    testWidgets('the screen: unconfirmed, then "check again" settles it',
        (tester) async {
      final server = FakeMemoryServer()
        ..proven = true
        ..deletionError = const TgApiError(null, 'm',
            code: 'account_deletion_unconfirmed');
      final wipes = <int>[];
      await pumpMemoryApp(tester, const AccountDeletionScreen(),
          server: server,
          overrides: [
            accountDeletionStepsProvider.overrideWithValue(AccountDeletionSteps(
              wipeLocal: () async => wipes.add(1),
              wasLinkedToGoogle: () async => true,
              relinkGoogle: () async => true,
            )),
          ]);
      await settle(tester);
      final box = find.text('فهمت أن الحذف نهائي');
      await tester.scrollUntilVisible(box, 200,
          scrollable: find.byType(Scrollable).first);
      await tester.tap(box);
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'احذف حسابي'));
      await settle(tester);
      await tester.tap(find.widgetWithText(TextButton, 'احذف حسابي'));
      await settle(tester);

      expect(find.textContaining('فلا نعرف بعد هل حُذف حسابك'), findsOneWidget);
      expect(find.text('لم يُحذف شيء. حاول مرة أخرى بعد قليل.'), findsNothing,
          reason: 'not known: never claimed');
      expect(wipes, isEmpty);

      server.probeAnswer = true; // the connection is back: the token is refused
      await tester.tap(find.text('تحقّق مرة أخرى'));
      await settle(tester);
      expect(server.startOvers, 1);
      expect(wipes, [1]);
      expect(find.text('حُذف حسابك'), findsOneWidget);
      // How far it reached is not known, and the page does not pretend.
      expect(find.textContaining('لم نتمكّن من التأكّد هل حُذف سجلّ حسابك'),
          findsOneWidget);
    });

    testWidgets('"check again" when nothing was deleted says so',
        (tester) async {
      final server = FakeMemoryServer()
        ..deletionStateValue = kAccountDeletionRequested
        ..probeAnswer = false;
      await pumpMemoryApp(tester, const AccountDeletionScreen(),
          server: server,
          overrides: [
            accountDeletionStepsProvider.overrideWithValue(AccountDeletionSteps(
              wipeLocal: () async {},
              wasLinkedToGoogle: () async => false,
            )),
          ]);
      await settle(tester);
      // Opened with a deletion still unsettled: settled before anything else.
      expect(server.calls.first, 'PROBE old token');
      expect(find.text('لم يُحذف شيء. حاول مرة أخرى بعد قليل.'), findsOneWidget);
      expect(server.deletionStateValue, isNull);
    });
  });

  // ── 5 ──────────────────────────────────────────────────────────────────
  group('5 · memory off pauses the follow-up loop', () {
    Widget today({bool withSwitch = false}) => Scaffold(
          body: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const TodayLoopCards(profile: _ahmad),
              if (withSwitch) const MemorySwitchTile(),
            ],
          ),
        );

    testWidgets('off: no card, and the due list is not even asked',
        (tester) async {
      final server = FakeMemoryServer()
        ..proven = true
        ..enabled = false
        ..due = [followupJson(7, 12)];
      await pumpMemoryApp(tester, today(), server: server);
      await settle(tester);
      expect(find.text('متابعة مع أحمد'), findsNothing);
      expect(server.calls.where((c) => c.contains('followups/due')), isEmpty);
    });

    testWidgets('switching off takes the card away at once', (tester) async {
      final server = FakeMemoryServer()
        ..proven = true
        ..due = [followupJson(7, 12)];
      await pumpMemoryApp(tester, today(withSwitch: true), server: server);
      await settle(tester);
      expect(find.text('متابعة مع أحمد'), findsOneWidget);
      await tester.scrollUntilVisible(find.byType(Switch), 200,
          scrollable: find.byType(Scrollable).first);
      await tester.tap(find.byType(Switch));
      await settle(tester);
      expect(server.enabled, isFalse);
      expect(find.text('متابعة مع أحمد'), findsNothing);
    });

    testWidgets('a push tapped while off: no answer buttons, why instead',
        (tester) async {
      final server = FakeMemoryServer()
        ..proven = true
        ..enabled = false
        ..followups[7] = followupJson(7, 12);
      await pumpMemoryApp(
          tester,
          Scaffold(
            body: Builder(
              builder: (context) => TextButton(
                onPressed: () => showFollowupSheet(context,
                    followupId: 7, source: FollowupSource.push),
                child: const Text('open'),
              ),
            ),
          ),
          server: server);
      await tester.tap(find.text('open'));
      await settle(tester);
      expect(find.byType(ChoiceChip), findsNothing);
      expect(find.text('إرسال'), findsNothing);
      expect(find.textContaining('الذاكرة متوقّفة'), findsOneWidget);
    });
  });

  // ── 6 ──────────────────────────────────────────────────────────────────
  group('6 · no link opens a parent screen over child mode', () {
    // The handler is a singleton, so a link it holds outlives the test's
    // container. Each test leaves child mode with nothing worth opening held
    // (the latest held link wins; `/` matches no arm).
    Future<void> release(WidgetTester tester, GlobalKey<NavigatorState> key,
        _ActiveChildMode mode) async {
      DeepLinkHandler.instance.handleForTest(Uri.parse('/'), key);
      mode.leave();
      await settle(tester);
    }

    for (final link in [
      '/followup/7',
      '/missions',
      '/license',
      '/inbox',
      '/l/lesson_7-9_x',
      '/p/path_7-9_x',
      // /go is not a parent screen: it saves its code over a child surface
      // too, and never unwinds it (programs_review2_fixes_test, PR #34).
    ]) {
      testWidgets(link, (tester) async {
        final key = GlobalKey<NavigatorState>();
        final server = FakeMemoryServer()
          ..proven = true
          ..followups[7] = followupJson(7, 12);
        late _ActiveChildMode mode;
        await pumpMemoryApp(
          tester,
          const Scaffold(body: Text('child surface')),
          server: server,
          navigatorKey: key,
          overrides: [
            childModeProvider.overrideWith(
                (ref) => mode = _ActiveChildMode(ref.read(tgClientProvider))),
          ],
        );
        DeepLinkHandler.instance.handleForTest(Uri.parse(link), key);
        await settle(tester);
        expect(find.text('child surface'), findsOneWidget);
        expect(find.byType(FollowupSheet), findsNothing);
        expect(tester.state<NavigatorState>(find.byType(Navigator)).canPop(),
            isFalse);
        await release(tester, key, mode);
      });
    }

    testWidgets('a held /followup opens once the parent leaves child mode',
        (tester) async {
      final key = GlobalKey<NavigatorState>();
      final server = FakeMemoryServer()
        ..proven = true
        ..followups[7] = followupJson(7, 12);
      late _ActiveChildMode mode;
      await pumpMemoryApp(
        tester,
        const Scaffold(body: Text('child surface')),
        server: server,
        navigatorKey: key,
        overrides: [
          childModeProvider.overrideWith(
              (ref) => mode = _ActiveChildMode(ref.read(tgClientProvider))),
        ],
      );
      DeepLinkHandler.instance.handleForTest(Uri.parse('/followup/7'), key);
      await settle(tester);
      expect(find.byType(FollowupSheet), findsNothing);
      mode.leave(); // the PIN exit — or restore() ending a cold start
      await settle(tester);
      expect(find.byType(FollowupSheet), findsOneWidget);
      expect(server.calls, contains('GET /api/children/followups/7'));
    });

    testWidgets('outside child mode /followup opens the sheet',
        (tester) async {
      final key = GlobalKey<NavigatorState>();
      final server = FakeMemoryServer()
        ..proven = true
        ..followups[7] = followupJson(7, 12);
      await pumpMemoryApp(tester, const Scaffold(body: Text('home')),
          server: server, navigatorKey: key);
      DeepLinkHandler.instance.handleForTest(Uri.parse('/followup/7'), key);
      await settle(tester);
      expect(find.byType(FollowupSheet), findsOneWidget);
    });
  });

  // ── 7 ──────────────────────────────────────────────────────────────────
  group('7 · only the launch registration may ask for permission', () {
    test('a re-registration uploads without asking', () async {
      var uploads = 0;
      expect(
          await PushService.registerWith(
            fetchToken: () async => 'fcm',
            upload: (_) async => uploads++,
          ),
          'fcm');
      expect(uploads, 1);
    });

    // The call sites, because PushService needs Firebase to run on a host.
    test('launch asks; the alert and the proof re-registration never do', () {
      final push =
          File('lib/features/push/push_service.dart').readAsStringSync();
      final alert = push.substring(push.indexOf('void _onAccountAlert()'));
      expect(alert.substring(0, alert.indexOf(';')),
          'void _onAccountAlert() => unawaited(registerToken())');
      expect(push, contains('..reRegisterPushToken = registerToken;'));
      expect(push.contains('registerToken(askPermission: true)'), isFalse,
          reason: 'nothing inside the service asks');
      final main = File('lib/main.dart').readAsStringSync();
      final loop = main.substring(main.indexOf('Future<void> _postLaunchGrowthLoop'));
      expect(loop, contains('registerToken(askPermission: true)'));
      expect(
          RegExp(r'registerToken\(').allMatches(main).length, 1,
          reason: 'the launch is the one registration in main');
    });
  });

  // ── 8 ──────────────────────────────────────────────────────────────────
  group('8 · a letter that now points at the child itself', () {
    test('is "another child", never the child\'s own name', () {
      // Written when the family was سارة(5), أحمد(12), عمر(30): «الطفل ب»
      // was أحمد. سارة deleted → letters shift → «الطفل ب» is عمر himself.
      final family = [
        const FamilyMember(id: 12, name: 'أحمد'),
        const FamilyMember(id: 30, name: 'عمر'),
      ];
      final r = renderMemory('الطفل ب يغار من طفلي',
          childName: 'عمر', family: family, subjectId: 30);
      expect(r.text, 'طفل آخر يغار من عمر');
      expect(r.text.contains('عمر يغار من عمر'), isFalse);
      // And it goes back as it was stored.
      expect(r.restore(r.text), 'الطفل ب يغار من طفلي');
      expect(
          renderMemoryText('الطفل ب is jealous of my child',
              childName: 'Omar', family: family, subjectId: 30, lang: 'en'),
          'another child is jealous of Omar');
      // A letter that is someone else is still their name.
      expect(
          renderMemoryText('الطفل أ يغار من طفلي',
              childName: 'عمر', family: family, subjectId: 30),
          'أحمد يغار من عمر');
    });
  });

  // ── 9 ──────────────────────────────────────────────────────────────────
  group('9 · data 404s are not missing features; deleting a child refreshes',
      () {
    test('only FastAPI\'s bare "Not Found" (or 405) is a missing endpoint',
        () {
      expect(const TgApiError(404, 'Not Found').isMissingEndpoint, isTrue);
      expect(const TgApiError(405, 'Method Not Allowed').isMissingEndpoint,
          isTrue);
      expect(const TgApiError(404, 'الطفل غير موجود.').isMissingEndpoint,
          isFalse);
      expect(
          const TgApiError(404, 'غير موجودة', code: 'followup_not_found')
              .isMissingEndpoint,
          isFalse);
    });

    testWidgets('deleting a child drops its due follow-up from Today',
        (tester) async {
      final server = _DeletingServer()
        ..proven = true
        ..children = [childJson(12, 'أحمد'), childJson(30, 'نور')]
        ..due = [followupJson(8, 30)];
      final container = await pumpMemoryApp(
        tester,
        Scaffold(
          body: ListView(children: const [TodayLoopCards(profile: _ahmad)]),
        ),
        server: server,
      );
      await settle(tester);
      expect(find.text('متابعة مع نور'), findsOneWidget);
      final asked = server.calls.where((c) => c.contains('followups/due')).length;

      final keepAlive = container.listen(deleteChildProvider, (_, _) {});
      addTearDown(keepAlive.close);
      await container.read(deleteChildProvider.notifier).call(30);
      await settle(tester);
      expect(server.calls.where((c) => c.contains('followups/due')).length,
          greaterThan(asked));
      expect(find.text('متابعة مع نور'), findsNothing);
    });
  });

  // ── 10 ─────────────────────────────────────────────────────────────────
  group('10 · voice recordings are excluded where they really are', () {
    // path_provider's getApplicationDocumentsDirectory() on Android is
    // Context.getDir("flutter") = <data dir>/app_flutter: the "root" domain.
    final excluded = 'app_flutter/${NarrationStore.folderName}/';
    final rule = RegExp('<exclude domain="root" path="${RegExp.escape(excluded)}" />');

    test('NarrationStore writes under the documents directory', () {
      final src =
          File('lib/features/screen_off/narration_store.dart').readAsStringSync();
      expect(src, contains('await getApplicationDocumentsDirectory()'));
      expect(src, contains(r"'${docs.path}/$folderName'"));
    });

    test('Android 11 and below (full-backup-content)', () {
      final xml = File('android/app/src/main/res/xml/backup_rules.xml')
          .readAsStringSync()
          .replaceAll(RegExp(r'<!--.*?-->', dotAll: true), '');
      expect(rule.allMatches(xml), hasLength(1));
    });

    test('Android 12+: cloud backup AND device transfer', () {
      // Comments out first: the header names the tags in prose.
      final xml = File('android/app/src/main/res/xml/data_extraction_rules.xml')
          .readAsStringSync()
          .replaceAll(RegExp(r'<!--.*?-->', dotAll: true), '');
      String section(String tag) =>
          xml.substring(xml.indexOf('<$tag>'), xml.indexOf('</$tag>'));
      expect(rule.hasMatch(section('cloud-backup')), isTrue);
      expect(rule.hasMatch(section('device-transfer')), isTrue);
    });
  });
}

/// The memory fake that can also delete a child, taking its follow-ups.
class _DeletingServer extends FakeMemoryServer {
  @override
  Future<Map<String, dynamic>> deleteChild(int childId) async {
    calls.add('DELETE /api/children/$childId');
    children.removeWhere((c) => c['id'] == childId);
    due.removeWhere((d) => d['child_id'] == childId);
    return {'deleted': true, 'child_id': childId};
  }
}
