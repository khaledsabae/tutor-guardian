/// PR #36 delta review (head 3814abbf) — one group per item, each by effect.
/// The reviewer's probes P1–P5 are ported where they belong.
///
///  1. A pending deletion can always settle: the DELETE's token is kept apart
///     from the session and the same DELETE is sent again; nothing blocks a
///     session meanwhile; a mint answered `410 device_erased` starts the
///     install over; "confirmed" and the erased id are written before the
///     keystore is cleared; the parent always has a way out.
///  2. A token that still works settles nothing: a slow DELETE stays
///     unknown, and when it commits the mint is refused, never served.
///  3. A backup cannot bring a deleted account back: the 410 covers the
///     device id in preferences; voice notes and agreement images are never
///     backed up; Android is asked for a new backup after the wipe.
///  4. The wipe removes preferences one by one, never clear-then-restore.
///  5. A deletion is seen through when its screen was closed under it.
///  6. The first frame never waits for the network.
///  7. A rename re-fetches memory; a child named «طفلي» keeps its letter.
///  8. A rename proves the phone when the server asks (PR #39); other edits
///     go as before.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/app_closer.dart';
import 'package:almorabbi/core/local_only_files.dart';
import 'package:almorabbi/features/child_memory/data/local_wipe.dart';
import 'package:almorabbi/features/child_memory/data/memory_repository.dart';
import 'package:almorabbi/features/child_memory/data/pending_deletion.dart';
import 'package:almorabbi/features/child_memory/data/placeholder_names.dart';
import 'package:almorabbi/features/child_memory/providers/memory_providers.dart';
import 'package:almorabbi/features/child_memory/screens/account_deletion_screen.dart';
import 'package:almorabbi/features/program/providers/settings_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';

import 'memory_fakes.dart';

class _MemStorage implements FlutterSecureStorage {
  final Map<String, String> store = {};

  /// When set, deleteAll() never returns: the app was killed right there.
  bool hangOnDeleteAll = false;

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
    if (hangOnDeleteAll) return Completer<void>().future;
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

http.Response _erased() => _json({
      'detail': {
        'code': 'device_erased',
        'message': 'حُذف هذا الحساب نهائيًا. سيبدأ التطبيق من جديد على هذا الهاتف.',
        'message_en':
            'This account was deleted. The app will start over on this phone.',
      }
    }, 410);

const _erasedId = '6f1c1d2e-0000-4000-8000-000000000001';

/// A client of the device `dev-old` holding session s1/tok1 (unless
/// [session] is false), over [answer]. [seen] records
/// `METHOD path Authorization` for every request; [mints] each mint's body.
({
  TgClient client,
  List<String> seen,
  List<Map<String, dynamic>> mints,
  List<String?> builds,
  _MemStorage storage,
}) _client(Future<http.Response> Function(http.Request req) answer,
    {bool session = true, String? deviceId = 'dev-old'}) {
  final seen = <String>[];
  final mints = <Map<String, dynamic>>[];
  final builds = <String?>[];
  final storage = _MemStorage();
  if (deviceId != null) storage.store['tg_device_id'] = deviceId;
  if (session) {
    storage.store['tg_session_id'] = 's1';
    storage.store['tg_token'] = 'tok1';
  }
  final client = TgClient.forTesting(
    baseUrl: 'http://api.test',
    storage: storage,
    httpClient: MockClient((req) async {
      seen.add('${req.method} ${req.url.path} ${req.headers['Authorization']}');
      if (req.url.path == '/api/chat/sessions' && req.method == 'POST') {
        mints.add(jsonDecode(req.body) as Map<String, dynamic>);
        builds.add(req.headers['X-App-Build']);
      }
      return answer(req);
    }),
  );
  return (
    client: client,
    seen: seen,
    mints: mints,
    builds: builds,
    storage: storage,
  );
}

bool _isMint(http.Request req) =>
    req.method == 'POST' && req.url.path == '/api/chat/sessions';

Future<void> _drain() async {
  for (var i = 0; i < 30; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    AppL10n.current = lookupAppLocalizations(const Locale('ar'));
  });
  tearDown(() => TgClient.appBuild = null);

