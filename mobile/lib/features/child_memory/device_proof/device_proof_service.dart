/// Device proof — the FCM challenge behind every protected memory route
/// (MOBILE_API.md §9.0.1).
///
/// The server proves that a session holds the phone by sending a one-time code
/// to the device's current push token as a silent data message
/// (`{"type": "device_proof", "challenge_id", "code"}`). The app posts the code
/// back with the same session, and that session is proven for as long as the
/// push token stays the same.
///
/// The message can arrive in two places:
///   * `FirebaseMessaging.onMessage`, in this isolate, when the app is in the
///     foreground — the usual case: the parent just tapped something;
///   * FCM's background handler, in FCM's own background isolate, when the app
///     went to the background while waiting.
///
/// The background isolate is NOT the app. PR #29 found the device-twin bug in
/// a second Flutter engine that ran `main()` — its own session mint, its own
/// device id. So the background handler does exactly one thing with a proof
/// message: it hands it to this isolate through [IsolateNameServer]
/// ([forwardDeviceProofFromBackground]). It never mints a session, never reads
/// the keystore, never posts the code itself, and never starts an engine. If
/// the app's isolate is gone, nothing was waiting for the code and it is
/// dropped; it expires on the server in five minutes.
library;

import 'dart:async';
import 'dart:isolate';
import 'dart:ui' show IsolateNameServer;

import 'package:flutter/foundation.dart';

import '../../../api/tg_client.dart';
import '../../../core/analytics.dart';
import '../../../l10n/l10n_global.dart';
import '../data/memory_models.dart';

/// Where the background isolate finds this isolate's inbox.
const String kDeviceProofPortName = 'tg.device_proof';

/// The data message's `type`.
const String kDeviceProofMessageType = 'device_proof';

/// The address the server names when the automatic path cannot work.
const String kSupportEmail = 'support@alsaba.cloud';

/// From FCM's background isolate: pass a device-proof message to the app's
/// isolate, and do nothing else. Returns true when [data] was a device-proof
/// message (whether or not anyone was listening), so the caller can stop.
bool forwardDeviceProofFromBackground(Map<String, dynamic> data) {
  if (data['type'] != kDeviceProofMessageType) return false;
  final challengeId = data['challenge_id'];
  final code = data['code'];
  if (challengeId is! String || code is! String) return true;
  IsolateNameServer.lookupPortByName(kDeviceProofPortName)?.send(
    <String, String>{
      'type': kDeviceProofMessageType,
      'challenge_id': challengeId,
      'code': code,
    },
  );
  return true;
}

/// Where the proof stands, for the screens that wait on it.
enum ProofPhase {
  /// Nothing asked yet this run.
  idle,

  /// A challenge is under way — «نتأكّد أن هذا هاتفك…».
  confirming,

  /// This session is proven.
  proven,

  /// The protected routes are paused (`device_proof_cooldown`) until
  /// [ProofState.pausedUntil]; a challenge cannot lift it.
  paused,

  /// The challenge could not complete; [ProofState.error] says why.
  failed,
}

@immutable
class ProofState {
  const ProofState({
    this.phase = ProofPhase.idle,
    this.pausedUntil,
    this.error,
    this.provenEpoch = 0,
  });

  final ProofPhase phase;
  final DateTime? pausedUntil;
  final TgApiError? error;

  /// Goes up by one on every success, so data that needs a proof (the Today
  /// follow-up card) can refetch the moment one lands.
  final int provenEpoch;

  ProofState copyWith({
    ProofPhase? phase,
    DateTime? pausedUntil,
    TgApiError? error,
    int? provenEpoch,
  }) =>
      ProofState(
        phase: phase ?? this.phase,
        pausedUntil: pausedUntil,
        error: error,
        provenEpoch: provenEpoch ?? this.provenEpoch,
      );
}

