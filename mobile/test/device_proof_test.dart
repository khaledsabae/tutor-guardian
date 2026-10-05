/// Device proof — the FCM challenge (MOBILE_API §9.0.1).
///
/// The service proves a session by posting back a code the server sent as a
/// silent data message. What is pinned here:
///   * the happy path, including a code that beats the `start` response;
///   * a code for another challenge is ignored — only ours is posted back;
///   * 20 s without the code → one more start → then the failure, with the
///     support address (never a third start);
///   * a pause is shown, never "proved through"; a rate limit is final;
///     `no_push_token` re-registers the token before the second start;
///   * one challenge at a time, and background attempts back off;
///   * the background isolate only forwards the code (PR #29: one `main()`
///     per process — FCM's isolate must never do the app's startup);
///   * the token is registered whether or not notifications were allowed.
library;

import 'dart:io';
import 'dart:isolate';
import 'dart:ui' show IsolateNameServer;

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/child_memory/data/memory_repository.dart';
import 'package:almorabbi/features/child_memory/device_proof/device_proof_service.dart';
import 'package:almorabbi/features/push/push_service.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';

import 'memory_fakes.dart';

/// A service over [server], with codes delivered the way FCM would.
DeviceProofService _service(
  FakeMemoryServer server, {
  Duration messageTimeout = const Duration(milliseconds: 60),
  Duration automaticBackoff = const Duration(minutes: 10),
}) {
  final service = DeviceProofService(
    server,
    messageTimeout: messageTimeout,
    automaticBackoff: automaticBackoff,
  );
  server.deliverCode = (id, code) => service.deliver(
      {'type': kDeviceProofMessageType, 'challenge_id': id, 'code': code});
  return service;
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    AppL10n.current = lookupAppLocalizations(const Locale('ar'));
  });

  group('the challenge', () {
    test('start → the code arrives → complete: the session is proven', () async {
      final server = FakeMemoryServer();
      final service = _service(server);
      await service.prove();
      expect(server.proven, isTrue);
      expect(server.starts, 1);
      expect(server.completes, 1);
      expect(service.state.value.phase, ProofPhase.proven);
      expect(service.state.value.provenEpoch, 1);
    });

    test('a code that beats the start response is still used', () async {
      late final DeviceProofService service;
      // No later delivery: only the one that lands before `start` returns.
      final server = _EarlyServer(() => service)..deliverCodes = false;
      service = DeviceProofService(server,
          messageTimeout: const Duration(milliseconds: 60));
      await service.prove();
      expect(server.proven, isTrue);
      expect(server.starts, 1);
    });

    test('an already proven session asks for nothing', () async {
      final server = FakeMemoryServer()..proven = true;
      final service = _service(server);
      await service.prove();
      expect(server.starts, 0);
      expect(service.state.value.phase, ProofPhase.proven);
    });

    test('a code for another challenge is ignored; ours is posted back',
        () async {
      final server = FakeMemoryServer()..deliverCodes = false;
      final service = _service(server);
      server.deliverCodes = true;
      // Delivered once the service is already waiting for its code.
      server.deliverCode = (id, code) => Future<void>.delayed(
            const Duration(milliseconds: 5),
            () {
              // Someone else's challenge first — must not be posted back…
              service.deliver({
                'type': kDeviceProofMessageType,
                'challenge_id': 'someone-elses',
                'code': 'their-code',
              });
              // …and an unrelated push of another type.
              service.deliver({'type': 'followup_due', 'link': '/followup/7'});
              service.deliver({
                'type': kDeviceProofMessageType,
                'challenge_id': id,
                'code': code,
              });
            },
          );
      await service.prove();
      expect(server.completes, 1); // only ours
      expect(server.proven, isTrue);
    });

    test('no code within the wait: one more start, then the failure',
        () async {
      final server = FakeMemoryServer()..deliverCodes = false;
      final service = _service(server);
      await expectLater(
        service.prove(),
        throwsA(isA<TgApiError>()
            .having((e) => e.code, 'code', 'proof_timeout')
            .having((e) => e.supportEmail, 'support', kSupportEmail)),
      );
      expect(server.starts, 2); // §9.0.1: start once more, not more
      expect(server.completes, 0);
      expect(service.state.value.phase, ProofPhase.failed);
    });

    test('a wrong code is answered by one more start', () async {
      final server = FakeMemoryServer();
      final service = _service(server);
      var first = true;
      server.deliverCode = (id, code) {
        service.deliver({
          'type': kDeviceProofMessageType,
          'challenge_id': id,
          'code': first ? 'garbled' : code,
        });
        first = false;
      };
      await service.prove();
      expect(server.starts, 2);
      expect(server.proven, isTrue);
    });

    test('a pause is shown with its end, and no challenge is started',
        () async {
      final until = DateTime.now().toUtc().add(const Duration(hours: 71));
      final server = FakeMemoryServer()..cooldownUntil = until;
      final service = _service(server);
      await expectLater(
        service.prove(),
        throwsA(isA<TgApiError>()
            .having((e) => e.code, 'code', 'device_proof_cooldown')
            .having((e) => e.availableAt!.difference(until).inSeconds.abs(),
                'available_at', lessThan(2))),
      );
      expect(server.starts, 0);
      expect(service.state.value.phase, ProofPhase.paused);
      expect(service.state.value.pausedUntil, isNotNull);
    });

    test('no_push_token: register the token, then start once more', () async {
      final server = FakeMemoryServer()..pushRegistered = false;
      final service = _service(server);
      var registered = 0;
      service.reRegisterPushToken = () async {
        registered++;
        server.pushRegistered = true;
      };
      await service.prove();
      expect(registered, 1);
      expect(server.starts, 2);
      expect(server.proven, isTrue);
    });

    test('no_push_token twice ends with the server\'s message and address',
        () async {
      final server = FakeMemoryServer()..pushRegistered = false;
      final service = _service(server);
      service.reRegisterPushToken = () async {};
      await expectLater(
          service.prove(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'no_push_token')
              .having((e) => e.supportEmail, 'support', 'support@alsaba.cloud')));
      expect(server.starts, 2);
    });

    test('a rate limit is final: no second start', () async {
      final server = FakeMemoryServer()
        ..startErrors.add(coded(429, 'proof_rate_limited'));
      final service = _service(server);
      await expectLater(
          service.prove(),
          throwsA(isA<TgApiError>()
              .having((e) => e.code, 'code', 'proof_rate_limited')));
      expect(server.starts, 1);
    });

    test('push_unavailable: start once more', () async {
      final server = FakeMemoryServer()
        ..startErrors.add(coded(503, 'push_unavailable'));
      final service = _service(server);
      await service.prove();
      expect(server.starts, 2);
      expect(server.proven, isTrue);
    });

    test('one challenge at a time: concurrent callers share it', () async {
      final server = FakeMemoryServer();
      final service = _service(server);
      await Future.wait([service.prove(), service.prove(), service.prove()]);
      expect(server.starts, 1);
    });

    test('background attempts back off after a failure; a tap does not',
        () async {
      final server = FakeMemoryServer()..deliverCodes = false;
      final service = _service(server);
      await service.prove().then((_) {}, onError: (_) {});
      expect(server.starts, 2);
      await service.prove(automatic: true).then((_) {}, onError: (_) {});
      expect(server.starts, 2, reason: 'held back: nothing was asked');
      server.deliverCodes = true;
      await service.prove(); // the parent's own "try again"
      expect(server.proven, isTrue);
      expect(server.starts, 3);
    });
  });

  group('proving in the background (§9.0.1 «When to prove»)', () {
    test('memory on and unproven: it proves', () async {
      final server = FakeMemoryServer();
      final service = _service(server);
      await service.proveIfUseful();
      expect(server.proven, isTrue);
    });

    test('memory off: nothing is started', () async {
      final server = FakeMemoryServer()..enabled = false;
      await _service(server).proveIfUseful();
      expect(server.starts, 0);
    });

    test('already proven: nothing is started', () async {
      final server = FakeMemoryServer()..proven = true;
      await _service(server).proveIfUseful();
      expect(server.starts, 0);
    });

    test('a pause: nothing is started, and the pause is recorded', () async {
      final server = FakeMemoryServer()
        ..cooldownUntil = DateTime.now().toUtc().add(const Duration(hours: 5));
      final service = _service(server);
      await service.proveIfUseful();
      expect(server.starts, 0);
      expect(service.state.value.phase, ProofPhase.paused);
    });

    test('a server without memory is left alone, quietly', () async {
      final server = FakeMemoryServer()..memorySupported = false;
      final service = _service(server);
      await service.proveIfUseful(); // must not throw
      expect(server.starts, 0);
      expect(server.calls, ['GET /api/children/memory/settings']);
    });
  });

  group('wired into the client', () {
    test('a protected call proves through the service and retries', () async {
      final server = FakeMemoryServer()
        ..facts[1] = [factJson(1, 1)];
      final service = _service(server);
      server.onDeviceProofRequired = () => service.prove();
      final memory = await MemoryRepository(server).facts(1);
      expect(memory.facts.single.id, 1);
      expect(server.calls.where((c) => c.startsWith('GET /api/children/1/memory')),
          hasLength(2));
    });
  });

  group('the background isolate only forwards', () {
    test('a code sent through the named port reaches the waiting challenge',
        () async {
      final server = FakeMemoryServer()..deliverCodes = false;
      final service = DeviceProofService(server,
          messageTimeout: const Duration(seconds: 2));
      service.init();
      addTearDown(service.dispose);
      server.deliverCodes = true;
      // As FCM's background isolate would: through the port, not a call.
      server.deliverCode = (id, code) => forwardDeviceProofFromBackground({
            'type': kDeviceProofMessageType,
            'challenge_id': id,
            'code': code,
          });
      await service.prove();
      expect(server.proven, isTrue);
    });

    test('init gives the client its proof hook and is idempotent', () async {
      final server = FakeMemoryServer();
      final service = DeviceProofService(server);
      service.init();
      service.init();
      addTearDown(service.dispose);
      expect(server.onDeviceProofRequired, isNotNull);
      expect(IsolateNameServer.lookupPortByName(kDeviceProofPortName), isNotNull);
    });

    test('other messages are not taken, and no listener is no error', () {
      IsolateNameServer.removePortNameMapping(kDeviceProofPortName);
      expect(forwardDeviceProofFromBackground({'type': 'followup_due'}), isFalse);
      expect(
          forwardDeviceProofFromBackground({
            'type': kDeviceProofMessageType,
            'challenge_id': 'x',
            'code': 'y',
          }),
          isTrue);
    });

    test('a forwarded message is a plain map of strings (sendable)', () async {
      final port = ReceivePort();
      IsolateNameServer.removePortNameMapping(kDeviceProofPortName);
      IsolateNameServer.registerPortWithName(port.sendPort, kDeviceProofPortName);
      addTearDown(() {
        IsolateNameServer.removePortNameMapping(kDeviceProofPortName);
        port.close();
      });
      forwardDeviceProofFromBackground({
        'type': kDeviceProofMessageType,
        'challenge_id': 'c1',
        'code': 'k1',
        'extra': 'not forwarded',
      });
      final got = await port.first.timeout(const Duration(seconds: 2));
      expect(got, {'type': kDeviceProofMessageType, 'challenge_id': 'c1', 'code': 'k1'});
    });

    // Source, not behaviour, deliberately: the handler runs in FCM's own
    // isolate, which no host test can start. PR #29 traced the device-twin bug
    // to a second isolate running the app's startup — its own session mint and
    // device id. Whatever this handler grows into, it must not do that.
    test('the background handler does not start the app', () {
      final src = File('lib/features/push/push_service.dart').readAsStringSync();
      final start = src.indexOf(
          'Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message)');
      expect(start, greaterThan(0), reason: 'the handler was renamed');
      final body = src.substring(start, src.indexOf('\n}\n', start));
      for (final forbidden in [
        'TgClient',
        'ensureSession',
        'createSession',
        'registerPushToken',
        'getOrCreateDeviceId',
        'SharedPreferences',
        'FlutterSecureStorage',
        'runApp',
        'main(',
        'DeviceProofService',
      ]) {
        expect(body.contains(forbidden), isFalse,
            reason: 'the background handler must not touch $forbidden');
      }
      expect(body.contains('forwardDeviceProofFromBackground'), isTrue);
    });
  });

  group('the push token is registered whatever the notification answer', () {
    test('a refusal still uploads the token (data messages need no permission)',
        () async {
      final uploaded = <String>[];
      final token = await PushService.registerWith(
        askPermission: () async => false,
        fetchToken: () async => 'fcm-token',
        upload: (t) async => uploaded.add(t),
      );
      expect(token, 'fcm-token');
      expect(uploaded, ['fcm-token']);
    });

    test('no token, no upload', () async {
      var uploads = 0;
      expect(
          await PushService.registerWith(
            askPermission: () async => true,
            fetchToken: () async => null,
            upload: (_) async => uploads++,
          ),
          isNull);
      expect(uploads, 0);
    });
  });
}

/// A server whose code arrives BEFORE `start` returns — FCM beat the HTTP
/// response. The service must find it when it learns the challenge id.
class _EarlyServer extends FakeMemoryServer {
  _EarlyServer(this._target);
  final DeviceProofService Function() _target;

  @override
  Future<Map<String, dynamic>> startDeviceProof() async {
    final answer = await super.startDeviceProof();
    _target().deliver({
      'type': kDeviceProofMessageType,
      'challenge_id': answer['challenge_id'],
      'code': 'code-$starts',
    });
    return answer;
  }
}