  // ── 1 ──────────────────────────────────────────────────────────────────
  group('1 · a pending deletion can always settle', () {
    test('P1 · the DELETE never left; "new conversation"; the launch sends it '
        'again with its own token and it goes through', () async {
      var deleteLeaves = false;
      final c = _client((req) async {
        if (req.url.path == '/api/device-proof') return _json({'proven': true});
        if (req.method == 'DELETE') {
          if (!deleteLeaves) throw http.ClientException('offline');
          return req.headers['Authorization'] == 'Bearer tok1'
              ? _json({'devices': 1, 'signed_in': false, 'deleted': {}})
              : _json({'detail': 'x'}, 401);
        }
        if (_isMint(req)) return _json({'session_id': 's2', 'token': 'tok2'}, 201);
        return _json({'children': []});
      });
      await expectLater(
          c.client.deleteAccount(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'account_deletion_unconfirmed')));
      expect(await c.client.accountDeletionState(), kAccountDeletionRequested);

      // The parent backs out to the chat and taps "new conversation": the
      // session token goes — the DELETE's own token does not.
      await c.client.endSession();
      expect(c.storage.store.containsKey('tg_token'), isFalse);
      expect(c.storage.store['tg_deletion_token'], 'tok1');
      // Nothing is blocked meanwhile.
      expect((await c.client.ensureSession()).token, 'tok2');

      // Next launch, online.
      deleteLeaves = true;
      final settled = await settlePendingAccountDeletion(client: c.client);
      expect(settled.outcome, PendingDeletion.deleted);
      expect(settled.result!.scopeKnown, isTrue, reason: 'the server answered');
      expect(c.seen.last, 'DELETE /api/privacy/account Bearer tok1');
      expect(c.storage.store['tg_device_id'], isNot('dev-old'));
      expect(await c.client.accountDeletionState(), kAccountDeletionConfirmed);
    });

    test('P2 · killed inside the start-over: the launch starts over again, '
        'then clears the phone — never bricked', () async {
      SharedPreferences.setMockInitialValues({
        kAccountDeletionKey: kAccountDeletionConfirmed,
        kAccountDeletionErasedIdKey: _erasedId,
        'tg_device_id_backup': _erasedId, // the backup copy outlived the kill
      });
      final c = _client(
          (req) async => _isMint(req)
              ? _json({'session_id': 's2', 'token': 'tok2'}, 201)
              : _json({'children': []}),
          session: false,
          deviceId: null); // deleteAll() already ran
      var wiped = 0;
      expect(
          await completePendingAccountDeletion(
              client: c.client, wipe: () async => wiped++),
          isTrue);
      expect(wiped, 1);
      expect(c.seen, isEmpty, reason: 'before the first frame: no network');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('tg_device_id_backup'), isNot(_erasedId));
      expect(c.storage.store['tg_device_id'], isNot(_erasedId));
      await c.client.ensureSession();
      expect(c.mints.single['device_id'], isNot(_erasedId));
      expect(c.mints.single['device_id'], c.storage.store['tg_device_id']);
    });

    test('P2 as probed: "requested" with an empty keystore (its token gone) '
        'is settled with a live session — the erased id is refused', () async {
      TgClient.appBuild = 120;
      SharedPreferences.setMockInitialValues({
        kAccountDeletionKey: kAccountDeletionRequested,
        'tg_device_id_backup': _erasedId,
      });
      final c = _client(
          (req) async => _isMint(req)
              ? (_mintedFor(req) == _erasedId
                  ? _erased()
                  : _json({'session_id': 's2', 'token': 'tok2'}, 201))
              : _json({'proven': true}),
          session: false,
          deviceId: null);
      for (var launch = 0; launch < 2; launch++) {
        final settled = await settlePendingAccountDeletion(client: c.client);
        if (launch == 0) {
          expect(settled.outcome, PendingDeletion.deleted);
        } else {
          expect(settled.outcome, PendingDeletion.none,
              reason: 'settled once; the wipe then drops the record');
        }
        await c.client.clearAccountDeletionState(); // what the wipe does
      }
      expect((await c.client.ensureSession()).token, 'tok2');
      expect(c.mints.last['device_id'], isNot(_erasedId));
    });

    test('…and on a server that keeps no erased ids, the DELETE is sent with '
        'the fresh session — the parent asked for it', () async {
      SharedPreferences.setMockInitialValues(
          {kAccountDeletionKey: kAccountDeletionRequested});
      final c = _client((req) async {
        if (_isMint(req)) return _json({'session_id': 's2', 'token': 'tok2'}, 201);
        if (req.method == 'DELETE') {
          return _json({'devices': 1, 'signed_in': false, 'deleted': {}});
        }
        return _json({'proven': true});
      }, session: false);
      final settled = await settlePendingAccountDeletion(client: c.client);
      expect(settled.outcome, PendingDeletion.deleted);
      expect(c.seen.last, 'DELETE /api/privacy/account Bearer tok2');
    });

