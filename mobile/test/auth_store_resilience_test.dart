// Device identity must survive storage hiccups (audit H7) and session minting
// must carry the device proof (audit H5).
//
// `_AuthStore._safeRead` used to call `deleteAll()` on ANY read exception, so a
// transient keystore error erased `tg_device_id` and orphaned every
// server-side record for the family.

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';

class _FlakyStorage implements FlutterSecureStorage {
  _FlakyStorage(this.store);

  final Map<String, String> store;
  int failReads = 0;
  bool deleteAllCalled = false;

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
    if (failReads > 0) {
      failReads--;
      throw Exception('keystore temporarily unavailable');
    }
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
    deleteAllCalled = true;
    store.clear();
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// Records the device_id and Authorization of every session mint.
class _Recorder {
  final bodies = <Map<String, dynamic>>[];
  final auths = <String?>[];
  int n = 0;

  MockClient client() => MockClient((req) async {
        if (req.url.path == '/api/chat/sessions') {
          bodies.add(jsonDecode(req.body) as Map<String, dynamic>);
          auths.add(req.headers['Authorization']);
          n++;
          return http.Response(
            jsonEncode({'session_id': 's$n', 'token': 'tok$n'}),
            201,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('{}', 404);
      });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('a transient read failure never wipes the stored device id', () async {
    final storage = _FlakyStorage({'tg_device_id': 'family-device-1'})
      ..failReads = 2; // both attempts of the first read fail
    final rec = _Recorder();
    final client = TgClient.forTesting(
      baseUrl: 'http://x', httpClient: rec.client(), storage: storage);

    await client.createSession();

    expect(storage.deleteAllCalled, isFalse);
    expect(storage.store['tg_device_id'], 'family-device-1',
        reason: 'the real id must still be in the keystore');
  });

  test('one failed read is retried and the real id is used', () async {
    final storage = _FlakyStorage({'tg_device_id': 'family-device-1'})
      ..failReads = 1;
    final rec = _Recorder();
    final client = TgClient.forTesting(
      baseUrl: 'http://x', httpClient: rec.client(), storage: storage);

    await client.createSession();
    expect(rec.bodies.single['device_id'], 'family-device-1');
  });

  test('the backup restores the identity when the keystore lost it', () async {
    SharedPreferences.setMockInitialValues({'tg_device_id_backup': 'family-device-1'});
    final storage = _FlakyStorage({}); // keystore reset by the platform
    final rec = _Recorder();
    final client = TgClient.forTesting(
      baseUrl: 'http://x', httpClient: rec.client(), storage: storage);

    await client.createSession();
    expect(rec.bodies.single['device_id'], 'family-device-1');
    expect(storage.store['tg_device_id'], 'family-device-1');
  });

  test('a new conversation mints with the previous token as proof', () async {
    final storage = _FlakyStorage({});
    final rec = _Recorder();
    final client = TgClient.forTesting(
      baseUrl: 'http://x', httpClient: rec.client(), storage: storage);

    await client.createSession();           // first install: no proof yet
    await client.endSession();              // "new conversation" clears it…
    await client.createSession();           // …but the proof survives

    expect(rec.auths.first, isNull);
    expect(rec.auths.last, 'Bearer tok1');
    expect(rec.bodies.first['device_id'], rec.bodies.last['device_id']);
  });
}
