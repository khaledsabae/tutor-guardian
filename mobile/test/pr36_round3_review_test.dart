/// PR #36 delta review, round 3 (head 7d3398ff) — one group per item, each
/// by effect. The reviewer's probes B, B2, C1, C2 and E are ported against
/// the review's own model of the server ([_Server]: chat.create_session,
/// privacy.erase_account and services/erased_devices as they decide).
///
///  1. With the server not refusing erased ids to this build, a deletion
///     waiting for its answer is settled BEFORE any mint for the old id; on a
///     re-send only the handler's own refusals prove the account is there.
///  2. A settle answer is acted on only while the install is still the
///     device it asked about, and still waiting for that answer.
///  3. The "unknown" copy promises no more than a check.
///  4. Nothing before the first frame waits for the network: the push
///     token's renewal comes after it, and every wipe step is bounded.
///  N. Nits: a 410 inside session recovery never pairs the erased session id
///     with the fresh token; an intact settle keeps the conversation; the
///     launch loop stops after any step once the account is gone.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/child_memory/data/local_wipe.dart';
import 'package:almorabbi/features/child_memory/data/pending_deletion.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';

class _Mem implements FlutterSecureStorage {
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
  }) async =>
      store.remove(key);

  @override
  Future<void> deleteAll({
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async =>
      store.clear();

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

http.Response _json(Object body, [int status = 200]) => http.Response.bytes(
    utf8.encode(jsonEncode(body)), status,
    headers: {'content-type': 'application/json; charset=utf-8'});

/// The review's model of the server's rules:
///   * a mint with a Bearer that is a live token is minted for THAT token's
///     device (201);
///   * else a claimed id that was erased, from a build ≥ the floor (floor
///     set) → 410 device_erased;
///   * else 201 for the claimed id — on a server without the floor, an
///     erased id comes back to life with a live token;
///   * the account DELETE with a dead token → 401; with a live one, every
///     token of that device goes and the id is erased → 200.
class _Server {
  _Server({this.floor});
  int? floor;
  final Map<String, String> tokens = {}; // live token -> device
  final Set<String> erased = {};
  final List<String> log = [];
  final List<String> mintedFor = []; // claimed ids of every mint
  var _n = 0;

  Completer<void>? holdFirstAppConfig;
  Completer<void>? holdMintFor;
  String? holdMintDevice;
  bool deleteAnswerLost = false; // commit, then drop the answer
  bool deleteUnreachable = false; // never reaches the origin
  http.Response? deleteOverride; // e.g. a pre-auth 429
  Completer<void>? holdDelete;

  String _mintFor(String device) {
    final t = 'tok${++_n}';
    tokens[t] = device;
    return t;
  }

  Future<http.Response> handle(http.Request req) async {
    final auth = req.headers['Authorization'];
    final bearer =
        auth != null && auth.startsWith('Bearer ') ? auth.substring(7) : null;
    log.add('${req.method} ${req.url.path} ${bearer ?? '-'}');
    if (req.url.path == '/api/app-config') {
      final hold = holdFirstAppConfig;
      if (hold != null) {
        holdFirstAppConfig = null;
        await hold.future;
      }
      return _json(
          {'minimum_build_number': 90, 'erased_device_410_min_build': floor});
    }
    if (req.method == 'POST' && req.url.path == '/api/chat/sessions') {
      final claimed =
          (jsonDecode(req.body) as Map<String, dynamic>)['device_id'] as String;
      mintedFor.add(claimed);
      final hold = holdMintFor;
      if (hold != null && holdMintDevice == claimed) {
        holdMintFor = null;
        final resp = _mint(req, claimed, bearer); // decided at the server
        await hold.future;
        return resp;
      }
      return _mint(req, claimed, bearer);
    }
    if (req.method == 'DELETE' && req.url.path == '/api/privacy/account') {
      if (holdDelete != null) await holdDelete!.future;
      if (deleteUnreachable) throw http.ClientException('offline');
      final override = deleteOverride;
      if (override != null) return override;
      final dev = bearer == null ? null : tokens[bearer];
      if (dev == null) return _json({'detail': 'مطلوب توثيق.'}, 401);
      tokens.removeWhere((_, d) => d == dev);
      erased.add(dev);
      if (deleteAnswerLost) throw http.ClientException('connection dropped');
      return _json({
        'devices': 1,
        'signed_in': false,
        'deleted': {'api_tokens': 1},
        'deleted_at': '2026-10-05T10:00:00Z',
      });
    }
    final dev = bearer == null ? null : tokens[bearer];
    if (dev == null) return _json({'detail': 'x'}, 401);
    if (req.url.path == '/api/device-proof') return _json({'proven': true});
    return _json({'enabled': true});
  }

  http.Response _mint(http.Request req, String claimed, String? bearer) {
    final build = int.tryParse(req.headers['X-App-Build'] ?? '');
    final proofDevice = bearer == null ? null : tokens[bearer];
    if (proofDevice != null) {
      final t = _mintFor(proofDevice);
      return _json(
          {'session_id': 's-$t', 'token': t, 'device_id': proofDevice}, 201);
    }
    if (erased.contains(claimed) &&
        floor != null &&
        build != null &&
        build >= floor!) {
      return _json({
        'detail': {
          'code': 'device_erased',
          'message': 'حُذف هذا الحساب نهائيًا.',
          'message_en': 'This account was deleted.',
        }
      }, 410);
    }
    final t = _mintFor(claimed);
    return _json({'session_id': 's-$t', 'token': t, 'device_id': claimed}, 201);
  }

  Iterable<String> liveTokensOf(String device) =>
      tokens.entries.where((e) => e.value == device).map((e) => e.key);
}

/// The device `dev-old` with session s1/tok0, live on [server].
({TgClient client, _Mem storage}) _client(_Server server,
    {bool session = true}) {
  final storage = _Mem()..store['tg_device_id'] = 'dev-old';
  if (session) {
    storage.store['tg_session_id'] = 's1';
    storage.store['tg_token'] = 'tok0';
    server.tokens['tok0'] = 'dev-old';
  }
  final client = TgClient.forTesting(
    baseUrl: 'http://api.test',
    storage: storage,
    httpClient: MockClient(server.handle),
  );
  return (client: client, storage: storage);
}

Future<void> _drain([int n = 50]) async {
  for (var i = 0; i < n; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    AppL10n.current = lookupAppLocalizations(const Locale('ar'));
    TgClient.appBuild = 120;
  });
  tearDown(() => TgClient.appBuild = null);

  // ── 1 ──────────────────────────────────────────────────────────────────
  group('1 · no mint for the old id before the deletion is settled', () {
    test('B · gate off: a 401 meets an unsettled deletion that went through — '
        'settled first; the erased id never gets a live token', () async {
      final server = _Server(floor: null)..deleteAnswerLost = true;
      final c = _client(server);
      await expectLater(
          c.client.deleteAccount(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'account_deletion_unconfirmed')));
      expect(server.erased, contains('dev-old'), reason: 'it committed');
      var told = 0;
      c.client.onDeviceErased = () async => told++;

      await c.client.getMemorySettings(); // the parent backs out; a screen asks
      await _drain();
      expect(server.liveTokensOf('dev-old'), isEmpty,
          reason: 'resurrected before: a post-deletion token for the erased id');
      expect(server.mintedFor, isNot(contains('dev-old')));
      expect(told, 1, reason: 'the app clears the phone');
      expect(c.storage.store['tg_device_id'], isNot('dev-old'));
      expect(await c.client.accountDeletionState(), kAccountDeletionConfirmed);

      // The next launch has nothing left to settle: the phone is cleared.
      final settled = await settlePendingAccountDeletion(client: c.client);
      expect(settled.outcome, PendingDeletion.none);
      expect(server.liveTokensOf('dev-old'), isEmpty);
    });

    test('…and when it did NOT go through, the re-sent DELETE finishes it, '
        'then the mint is for a fresh id', () async {
      final server = _Server(floor: null)..deleteUnreachable = true;
      final c = _client(server);
      await expectLater(c.client.deleteAccount(), throwsA(isA<TgApiError>()));
      expect(server.erased, isEmpty);
      server.deleteUnreachable = false;
      await c.client.endSession(); // "new conversation": a mint is needed
      await c.client.ensureSession();
      expect(server.erased, contains('dev-old'), reason: 'the parent asked');
      expect(server.mintedFor, isNot(contains('dev-old')));
      expect(server.liveTokensOf('dev-old'), isEmpty);
    });

    test('no answer to that DELETE: no mint at all for an id that may be erased',
        () async {
      final server = _Server(floor: null)..deleteAnswerLost = true;
      final c = _client(server);
      await expectLater(c.client.deleteAccount(), throwsA(isA<TgApiError>()));
      server.deleteUnreachable = true;
      await expectLater(c.client.getMemorySettings(), throwsA(isA<TgApiError>()));
      expect(server.mintedFor, isEmpty);
      expect(await c.client.accountDeletionState(), kAccountDeletionRequested);
      expect(c.storage.store['tg_deletion_token'], 'tok0',
          reason: 'still able to settle it, and the way out stays');
    });

    test('a gate that refuses erased ids to this build needs no settle first: '
        'the mint gets 410 and a fresh id', () async {
      final server = _Server(floor: 110)..deleteAnswerLost = true;
      final c = _client(server);
      await expectLater(c.client.deleteAccount(), throwsA(isA<TgApiError>()));
      var told = 0;
      c.client.onDeviceErased = () async => told++;
      await c.client.getMemorySettings();
      await _drain();
      expect(server.log.where((l) => l.startsWith('DELETE')), hasLength(1),
          reason: 'the 410 settled it; no DELETE re-sent');
      expect(server.liveTokensOf('dev-old'), isEmpty);
      expect(told, 1);
    });

    test('one settle at a time: a mint arriving meanwhile joins it', () async {
      final server = _Server(floor: null)..deleteAnswerLost = true;
      final c = _client(server, session: true);
      await expectLater(c.client.deleteAccount(), throwsA(isA<TgApiError>()));
      server.deleteAnswerLost = false;
      await c.client.endSession();
      server.holdDelete = Completer<void>();
      final launch = settlePendingAccountDeletion(client: c.client);
      await _drain();
      final screen = c.client.ensureSession(); // joins, does not mint
      await _drain();
      expect(server.mintedFor, isEmpty);
      server.holdDelete!.complete();
      expect((await launch).outcome, PendingDeletion.deleted);
      await screen;
      expect(server.log.where((l) => l.startsWith('DELETE')), hasLength(2),
          reason: 'the first attempt and ONE re-send');
      expect(server.mintedFor.single, isNot('dev-old'));
    });

    test('the settle\'s own mint never waits for the settle (re-entry)',
        () async {
      // Neither the DELETE's token nor a session is left (keystore reset).
      SharedPreferences.setMockInitialValues(
          {kAccountDeletionKey: kAccountDeletionRequested});
      final server = _Server(floor: null);
      final c = _client(server, session: false);
      final settled = await settlePendingAccountDeletion(client: c.client)
          .timeout(const Duration(seconds: 5));
      expect(settled.outcome, PendingDeletion.deleted);
      expect(server.erased, contains('dev-old'));
    });

    group('B2 · on a re-send only the handler\'s refusals prove the account', () {
      Future<({TgClient client, _Mem storage})> lostAnswer(_Server s) async {
        s.deleteAnswerLost = true;
        final c = _client(s);
        await expectLater(c.client.deleteAccount(), throwsA(isA<TgApiError>()));
        s.deleteAnswerLost = false;
        return c;
      }

      for (final (label, response) in [
        ('a rate limit before auth (429)', _json({'detail': 'طلبات كثيرة'}, 429)),
        ('an uncoded edge 403', http.Response('<html>blocked</html>', 403)),
        ('a bare 404', _json({'detail': 'Not Found'}, 404)),
      ]) {
        test('$label: unknown — never «لم يُحذف حسابك»', () async {
          final server = _Server(floor: null);
          final c = await lostAnswer(server);
          server.deleteOverride = response;
          final settled = await settlePendingAccountDeletion(client: c.client);
          expect(settled.outcome, PendingDeletion.unknown);
          expect(await c.client.accountDeletionState(), kAccountDeletionRequested);
          expect(c.storage.store['tg_deletion_token'], 'tok0');
        });
      }

      test('a coded refusal from the handler: the account is there', () async {
        final server = _Server(floor: null);
        final c = await lostAnswer(server);
        server.deleteOverride = _json({
          'detail': {'code': 'device_proof_required', 'message': 'm'}
        }, 403);
        final settled = await settlePendingAccountDeletion(client: c.client);
        expect(settled.outcome, PendingDeletion.notDeleted);
        expect(await c.client.accountDeletionState(), isNull);
      });

      test('a first attempt refused before auth deleted nothing', () async {
        final server = _Server(floor: null)
          ..deleteOverride = _json({'detail': 'طلبات كثيرة'}, 429);
        final c = _client(server);
        await expectLater(
            c.client.deleteAccount(),
            throwsA(isA<TgApiError>().having((e) => e.statusCode, 'status', 429)));
        expect(await c.client.accountDeletionState(), isNull);
      });
    });
  });

  // ── 2 ──────────────────────────────────────────────────────────────────
  group('2 · an answer is acted on only while the install still awaits it', () {
    test('C1 · gate on: a 410 met elsewhere while the settle waited — the '
        'settle reports nothing and leaves the confirmed record', () async {
      final server = _Server(floor: 110)..deleteAnswerLost = true;
      final c = _client(server);
      await expectLater(c.client.deleteAccount(), throwsA(isA<TgApiError>()));
      // -- next launch --
      final gate = Completer<void>();
      server.holdFirstAppConfig = gate; // the settle's own gate read waits
      final settling = settlePendingAccountDeletion(client: c.client);
      await _drain();
      var told = 0;
      c.client.onDeviceErased = () async => told++;
      await c.client.getMemorySettings(); // home: 401 → mint → 410 → fresh
      await _drain();
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(kAccountDeletionKey), kAccountDeletionConfirmed);
      final fresh = c.storage.store['tg_device_id'];
      final mints =
          server.log.where((l) => l.startsWith('POST /api/chat/sessions')).length;
      gate.complete(); // the settle's gate read answers now
      final settled = await settling;
      expect(
          server.log.where((l) => l.startsWith('POST /api/chat/sessions')),
          hasLength(mints),
          reason: 'nothing sent for the old id with the fresh install\'s token');
      expect(settled.outcome, isNot(PendingDeletion.notDeleted),
          reason: 'never «لم يُحذف» over the deleted page');
      expect(prefs.getString(kAccountDeletionKey), kAccountDeletionConfirmed,
          reason: 'the record stays for the wipe');
      expect(c.storage.store['tg_device_id'], fresh);
      expect(told, 1);
    });

    test('C2 · intact; the way out taken while the settle\'s mint travels: no '
        'old token kept, the old id never adopted back', () async {
      final server = _Server(floor: 110);
      final c = _client(server);
      SharedPreferences.setMockInitialValues(
          {kAccountDeletionKey: kAccountDeletionRequested});
      c.storage.store['tg_deletion_token'] = 'tok0';
      final hold = Completer<void>();
      server.holdMintFor = hold;
      server.holdMintDevice = 'dev-old';
      final settling = settlePendingAccountDeletion(client: c.client);
      await _drain();
      await c.client.startOverAfterAccountDeletion(); // the way out
      final fresh = c.storage.store['tg_device_id'];
      expect(fresh, isNot('dev-old'));
      hold.complete();
      final settled = await settling;
      expect(settled.outcome, PendingDeletion.none,
          reason: 'the way out reports, not this answer');
      expect(server.tokens[c.storage.store['tg_token']], isNot('dev-old'));
      expect(server.tokens[c.storage.store['tg_device_proof']], isNot('dev-old'));
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(kAccountDeletionKey), kAccountDeletionConfirmed);
      await c.client.endSession();
      await c.client.ensureSession();
      expect(c.storage.store['tg_device_id'], fresh);
    });
  });

  // ── 3 ──────────────────────────────────────────────────────────────────
  group('3 · the "unknown" copy promises a check, not an outcome', () {
    test('Arabic and English, as reviewed', () {
      final ar = lookupAppLocalizations(const Locale('ar'));
      final en = lookupAppLocalizations(const Locale('en'));
      expect(ar.deleteAccountUnconfirmed,
          'لم يصلنا ردّ واضح من الخادم، فلا نعرف بعد هل حُذف حسابك. سنتحقّق من ذلك حين يعود الاتصال: اضغط «تحقّق مرة أخرى»، أو يتحقّق التطبيق وحده حين تفتحه في المرة القادمة.');
      expect(en.deleteAccountUnconfirmed,
          "We didn't get a clear answer from the server, so we don't know yet whether your account was deleted. We'll check once you're back online: tap \"Check again\", or the app checks by itself next time you open it.");
      expect(ar.deleteAccountUnconfirmed, isNot(contains('انقطع الاتصال')),
          reason: 'an origin 5xx is not a dropped connection');
    });
  });

  // ── 4 ──────────────────────────────────────────────────────────────────
  group('4 · nothing before the first frame waits for the network', () {
    test('a wipe step that never answers is cut off',
        timeout: const Timeout(Duration(seconds: 20)), () async {
      final started = DateTime.now();
      await wipeStep(() => Completer<void>().future,
          timeout: const Duration(milliseconds: 50));
      expect(DateTime.now().difference(started),
          lessThan(const Duration(seconds: 2)));
    });

    test('the push token is renewed after the first frame, not before', () {
      final pending = File('lib/features/child_memory/data/pending_deletion.dart')
          .readAsStringSync();
      expect(pending, contains('wipeLocalDataAfterAccountDeletion(pushTokenLater: true)'));
      final wipe = File('lib/features/child_memory/data/local_wipe.dart')
          .readAsStringSync();
      expect(wipe, contains('if (!pushTokenLater) await renewPushTokenAfterWipe();'));
      expect(RegExp(r'deleteToken\(\)').allMatches(wipe), hasLength(1),
          reason: 'only inside renewPushTokenAfterWipe');
      final main = File('lib/main.dart').readAsStringSync();
      final run = main.indexOf('runApp(');
      final renew = main.indexOf('renewPushTokenAfterWipe()');
      expect(renew, greaterThan(run));
      expect(main.substring(renew - 60, renew),
          contains('if (clearedBeforeFirstFrame)'));
    });
  });

  // ── nits ───────────────────────────────────────────────────────────────
  group('nits', () {
    test('E · a 410 inside session recovery: the fresh device never carries '
        'the erased account\'s session id', () async {
      final server = _Server(floor: 110);
      final c = _client(server);
      server.tokens.clear(); // erased from another phone of the family
      server.erased.add('dev-old');
      await c.client.getMemorySettings();
      final token = c.storage.store['tg_token'];
      expect(server.tokens[token], c.storage.store['tg_device_id']);
      expect(c.storage.store['tg_device_id'], isNot('dev-old'));
      expect(c.storage.store['tg_session_id'], isNot('s1'));
      expect(c.storage.store['tg_session_id'], 's-$token');
    });

    test('an intact settle keeps the conversation and takes the new token',
        () async {
      final server = _Server(floor: 110);
      final c = _client(server);
      SharedPreferences.setMockInitialValues(
          {kAccountDeletionKey: kAccountDeletionRequested});
      c.storage.store['tg_deletion_token'] = 'tok0';
      final settled = await settlePendingAccountDeletion(client: c.client);
      expect(settled.outcome, PendingDeletion.notDeleted);
      expect(c.storage.store['tg_session_id'], 's1');
      expect(c.storage.store['tg_token'], isNot('tok0'));
      expect(server.tokens[c.storage.store['tg_token']], 'dev-old');
    });

    test('the launch loop stops after any step once the account is gone', () {
      final main = File('lib/main.dart').readAsStringSync();
      final start = main.indexOf('Future<void> _postLaunchGrowthLoop() async {');
      final loop = main.substring(start, main.indexOf('\n}\n', start));
      final steps =
          RegExp(r'^\s*await ', multiLine: true).allMatches(loop).length;
      final guards = 'if (_accountGone) return;'.allMatches(loop).length;
      expect(guards, steps - 1,
          reason: 'one check after every step but the last');
    });
  });
}