    test('"confirmed" and the erased id are written before the keystore is '
        'cleared', () async {
      final c = _client((req) async => _json({}));
      c.storage.hangOnDeleteAll = true; // killed inside deleteAll()
      unawaited(c.client.startOverAfterAccountDeletion());
      await _drain();
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(kAccountDeletionKey), kAccountDeletionConfirmed);
      expect(prefs.getString(kAccountDeletionErasedIdKey), 'dev-old');
    });

    test('a second start-over never erases the fresh id', () async {
      final c = _client((req) async => _json({}));
      await c.client.startOverAfterAccountDeletion();
      final fresh = c.storage.store['tg_device_id'];
      expect(fresh, isNot('dev-old'));
      await c.client.startOverAfterAccountDeletion(); // a 410 racing the 200
      expect(c.storage.store['tg_device_id'], fresh);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(kAccountDeletionErasedIdKey), 'dev-old');
    });

    test('P3 · erased, then a 401 handler ended the session: the launch still '
        'settles it with the DELETE\'s token', () async {
      var committed = false;
      final c = _client((req) async {
        if (req.method == 'DELETE') {
          if (!committed) {
            committed = true;
            throw http.ClientException('connection reset after commit');
          }
          return _json({'detail': 'Token غير صالح'}, 401);
        }
        if (req.url.path == '/api/device-proof' && !committed) {
          return _json({'proven': true});
        }
        if (_isMint(req)) return _json({'session_id': 's2', 'token': 'tok2'}, 201);
        return _json({'detail': 'Token غير صالح'}, 401); // the account is gone
      });
      await expectLater(c.client.deleteAccount(), throwsA(isA<TgApiError>()));
      // e.g. routine_providers: on 401 → endSession().
      try {
        await c.client.fetchTodayRoutine(12);
      } on TgApiError catch (e) {
        if (e.statusCode == 401) await c.client.endSession();
      }
      final settled = await settlePendingAccountDeletion(client: c.client);
      expect(settled.outcome, PendingDeletion.deleted);
      expect(settled.result!.scopeKnown, isFalse);
      expect(c.seen.last, 'DELETE /api/privacy/account Bearer tok1');
      expect(c.storage.store['tg_device_id'], isNot('dev-old'));
    });

    test('the token the DELETE carries is one the server just accepted',
        () async {
      // tok1 lapsed while idle (H5): renewed before the DELETE, so a 401 to
      // the DELETE can only mean "gone".
      final c = _client((req) async {
        final auth = req.headers['Authorization'];
        if (_isMint(req)) return _json({'session_id': 's1', 'token': 'tok2'}, 201);
        if (auth == 'Bearer tok1') return _json({'detail': 'expired'}, 401);
        if (req.method == 'DELETE') {
          return _json({'devices': 1, 'signed_in': false, 'deleted': {}});
        }
        return _json({'proven': true});
      });
      await c.client.deleteAccount();
      expect(c.seen.where((s) => s.startsWith('DELETE')).single,
          'DELETE /api/privacy/account Bearer tok2');
    });

    test('a mint answered 410 device_erased: never the old id again — a new '
        'device, its own mint (201), and the app told', () async {
      TgClient.appBuild = 120;
      final c = _client(
          (req) async => _isMint(req)
              ? (_mintedFor(req) == 'dev-old'
                  ? _erased()
                  : _json({'session_id': 's9', 'token': 'tok9'}, 201))
              : _json({}),
          session: false);
      c.storage.store['tg_device_proof'] = 'tok-before-deletion';
      var told = 0;
      c.client.onDeviceErased = () async => told++;
      final session = await c.client.ensureSession();
      await _drain();
      expect(session.token, 'tok9');
      expect(told, 1);
      expect(c.builds, everyElement('120'),
          reason: 'every mint says which build asks');
      expect(c.mints.map((m) => m['device_id'] == 'dev-old'), [true, false],
          reason: 'the old id once, then a fresh one — never the old id again');
      final fresh = c.storage.store['tg_device_id'];
      expect(fresh, isNot('dev-old'));
      expect(c.mints.last['device_id'], fresh);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('tg_device_id_backup'), fresh);
      expect(prefs.getString(kAccountDeletionErasedIdKey), 'dev-old');
      expect(await c.client.accountDeletionState(), kAccountDeletionConfirmed,
          reason: 'the launch clears the phone even if killed now');
      expect(c.storage.store.containsKey('tg_device_proof'), isTrue);
      expect(c.storage.store['tg_device_proof'], 'tok9',
          reason: 'the last token now belongs to the fresh device');
    });

    test('making the token live meets the 410: the account was already '
        'deleted, and the fresh device is never deleted', () async {
      TgClient.appBuild = 120;
      final c = _client(
          (req) async => _isMint(req)
              ? (_mintedFor(req) == 'dev-old'
                  ? _erased()
                  : _json({'session_id': 's9', 'token': 'tok9'}, 201))
              : _json({'proven': true}),
          session: false);
      final body = await c.client.deleteAccount();
      expect(body, isEmpty, reason: 'scope unknown: deleted elsewhere');
      expect(c.seen.where((s) => s.startsWith('DELETE')), isEmpty);
      expect(await c.client.accountDeletionState(), kAccountDeletionConfirmed);
    });

    test('no build number known: no header, and the server answers as before',
        () async {
      final c = _client(
          (req) async => _json({'session_id': 's2', 'token': 'tok2'}, 201),
          session: false);
      await c.client.ensureSession();
      expect(c.builds.single, isNull);
    });

    testWidgets('the way out: «ابدأ من جديد على هذا الهاتف» clears the phone '
        'and says the server\'s copy is not known to be gone', (tester) async {
      final server = FakeMemoryServer()
        ..deletionStateValue = kAccountDeletionRequested
        ..resendAnswer = null; // still no answer
      final wipes = <int>[];
      await pumpMemoryApp(tester, const AccountDeletionScreen(),
          server: server,
          overrides: [
            accountDeletionStepsProvider.overrideWithValue(AccountDeletionSteps(
              wipeLocal: () async => wipes.add(1),
              wasLinkedToGoogle: () async => false,
            )),
          ]);
      await settle(tester);
      expect(find.textContaining('فلا نعرف بعد هل حُذف حسابك'), findsOneWidget);
      await tester.tap(find.text('ابدأ من جديد على هذا الهاتف'));
      await settle(tester);
      expect(find.text('البدء من جديد على هذا الهاتف؟'), findsOneWidget);
      expect(find.textContaining('لتتأكّد من حذفه راسلنا على support@alsaba.cloud'),
          findsOneWidget);
      await tester.tap(find.widgetWithText(TextButton, 'ابدأ من جديد'));
      await settle(tester);
      expect(server.startOvers, 1);
      expect(wipes, [1]);
      expect(find.text('بدأ التطبيق من جديد على هذا الهاتف'), findsOneWidget);
      expect(find.textContaining('لم نتأكّد هل حُذف حسابك'), findsOneWidget);
      expect(find.text('حُذف حسابك'), findsNothing,
          reason: 'a start-over is not a deletion');
    });

    testWidgets('the way out reads the same in English', (tester) async {
      final server = FakeMemoryServer()
        ..deletionStateValue = kAccountDeletionRequested
        ..resendAnswer = null;
      await pumpMemoryApp(tester, const AccountDeletionScreen(),
          server: server,
          locale: const Locale('en'),
          overrides: [
            accountDeletionStepsProvider.overrideWithValue(AccountDeletionSteps(
              wipeLocal: () async {},
              wasLinkedToGoogle: () async => false,
            )),
          ]);
      await settle(tester);
      await tester.tap(find.text('Start over on this phone'));
      await settle(tester);
      await tester.tap(find.widgetWithText(TextButton, 'Start over'));
      await settle(tester);
      expect(find.text('The app has started over on this phone'), findsOneWidget);
    });
  });

  // ── 2 ──────────────────────────────────────────────────────────────────
  group('2 · a token that still works settles nothing', () {
    /// A family whose DELETE answer was lost: `dev-old`, the DELETE's token
    /// `tok1` kept, the record "requested". [config] is `GET /api/app-config`.
    ({
      TgClient client,
      List<String> seen,
      List<Map<String, dynamic>> mints,
      List<String?> builds,
      _MemStorage storage,
    }) lost(Future<http.Response> Function(http.Request req) answer) {
      SharedPreferences.setMockInitialValues(
          {kAccountDeletionKey: kAccountDeletionRequested});
      final c = _client(answer, session: false);
      c.storage.store['tg_deletion_token'] = 'tok1';
      return c;
    }

    http.Response config(int? floor) => _json(
        {'minimum_build_number': 90, 'erased_device_410_min_build': floor});

    test('the server keeps erased ids for this build: a mint for the same id '
        'settles it — 410, deleted; no DELETE sent', () async {
      TgClient.appBuild = 120;
      final c = lost((req) async {
        if (req.url.path == '/api/app-config') return config(110);
        if (_isMint(req)) return _erased();
        return _json({});
      });
      final settled = await settlePendingAccountDeletion(client: c.client);
      expect(settled.outcome, PendingDeletion.deleted);
      expect(settled.result!.scopeKnown, isFalse);
      expect(c.seen, contains('POST /api/chat/sessions Bearer tok1'),
          reason: 'the old token as proof, as always');
      expect(c.mints.single['device_id'], 'dev-old');
      expect(c.seen.where((s) => s.startsWith('DELETE')), isEmpty);
      expect(c.storage.store['tg_device_id'], isNot('dev-old'));
    });

    test('…201: intact — «لم يُحذف شيء», the DELETE is not sent again, and '
        'the session is this device\'s own', () async {
      TgClient.appBuild = 120;
      final c = lost((req) async {
        if (req.url.path == '/api/app-config') return config(120);
        if (_isMint(req)) return _json({'session_id': 's5', 'token': 'tok5'}, 201);
        return _json({});
      });
      final settled = await settlePendingAccountDeletion(client: c.client);
      expect(settled.outcome, PendingDeletion.notDeleted);
      expect(await c.client.accountDeletionState(), isNull);
      expect(c.storage.store.containsKey('tg_deletion_token'), isFalse);
      expect(c.storage.store['tg_token'], 'tok5');
      expect(c.storage.store['tg_device_id'], 'dev-old');
      expect(c.seen.where((s) => s.startsWith('DELETE')), isEmpty);
    });

    test('…and "check again" says so, offering to try again', () async {
      TgClient.appBuild = 120;
      final c = lost((req) async {
        if (req.url.path == '/api/app-config') return config(100);
        if (_isMint(req)) return _json({'session_id': 's5', 'token': 'tok5'}, 201);
        return _json({});
      });
      await expectLater(
          MemoryRepository(c.client).resolvePendingDeletion(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'account_not_deleted')
              .having((e) => e.message, 'message',
                  'لم يُحذف شيء. حاول مرة أخرى بعد قليل.')));
    });

    test('…no answer to that mint: still unknown, the way out kept', () async {
      TgClient.appBuild = 120;
      final c = lost((req) async {
        if (req.url.path == '/api/app-config') return config(110);
        throw http.ClientException('offline');
      });
      final settled = await settlePendingAccountDeletion(client: c.client);
      expect(settled.outcome, PendingDeletion.unknown);
      expect(await c.client.accountDeletionState(), kAccountDeletionRequested);
      expect(c.storage.store['tg_deletion_token'], 'tok1');
    });

    for (final (label, floor, build) in [
      ('a gate above this build', 130, 120),
      ('no gate yet', null, 120),
      ('no build number (nothing to compare)', 110, null),
    ]) {
      test('$label: the same DELETE again — 401, already deleted', () async {
        TgClient.appBuild = build;
        final c = lost((req) async {
          if (req.url.path == '/api/app-config') return config(floor);
          if (req.method == 'DELETE') return _json({'detail': 'x'}, 401);
          return _json({'session_id': 's5', 'token': 'tok5'}, 201);
        });
        final settled = await settlePendingAccountDeletion(client: c.client);
        expect(settled.outcome, PendingDeletion.deleted);
        expect(c.mints, isEmpty, reason: 'no mint stands in for the answer');
        expect(c.seen.last, 'DELETE /api/privacy/account Bearer tok1');
      });
    }

    test('P4 · a slow DELETE: unknown, not "nothing deleted"; when it commits, '
        'the mint is refused — never served for the erased id', () async {
      TgClient.appBuild = 120;
      var committed = false;
      final c = _client((req) async {
        if (req.method == 'DELETE') {
          throw TimeoutException('client timeout; origin still working');
        }
        if (_isMint(req)) {
          return _mintedFor(req) == 'dev-old' && committed
              ? _erased()
              : _json({'session_id': 's9', 'token': 'tok9'}, 201);
        }
        final auth = req.headers['Authorization'];
        if (auth == 'Bearer tok1' && !committed) return _json({'enabled': true});
        if (auth == 'Bearer tok9') return _json({'enabled': true});
        return _json({'detail': 'x'}, 401);
      });
      await expectLater(
          c.client.deleteAccount(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'account_deletion_unconfirmed')));
      // The old token still works — that settles nothing.
      await c.client.getMemorySettings();
      expect(await c.client.accountDeletionState(), kAccountDeletionRequested);

      committed = true; // the in-flight DELETE commits now
      // 401 → recovery → the mint for dev-old is refused (410) → a fresh
      // device mints its own session, and the request goes on with it.
      await c.client.getMemorySettings();
      expect(c.mints.where((m) => m['device_id'] == 'dev-old'), isNotEmpty);
      expect(c.mints.last['device_id'], isNot('dev-old'),
          reason: 'no session was served for the erased id');
      expect(c.storage.store['tg_device_id'], c.mints.last['device_id']);
      expect(await c.client.accountDeletionState(), kAccountDeletionConfirmed);
    });
  });

  // ── 3 ──────────────────────────────────────────────────────────────────
  group('3 · a backup cannot bring a deleted account back', () {
    test('P5 · a restored backup holding the erased id: the mint is refused, '
        'the install starts over, the app is told', () async {
      TgClient.appBuild = 120;
      SharedPreferences.setMockInitialValues({
        'tg_device_id_backup': _erasedId,
        'tg.active_child_name': 'أحمد',
      });
      final c = _client(
          (req) async => _mintedFor(req) == _erasedId
              ? _erased()
              : _json({'session_id': 's1', 'token': 'tok1'}, 201),
          session: false,
          deviceId: null); // the keystore is not in the backup
      var told = 0;
      c.client.onDeviceErased = () async => told++;
      expect(await completePendingAccountDeletion(client: c.client), isFalse);
      await c.client.ensureSession();
      await _drain();
      expect(c.mints.first['device_id'], _erasedId);
      expect(c.mints.last['device_id'], isNot(_erasedId));
      expect(told, 1);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('tg_device_id_backup'), isNot(_erasedId),
          reason: 'the restored backup copy of the id is replaced');
    });

    testWidgets('told, the app clears the phone and ends on the deleted page',
        (tester) async {
      final key = GlobalKey<NavigatorState>();
      await pumpMemoryApp(tester, const Scaffold(body: Text('home')),
          server: FakeMemoryServer(), navigatorKey: key);
      var wiped = 0;
      await finishDeletedAccount(key, wipe: () async => wiped++);
      await settle(tester);
      await tester.pump(const Duration(seconds: 1)); // the page transition
      expect(wiped, 1);
      expect(find.text('حُذف حسابك'), findsOneWidget);
      expect(find.text('home'), findsNothing);
    });

    group('what a backup never carries', () {
      final rule = RegExp(
          '<exclude domain="root" path="app_flutter/$localOnlyFolderName/" />');
      String noComments(String path) => File(path)
          .readAsStringSync()
          .replaceAll(RegExp(r'<!--.*?-->', dotAll: true), '');

      test('the local-only folder is excluded on Android ≤ 11', () {
        expect(
            rule.allMatches(
                noComments('android/app/src/main/res/xml/backup_rules.xml')),
            hasLength(1));
      });

      test('…and on Android 12+, from cloud backup AND device transfer', () {
        final xml =
            noComments('android/app/src/main/res/xml/data_extraction_rules.xml');
        String section(String tag) =>
            xml.substring(xml.indexOf('<$tag>'), xml.indexOf('</$tag>'));
        expect(rule.hasMatch(section('cloud-backup')), isTrue);
        expect(rule.hasMatch(section('device-transfer')), isTrue);
      });

      test('the device id backup stays in it: the 410 covers a restored one',
          () {
        for (final f in [
          'android/app/src/main/res/xml/backup_rules.xml',
          'android/app/src/main/res/xml/data_extraction_rules.xml',
        ]) {
          expect(noComments(f), isNot(contains('FlutterSharedPreferences')));
        }
      });

      test('voice notes and agreement images are written into that folder',
          () {
        for (final f in [
          'lib/features/feedback/feedback_screen.dart',
          'lib/features/agreement/agreement_export.dart',
        ]) {
          final src = File(f).readAsStringSync();
          expect(src, contains('await localOnlyDirectory()'), reason: f);
          expect(src, isNot(contains('getApplicationDocumentsDirectory')),
              reason: f);
        }
        expect(File('lib/core/local_only_files.dart').readAsStringSync(),
            contains(r"Directory('${docs.path}/$localOnlyFolderName')"));
      });

      test('what older builds left loose is removed', () async {
        final docs = await Directory.systemTemp.createTemp('wt-memui-docs');
        addTearDown(() => docs.delete(recursive: true));
        for (final name in [
          'feedback_1759600000000.m4a',
          'agreement_أحمد.png',
          'agreement_child.png',
          'notes.txt',
          'feedback.json',
        ]) {
          await File('${docs.path}/$name').writeAsString('x');
        }
        await Directory('${docs.path}/narrations').create();
        await removeStrayPrivateFiles(documents: docs);
        final left = docs
            .listSync()
            .map((e) => e.uri.pathSegments.where((s) => s.isNotEmpty).last)
            .toSet();
        expect(left, {'notes.txt', 'feedback.json', 'narrations'});
      });

      test('the rules\' comments name tests that exist', () {
        for (final f in [
          'android/app/src/main/res/xml/backup_rules.xml',
          'android/app/src/main/res/xml/data_extraction_rules.xml',
        ]) {
          for (final m in RegExp(r'test/[\w/]+\.dart')
              .allMatches(File(f).readAsStringSync())) {
            expect(File(m.group(0)!).existsSync(), isTrue, reason: m.group(0));
          }
        }
      });
    });

    testWidgets('after the wipe Android is asked for a new backup',
        (tester) async {
      final calls = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          appChannel, (call) async {
        calls.add(call.method);
        return true;
      });
      addTearDown(() => tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(appChannel, null));
      await notifyBackupDataChanged();
      expect(calls, ['backupDataChanged']);

      // No native side (iOS, an old build) or no reply: nothing breaks.
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          appChannel, (call) async => throw MissingPluginException());
      await notifyBackupDataChanged();
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          appChannel, (call) => Completer<Object?>().future);
      final asking = notifyBackupDataChanged();
      await tester.pump(const Duration(seconds: 4));
      await asking;
    });

    test('…by the native side, as the wipe\'s last step', () {
      final kotlin = File(
              'android/app/src/main/kotlin/com/alsaba/almorabbi/MainActivity.kt')
          .readAsStringSync();
      expect(kotlin, contains('"backupDataChanged" ->'));
      expect(kotlin, contains('BackupManager(this).dataChanged()'));
      final wipe = File('lib/features/child_memory/data/local_wipe.dart')
          .readAsStringSync();
      final recordGone = wipe.lastIndexOf('remove(kAccountDeletionKey)');
      final backup = wipe.indexOf('_step(notifyBackupDataChanged)');
      expect(recordGone, greaterThan(0));
      expect(backup, greaterThan(recordGone));
    });
  });

  // ── 4 ──────────────────────────────────────────────────────────────────
  group('4 · the wipe never loses the deletion record', () {
    test('preferences go one by one: kept keys are never cleared', () async {
      SharedPreferences.setMockInitialValues({
        kAccountDeletionKey: kAccountDeletionConfirmed,
        kAccountDeletionErasedIdKey: 'dev-old',
        'tg_device_id_backup': 'dev-new',
        'tg.ui_language': 'en',
        'tg.analytics.once.first_open': true,
        'tg.chat_snapshot': '[]',
        'tg.active_child_name': 'أحمد',
      });
      final prefs = await SharedPreferences.getInstance();
      await clearPreferencesForFreshStart(prefs);
      expect(prefs.getKeys(), {
        kAccountDeletionKey,
        kAccountDeletionErasedIdKey,
        'tg_device_id_backup',
        'tg.ui_language',
        'tg.analytics.once.first_open',
      });
      final src = File('lib/features/child_memory/data/local_wipe.dart')
          .readAsStringSync();
      final body = src.substring(
          src.indexOf('Future<void> clearPreferencesForFreshStart'),
          src.indexOf('/// Delete what is inside'));
      expect(body, isNot(contains('.clear()')),
          reason: 'killed between clear() and the rewrite, the record is lost');
    });
  });

  // ── 5 ──────────────────────────────────────────────────────────────────
  group('5 · a deletion is seen through when its screen was closed under it',
      () {
    testWidgets('a notification pops the screen during the DELETE: the phone '
        'is still cleared, and the result page still shown', (tester) async {
      final key = GlobalKey<NavigatorState>();
      final gate = Completer<void>();
      final server = FakeMemoryServer()
        ..proven = true
        ..deletionGate = gate;
      final wipes = <int>[];
      await pumpMemoryApp(
        tester,
        Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                  builder: (_) => const AccountDeletionScreen())),
              child: const Text('open'),
            ),
          ),
        ),
        server: server,
        navigatorKey: key,
        overrides: [
          accountDeletionStepsProvider.overrideWithValue(AccountDeletionSteps(
            wipeLocal: () async => wipes.add(1),
            wasLinkedToGoogle: () async => false,
          )),
        ],
      );
      await tester.tap(find.text('open'));
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
      expect(find.text('جارٍ الحذف…'), findsOneWidget);

      // A push is tapped: the deep link unwinds to the root.
      key.currentState!.popUntil((route) => route.isFirst);
      await settle(tester);
      await tester.pump(const Duration(seconds: 1)); // gone, not leaving
      expect(find.byType(AccountDeletionScreen), findsNothing);

      gate.complete(); // the server answers
      await settle(tester);
      expect(tester.takeException(), isNull);
      expect(wipes, [1]);
      expect(find.text('حُذف حسابك'), findsOneWidget);
    });
  });

  // ── 6 ──────────────────────────────────────────────────────────────────
  group('6 · the first frame never waits for the network', () {
    test('a deletion awaiting its answer is not settled before runApp',
        () async {
      SharedPreferences.setMockInitialValues(
          {kAccountDeletionKey: kAccountDeletionRequested});
      final c = _client((req) async => _json({}));
      var wiped = 0;
      expect(
          await completePendingAccountDeletion(
              client: c.client, wipe: () async => wiped++),
          isFalse);
      expect(c.seen, isEmpty);
      expect(wiped, 0);
    });

    test('main(): local finishing before runApp, the settle after it', () {
      final src = File('lib/main.dart').readAsStringSync();
      final run = src.indexOf('runApp(');
      expect(src.indexOf('TgClient.appBuild ='), inInclusiveRange(0, run));
      expect(src.indexOf('TgClient.shared.onDeviceErased ='),
          inInclusiveRange(0, run));
      expect(src.indexOf('await completePendingAccountDeletion()'),
          inInclusiveRange(0, run));
      expect(src.indexOf('await _settleLostDeletion()'), greaterThan(run));
      expect(src.indexOf('settlePendingAccountDeletion()'), greaterThan(run));
      // An account found erased this run stops the growth loop: nothing in
      // it is wanted for a phone about to close.
      final loop = src.substring(src.indexOf('Future<void> _postLaunchGrowthLoop'));
      expect(loop.indexOf('if (_accountGone) return;'),
          inInclusiveRange(0, loop.indexOf('registerToken(')));
      expect(src, contains('_accountGone = true;'));
    });
  });

  // ── 7 ──────────────────────────────────────────────────────────────────
  group('7 · names: a rename re-fetches memory; «طفلي» keeps its letter', () {
    testWidgets('a rename re-fetches memory; another edit does not',
        (tester) async {
      final server = _RenamingServer()
        ..proven = true
        ..children = [childJson(12, 'أحمد'), childJson(30, 'نور')]
        ..facts[12] = [factJson(1, 12, fact: 'طفلي يغار من الطفل ب')];
      final container = await pumpMemoryApp(
          tester, const Scaffold(body: _MemoryText(childId: 12)),
          server: server);
      await settle(tester);
      expect(find.text('أحمد يغار من نور'), findsOneWidget);
      int reads() =>
          server.calls.where((c) => c == 'GET /api/children/12/memory').length;
      final before = reads();
      final keepAlive = container.listen(updateChildProvider, (_, _) {});
      addTearDown(keepAlive.close);

      await container.read(updateChildProvider.notifier).call(
          childId: 30, name: 'نور', ageGroup: '10-12', renamed: false);
      await settle(tester);
      expect(reads(), before, reason: 'an age change renders nothing new');

      await container.read(updateChildProvider.notifier).call(
          childId: 30, name: 'نورة', ageGroup: '10-12', renamed: true);
      await settle(tester);
      expect(reads(), greaterThan(before));
      expect(find.text('أحمد يغار من نورة'), findsOneWidget);
    });

    test('a child named «طفلي» keeps its letter: the next sibling is ب', () {
      const family = [
        FamilyMember(id: 1, name: 'طفلي'),
        FamilyMember(id: 2, name: 'سارة'),
        FamilyMember(id: 3, name: 'عمر'),
      ];
      expect(
          renderMemoryText('طفلي يحب الطفل ب',
              childName: 'عمر', family: family, subjectId: 3),
          'عمر يحب سارة');
    });

    test('…and is never shown as «طفلي»: that word is the fact\'s own child',
        () {
      const family = [
        FamilyMember(id: 1, name: 'طفلي'),
        FamilyMember(id: 2, name: 'عمر'),
      ];
      final r = renderMemory('الطفل أ يغار من طفلي',
          childName: 'عمر', family: family, subjectId: 2);
      expect(r.text, 'الطفل أ يغار من عمر');
      expect(r.restore('الطفل أ يغار كثيرًا من عمر'),
          'الطفل أ يغار كثيرًا من طفلي');
    });

    test('a child whose own name is a default needs no swap', () {
      for (final (name, text, lang) in [
        ('طفلي', 'طفلي يخاف من الظلام', 'ar'),
        ('طِفْلي', 'طفلي يخاف من الظلام', 'ar'),
        ('My child', 'my child is afraid of the dark', 'en'),
        ('ابنتي', 'طفلي تحب الرسم', 'ar'),
      ]) {
        final r = renderMemory(text, childName: name, lang: lang);
        expect(r.text, text, reason: name);
        expect(r.insertions, isEmpty, reason: name);
      }
      expect(isDefaultChildName('أحمد'), isFalse);
      expect(isDefaultChildName('نور'), isFalse);
    });
  });

  // ── 8 ──────────────────────────────────────────────────────────────────
  group('8 · a rename proves the phone when the server asks', () {
    testWidgets('a rename on a proven-required device: proves, sends once more',
        (tester) async {
      final server = _RenamingServer()
        ..children = [childJson(12, 'أحمد'), childJson(30, 'نور')]
        ..renameNeedsProof = true;
      final container = await pumpMemoryApp(
          tester, const Scaffold(body: Text('edit')),
          server: server);
      final keepAlive = container.listen(updateChildProvider, (_, _) {});
      addTearDown(keepAlive.close);
      final saving = container.read(updateChildProvider.notifier).call(
          childId: 30, name: 'نورة', ageGroup: '7-9', renamed: true);
      await settle(tester);
      final child = await saving;
      expect(child.name, 'نورة');
      final patches =
          server.calls.where((c) => c.startsWith('PATCH /api/children/30'));
      expect(patches, hasLength(2), reason: 'refused, proven, sent once more');
      expect(server.calls, contains('POST /api/device-proof/complete'));
    });

    testWidgets('another edit goes as before: one PATCH, no proof',
        (tester) async {
      final server = _RenamingServer()
        ..children = [childJson(12, 'أحمد'), childJson(30, 'نور')]
        ..renameNeedsProof = true;
      final container = await pumpMemoryApp(
          tester, const Scaffold(body: Text('edit')),
          server: server);
      final keepAlive = container.listen(updateChildProvider, (_, _) {});
      addTearDown(keepAlive.close);
      await container.read(updateChildProvider.notifier).call(
          childId: 30, name: 'نور', ageGroup: '10-12', renamed: false);
      expect(
          server.calls.where((c) => c.startsWith('PATCH /api/children/30')),
          hasLength(1));
      expect(server.calls.where((c) => c.contains('device-proof')), isEmpty);
    });

    testWidgets('an older server never asks: a rename is one PATCH',
        (tester) async {
      final server = _RenamingServer()
        ..children = [childJson(12, 'أحمد'), childJson(30, 'نور')];
      final container = await pumpMemoryApp(
          tester, const Scaffold(body: Text('edit')),
          server: server);
      final keepAlive = container.listen(updateChildProvider, (_, _) {});
      addTearDown(keepAlive.close);
      await container.read(updateChildProvider.notifier).call(
          childId: 30, name: 'نورة', ageGroup: '7-9', renamed: true);
      expect(
          server.calls.where((c) => c.startsWith('PATCH /api/children/30')),
          hasLength(1));
      expect(server.calls.where((c) => c.contains('device-proof')), isEmpty);
    });

    test('the edit screen says when a rename is one', () {
      final src = File('lib/features/program/screens/edit_child_screen.dart')
          .readAsStringSync();
      expect(src, contains('renamed: name != widget.child.name.trim()'));
      expect(src, contains('describeActionFailure(context, e)'),
          reason: 'a 72-hour pause says until when');
    });
  });
}

