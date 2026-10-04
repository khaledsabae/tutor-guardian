// One install, one device id — however many callers ask at once.
//
// 2026-10-04: a fresh install minted TWO device ids in the same second (same
// FCM token). The cause was a second Flutter engine running main() (see
// single_dart_entrypoint_test.dart), but the identity code was racy on its own
// too: getOrCreateDeviceId() checked a cache, then awaited the keystore, so
// every caller that arrived during that await minted its own id. These tests
// reproduce both races — within one isolate, and across "engines" (separate
// TgClients / real isolates sharing one keystore) — and pin the fix.

import 'dart:convert';
import 'dart:io';
import 'dart:isolate';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import 'package:almorabbi/api/device_id_claim.dart';
import 'package:almorabbi/api/tg_client.dart';

/// A keystore that takes as long as a real first-use keystore does (key
/// generation, a platform round trip) — long enough for callers to overlap.
class _SlowKeystore implements FlutterSecureStorage {
  _SlowKeystore(this.store);

  final Map<String, String> store;
  final writes = <String, int>{};
  static const _latency = Duration(milliseconds: 25);

  @override
  Future<String?> read({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    await Future<void>.delayed(_latency);
    return store[key];
  }

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
    await Future<void>.delayed(_latency);
    writes[key] = (writes[key] ?? 0) + 1;
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
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// The backend, as far as identity goes: records which device each mint,
/// feedback and push registration claimed.
class _Server {
  _Server({this.mintAs, this.pushRecoversTo});

  /// When set, every mint answers for this device (a twin re-attached).
  final String? mintAs;

  /// When set, push registration answers with this canonical device.
  final String? pushRecoversTo;

  final mintedFor = <String>[];
  final mintProofs = <String?>[];
  final feedbackFrom = <String>[];
  int _n = 0;

  MockClient client() => MockClient((req) async {
        switch (req.url.path) {
          case '/api/chat/sessions':
            final body = jsonDecode(req.body) as Map<String, dynamic>;
            mintedFor.add(body['device_id'] as String);
            mintProofs.add(req.headers['Authorization']);
            _n++;
            return http.Response(
              jsonEncode({
                'session_id': 's$_n',
                'token': 'tok$_n',
                'device_id': ?mintAs,
              }),
              201,
              headers: {'content-type': 'application/json'},
            );
          case '/api/feedback/app':
            final body = jsonDecode(req.body) as Map<String, dynamic>;
            feedbackFrom.add(body['device_id'] as String);
            return http.Response(jsonEncode({'id': 'f1'}), 201,
                headers: {'content-type': 'application/json'});
          case '/api/push/register':
            return http.Response(
              jsonEncode({
                'ok': true,
                if (pushRecoversTo != null) ...{
                  'device_id': pushRecoversTo,
                  'identity_recovered': true,
                },
              }),
              200,
              headers: {'content-type': 'application/json'},
            );
        }
        return http.Response('{}', 404);
      });
}

DeviceIdClaim _claimIn(Directory dir) => DeviceIdClaim(() async => dir);

/// An isolate entry that captures nothing but the directory path.
Future<String?> Function() _claimer(String path) => () =>
    DeviceIdClaim(() async => Directory(path)).claim(const Uuid().v4());

/// No claim at all — what every engine had before the fix.
DeviceIdClaim _noClaim() => DeviceIdClaim(() async => null);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tmp;
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    tmp = Directory.systemTemp.createTempSync('tg_claim_');
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  group('within one isolate', () {
    test('parallel startup callers share one device id, persisted once',
        () async {
      final keystore = _SlowKeystore({});
      final server = _Server();
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _noClaim(), // the in-isolate fix must stand on its own
      );

      // What a cold start does at once: the growth loop's mint, a screen's
      // own createSession, and a feedback send.
      await Future.wait([
        client.createSession(),
        client.createSession(),
        client.sendAppFeedback(message: 'x'),
      ]);

      final ids = {...server.mintedFor, ...server.feedbackFrom};
      expect(ids, hasLength(1), reason: 'one install must be one device');
      expect(keystore.store['tg_device_id'], ids.single);
      expect(keystore.writes['tg_device_id'], 1,
          reason: 'resolved once, not once per caller');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('tg_device_id_backup'), ids.single);
    });

    test('an id already in the keystore is never replaced by a claim',
        () async {
      File('${tmp.path}/tg_device_id.claim').writeAsStringSync('stale-claim');
      final keystore = _SlowKeystore({'tg_device_id': 'family-1'});
      final server = _Server();
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.createSession();
      expect(server.mintedFor, ['family-1']);
    });

    test('the claim file brings the id back when keystore and backup are gone',
        () async {
      File('${tmp.path}/tg_device_id.claim').writeAsStringSync('family-1');
      final keystore = _SlowKeystore({}); // keystore reset, backup cleared
      final server = _Server();
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.createSession();
      expect(server.mintedFor, ['family-1']);
      expect(keystore.store['tg_device_id'], 'family-1');
    });
  });

  group('across engines (two TgClients = two isolates\' memories)', () {
    Future<Set<String>> freshInstallWithTwoEngines(DeviceIdClaim Function() claim) async {
      final keystore = _SlowKeystore({}); // one keystore, as on the phone
      final server = _Server();
      TgClient engine() => TgClient.forTesting(
            baseUrl: 'http://x',
            httpClient: server.client(),
            storage: keystore,
            deviceIdClaim: claim(),
          );
      await Future.wait([engine().createSession(), engine().createSession()]);
      return server.mintedFor.toSet();
    }

    test('without a shared claim, two engines mint two ids (the bug)',
        () async {
      // This is what production did on ~40% of fresh installs: each engine
      // found the keystore empty and minted its own family.
      final ids = await freshInstallWithTwoEngines(_noClaim);
      expect(ids, hasLength(2));
    });

    test('with the claim, two engines on a fresh install mint one id',
        () async {
      final ids = await freshInstallWithTwoEngines(() => _claimIn(tmp));
      expect(ids, hasLength(1));
    });
  });

  group('DeviceIdClaim across real isolates', () {
    test('exactly one candidate wins, whoever asks', () async {
      final path = tmp.path;
      final results = await Future.wait([
        for (var i = 0; i < 8; i++) Isolate.run(_claimer(path)),
      ]);
      expect(results.toSet(), hasLength(1), reason: '$results');
      expect(results.first, isNotNull);
      expect(File('$path/tg_device_id.claim').readAsStringSync(), results.first);
    });

    test('a claim whose writer died does not hang startup', () async {
      File('${tmp.path}/tg_device_id.claim').createSync(); // empty forever
      final sw = Stopwatch()..start();
      final got = await _claimIn(tmp).claim('candidate');
      expect(got, isNull, reason: 'the caller falls back to its own id');
      expect(sw.elapsed, lessThan(const Duration(seconds: 5)));
    });

    test('no directory, no claim — the caller keeps its candidate', () async {
      expect(await _noClaim().claim('candidate'), isNull);
    });
  });

  group('a device id the server would refuse (keystore garbage)', () {
    // The shapes production holds (2026-10-04): mostly U+FFFD with stray
    // characters — a keystore decrypting with the wrong key — and one with
    // spaces. The server answers 422 to such an id on every mint, forever.
    const garbage = '\uFFFD\uFFFDk\uFFFD9 \uFFFD-\uFFFD\uFFFD';
    const spaced = 'abcd efgh ijkl mnop';

    test('the rule is the server\'s', () {
      expect(isValidDeviceId('0b5c2f6e-1d2a-4c3b-9f8e-7a6b5c4d3e2f'), isTrue);
      expect(isValidDeviceId('device_0123456789ab'), isTrue);
      expect(isValidDeviceId('a' * 128), isTrue);
      for (final bad in [null, '', spaced, garbage, 'a' * 129, 'é', 'a/b']) {
        expect(isValidDeviceId(bad), isFalse, reason: '$bad');
      }
    });

    test('is never sent: a fresh valid id replaces it, and the proof still goes',
        () async {
      final keystore = _SlowKeystore({
        'tg_device_id': garbage,
        'tg_device_proof': 'tok-of-the-family-device',
      });
      final server = _Server();
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.createSession();

      final sent = server.mintedFor.single;
      expect(isValidDeviceId(sent), isTrue);
      expect(keystore.store['tg_device_id'], sent, reason: 'the garbage is overwritten');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('tg_device_id_backup'), sent);
      // The proof is what lets the server move the family's device to the new
      // id (device_twins.resolve_mint); dropping it would orphan the family.
      expect(server.mintProofs.single, 'Bearer tok-of-the-family-device');
    });

    test('a valid backup wins over a garbage keystore id', () async {
      SharedPreferences.setMockInitialValues({'tg_device_id_backup': 'family-1'});
      final keystore = _SlowKeystore({'tg_device_id': spaced});
      final server = _Server();
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.createSession();
      expect(server.mintedFor, ['family-1']);
      expect(keystore.store['tg_device_id'], 'family-1');
    });

    test('a garbage backup is not trusted either', () async {
      SharedPreferences.setMockInitialValues({'tg_device_id_backup': garbage});
      final keystore = _SlowKeystore({'tg_device_id': spaced});
      final server = _Server();
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.createSession();
      final sent = server.mintedFor.single;
      expect(isValidDeviceId(sent), isTrue);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('tg_device_id_backup'), sent);
    });

    test('a garbage claim file is replaced, not adopted', () async {
      File('${tmp.path}/tg_device_id.claim').writeAsStringSync(garbage);
      final keystore = _SlowKeystore({});
      final server = _Server();
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.createSession();
      final sent = server.mintedFor.single;
      expect(isValidDeviceId(sent), isTrue);
      expect(File('${tmp.path}/tg_device_id.claim').readAsStringSync(), sent);
    });

    test('a device id the server hands back is adopted only if valid', () async {
      final keystore = _SlowKeystore({'tg_device_id': 'family'});
      final server = _Server(mintAs: spaced);
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.createSession();
      expect(keystore.store['tg_device_id'], 'family');
    });
  });

  group('the server re-attached this install to the family device', () {
    test('a mint answered for another device is adopted for good', () async {
      final keystore = _SlowKeystore({'tg_device_id': 'twin'});
      final server = _Server(mintAs: 'family');
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.createSession();
      await client.sendAppFeedback(message: 'after');

      expect(server.mintedFor, ['twin']);
      expect(server.feedbackFrom, ['family']);
      expect(keystore.store['tg_device_id'], 'family');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('tg_device_id_backup'), 'family');
      expect(File('${tmp.path}/tg_device_id.claim').readAsStringSync(), 'family');
    });

    test('push registration that recovered the identity is adopted', () async {
      final keystore = _SlowKeystore({'tg_device_id': 'twin'});
      final server = _Server(pushRecoversTo: 'family');
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.registerPushToken('fcm-token');
      await client.sendAppFeedback(message: 'after');

      expect(server.feedbackFrom, ['family']);
      expect(keystore.store['tg_device_id'], 'family');
    });

    test('an ordinary push registration changes nothing', () async {
      final keystore = _SlowKeystore({'tg_device_id': 'family'});
      final server = _Server();
      final client = TgClient.forTesting(
        baseUrl: 'http://x',
        httpClient: server.client(),
        storage: keystore,
        deviceIdClaim: _claimIn(tmp),
      );

      await client.registerPushToken('fcm-token');
      expect(keystore.store['tg_device_id'], 'family');
      expect(keystore.writes['tg_device_id'], isNull);
    });
  });
}