class DeviceProofService {
  DeviceProofService(
    this._client, {
    this.messageTimeout = const Duration(seconds: 20),
    this.automaticBackoff = const Duration(minutes: 10),
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now;

  static DeviceProofService? _instance;

  /// The app-wide service, over [TgClient.shared].
  static DeviceProofService get instance =>
      _instance ??= DeviceProofService(TgClient.shared);

  @visibleForTesting
  static set instance(DeviceProofService? service) => _instance = service;

  final TgClient _client;

  /// §9.0.1: wait at most 20 seconds for the message.
  final Duration messageTimeout;

  /// After a failure, background attempts wait this long before trying
  /// again — five starts an hour is the server's limit per session, and a
  /// phone that cannot receive the code will not receive it on the next
  /// screen either. A parent's own tap ("Try again") is never held back.
  final Duration automaticBackoff;
  final DateTime Function() _now;

  /// Registers this phone's push token again (wired to PushService in
  /// `main`): the answer to `no_push_token`.
  Future<void> Function()? reRegisterPushToken;

  final ValueNotifier<ProofState> state = ValueNotifier(const ProofState());

  /// Codes that came before anyone asked for them, by challenge id: the data
  /// message can beat the `start` response. Never logged, never shown, kept
  /// in memory for the code's own lifetime at most.
  final Map<String, ({String code, DateTime at})> _early = {};
  final Map<String, Completer<String>> _waiting = {};

  Future<void>? _inflight;
  DateTime? _lastFailureAt;
  ReceivePort? _port;
  StreamSubscription<Map<String, dynamic>>? _foreground;

  /// Start listening, and give the client its proof hook. Idempotent.
  ///
  /// [foregroundMessages] is `FirebaseMessaging.onMessage` (as data maps);
  /// the background isolate reaches us through the named port.
  void init({Stream<Map<String, dynamic>>? foregroundMessages}) {
    _client.onDeviceProofRequired ??= () => prove();
    if (_port == null) {
      final port = ReceivePort();
      IsolateNameServer.removePortNameMapping(kDeviceProofPortName);
      IsolateNameServer.registerPortWithName(port.sendPort, kDeviceProofPortName);
      port.listen((message) {
        if (message is Map) deliver(Map<String, dynamic>.from(message));
      });
      _port = port;
    }
    if (foregroundMessages != null) {
      _foreground ??= foregroundMessages.listen(deliver, onError: (_) {});
    }
  }

  /// Stop listening (tests; the app's service lives as long as the app).
  @visibleForTesting
  Future<void> dispose() async {
    await _foreground?.cancel();
    _foreground = null;
    final port = _port;
    if (port != null) {
      if (IsolateNameServer.lookupPortByName(kDeviceProofPortName) ==
          port.sendPort) {
        IsolateNameServer.removePortNameMapping(kDeviceProofPortName);
      }
      port.close();
    }
    _port = null;
  }

  /// A data message, from either isolate. Anything that is not a device-proof
  /// message is ignored; so is a code nobody here asked for, once it ages out.
  void deliver(Map<String, dynamic> data) {
    if (data['type'] != kDeviceProofMessageType) return;
    final id = data['challenge_id'];
    final code = data['code'];
    if (id is! String || code is! String || id.isEmpty || code.isEmpty) return;
    final waiter = _waiting.remove(id);
    if (waiter != null) {
      if (!waiter.isCompleted) waiter.complete(code);
      return;
    }
    _pruneEarly();
    _early[id] = (code: code, at: _now());
  }

  void _pruneEarly() {
    final cutoff = _now().subtract(const Duration(minutes: 5));
    _early.removeWhere((_, v) => v.at.isBefore(cutoff));
  }

  /// Prove this session. Single-flight: concurrent callers share one run.
  ///
  /// Completes when the session is proven. Throws a [TgApiError] when it
  /// cannot be: `device_proof_cooldown` (with `available_at`) during a pause,
  /// or the challenge's own error — `no_push_token`, `push_unavailable`,
  /// `proof_rate_limited`, `proof_failed`, or `proof_timeout` when the code
  /// never came — with the support address to offer.
  ///
  /// [automatic] marks a background attempt nobody is looking at: it is held
  /// back for [automaticBackoff] after a failure.
  Future<void> prove({bool automatic = false}) {
    final running = _inflight;
    if (running != null) return running;
    final last = _lastFailureAt;
    if (automatic &&
        last != null &&
        _now().difference(last) < automaticBackoff) {
      return Future.error(state.value.error ?? _timeoutError());
    }
    final run = _run();
    _inflight = run;
    run.then((_) {}, onError: (_) {}).whenComplete(() {
      if (identical(_inflight, run)) _inflight = null;
    });
    return run;
  }

  /// §9.0.1 «When to prove»: in the background after a launch (a new
  /// session) or a new push token, while memory is in use — otherwise answers
  /// and coach tips go without memory until the parent opens a protected
  /// screen. Quiet: never throws, never shows anything. A server that does
  /// not know memory (404) is simply left alone.
  Future<void> proveIfUseful() async {
    try {
      final settings =
          MemorySettings.fromJson(await _client.getMemorySettings());
      if (!settings.enabled || settings.proven) return;
      if (settings.cooldownUntil != null) {
        _pause(settings.cooldownUntil!, null);
        return;
      }
      await prove(automatic: true);
    } catch (_) {
      // Background work: a failure here is recorded in [state] and retried
      // when a screen needs the proof.
    }
  }

  Future<void> _run() async {
    state.value = state.value.copyWith(phase: ProofPhase.confirming);
    try {
      final status = await _statusOrNull();
      if (status != null) {
        if (status.proven) {
          _succeed(record: false);
          return;
        }
        final until = status.cooldownUntil;
        if (until != null && until.isAfter(_now().toUtc())) {
          throw _pausedError(until);
        }
      }
      TgApiError? last;
      for (var attempt = 0; attempt < 2; attempt++) {
        try {
          await _attempt();
          _succeed();
          return;
        } on TgApiError catch (e) {
          last = e;
          switch (e.code) {
            case 'no_push_token':
              // Register the token, then start once more.
              if (attempt == 0) await _reRegister();
              continue;
            case 'push_unavailable':
            case 'proof_failed':
            case 'proof_timeout':
              continue; // "start once more"
            default:
              rethrow; // rate limit, cooldown, transport: no second start
          }
        }
      }
      throw last!;
    } on TgApiError catch (e) {
      _fail(e);
      rethrow;
    } catch (e) {
      final err = TgApiError(null, AppL10n.current.proofFailedBody,
          code: 'proof_timeout', details: const {'support_email': kSupportEmail});
      _fail(err);
      throw err;
    }
  }

  Future<DeviceProofStatus?> _statusOrNull() async {
    try {
      return DeviceProofStatus.fromJson(await _client.getDeviceProofStatus());
    } on TgApiError catch (e) {
      // A server without the status route still answers start/complete the
      // same way; let the challenge itself decide.
      if (e.isMissingEndpoint) return null;
      rethrow;
    }
  }

  Future<void> _attempt() async {
    final started = await _client.startDeviceProof();
    final id = started['challenge_id'];
    if (id is! String || id.isEmpty) {
      throw TgApiError(409, AppL10n.current.proofFailedBody,
          code: 'proof_failed', details: const {'reason': 'not_found'});
    }
    final String code;
    try {
      code = await _codeFor(id);
    } on TimeoutException {
      throw _timeoutError();
    }
    await _client.completeDeviceProof(id, code);
  }

  /// The code for [challengeId]: one that already arrived, or the next one.
  Future<String> _codeFor(String challengeId) {
    final early = _early.remove(challengeId);
    if (early != null) return Future.value(early.code);
    final waiter = Completer<String>();
    _waiting[challengeId] = waiter;
    return waiter.future.timeout(messageTimeout, onTimeout: () {
      _waiting.remove(challengeId);
      throw TimeoutException('device proof message', messageTimeout);
    });
  }

  Future<void> _reRegister() async {
    final register = reRegisterPushToken;
    if (register == null) return;
    try {
      await register();
    } catch (_) {
      // The second start answers no_push_token again, with its message.
    }
  }

  TgApiError _timeoutError() => TgApiError(
        null,
        AppL10n.current.proofFailedBody,
        code: 'proof_timeout',
        details: const {'support_email': kSupportEmail},
      );

  TgApiError _pausedError(DateTime until) => TgApiError(
        403,
        AppL10n.current.proofPausedMemoryBody,
        code: 'device_proof_cooldown',
        details: {
          'available_at': until.toUtc().toIso8601String(),
          'support_email': kSupportEmail,
        },
      );

  void _succeed({bool record = true}) {
    _lastFailureAt = null;
    state.value = ProofState(
      phase: ProofPhase.proven,
      provenEpoch: state.value.provenEpoch + 1,
    );
    if (record) unawaited(Analytics.deviceProofResult('proven'));
  }

  void _pause(DateTime until, TgApiError? error) {
    state.value = state.value.copyWith(
      phase: ProofPhase.paused,
      pausedUntil: until,
      error: error ?? _pausedError(until),
    );
  }

  void _fail(TgApiError e) {
    _lastFailureAt = _now();
    if (e.code == 'device_proof_cooldown') {
      _pause(e.availableAt ?? _now().toUtc(), e);
    } else {
      state.value = state.value.copyWith(phase: ProofPhase.failed, error: e);
    }
    unawaited(Analytics.deviceProofResult(switch (e.code) {
      'device_proof_cooldown' => 'cooldown',
      'no_push_token' => 'no_push_token',
      'push_unavailable' => 'push_unavailable',
      'proof_rate_limited' => 'rate_limited',
      'proof_timeout' => 'timeout',
      'proof_failed' => 'failed',
      _ => e.isMissingEndpoint ? 'unsupported' : 'error',
    }));
  }
}