/// The device id a mint asks for.
String? _mintedFor(http.Request req) =>
    (jsonDecode(req.body) as Map<String, dynamic>)['device_id'] as String?;

/// The memory fake that can also rename a child: like PR #39's server, a
/// rename re-letters nothing here (same order) but needs a proven session on
/// a device that has proven ([renameNeedsProof]).
class _RenamingServer extends FakeMemoryServer {
  bool renameNeedsProof = false;

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
    calls.add('PATCH /api/children/$childId name=$name');
    final child = children.firstWhere((c) => c['id'] == childId);
    final renaming = name != null && name != child['name'];
    if (renaming && renameNeedsProof && !proven) {
      throw coded(403, 'device_proof_required');
    }
    if (name != null) child['name'] = name;
    if (ageGroup != null) child['age_group'] = ageGroup;
    return Map<String, dynamic>.from(child);
  }
}

/// The child's memory as the memory screen renders it, alone.
class _MemoryText extends ConsumerWidget {
  const _MemoryText({required this.childId});
  final int childId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final memory = ref.watch(childMemoryProvider(childId)).valueOrNull;
    final family = ref.watch(familyMembersProvider);
    if (memory == null) return const SizedBox.shrink();
    return Column(children: [
      for (final f in memory.facts)
        Text(renderMemoryText(f.fact,
            childName: 'أحمد', family: family, subjectId: childId)),
    ]);
  }
}
