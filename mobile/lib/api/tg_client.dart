/// Thin HTTP/SSE client for the Tutor Guardian backend.
///
/// Implements the v1 contract in `MOBILE_API.md`:
///   * `createSession()`        → POST /api/chat/sessions
///   * `streamQuery()`          → POST /api/assistant/stream (SSE)
///   * `query()`                → POST /api/assistant/query (blocking fallback)
///   * `getHistory()`           → GET  /api/chat/sessions/{id}
///   * `sendFeedback()`         → POST /api/feedback
///
/// Central error handling:
///   * 401 → caller must create a new session (we surface `TgApiError`).
///   * 404 (session) → same: caller drops the session id and retries.
///   * 429 → reads `Retry-After` and waits that many seconds before
///           re-throwing a `TgApiError` with `retryAfter` set.
///   * 422/5xx → `TgApiError` with the server's `detail` message.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io' show SocketException;

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import '../config/app_config.dart';
import '../models/api_models.dart';
import 'device_id_claim.dart';
import 'package:almorabbi/l10n/l10n_global.dart';

/// Raised for any non-recoverable HTTP failure the UI should display.
class TgApiError implements Exception {
  final int? statusCode;
  final String message;
  final Duration? retryAfter;

  /// The machine-readable reason, when the server sent one.
  ///
  /// The family-programs endpoints (MOBILE_API §11.6) answer
  /// `{"detail": {"error": "<code>", ...extra}}`. Before this field existed the
  /// whole object was thrown away and every refusal read as "HTTP 409", so a
  /// screen could not tell "already recorded" (show ✓) from a real failure.
  /// The branchable errors of §9.0 send it as `detail.code` instead, e.g.
  /// `device_proof_required`. Null for plain-string details and transport
  /// failures.
  final String? code;

  /// The rest of that object (`next_stage`, `available_on`, `markable_up_to`,
  /// `support_email`, `available_at`…), as the server sent it.
  final Map<String, dynamic>? details;

  /// The response body when it was not ours to show — an HTML error page, or
  /// Cloudflare's JSON problem page (`application/problem+json`, whose
  /// `detail` reads "The origin web server returned an invalid or incomplete
  /// response to Cloudflare…"). Kept for logs; [message] is the generic line.
  final String? raw;

  const TgApiError(this.statusCode, this.message,
      {this.retryAfter, this.code, this.details, this.raw});

  /// The address to offer when the automatic path cannot work (§9.0.1).
  String? get supportEmail {
    final v = details?['support_email'];
    return v is String && v.isNotEmpty ? v : null;
  }

  /// When a paused route opens again (`device_proof_cooldown`), as UTC. The
  /// contract sends ISO 8601 with `Z`; a value without a zone is UTC as well,
  /// never the phone's local time.
  DateTime? get availableAt {
    final v = details?['available_at'];
    if (v is! String || v.trim().isEmpty) return null;
    final s = v.trim();
    final zoned = RegExp(r'(Z|[+-]\d{2}:?\d{2})$').hasMatch(s);
    return DateTime.tryParse(zoned ? s : '${s.replaceFirst(' ', 'T')}Z')
        ?.toUtc();
  }

  /// The route answered "not here" rather than "not yours": a server that
  /// predates the endpoint. Only FastAPI's own bare `{"detail": "Not Found"}`
  /// (and 405) says that — a 404 with a message of our own («الطفل غير
  /// موجود», a coded `followup_not_found`) is about the data, and must not
  /// hide a feature the server does have.
  bool get isMissingEndpoint =>
      statusCode == 405 ||
      (statusCode == 404 && code == null && message == kFastApiNotFound);

  /// FastAPI's detail for a path no route matches.
  static const String kFastApiNotFound = 'Not Found';

  /// For logs only. Never put this on a screen — see `friendlyError`.
  @override
  String toString() =>
      'TgApiError(${statusCode ?? '?'}${code == null ? '' : ' $code'}): $message'
      '${raw == null ? '' : ' [raw: $raw]'}';
}

/// An answer about an account deletion arrived after the install moved on
/// (it became a new device meanwhile): not acted on.
class _InstallMovedOn implements Exception {
  const _InstallMovedOn();
}

/// Where an account deletion stands on this phone (MOBILE_API §10) — a
/// SharedPreferences key, so it survives the process.
const String kAccountDeletionKey = 'tg.account_deletion';

/// The DELETE is on its way, or its answer was lost: whether the server
/// committed it is not known yet. The token it carries is kept apart from the
/// session (clearing the session never touches it), because sending that same
/// DELETE again is how the answer is settled (`TgClient.settleAccountDeletion`).
/// The app works on meanwhile: for an erased device id the server refuses the
/// session mint with `410 device_erased`.
const String kAccountDeletionRequested = 'requested';

/// The server deleted the account; this install is a new device, or becoming
/// one. The phone still has to be cleared.
const String kAccountDeletionConfirmed = 'confirmed';

/// The device id the deletion erased, recorded with [kAccountDeletionConfirmed]
/// BEFORE the keystore is cleared: a launch that finds it still held — the app
/// was killed in the middle — starts over again before the phone is cleared.
const String kAccountDeletionErasedIdKey = 'tg.account_deletion.erased_id';

/// One event yielded by `streamQuery`.
sealed class TgStreamEvent {
  const TgStreamEvent();
}

class TgTokenEvent extends TgStreamEvent {
  final String delta;
  const TgTokenEvent(this.delta);
}

/// Terminal event with the authoritative `AssistantReply`.
class TgDoneEvent extends TgStreamEvent {
  final AssistantReply reply;
  const TgDoneEvent(this.reply);
}

/// Terminal event emitted on stream failure (separate from
/// HTTP errors that are raised before streaming starts).
class TgStreamError extends TgStreamEvent {
  final String detail;

  /// True when the server itself ended the turn with an `error` event (it
  /// stored an apology — there is no answer to recover). False when the
  /// connection died or stalled on this side: the server may still have
  /// finished the answer.
  final bool fromServer;
  const TgStreamError(this.detail, {this.fromServer = false});
}

/// First frame from servers since 2026-10: the id the server gave this
/// question. Lets the app find THIS turn's answer in the session history
/// later, instead of guessing by text. Older servers never send it.
class TgTurnEvent extends TgStreamEvent {
  final int messageId;
  const TgTurnEvent(this.messageId);
}

/// SharedPreferences key holding the child a child-mode surface was opened
/// for (written by `ChildModeNotifier` on entry, removed on exit). The child
/// token is renewed for this child.
const kChildModeChildIdKey = 'child_mode_child_id';

/// Default secure storage with resetOnError enabled to self-heal against
/// Android Keystore desync / BadPaddingException on reinstall or lock change.
FlutterSecureStorage createDefaultSecureStorage() {
  return const FlutterSecureStorage(
    aOptions: AndroidOptions(
      resetOnError: true,
    ),
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock,
    ),
  );
}

/// Single source of truth for the device id, session id, and bearer token.
/// Persisted in `flutter_secure_storage` (Android Keystore).
class _AuthStore {
  _AuthStore(this._storage, this._claim);

  static const _kDeviceId = 'tg_device_id';
  static const _kSessionId = 'tg_session_id';
  static const _kToken = 'tg_token';
  static const _kActiveChildId = 'tg_active_child_id';
  static const _kChildToken = 'tg_child_session_token';

  /// The last session token, kept across [clearSession] so the next
  /// `POST /api/chat/sessions` can prove it is this device (audit H5).
  static const _kDeviceProof = 'tg_device_proof';

  /// A copy of the device id outside the keystore. Only ever read when the
  /// secure copy is missing or unreadable — see [getOrCreateDeviceId].
  static const _kDeviceIdBackup = 'tg_device_id_backup';

  /// The token an account DELETE was sent with (MOBILE_API §10). Not part of
  /// the session: "new conversation" and the 401 handlers clear the session,
  /// and this token is the only way to send the same DELETE again when its
  /// answer was lost.
  static const _kDeletionToken = 'tg_deletion_token';

  final FlutterSecureStorage _storage;
  final DeviceIdClaim _claim;
  final Uuid _uuid = const Uuid();

  String? _cachedDeviceId;
  String? _cachedSessionId;
  String? _cachedToken;

  /// The device-id resolution in flight, shared by every concurrent caller.
  Future<String>? _deviceIdLoad;

  /// Read a key, retrying once. Returns (value, readSucceeded).
  ///
  /// This used to call `deleteAll()` on ANY exception. A transient keystore
  /// error — the device still locked early after boot, a plugin hiccup —
  /// therefore erased `tg_device_id`, and with it the family's link to every
  /// server-side record: children, progress, chat history (audit H7). Genuine
  /// corruption (BadPadding after a restore) is already handled by the
  /// plugin itself via `resetOnError: true`; this layer must never escalate a
  /// read failure into a wipe.
  Future<(String?, bool)> _readChecked(String key) async {
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        return (await _storage.read(key: key), true);
      } catch (_) {
        if (attempt == 0) {
          await Future<void>.delayed(const Duration(milliseconds: 150));
        }
      }
    }
    return (null, false);
  }

  Future<String?> _safeRead(String key) async => (await _readChecked(key)).$1;

  Future<void> _safeWrite(String key, String value) async {
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        await _storage.write(key: key, value: value);
        return;
      } catch (_) {
        if (attempt == 0) {
          await Future<void>.delayed(const Duration(milliseconds: 150));
        }
      }
    }
  }

  Future<String?> _readDeviceIdBackup() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final v = prefs.getString(_kDeviceIdBackup);
      return (v != null && v.isNotEmpty) ? v : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> _writeDeviceIdBackup(String id) async {
    if (!isValidDeviceId(id)) return; // never let garbage replace a good copy
    try {
      final prefs = await SharedPreferences.getInstance();
      if (prefs.getString(_kDeviceIdBackup) != id) {
        await prefs.setString(_kDeviceIdBackup, id);
      }
    } catch (_) {
      // Best effort — the keystore copy is still the primary.
    }
  }

  Future<void> _safeDelete(String key) async {
    try {
      await _storage.delete(key: key);
    } catch (_) {}
  }

  /// The install's device id: read back, or created exactly once.
  ///
  /// Single-flight. This used to check the cache, then await the keystore —
  /// so two callers arriving together (session mint, push registration,
  /// feedback, a screen's own `createSession`) both found it empty and each
  /// minted its own id: one install, two families on the server, and the
  /// next launch came back as whichever was written last. Now every caller
  /// awaits the same resolution, which persists the id before anyone gets it.
  ///
  /// A fresh id additionally goes through [DeviceIdClaim], because the same
  /// race also ran between isolates — see that class.
  Future<String> getOrCreateDeviceId() {
    final cached = _cachedDeviceId;
    if (cached != null) return Future.value(cached);
    return _deviceIdLoad ??= _resolveDeviceId().then(
      // `??=`: an id the server handed over meanwhile (adoptDeviceId) wins.
      (id) => _cachedDeviceId ??= id,
      onError: (Object e, StackTrace s) {
        _deviceIdLoad = null; // the next caller retries
        Error.throwWithStackTrace(e, s);
      },
    );
  }

  Future<String> _resolveDeviceId() async {
    final (existing, readOk) = await _readChecked(_kDeviceId);
    if (isValidDeviceId(existing)) {
      await _writeDeviceIdBackup(existing!);
      return existing;
    }
    // Secure copy missing, unreadable, or garbage the server would refuse
    // with 422 on every mint (a keystore decrypting with the wrong key): the
    // backup is the same identity, if it is a valid one.
    final backup = await _readDeviceIdBackup();
    if (isValidDeviceId(backup)) {
      if (readOk) await _safeWrite(_kDeviceId, backup!);
      return backup!;
    }
    // Nothing usable persisted. Claim a fresh id — or get the one another
    // isolate claimed a moment ago, or an earlier run left in the claim file.
    // The family is not lost with the old id: the next mint still carries the
    // device proof, and the server moves the proven device to this id.
    final candidate = _uuid.v4();
    final claimed = await _claim.claim(candidate);
    final id = isValidDeviceId(claimed) ? claimed! : candidate;
    // Only persist into the keystore when we KNOW it was empty. If the read
    // failed, an id may still be in there; overwriting it would orphan the
    // family's data just as the old deleteAll() did. The next launch reads
    // the real one back.
    if (readOk) await _safeWrite(_kDeviceId, id);
    await _writeDeviceIdBackup(id);
    return id;
  }

  /// Become [id]: the server re-attached this install to the device that
  /// holds the family's data (a split-off twin, see the backend's
  /// `device_twins`). Written everywhere the id lives, so the next launch
  /// starts as that device instead of asking the server to map it again.
  Future<void> adoptDeviceId(String id) async {
    if (!isValidDeviceId(id) || id == _cachedDeviceId) return;
    _cachedDeviceId = id;
    await _safeWrite(_kDeviceId, id);
    await _writeDeviceIdBackup(id);
    await _claim.replace(id);
  }

  Future<void> setSession({required String sessionId, required String token}) async {
    _cachedSessionId = sessionId;
    _cachedToken = token;
    await _safeWrite(_kSessionId, sessionId);
    await _safeWrite(_kToken, token);
    await _safeWrite(_kDeviceProof, token);
  }

  /// The last token this device held — survives [clearSession]. Builds that
  /// predate the proof key still hold their live token, which proves the
  /// same thing.
  Future<String?> readDeviceProof() async =>
      await _safeRead(_kDeviceProof) ?? await _safeRead(_kToken);

  Future<void> clearDeviceProof() => _safeDelete(_kDeviceProof);

  Future<(String?, String?)> readSession() async {
    if (_cachedSessionId != null && _cachedToken != null) {
      return (_cachedSessionId!, _cachedToken!);
    }
    final sid = await _safeRead(_kSessionId);
    final tok = await _safeRead(_kToken);
    _cachedSessionId = sid;
    _cachedToken = tok;
    return (sid, tok);
  }

  Future<void> clearSession() async {
    _cachedSessionId = null;
    _cachedToken = null;
    await _safeDelete(_kSessionId);
    await _safeDelete(_kToken);
  }

  Future<int?> readActiveChildId() async {
    final raw = await _safeRead(_kActiveChildId);
    if (raw == null) return null;
    return int.tryParse(raw);
  }

  Future<void> writeActiveChildId(int? childId) async {
    if (childId == null) {
      await _safeDelete(_kActiveChildId);
    } else {
      await _safeWrite(_kActiveChildId, childId.toString());
    }
  }

  Future<String?> readChildToken() async {
    return await _safeRead(_kChildToken);
  }

  Future<void> writeChildToken(String token) async {
    await _safeWrite(_kChildToken, token);
  }

  Future<void> clearChildToken() async {
    await _safeDelete(_kChildToken);
  }

  Future<void> writeDeletionToken(String token) =>
      _safeWrite(_kDeletionToken, token);

  Future<String?> readDeletionToken() => _safeRead(_kDeletionToken);

  Future<void> clearDeletionToken() => _safeDelete(_kDeletionToken);

  /// The device id this install holds, without creating one.
  Future<String?> peekDeviceId() async {
    final cached = _cachedDeviceId;
    if (cached != null) return cached;
    final (stored, _) = await _readChecked(_kDeviceId);
    if (isValidDeviceId(stored)) return stored;
    final backup = await _readDeviceIdBackup();
    return isValidDeviceId(backup) ? backup : null;
  }

  /// Whether [id] is still this install's id anywhere it lives — the memory
  /// cache, the keystore, the backup copy. A keystore that cannot be read
  /// counts as holding it: starting over once more costs nothing.
  Future<bool> stillHolds(String id) async {
    if (_cachedDeviceId == id) return true;
    final (stored, readOk) = await _readChecked(_kDeviceId);
    if (!readOk || stored == id) return true;
    return await _readDeviceIdBackup() == id;
  }

  /// After the account was deleted (MOBILE_API §10): forget the session and
  /// every secret this install held, and become a brand-new device.
  ///
  /// The fresh id goes everywhere the id lives — the keystore, the backup
  /// and the cross-isolate claim (DeviceIdClaim) — straight away, rather
  /// than left for [getOrCreateDeviceId] to make on demand: the claim in
  /// particular would otherwise hand the erased id back to a launch that
  /// found the keystore and the backup empty.
  Future<void> startOverAsNewDevice() async {
    _cachedSessionId = null;
    _cachedToken = null;
    try {
      // Session, token, device proof, child tokens, child-mode PIN: all of
      // it belonged to the account that no longer exists.
      await _storage.deleteAll();
    } catch (_) {
      for (final key in [_kSessionId, _kToken, _kDeviceProof, _kChildToken,
          _kActiveChildId, _kDeviceId, _kDeletionToken]) {
        await _safeDelete(key);
      }
    }
    final fresh = _uuid.v4();
    _cachedDeviceId = fresh;
    _deviceIdLoad = Future.value(fresh);
    await _safeWrite(_kDeviceId, fresh);
    await _writeDeviceIdBackup(fresh);
    await _claim.replace(fresh);
  }
}

/// The Tutor Guardian API client.
///
/// Use [TgClient.shared] (or `tgClientProvider`, which returns it) — never a
/// fresh `TgClient()` per call site (audit M12). Every instance owns its own
/// `http.Client` and its own in-memory copy of the session: 19 ad-hoc
/// instances meant 19 unclosed connection pools, sessions minted twice when
/// two screens raced `ensureSession()`, and one instance holding a token
/// another had already replaced.
class TgClient {
  TgClient({
    http.Client? httpClient,
    FlutterSecureStorage? storage,
    DeviceIdClaim? deviceIdClaim,
    this.onNeedActiveChildId,
    Duration? streamIdleTimeout,
  })  : _raw = httpClient ?? http.Client(),
        _auth = _AuthStore(storage ?? createDefaultSecureStorage(),
            deviceIdClaim ?? DeviceIdClaim.inAppCache()),
        _ownsHttpClient = httpClient == null,
        _baseUrlOverride = null,
        streamIdleTimeout = streamIdleTimeout ?? AppConfig.streamIdleTimeout;

  /// Test-only constructor that bypasses [AppConfig.apiBaseUrl].
  @visibleForTesting
  TgClient.forTesting({
    required String baseUrl,
    http.Client? httpClient,
    FlutterSecureStorage? storage,
    DeviceIdClaim? deviceIdClaim,
    this.onNeedActiveChildId,
    Duration? streamIdleTimeout,
  })  : _raw = httpClient ?? http.Client(),
        _auth = _AuthStore(storage ?? createDefaultSecureStorage(),
            deviceIdClaim ?? DeviceIdClaim.inAppCache()),
        _ownsHttpClient = httpClient == null,
        _baseUrlOverride = baseUrl,
        streamIdleTimeout = streamIdleTimeout ?? AppConfig.streamIdleTimeout;

  static TgClient? _shared;

  /// The app-wide client. Code without a `WidgetRef` (services, `main`) uses
  /// this; widgets and providers go through `tgClientProvider`, which returns
  /// the same instance so tests can still override it.
  static TgClient get shared => _shared ??= TgClient();

  @visibleForTesting
  static set shared(TgClient? client) => _shared = client;

  /// UI language, sent as `?lang=` on curriculum reads.
  ///
  /// The backend serves Arabic unless asked otherwise. All 170 lessons and 39
  /// paths have English translations on disk, but until 2026-08-13 nothing
  /// requested them, so English users read Arabic — reported twice from inside
  /// the app. Set by the app when the locale changes; `null` keeps Arabic.
  static String? uiLanguage;

  /// This build's number, sent as `X-App-Build` with every session mint. A
  /// build that handles `410 device_erased` says so this way, and only such a
  /// build gets that answer for an erased device id (MOBILE_API §10). Set once
  /// in `main()`; null (host tests, no platform channel) sends nothing, and
  /// the server answers as it always did.
  static int? appBuild;

  /// The transport as injected. Only session minting and the account DELETE
  /// use it directly.
  final http.Client _raw;

  /// Everything else goes through this: it renews an expired session once
  /// and replays the request (see [_SessionRecoveringClient]).
  late final http.Client _http = _SessionRecoveringClient(_raw, _recoverSession);

  final _AuthStore _auth;

  /// Settable so `tgClientProvider` can wire the Riverpod active child into
  /// the shared instance.
  Future<int?> Function()? onNeedActiveChildId;

  /// Runs the device-proof challenge for this session (MOBILE_API §9.0.1):
  /// completes once the session is proven, throws a [TgApiError] when it
  /// cannot be. Wired by `DeviceProofService.init`; null means "no way to
  /// prove here", and a `device_proof_required` reaches the caller as is.
  Future<void> Function()? onDeviceProofRequired;

  /// Called once this install has become a new device because a session mint
  /// was answered `410 device_erased`: its device id belongs to a deleted
  /// account — a phone backup restored after the deletion, or a deletion
  /// whose answer was lost. The app clears the phone and says the account was
  /// deleted. Wired in `main()`; null does the start-over alone.
  Future<void> Function()? onDeviceErased;

  /// Sends [send]; on `device_proof_required` proves the session once and
  /// sends it once more — the client flow §9.0 prescribes. A cooldown
  /// (`device_proof_cooldown`) is never retried: the proof cannot lift it.
  Future<T> withDeviceProof<T>(Future<T> Function() send) async {
    try {
      return await send();
    } on TgApiError catch (e) {
      final prove = onDeviceProofRequired;
      if (e.code != 'device_proof_required' || prove == null) rethrow;
      await prove();
      return await send();
    }
  }

  /// A stream that delivers no bytes for this long is treated as dead
  /// (audit M13). The server sends an SSE comment every 15 s while the
  /// model is still thinking, so this only fires on a stalled connection.
  final Duration streamIdleTimeout;

  /// The mint in flight, shared by every caller that needs a session now.
  Future<SessionResponse>? _minting;

  final bool _ownsHttpClient;
  final String? _baseUrlOverride;
  /// The child-token renewal in flight, shared by every caller that hit a 401
  /// meanwhile — a second caller used to get null and hide its card.
  Future<String?>? _childTokenRenewal;

  String get _baseUrl => _baseUrlOverride ?? AppConfig.apiBaseUrl;

  // ── Public surface ────────────────────────────────────────────────────

  /// Create a new session (server returns a fresh `session_id` + bearer
  /// token). The token is persisted for the lifetime of the install.
  Future<SessionResponse> createSession({
    Map<String, dynamic>? metadata,
  }) async {
    // A deletion still waiting for its answer, on a server that would not
    // refuse an erased id to this build: settled first, so no mint ever gives
    // the erased id a live token again (see [_settleBeforeMinting]).
    await _settleBeforeMinting();
    var deviceId = await _auth.getOrCreateDeviceId();
    var resp = await _postMint(deviceId, metadata: metadata);
    if (resp.statusCode == 410) {
      final error = _wrap(resp);
      if (error.code != 'device_erased') throw error;
      // This device id was erased with its account — a phone backup restored
      // after the deletion, or a deletion whose answer was lost (MOBILE_API
      // §3.2). Never retry it: become a new device (session, last token, id
      // and its backup copy all go), mint for that, and let the app clear
      // what the backup brought back. Not an error for the caller.
      await _deviceErased();
      deviceId = await _auth.getOrCreateDeviceId();
      resp = await _postMint(deviceId, metadata: metadata);
      if (resp.statusCode == 410) throw _wrap(resp); // never twice
    }
    if (resp.statusCode != 201) {
      throw _wrapStreamed(resp.statusCode, const {});
    }
    return _keepMinted(resp, deviceId);
  }

  /// `POST /api/chat/sessions` for [deviceId], with the last token as proof.
  ///
  /// Prove this is the same device (audit H5): the server refuses a proof
  /// that belongs to another device, and — once SESSION_MINT_ENFORCE is on —
  /// refuses to mint for a known device without one. [proof] overrides the
  /// stored one (settling a deletion sends the token the DELETE carried).
  Future<http.Response> _postMint(String deviceId,
      {Map<String, dynamic>? metadata, String? proof}) async {
    final body = jsonEncode(<String, dynamic>{
      'device_id': deviceId,
      'metadata': ?metadata,
    });
    final build = appBuild;
    Future<http.Response> post(String? proof) => _raw
        .post(
          Uri.parse('$_baseUrl/api/chat/sessions'),
          headers: {
            'Content-Type': 'application/json; charset=utf-8',
            if (proof != null && proof.isNotEmpty) 'Authorization': 'Bearer $proof',
            // "I handle 410 device_erased" (MOBILE_API §3.2): the Android
            // versionCode, on every mint.
            'X-App-Build': ?build?.toString(),
          },
          body: body,
        )
        .timeout(AppConfig.httpTimeout);

    final token = proof ?? await _auth.readDeviceProof();
    var resp = await post(token);
    if ((resp.statusCode == 401 || resp.statusCode == 403) && token != null) {
      // A proof the server no longer accepts (e.g. a restored backup whose
      // token was never issued for this id). Drop it and try once without.
      await _auth.clearDeviceProof();
      resp = await post(null);
    }
    return resp;
  }

  /// Store the session a `201` mint returned for [deviceId]. With
  /// [keepConversation] only the token is taken: the conversation stays the
  /// one already open (the server checks session ownership by device).
  Future<SessionResponse> _keepMinted(http.Response resp, String deviceId,
      {bool keepConversation = false}) async {
    final parsed =
        SessionResponse.fromJson(jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>);
    final (current, _) = await _auth.readSession();
    await _auth.setSession(
        sessionId: keepConversation && current != null ? current : parsed.sessionId,
        token: parsed.token);
    // The server minted for a different device than we asked for: this
    // install had split into twins and the server re-attached it to the one
    // holding the family's data. Become that device for good.
    final minted = parsed.deviceId;
    if (minted != null && minted.isNotEmpty && minted != deviceId) {
      await _auth.adoptDeviceId(minted);
    }
    return parsed;
  }

  /// Stream an assistant reply over Server-Sent Events. Yields:
  ///   * `TgTokenEvent`      — incremental delta (0+ times)
  ///   * `TgDoneEvent`       — terminal: the authoritative `AssistantReply`
  ///   * `TgStreamError`     — terminal: backend sent an `event: error`
  ///
  /// On HTTP 401/404/429/5xx the call throws `TgApiError` BEFORE yielding
  /// any event. On network errors mid-stream, yields a terminal
  /// `TgStreamError` so the UI can show a retry banner.
  Stream<TgStreamEvent> streamQuery(AssistantQuery q) async* {
    final (sid, tok) = await _auth.readSession();
    if (sid == null || tok == null) {
      throw TgApiError(401, AppL10n.current.noActiveSession);
    }

    final uri = Uri.parse('$_baseUrl/api/assistant/stream');
    final request = http.Request('POST', uri)
      ..headers['Content-Type'] = 'application/json; charset=utf-8'
      ..headers['Accept'] = 'text/event-stream'
      ..headers['Authorization'] = 'Bearer $tok'
      ..body = jsonEncode(q.toJson());

    final http.StreamedResponse response;
    try {
      response = await _http.send(request).timeout(AppConfig.streamTimeout);
    } on TimeoutException {
      throw TgApiError(null, AppL10n.current.apiTimeout);
    } on SocketException catch (e) {
      throw TgApiError(null, AppL10n.current.apiConnectionFailed,
          raw: e.message);
    }

    if (response.statusCode != 200) {
      // Read the (small) error body so server-provided Arabic messages —
      // e.g. the gentle daily-quota one — reach the user instead of a bare
      // «خطأ HTTP 429».
      String body = '';
      try {
        body = await response.stream
            .bytesToString()
            .timeout(const Duration(seconds: 3));
      } catch (_) {/* keep empty body */}
      throw _wrapStatus(response.statusCode, body, response.headers);
    }

    // Parse SSE byte-by-byte. Frame = `event: <name>\ndata: <json>\n\n`.
    String currentEvent = 'message';
    final dataBuffer = StringBuffer();

    // Idle timeout per chunk (audit M13): the header timeout above only
    // covered the wait for the response to start, so a connection that went
    // silent mid-answer (a proxy dropping it, the phone changing networks)
    // left the chat "typing" forever with Stop as the only way out.
    final lineStream = response.stream
        .timeout(streamIdleTimeout)
        .transform(utf8.decoder)
        .transform(const LineSplitter());

    try {
      await for (final rawLine in lineStream) {
        // The decoder may leave a trailing \r on each line; trim it.
        final line = rawLine.endsWith('\r') ? rawLine.substring(0, rawLine.length - 1) : rawLine;

        if (line.isEmpty) {
          // End of one frame — dispatch whatever we accumulated.
          if (dataBuffer.isNotEmpty) {
            final ev = _parseFrame(currentEvent, dataBuffer.toString());
            if (ev != null) yield ev;
          }
          currentEvent = 'message';
          dataBuffer.clear();
          continue;
        }

        if (line.startsWith('event:')) {
          currentEvent = line.substring(6).trim();
        } else if (line.startsWith('data:')) {
          if (dataBuffer.isNotEmpty) dataBuffer.write('\n');
          dataBuffer.write(line.substring(5).trimLeft());
        } else if (line.startsWith(':')) {
          // SSE comment / keep-alive; ignore.
        }
        // Other lines (id:, retry:) — ignore for v1.
      }
    } on TimeoutException {
      yield TgStreamError(AppL10n.current.apiStreamStalled);
      return;
    } on SocketException catch (e) {
      debugPrint('[TgClient.streamQuery] connection lost: ${e.message}');
      yield TgStreamError(AppL10n.current.apiConnectionFailed);
      return;
    } on http.ClientException catch (e) {
      // The connection died mid-response.
      debugPrint('[TgClient.streamQuery] connection lost: ${e.message}');
      yield TgStreamError(AppL10n.current.apiConnectionFailed);
      return;
    }

    // If the stream ended without a terminal frame, surface a stream error.
    if (dataBuffer.isNotEmpty) {
      final ev = _parseFrame(currentEvent, dataBuffer.toString());
      if (ev != null) yield ev;
    }
  }

  /// Non-streaming query (used for feedback pre-checks or as a fallback
  /// when the stream is unavailable).
  Future<AssistantReply> query(AssistantQuery q) async {
    final (sid, tok) = await _auth.readSession();
    if (sid == null || tok == null) {
      throw TgApiError(401, AppL10n.current.noActiveSession);
    }
    final resp = await _http
        .post(
          Uri.parse('$_baseUrl/api/assistant/query'),
          headers: _authHeaders(tok),
          body: jsonEncode(q.toJson()),
        )
        .timeout(AppConfig.httpTimeout);

    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return AssistantReply.fromJson(
      jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>,
    );
  }

  /// Fetch full session history. Throws `TgApiError(404)` if the session
  /// was deleted server-side.
  /// Ask the server to stop the answer it is generating for [sessionId] —
  /// the parent pressed Stop. Best-effort: false when nothing was running,
  /// on any error, and on servers older than 2026-10 (404), which simply
  /// finish the answer in the background as before.
  ///
  /// [messageId] is the question the parent is stopping (the stream's `turn`
  /// frame): the server cuts that turn only, never a newer one.
  Future<bool> stopAnswer(String sessionId, {required int messageId}) async {
    try {
      final (_, tok) = await _auth.readSession();
      if (tok == null) return false;
      final resp = await _http
          .post(
            Uri.parse('$_baseUrl/api/chat/sessions/$sessionId/stop'),
            headers: _authHeaders(tok),
            body: jsonEncode({'message_id': messageId}),
          )
          .timeout(const Duration(seconds: 10));
      if (resp.statusCode != 200) return false;
      final body = jsonDecode(utf8.decode(resp.bodyBytes));
      return body is Map && body['stopped'] == true;
    } catch (_) {
      return false;
    }
  }

  Future<SessionHistory> getHistory(String sessionId) async {
    final (sid, tok) = await _auth.readSession();
    if (tok == null) {
      throw TgApiError(401, AppL10n.current.apiNoSession);
    }
    final resp = await _http
        .get(
          Uri.parse('$_baseUrl/api/chat/sessions/$sessionId'),
          headers: _authHeaders(tok),
        )
        .timeout(AppConfig.httpTimeout);

    if (resp.statusCode == 404) {
      // The session was removed server-side; clear local copy so the
      // caller can re-create transparently.
      await _auth.clearSession();
      throw TgApiError(404, AppL10n.current.apiSessionNotFound);
    }
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return SessionHistory.fromJson(
      jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>,
    );
  }

  /// Generate a personalized children's story (a coins redeemable).
  /// Currently public server-side, but we send the Bearer token so the
  /// backend can start requiring auth once this client version is adopted.
  Future<String> generateStory({
    required String childName,
    required String ageGroup,
    required String theme,
    int? childId,
  }) async {
    final session = await ensureSession();
    final resp = await _http
        .post(
          Uri.parse('$_baseUrl/api/program/story'),
          headers: _authHeaders(session.token),
          body: jsonEncode({
            'child_name': childName,
            'age_group': ageGroup,
            'theme': theme,
            // Lets the backend resolve the child's gender for correctly
            // conjugated pre-generated stories (cache tier).
            'child_id': ?childId,
          }),
        )
        // stories are slower (full LLM generation) — allow the SSE-style budget
        .timeout(AppConfig.streamTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    final data = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    return (data['story'] as String?) ?? '';
  }

  /// Send general in-app feedback (text and/or a base64 voice note) to Khaled.
  ///
  /// The device id and app version are resolved here rather than passed in by
  /// the caller. They used to be optional parameters, and the one call site
  /// never supplied them — so every stored row had `device_id = NULL`, which
  /// made it impossible to deliver a reply back to whoever wrote the feedback.
  /// Identity is this client's job, not a UI screen's.
  ///
  /// This endpoint is deliberately unauthenticated (a user whose session is
  /// broken must still be able to report that), so the device id travels in the
  /// body rather than coming from a token.
  Future<String> sendAppFeedback({
    String message = '',
    String? contact,
    String? audioBase64,
  }) async {
    final deviceId = await _auth.getOrCreateDeviceId();
    final appVersion = await _appVersion();
    final resp = await _http
        .post(
          Uri.parse('$_baseUrl/api/feedback/app'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({
            'message': message,
            if (contact != null && contact.isNotEmpty) 'contact': contact,
            'audio_base64': ?audioBase64,
            'device_id': deviceId,
            'app_version': ?appVersion,
          }),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 201) {
      throw _wrap(resp);
    }
    final body = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    return body['id'] as String;
  }

  /// Replies Khaled has written back to this device's feedback.
  ///
  /// Authenticated: the server reads the device id from the token, so there is
  /// no parameter to spoof. Returns [] rather than throwing when there is no
  /// session yet — an empty inbox and a broken session look the same to the
  /// user, and neither is worth an error banner on a screen they opened to
  /// complain about something else.
  Future<List<FeedbackReply>> listFeedbackReplies() async {
    final (_, tok) = await _auth.readSession();
    if (tok == null) return const [];
    try {
      final resp = await _http
          .get(
            Uri.parse('$_baseUrl/api/feedback/replies'),
            headers: {'Authorization': 'Bearer $tok'},
          )
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) return const [];
      final body =
          jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      return (body['items'] as List<dynamic>? ?? const [])
          .map((e) => FeedbackReply.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return const [];
    }
  }

  /// Best-effort "I've seen it". Never throws: failing to clear a badge must
  /// not surface as an error.
  Future<void> markFeedbackReplyRead(String replyId) async {
    final (_, tok) = await _auth.readSession();
    if (tok == null) return;
    try {
      await _http
          .post(
            Uri.parse('$_baseUrl/api/feedback/replies/$replyId/read'),
            headers: {'Authorization': 'Bearer $tok'},
          )
          .timeout(AppConfig.httpTimeout);
    } catch (_) {
      // ignore
    }
  }

  /// "1.0.28+73", or null if the platform channel is unavailable (tests).
  /// Never throws — a missing version must not block a bug report.
  Future<String?> _appVersion() async {
    final info = await _packageInfo();
    return info == null ? null : '${info.version}+${info.buildNumber}';
  }

  /// Null when the platform channel is unavailable (host tests, and any device
  /// where the plugin fails to answer). Never throws: neither a bug report nor
  /// a push registration may be lost over a missing version string.
  Future<PackageInfo?> _packageInfo() async {
    try {
      return await PackageInfo.fromPlatform();
    } catch (_) {
      return null;
    }
  }

  /// List the device's past conversations (for the history drawer).
  /// Returns [] when there is no active session yet.
  Future<List<ChatSessionSummary>> listSessions() async {
    final (sid, tok) = await _auth.readSession();
    if (tok == null) return const [];
    final resp = await _http
        .get(
          Uri.parse('$_baseUrl/api/chat/sessions'),
          headers: _authHeaders(tok),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    final data = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    final raw = (data['sessions'] as List?) ?? const [];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(ChatSessionSummary.fromJson)
        .toList();
  }

  /// Submit 👍/👎 for the current turn.
  Future<void> sendFeedback({
    required String rating, // "up" | "down"
    String? comment,
    String? sessionId,
  }) async {
    final (sid, tok) = await _auth.readSession();
    if (tok == null) {
      throw TgApiError(401, AppL10n.current.apiNoSession);
    }
    final body = <String, dynamic>{
      'rating': rating,
      if (comment != null && comment.isNotEmpty) 'comment': comment,
      'session_id': ?sessionId,
    };
    final resp = await _http
        .post(
          Uri.parse('$_baseUrl/api/feedback'),
          headers: _authHeaders(tok),
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);

    if (resp.statusCode == 401) {
      // The stored token expired; clear it so the next call creates a
      // fresh session.
      await _auth.clearSession();
      throw TgApiError(401, AppL10n.current.apiSessionExpired);
    }
    if (resp.statusCode != 201) {
      throw _wrapStreamed(resp.statusCode, const {});
    }
  }

  // ── Lifecycle helpers used by the chat notifier ──────────────────────

  /// Returns a (sessionId, token) pair, creating a session if none exists.
  ///
  /// Concurrent callers share one mint: app start, push registration and the
  /// first screen all ask at once, and each used to create its own session.
  Future<SessionResponse> ensureSession() async {
    final (sid, tok) = await _auth.readSession();
    if (sid != null && tok != null) {
      return SessionResponse(sessionId: sid, token: tok);
    }
    return _mintOnce();
  }

  Future<SessionResponse> _mintOnce() =>
      _minting ??= createSession().whenComplete(() => _minting = null);

  /// Called by [_SessionRecoveringClient] when the server refused
  /// [rejectedToken] (it expired: tokens now lapse after a long idle, audit
  /// H5). Returns the token to replay the request with, or null to give up.
  ///
  /// The rejected token stays the device proof (readDeviceProof survives
  /// clearSession), and the server accepts an expired token as proof, so the
  /// new token belongs to the same device and its data.
  ///
  /// Only the token is renewed: the conversation stays in the session it was
  /// in (the server checks session ownership by device, not by token), so a
  /// parent mid-conversation keeps it — and its history after a restart.
  Future<String?> _recoverSession(String rejectedToken) async {
    try {
      // During an unsettled account deletion too: the mint settles it first
      // where it must, and for an erased id it answers `410 device_erased`,
      // which starts this install over (createSession) instead of bringing
      // the account back.
      final (sessionId, current) = await _auth.readSession();
      if (current != null && current != rejectedToken) {
        return current; // another request already renewed it
      }
      final erasures = _erasures;
      if (_minting == null) await _auth.clearSession();
      final fresh = await _mintOnce();
      // The conversation stays — unless the mint made this a new device: the
      // old session is then the erased account's, never paired with the
      // fresh device's token.
      if (sessionId != null && _erasures == erasures) {
        await _auth.setSession(sessionId: sessionId, token: fresh.token);
      }
      return fresh.token;
    } catch (_) {
      return null;
    }
  }

  /// Persist a session after the caller (e.g. UI) creates one explicitly.
  Future<void> saveSession(String sessionId, String token) =>
      _auth.setSession(sessionId: sessionId, token: token);

  /// Read the currently-persisted session id (or null).
  Future<String?> currentSessionId() async {
    final (sid, _) = await _auth.readSession();
    return sid;
  }

  /// Drop the current session (used by the "start a new conversation" button).
  Future<void> endSession() => _auth.clearSession();

  // ── Curriculum program layer (Phase 4) ────────────────────────────────
  //
  // Read-only endpoints mounted under `/api/program/*`. Public per the
  // backend auth middleware (no Bearer required for v1).
  //
  //   GET /api/program/paths?age_group=&domain=
  //   GET /api/program/paths/{id}?include=lessons
  //   GET /api/program/lessons/{id}
  //
  // The repository layer is the only consumer of these; tests should
  // mock [TgClient] rather than call them directly.

  Future<Map<String, dynamic>> getPathsList({
    String? ageGroup,
    String? domain,
  }) async {
    final qs = <String, String>{};
    if (ageGroup != null && ageGroup.isNotEmpty) qs['age_group'] = ageGroup;
    if (domain != null && domain.isNotEmpty) qs['domain'] = domain;
    final lang = uiLanguage;
    if (lang != null && lang.isNotEmpty) qs['lang'] = lang;
    final uri = Uri.parse(
      '$_baseUrl/api/program/paths',
    ).replace(queryParameters: qs.isEmpty ? null : qs);
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getPathDetail(
    String pathId, {
    bool includeLessons = false,
  }) async {
    final qs = <String, String>{};
    if (includeLessons) qs['include'] = 'lessons';
    final lang = uiLanguage;
    if (lang != null && lang.isNotEmpty) qs['lang'] = lang;
    final uri = Uri.parse(
      '$_baseUrl/api/program/paths/$pathId',
    ).replace(queryParameters: qs.isEmpty ? null : qs);
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getLesson(String lessonId) async {
    final lang = uiLanguage;
    final uri = Uri.parse('$_baseUrl/api/program/lessons/$lessonId').replace(
      queryParameters:
          (lang != null && lang.isNotEmpty) ? {'lang': lang} : null,
    );
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getLessonAssets(String lessonId, {String? lang}) async {
    final queryParams = lang != null && lang.isNotEmpty ? {'lang': lang} : const <String, String>{};
    final uri = Uri.parse('$_baseUrl/api/program/lesson-assets/$lessonId')
        .replace(queryParameters: queryParams.isEmpty ? null : queryParams);
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getAssetContent(String assetId) async {
    final uri = Uri.parse('$_baseUrl/api/program/asset-content/$assetId');
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// Tafsir of a single ayah, from `/api/tafsir/{surah}/{ayah}`.
  ///
  /// The backend has proxied `mcp.tafsir.net` (with a 30-day SQLite cache)
  /// since before this client existed; nothing in the app ever called it, so
  /// every parent who wanted to know what an ayah means got nothing.
  ///
  /// Public endpoint — `_PROTECTED_PREFIXES` in the backend auth middleware is
  /// an allowlist and `/api/tafsir` is not on it. No token is attached.
  Future<Map<String, dynamic>> getTafsir(int surah, int ayah,
      {List<String>? sources}) async {
    final uri = Uri.parse('$_baseUrl/api/tafsir/$surah/$ayah').replace(
      queryParameters:
          (sources != null && sources.isNotEmpty) ? {'sources': sources} : null,
    );
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// Reason for revelation of an ayah, from `/api/tafsir/{surah}/{ayah}/nuzool`.
  ///
  /// Returns `null` on 404. Most ayahs have no documented sabab nuzool, and the
  /// backend says so with a 404 carrying «لا يتوفر سبب نزول موثّق لهذه الآية» —
  /// that is an answer, not a failure, and the UI must not show it as one.
  Future<Map<String, dynamic>?> getNuzool(int surah, int ayah) async {
    final uri = Uri.parse('$_baseUrl/api/tafsir/$surah/$ayah/nuzool');
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode == 404) return null;
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> searchCurriculum(String query,
      {int limit = 20}) async {
    final lang = uiLanguage;
    final uri = Uri.parse('$_baseUrl/api/program/search').replace(
      queryParameters: {
        'q': query,
        'limit': '$limit',
        // The backend has accepted `lang` here since 2026-08-13. The client
        // never sent it, so an English reader's search results came back
        // Arabic — one of the surfaces behind «أغير الاعدادات الى اللغة
        // الانجليزية لكن الدروس باللغة العربية».
        if (lang != null && lang.isNotEmpty) 'lang': lang,
      },
    );
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// `GET /api/program/coach-tip?child_id=` (authed). Fetching also records
  /// the "shown" signal server-side (deduped once/day).
  Future<Map<String, dynamic>> getCoachTip(int childId) async {
    final session = await ensureSession();
    final token = session.token;
    // `_langParam()` — the one content read that did not carry it. On an
    // English phone the Home tab's most prominent card rendered Arabic, which
    // is the same omission that left 170 translated lessons unread until
    // 2026-08-13, in the one place that had not been swept.
    final uri = Uri.parse('$_baseUrl/api/program/coach-tip')
        .replace(queryParameters: {'child_id': '$childId', ..._langParam()});
    final resp = await _http
        .get(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// `GET /api/program/next-lesson?age_group=&child_id=` — the one lesson to
  /// put in front of this parent now, so the home CTA can open content rather
  /// than hand them a 39-item list to browse.
  Future<Map<String, dynamic>> getNextLesson(
    String ageGroup, {
    int? childId,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final lang = uiLanguage;
    final uri = Uri.parse('$_baseUrl/api/program/next-lesson').replace(
      queryParameters: {
        'age_group': ageGroup,
        if (childId != null) 'child_id': '$childId',
        // This feeds the home screen's primary CTA — the lesson title and
        // path title a parent reads before anything else. It was always
        // Arabic: the endpoint took no `lang` at all.
        if (lang != null && lang.isNotEmpty) 'lang': lang,
      },
    );
    final resp = await _http
        .get(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// `POST /api/program/coach-tip/{id}/tap` (authed) — light engagement log.
  /// Since v1.0.30 the server returns 200 for stale/missing tips; older server
  /// versions may still return 404. Swallow 404 so older backends don't crash
  /// the app on stale tap IDs.
  Future<void> recordCoachTipTap(int tipId) async {
    final session = await ensureSession();
    final token = session.token;
    final resp = await _http
        .post(Uri.parse('$_baseUrl/api/program/coach-tip/$tipId/tap'),
            headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200 && resp.statusCode != 404) {
      throw _wrap(resp);
    }
  }

  // ── «رحلة الطفل» current challenge (feeds the coach) ────────────────────

  /// `GET /api/children/{id}/challenge` (authed). Returns the active
  /// challenge map (`{challenge_key, topic, domain, note, started_at}`) or
  /// null when none is set.
  Future<Map<String, dynamic>?> getChallenge(int childId) async {
    final session = await ensureSession();
    final token = session.token;
    final resp = await _http
        .get(Uri.parse('$_baseUrl/api/children/$childId/challenge'),
            headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    final body = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    return body['challenge'] as Map<String, dynamic>?;
  }

  /// `GET /api/referral/me` (authed) → `{code, invited_count, reward_coins,
  /// share_url}`. Creates the device's referral code on first call.
  Future<Map<String, dynamic>> getReferral() async {
    final session = await ensureSession();
    final resp = await _http
        .get(Uri.parse('$_baseUrl/api/referral/me'),
            headers: _authHeaders(session.token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// `GET /api/stats/community` (public) → `{families, lessons_completed,
  /// active_this_week}`. Aggregate social proof for the Home surface.
  Future<Map<String, dynamic>> getCommunityStats() async {
    final resp = await _http
        .get(Uri.parse('$_baseUrl/api/stats/community'))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// `GET /api/app-config` (public) → `{minimum_build_number, store_url}`.
  Future<Map<String, dynamic>> fetchAppConfig() async {
    final resp = await _http
        .get(Uri.parse('$_baseUrl/api/app-config'))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// `GET /api/support/transparency` (public) → `{enabled, month, cost_usd,
  /// covered_usd, covered_pct, supports, breakdown, approximate}`.
  /// Older servers 404 — callers treat any failure as "nothing to show".
  Future<Map<String, dynamic>> fetchSupportTransparency() async {
    return _guard(() async {
      final resp = await _http
          .get(Uri.parse('$_baseUrl/api/support/transparency'))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    });
  }

  /// `POST /api/support/verify` (authed). The server checks the token with
  /// Play, records it, and consumes it. Returns the body as sent —
  /// `{ok, consumed, already_recorded, pending}`, with `pending: true` on a
  /// 202. Throws [TgApiError] otherwise (400 rejected, 503 retry later).
  Future<Map<String, dynamic>> verifySupportPurchase({
    required String productId,
    required String purchaseToken,
    int? priceMicros,
    String? currency,
  }) async {
    return _guard(() async {
      final session = await ensureSession();
      final resp = await _http
          .post(Uri.parse('$_baseUrl/api/support/verify'),
              headers: _authHeaders(session.token),
              body: jsonEncode({
                'product_id': productId,
                'purchase_token': purchaseToken,
                'price_micros': ?priceMicros,
                if (currency != null && currency.length == 3) 'currency': currency,
              }))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200 && resp.statusCode != 202) throw _wrap(resp);
      return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    });
  }

  /// `POST /api/referral/claim` (authed) → `{ok, already_claimed,
  /// reward_coins}`. Records this device as referred by [code].
  Future<Map<String, dynamic>> claimReferral(String code) async {
    final session = await ensureSession();
    final resp = await _http
        .post(Uri.parse('$_baseUrl/api/referral/claim'),
            headers: _authHeaders(session.token),
            body: jsonEncode({'code': code}))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// `POST /api/push/register` (authed) — store FCM token on the server.
  Future<void> registerPushToken(String token, {String platform = 'android'}) async {
    final session = await ensureSession();
    // The build census rides along here because this is the one request the
    // app makes on every launch. The version was previously recorded in the
    // session metadata, which cannot answer "what is installed today": a
    // session is created once per install and never updated, so a device that
    // installed on 1.0.29 and now runs 1.0.51 still reported 1.0.29. Without a
    // live count, MINIMUM_BUILD_NUMBER cannot be raised on evidence — see
    // docs/OPS_RUNBOOK.md §10.1.
    final info = await _packageInfo();
    final resp = await _http
        .post(Uri.parse('$_baseUrl/api/push/register'),
            headers: _authHeaders(session.token),
            body: jsonEncode({
              'token': token,
              'platform': platform,
              'app_version': ?info?.version,
              'build_number': ?int.tryParse(info?.buildNumber ?? ''),
            }))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    // Registering is where the server recognises a split-off twin (same FCM
    // token as the family's device, born in the same seconds, no child) and
    // re-attaches it; it then names the device this install now is.
    try {
      final data = jsonDecode(utf8.decode(resp.bodyBytes));
      final canonical = data is Map ? data['device_id'] : null;
      if (canonical is String && canonical.isNotEmpty) {
        await _auth.adoptDeviceId(canonical);
      }
    } on FormatException {
      // An older server answers without a body worth reading.
    }
  }

  /// `POST /api/identity/link-google` (authed) — link Google ID token to device_id.
  /// The backend verifies the ID token with Google's public tokeninfo endpoint.
  /// Returns the server's JSON response (e.g. `{ok: true, google_id, email}`).
  Future<Map<String, dynamic>> linkGoogleIdentity({required String idToken}) async {
    final session = await ensureSession();
    final resp = await _http
        .post(Uri.parse('$_baseUrl/api/identity/link-google'),
            headers: _authHeaders(session.token),
            body: jsonEncode({'id_token': idToken}))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    final body = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    if (body['ok'] != true) {
      throw TgApiError(400, body['error']?.toString() ?? AppL10n.current.apiGoogleLinkFailed);
    }
    return body;
  }

  /// `GET /api/identity/me` (authed) → `{linked, email, display_name}`.
  Future<Map<String, dynamic>> getIdentity() async {
    final session = await ensureSession();
    final resp = await _http
        .get(Uri.parse('$_baseUrl/api/identity/me'),
            headers: _authHeaders(session.token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// `PUT /api/children/{id}/challenge` (authed) — set/replace the active
  /// challenge by key (one of the server's known keys).
  Future<void> setChallenge(int childId, String challengeKey,
      {String? note}) async {
    final session = await ensureSession();
    final token = session.token;
    final resp = await _http
        .put(
          Uri.parse('$_baseUrl/api/children/$childId/challenge'),
          headers: _authHeaders(token),
          body: jsonEncode({
            'challenge_key': challengeKey,
            if (note != null && note.isNotEmpty) 'note': note,
          }),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
  }

  /// `DELETE /api/children/{id}/challenge` (authed) — resolve/clear it.
  Future<void> clearChallenge(int childId) async {
    final session = await ensureSession();
    final token = session.token;
    final resp = await _http
        .delete(Uri.parse('$_baseUrl/api/children/$childId/challenge'),
            headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
  }

  // ── Children + progress (Phase 5) ──────────────────────────────────────
  //
  // All three require a Bearer token (set by [_AuthHeaders] on the
  // POST/PATCH, the GET is also auth-protected). The token is
  // pulled from `_auth.readSession()` exactly like the chat endpoints.

  Future<Map<String, dynamic>> createChild({
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
    String? birthMonth,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final body = <String, dynamic>{
      'name': name,
      'age_group': ageGroup,
      'gender': ?gender,
      'avatar_emoji': ?avatarEmoji,
      // "YYYY-MM", optional (MOBILE_API §11.1). A server older than schema v34
      // ignores the key, which is why the field is only offered when the
      // programs API answers (see `programsAvailableProvider`).
      'birth_month': ?birthMonth,
    };
    final resp = await _http
        .post(
          Uri.parse('$_baseUrl/api/children'),
          headers: _authHeaders(token),
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 201) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getChildProgress(
    int childId, {
    String? pathId,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final qs = <String, String>{};
    if (pathId != null) qs['path_id'] = pathId;
    final uri = Uri.parse(
      '$_baseUrl/api/children/$childId/progress',
    ).replace(queryParameters: qs.isEmpty ? null : qs);
    final resp = await _http
        .get(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> patchLessonProgress({
    required String lessonId,
    required String status, // "not_started" | "in_progress" | "completed"
    int? childId,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    // Without child_id the server falls back to the device's FIRST-created
    // child, so on a family with more than one child every completion landed
    // on the wrong sibling and the parent saw a lesson they had just finished
    // still marked undone. Measured 2026-08-13: 99 of 451 completions (22%)
    // sat on a child whose age band did not match the lesson's, across 55
    // devices — 9.1% of families have more than one child.
    final resp = await _http
        .patch(
          Uri.parse('$_baseUrl/api/program/lessons/$lessonId/progress'),
          headers: _authHeaders(token),
          body: jsonEncode({
            'status': status,
            // The entry disappears when childId is null, so the server's
            // legacy fallback still applies for single-child devices.
            'child_id': ?childId,
          }),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  // ── Phase 7 — list / update / reset ───────────────────────────────────

  Future<Map<String, dynamic>> listChildren() async {
    final session = await ensureSession();
    final token = session.token;
    final resp = await _http
        .get(
          Uri.parse('$_baseUrl/api/children'),
          headers: _authHeaders(token),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateChild({
    required int childId,
    String? name,
    String? ageGroup,
    String? gender,
    String? avatarEmoji,
    String? birthMonth,
    bool clearBirthMonth = false,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final body = <String, dynamic>{};
    if (name != null) body['name'] = name;
    if (ageGroup != null) body['age_group'] = ageGroup;
    if (gender != null) body['gender'] = gender;
    if (avatarEmoji != null) body['avatar_emoji'] = avatarEmoji;
    // An explicit `null` clears the birth month; leaving the key out leaves it
    // alone (MOBILE_API §11.1). Two arguments rather than a nullable one,
    // because "not given" and "remove it" are different requests.
    if (clearBirthMonth) {
      body['birth_month'] = null;
    } else if (birthMonth != null) {
      body['birth_month'] = birthMonth;
    }
    final resp = await _http
        .patch(
          Uri.parse('$_baseUrl/api/children/$childId'),
          headers: _authHeaders(token),
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// `DELETE /api/children/{id}/progress`. Destructive: once this device has
  /// proven, the server wants a proven session (§9.0), so a
  /// `device_proof_required` proves and retries once.
  Future<Map<String, dynamic>> resetChildProgress(int childId) =>
      withDeviceProof(() async {
        final session = await ensureSession();
        final token = session.token;
        final resp = await _http
            .delete(
              Uri.parse('$_baseUrl/api/children/$childId/progress'),
              headers: _authHeaders(token),
            )
            .timeout(AppConfig.httpTimeout);
        if (resp.statusCode != 200) {
          throw _wrap(resp);
        }
        return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      });

  /// `DELETE /api/children/{id}` — removes the child profile entirely. Same
  /// proof rule as [resetChildProgress].
  Future<Map<String, dynamic>> deleteChild(int childId) =>
      withDeviceProof(() async {
        final session = await ensureSession();
        final token = session.token;
        final resp = await _http
            .delete(
              Uri.parse('$_baseUrl/api/children/$childId'),
              headers: _authHeaders(token),
            )
            .timeout(AppConfig.httpTimeout);
        if (resp.statusCode != 200) {
          throw _wrap(resp);
        }
        return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      });

  // ── «المربّي يعرف ابنك» — MOBILE_API §9–§10 ──────────────────────────
  //
  // Raw calls: each returns the decoded body or throws [TgApiError] (with
  // `code` for the branchable errors). Which of them prove-and-retry on
  // `device_proof_required` is decided one level up, in MemoryRepository —
  // the Today cards must never start a challenge on their own.

  /// One authed JSON call; [ok] lists the statuses that carry the answer.
  Future<Map<String, dynamic>> _authedJson(
    String method,
    String path, {
    Map<String, String>? query,
    Object? body,
    Set<int> ok = const {200},
  }) {
    return _guard(() async {
      final session = await ensureSession();
      final uri = Uri.parse('$_baseUrl$path')
          .replace(queryParameters: query == null || query.isEmpty ? null : query);
      final request = http.Request(method, uri)
        ..headers.addAll(_authHeaders(session.token));
      if (body != null) request.body = jsonEncode(body);
      final resp = await http.Response.fromStream(
        await _http.send(request).timeout(AppConfig.httpTimeout),
      ).timeout(AppConfig.httpTimeout);
      if (!ok.contains(resp.statusCode)) throw _wrap(resp);
      final text = utf8.decode(resp.bodyBytes);
      if (text.trim().isEmpty) return <String, dynamic>{};
      final decoded = jsonDecode(text);
      return decoded is Map<String, dynamic> ? decoded : <String, dynamic>{};
    });
  }

  /// `GET /api/device-proof` → `{proven, proven_at, push_registered,
  /// cooldown_until, deletion_paused_until}`.
  Future<Map<String, dynamic>> getDeviceProofStatus() =>
      _authedJson('GET', '/api/device-proof');

  /// `POST /api/device-proof/start` → `202 {challenge_id, expires_in}`; the
  /// code itself arrives as a silent FCM data message.
  Future<Map<String, dynamic>> startDeviceProof() =>
      _authedJson('POST', '/api/device-proof/start', ok: const {200, 202});

  /// `POST /api/device-proof/complete` with the same session that started.
  Future<Map<String, dynamic>> completeDeviceProof(
          String challengeId, String code) =>
      _authedJson('POST', '/api/device-proof/complete',
          body: {'challenge_id': challengeId, 'code': code});

  /// `GET /api/children/memory/settings` — no proof needed.
  Future<Map<String, dynamic>> getMemorySettings() =>
      _authedJson('GET', '/api/children/memory/settings');

  /// `PUT /api/children/memory/settings` — off never needs a proof; on does.
  Future<Map<String, dynamic>> putMemorySettings({required bool enabled}) =>
      _authedJson('PUT', '/api/children/memory/settings',
          body: {'enabled': enabled});

  /// `GET /api/children/{id}/memory?status=all`.
  Future<Map<String, dynamic>> getChildMemory(int childId,
          {String status = 'all'}) =>
      _authedJson('GET', '/api/children/$childId/memory',
          query: {'status': status});

  /// `POST /api/children/{id}/memory` → 201 Fact (`parent_manual`, active).
  Future<Map<String, dynamic>> addChildFact(int childId,
          {required String category, required String fact}) =>
      _authedJson('POST', '/api/children/$childId/memory',
          body: {'category': category, 'fact': fact}, ok: const {200, 201});

  /// `PATCH /api/children/{id}/memory/{factId}` — at least one field.
  Future<Map<String, dynamic>> patchChildFact(int childId, int factId,
          {String? fact, String? category, String? status}) =>
      _authedJson('PATCH', '/api/children/$childId/memory/$factId', body: {
        'fact': ?fact,
        'category': ?category,
        'status': ?status,
      });

  /// `DELETE /api/children/{id}/memory/{factId}`.
  Future<Map<String, dynamic>> deleteChildFact(int childId, int factId) =>
      _authedJson('DELETE', '/api/children/$childId/memory/$factId');

  /// `DELETE /api/children/{id}/memory` — everything about one child.
  Future<Map<String, dynamic>> deleteChildMemory(int childId) =>
      _authedJson('DELETE', '/api/children/$childId/memory');

  /// `GET /api/children/followups/due` — pending and due, every child.
  /// [tzOffsetMinutes] is how the follow-up push learns the family's evening.
  Future<Map<String, dynamic>> getDueFollowups(
          {int limit = 10, int? tzOffsetMinutes}) =>
      _authedJson('GET', '/api/children/followups/due', query: {
        'limit': '$limit',
        if (tzOffsetMinutes != null) 'tz_offset_minutes': '$tzOffsetMinutes',
      });

  /// `GET /api/children/followups/{id}` — any status (the deep link).
  Future<Map<String, dynamic>> getFollowup(int followupId) =>
      _authedJson('GET', '/api/children/followups/$followupId');

  /// `POST /api/children/followups/{id}/answer`.
  Future<Map<String, dynamic>> answerFollowup(int followupId,
          {required String outcome, String? note}) =>
      _authedJson('POST', '/api/children/followups/$followupId/answer',
          body: {
            'outcome': outcome,
            if (note != null && note.trim().isNotEmpty) 'note': note.trim(),
          });

  /// `POST /api/children/followups/{id}/dismiss`.
  Future<Map<String, dynamic>> dismissFollowup(int followupId) =>
      _authedJson('POST', '/api/children/followups/$followupId/dismiss');

  /// `GET /api/children/{id}/weekly-plan` — no proof needed.
  Future<Map<String, dynamic>> getWeeklyPlan(int childId,
          {String? lang, int? tzOffsetMinutes}) =>
      _authedJson('GET', '/api/children/$childId/weekly-plan', query: {
        'lang': ?lang,
        if (tzOffsetMinutes != null) 'tz_offset_minutes': '$tzOffsetMinutes',
      });

  /// `DELETE /api/privacy/memory` — memory of every child of this device.
  Future<Map<String, dynamic>> deleteAllMemory() =>
      _authedJson('DELETE', '/api/privacy/memory');

  /// `DELETE /api/privacy/account?confirm=true` (§10).
  ///
  /// The token the DELETE carries is revoked by it, so on success this install
  /// stops being the deleted device at once, before any other request can
  /// run: a brand-new device id replaces the old one (and a mint for the old
  /// one is refused with `410 device_erased` by servers that keep erased ids).
  ///
  /// The deletion is one transaction on the server, but not on the way back
  /// (PR #36 reviews): the origin can commit and the answer still be lost — a
  /// dropped connection, a client timeout while the origin works on, an edge
  /// 502/504/52x. So, before the DELETE leaves:
  ///   * the token is one the server accepts right now (an idle-lapsed token
  ///     is renewed first, H5), so a 401 to the DELETE can only mean the
  ///     account is gone;
  ///   * that token is copied to a key of its own, which clearing the session
  ///     ("new conversation", a 401 handler) never touches;
  ///   * the attempt is recorded ([kAccountDeletionRequested]).
  /// Then the answer decides — see [_sendAccountDeletion]: the server's body
  /// (200); `{}` when the account was already gone (401/410 — its scope is
  /// then unknown); the server's refusal when it deleted nothing (any other
  /// 4xx: nothing is left pending); or `account_deletion_unconfirmed` when
  /// there is no answer (5xx, timeout, no connection), with the record and
  /// the token kept for [settleAccountDeletion]. Nothing is ever concluded
  /// from a token merely still working: an in-flight DELETE can commit after.
  Future<Map<String, dynamic>> deleteAccount() async {
    final token = await _liveToken();
    // Making the token live met `410 device_erased`: the account was already
    // deleted (another phone of the family), and this install has started
    // over. Nothing is left to delete — never the fresh device's account.
    if (await accountDeletionState() == kAccountDeletionConfirmed) {
      return const <String, dynamic>{};
    }
    final askedId = await _auth.peekDeviceId();
    await _auth.writeDeletionToken(token);
    await _setAccountDeletionState(kAccountDeletionRequested);
    try {
      return await _sendAccountDeletion(token, askedId: askedId, resend: false);
    } on _InstallMovedOn {
      // A `410 device_erased` met elsewhere started this install over while
      // the answer travelled: the account is gone either way.
      return const <String, dynamic>{};
    }
  }

  /// Settle a deletion whose answer was lost (MOBILE_API §10) — find out,
  /// never guess:
  ///   * where the server keeps erased device ids for this build
  ///     (`GET /api/app-config` → `erased_device_410_min_build` ≤ [appBuild]):
  ///     a mint for the same device id, with the old token as proof, is the
  ///     authoritative answer ([_settleByMint]) — `410 device_erased`: it was
  ///     deleted; `201`: it was not, and the DELETE is not sent again without
  ///     asking the parent;
  ///   * otherwise (that gate off, an older server): the same DELETE is sent
  ///     again with the token it first carried and no session recovery
  ///     ([_sendAccountDeletion]) — `200`: deleted now; `401`: already
  ///     deleted; only the handler's own refusals prove the account is still
  ///     there.
  /// Returns the server's body (`{}` when the deletion is known only that
  /// way: scope unknown), or null when nothing is pending — or when the
  /// install moved on while the answer travelled (a `410` met elsewhere, the
  /// parent's way out): whoever moved it reports. Throws
  /// `account_not_deleted` (nothing was deleted, nothing is pending any more
  /// — a 72-hour pause keeps its own code, `device_proof_cooldown`), or
  /// `account_deletion_unconfirmed` while there is still no answer.
  ///
  /// Single-flight: a mint waiting for it ([_settleBeforeMinting]) joins the
  /// one in flight. Nothing in it mints through [createSession], and a mint
  /// started from inside it never waits for it (the zone marks it).
  Future<Map<String, dynamic>?> settleAccountDeletion() =>
      _settling ??= runZoned(_settleNow, zoneValues: {_settlingZone: true})
          .whenComplete(() => _settling = null);

  Future<Map<String, dynamic>?>? _settling;
  static const Symbol _settlingZone = #tgSettlingAccountDeletion;

  Future<Map<String, dynamic>?> _settleNow() async {
    final state = await accountDeletionState();
    if (state == null) return null;
    if (state == kAccountDeletionConfirmed) {
      await startOverAfterAccountDeletion();
      return const <String, dynamic>{};
    }
    final askedId = await _auth.peekDeviceId();
    try {
      if (askedId != null && await _erasedIdsKeptForThisBuild()) {
        return await _settleByMint(askedId);
      }
      var token = await _auth.readDeletionToken();
      if (token == null || token.isEmpty) {
        // The DELETE's own token is gone (a keystore reset): the session's,
        // and failing that a session minted for the device as it stands.
        token = (await _auth.readSession()).$2;
        if (token == null || token.isEmpty) {
          token = await _mintToSettle(askedId);
          if (token == null) return const <String, dynamic>{}; // erased
        }
        await _auth.writeDeletionToken(token);
      }
      return await _sendAccountDeletion(token, askedId: askedId, resend: true);
    } on _InstallMovedOn {
      return null;
    } on TgApiError catch (e) {
      switch (e.code) {
        case 'account_deletion_unconfirmed' ||
              'account_not_deleted' ||
              'device_proof_cooldown':
          rethrow;
      }
      throw TgApiError(e.statusCode, AppL10n.current.deleteAccountServerError,
          code: 'account_not_deleted', details: e.details);
    }
  }

  /// MOBILE_API §10 (PR #36 review, round 3): while a deletion waits for its
  /// answer on a server that does not refuse erased ids to this build, a mint
  /// for the old id would give a deleted account a live token again — rows
  /// written under it would outlive the deletion. So the deletion is settled
  /// first (the same DELETE again): deleted — the install is a new device and
  /// the app is told; still there — the mint is for a live account; no answer
  /// — no mint at all, rather than one that may bring the account back.
  Future<void> _settleBeforeMinting() async {
    if (Zone.current[_settlingZone] == true) return; // the settle's own mint
    if (await accountDeletionState() != kAccountDeletionRequested) return;
    if (await _erasedIdsKeptForThisBuild()) return; // the 410 guards the mint
    try {
      if (await settleAccountDeletion() != null) _tellDeviceErased();
    } on TgApiError catch (e) {
      if (e.code == 'account_deletion_unconfirmed') rethrow;
      // Refused or intact: the account is there, and minting brings nothing
      // back.
    }
  }

  /// Does the server answer `410 device_erased` to this build? Only then is a
  /// mint for the old id a statement about the deletion. Any failure to tell
  /// is a no — the DELETE path then decides.
  Future<bool> _erasedIdsKeptForThisBuild() async {
    final build = appBuild;
    if (build == null) return false;
    try {
      final floor = (await fetchAppConfig())['erased_device_410_min_build'];
      return floor is int && floor <= build;
    } catch (_) {
      return false;
    }
  }

  /// The authoritative answer (§10): mint for [askedId], with the token the
  /// DELETE carried as proof. `410 device_erased` → deleted: start over, `{}`
  /// (scope unknown). `201` → not deleted: the token is kept (the
  /// conversation stays), the record is dropped, and `account_not_deleted`
  /// is thrown («لم يُحذف شيء» — the parent may try again). No answer →
  /// `account_deletion_unconfirmed`.
  Future<Map<String, dynamic>> _settleByMint(String askedId) async {
    await _requireStillAwaiting(askedId); // never with a fresh install's proof
    final proof =
        await _auth.readDeletionToken() ?? await _auth.readDeviceProof();
    final http.Response resp;
    try {
      resp = await _postMint(askedId, proof: proof);
    } catch (_) {
      throw _deletionUnconfirmed(null);
    }
    await _requireStillAwaiting(askedId);
    if (resp.statusCode == 410 && _wrap(resp).code == 'device_erased') {
      await startOverAfterAccountDeletion();
      return const <String, dynamic>{};
    }
    if (resp.statusCode == 201) {
      try {
        await _keepMinted(resp, askedId, keepConversation: true);
      } catch (_) {}
      await _abandonAccountDeletion();
      throw TgApiError(201, AppL10n.current.deleteAccountServerError,
          code: 'account_not_deleted');
    }
    throw _deletionUnconfirmed(resp.statusCode);
  }

  /// Neither the DELETE's token nor a session is left (a keystore reset):
  /// mint one for [askedId] — raw, never through [createSession] — to send
  /// the DELETE with. Null when that mint says the id was erased (the install
  /// has started over). On a server without erased ids the mint brings the id
  /// back for a moment, and the DELETE sent with it removes it again at once.
  Future<String?> _mintToSettle(String? askedId) async {
    if (askedId == null) throw _deletionUnconfirmed(null); // nothing to ask
    await _requireStillAwaiting(askedId);
    final http.Response resp;
    try {
      resp = await _postMint(askedId);
    } catch (_) {
      throw _deletionUnconfirmed(null);
    }
    await _requireStillAwaiting(askedId);
    if (resp.statusCode == 410 && _wrap(resp).code == 'device_erased') {
      await startOverAfterAccountDeletion();
      return null;
    }
    if (resp.statusCode != 201) throw _deletionUnconfirmed(resp.statusCode);
    return (await _keepMinted(resp, askedId)).token;
  }

  /// A token the server accepted a moment ago: a request through the
  /// session-recovering transport first (it renews an idle-lapsed token), then
  /// the session as it stands.
  Future<String> _liveToken() async {
    await getDeviceProofStatus();
    final (_, token) = await _auth.readSession();
    if (token == null || token.isEmpty) {
      throw TgApiError(401, AppL10n.current.noActiveSession);
    }
    return token;
  }

  /// Send the account DELETE with [token] over the raw transport — a 401 must
  /// reach this code, never a session recovery minting for the erased id —
  /// and act on the answer, if the install is still [askedId] waiting for it
  /// (otherwise [_InstallMovedOn]):
  ///   * 200: deleted. The install starts over; the server's body is returned.
  ///   * 401 / 410: the token died with the account — an earlier attempt went
  ///     through (a token lapses only after 180 idle days). The install
  ///     starts over; `{}` (scope unknown).
  ///   * another 4xx on the first attempt: the server refused it (a pause, no
  ///     proof, no route, a rate limit). Nothing was deleted; nothing is left
  ///     pending; the refusal is rethrown as the server sent it.
  ///   * another 4xx on a [resend]: only the handler's own refusals
  ///     (`device_proof_*`, `confirm_required`) prove the account is still
  ///     there. A rate limit (429) or an uncoded answer from an edge may come
  ///     before the token is even read — unknown.
  ///   * 5xx, a timeout, no connection: unknown — the record and the token
  ///     stay, and `account_deletion_unconfirmed` is thrown.
  Future<Map<String, dynamic>> _sendAccountDeletion(String token,
      {required String? askedId, required bool resend}) async {
    await _requireStillAwaiting(askedId);
    final http.Response resp;
    try {
      resp = await _raw
          .delete(
            Uri.parse('$_baseUrl/api/privacy/account')
                .replace(queryParameters: const {'confirm': 'true'}),
            headers: _authHeaders(token),
          )
          .timeout(AppConfig.httpTimeout);
    } catch (_) {
      throw _deletionUnconfirmed(null);
    }
    await _requireStillAwaiting(askedId);
    final status = resp.statusCode;
    if (status == 200) {
      Map<String, dynamic> body = const {};
      try {
        final decoded = jsonDecode(utf8.decode(resp.bodyBytes));
        if (decoded is Map<String, dynamic>) body = decoded;
      } catch (_) {}
      await startOverAfterAccountDeletion();
      return body;
    }
    if (status == 401 || status == 410) {
      await startOverAfterAccountDeletion();
      return const <String, dynamic>{};
    }
    if (status >= 500 || status < 400) throw _deletionUnconfirmed(status);
    final refusal = _wrap(resp);
    final code = refusal.code;
    final provesAccount = code != null &&
        (code.startsWith('device_proof_') || code == 'confirm_required');
    if (resend && !provesAccount) throw _deletionUnconfirmed(status);
    await _abandonAccountDeletion();
    throw refusal;
  }

  /// Act on an answer about [askedId] only while the deletion still waits for
  /// it and the install is still that device. Anything else means it moved
  /// on while the answer travelled — a `410 device_erased` met elsewhere, the
  /// parent's way out — and the answer is not acted on: no session kept,
  /// nothing abandoned, no second start-over.
  Future<void> _requireStillAwaiting(String? askedId) async {
    if (await accountDeletionState() != kAccountDeletionRequested ||
        await _auth.peekDeviceId() != askedId) {
      throw const _InstallMovedOn();
    }
  }

  TgApiError _deletionUnconfirmed(int? status) => TgApiError(
      status, AppL10n.current.deleteAccountUnconfirmed,
      code: 'account_deletion_unconfirmed');

  /// The server refused the DELETE: nothing was deleted, nothing is pending.
  /// Only a deletion still waiting for its answer is dropped — never a
  /// confirmed one whose phone is still to be cleared.
  Future<void> _abandonAccountDeletion() async {
    if (await accountDeletionState() != kAccountDeletionRequested) return;
    await _auth.clearDeletionToken();
    await _setAccountDeletionState(null);
  }

  /// Where an account deletion stands on this phone (SharedPreferences):
  /// [kAccountDeletionRequested], [kAccountDeletionConfirmed], or null.
  Future<String?> accountDeletionState() async {
    try {
      return (await SharedPreferences.getInstance())
          .getString(kAccountDeletionKey);
    } catch (_) {
      return null;
    }
  }

  Future<void> _setAccountDeletionState(String? state) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      if (state == null) {
        await prefs.remove(kAccountDeletionKey);
      } else {
        await prefs.setString(kAccountDeletionKey, state);
      }
    } catch (_) {}
  }

  /// Nothing of a deletion is left to do on this phone: the record, the id it
  /// erased and the token it was sent with all go.
  Future<void> clearAccountDeletionState() async {
    await _auth.clearDeletionToken();
    await _setAccountDeletionState(null);
    try {
      await (await SharedPreferences.getInstance())
          .remove(kAccountDeletionErasedIdKey);
    } catch (_) {}
  }

  Future<void>? _startingOver;

  /// The server deleted the account, or erased this device id: become a
  /// brand-new device. What happened is recorded first —
  /// [kAccountDeletionConfirmed] and the erased id, BEFORE the keystore is
  /// cleared — so a launch that finds the record finishes the job even if the
  /// app was killed in the middle: it starts over again while the erased id is
  /// still held anywhere, then clears the phone (completePendingAccountDeletion).
  ///
  /// Single-flight, and a no-op once the erased id is gone from everywhere —
  /// a second caller (the DELETE's answer and a `410` racing) never erases the
  /// fresh id it just got. Also the parent's way out of a deletion that cannot
  /// be settled («ابدأ من جديد على هذا الهاتف»).
  Future<void> startOverAfterAccountDeletion() =>
      _startingOver ??= _startOver().whenComplete(() => _startingOver = null);

  Future<void> _startOver() async {
    SharedPreferences? prefs;
    try {
      prefs = await SharedPreferences.getInstance();
    } catch (_) {}
    if (prefs?.getString(kAccountDeletionKey) == kAccountDeletionConfirmed) {
      final erased = prefs!.getString(kAccountDeletionErasedIdKey);
      if (erased == null || !await _auth.stillHolds(erased)) return;
    } else {
      final erased = await _auth.peekDeviceId();
      try {
        if (erased != null) {
          await prefs?.setString(kAccountDeletionErasedIdKey, erased);
        }
        await prefs?.setString(kAccountDeletionKey, kAccountDeletionConfirmed);
      } catch (_) {}
    }
    _erasures++;
    await _auth.startOverAsNewDevice();
  }

  /// How many times this client became a new device (session recovery must
  /// not pair the erased account's session id with a fresh token).
  int _erasures = 0;

  /// A mint answered `410 device_erased`: start over (nothing may mint for
  /// that id again), then let the app clear the phone and say so.
  Future<void> _deviceErased() async {
    await startOverAfterAccountDeletion();
    _tellDeviceErased();
  }

  void _tellDeviceErased() {
    final handler = onDeviceErased;
    if (handler != null) {
      unawaited(Future<void>.sync(handler).catchError((Object _) {}));
    }
  }

  // ── Daily routine — حساب اليوم ───────────────────────────────────────

  Future<Map<String, dynamic>> fetchTodayRoutine(int childId) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/daily-routine/today')
        .replace(queryParameters: {'child_id': '$childId'});
    final resp = await _http
        .get(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createRoutineEvent(
    int childId, {
    required Map<String, dynamic> body,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/daily-routine/events')
        .replace(queryParameters: {'child_id': '$childId'});
    final resp = await _http
        .post(
          uri,
          headers: _authHeaders(token),
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateRoutineEvent(
    int eventId, {
    required Map<String, dynamic> body,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final resp = await _http
        .patch(
          Uri.parse('$_baseUrl/api/daily-routine/events/$eventId'),
          headers: _authHeaders(token),
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> deleteRoutineEvent(int eventId) async {
    final session = await ensureSession();
    final token = session.token;
    final resp = await _http
        .delete(
          Uri.parse('$_baseUrl/api/daily-routine/events/$eventId'),
          headers: _authHeaders(token),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchRoutineSummary(
    int childId, {
    int days = 7,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/daily-routine/summary')
        .replace(queryParameters: {'child_id': '$childId', 'days': '$days'});
    final resp = await _http
        .get(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchParentingInsights(int childId) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/insights/parenting')
        .replace(queryParameters: {'child_id': '$childId'});
    final resp = await _http
        .get(uri, headers: _authHeaders(token))
        .timeout(const Duration(seconds: 90));
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  // ── Value tracking — ميزان العادات ────────────────────────────────────

  Future<Map<String, dynamic>> fetchTodayHabits(int childId) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/value-tracking/today')
        .replace(queryParameters: {'child_id': '$childId'});
    final resp = await _http
        .get(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createHabitEvent(
    int childId, {
    required Map<String, dynamic> body,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/value-tracking/events')
        .replace(queryParameters: {'child_id': '$childId'});
    final resp = await _http
        .post(
          uri,
          headers: _authHeaders(token),
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> deleteHabitEvent(int eventId) async {
    final session = await ensureSession();
    final token = session.token;
    final resp = await _http
        .delete(
          Uri.parse('$_baseUrl/api/value-tracking/events/$eventId'),
          headers: _authHeaders(token),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchHabitSummary(
    int childId, {
    int days = 7,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/value-tracking/summary')
        .replace(queryParameters: {'child_id': '$childId', 'days': '$days'});
    final resp = await _http
        .get(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  // ── Custom habit templates ────────────────────────────────────────────

  Future<Map<String, dynamic>> createHabitTemplate(
    int childId, {
    required Map<String, dynamic> body,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/habit-templates')
        .replace(queryParameters: {'child_id': '$childId'});
    final resp = await _http
        .post(
          uri,
          headers: _authHeaders(token),
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 201) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> listHabitTemplates(
    int childId, {
    bool activeOnly = false,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/habit-templates').replace(
      queryParameters: {
        'child_id': '$childId',
        if (activeOnly) 'active_only': 'true',
      },
    );
    final resp = await _http
        .get(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    final raw = jsonDecode(utf8.decode(resp.bodyBytes)) as List<dynamic>;
    return <String, dynamic>{'templates': raw};
  }

  Future<Map<String, dynamic>> updateHabitTemplate(
    int templateId, {
    required Map<String, dynamic> body,
  }) async {
    final session = await ensureSession();
    final token = session.token;
    final resp = await _http
        .patch(
          Uri.parse('$_baseUrl/api/habit-templates/$templateId'),
          headers: _authHeaders(token),
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  // ── Child mode ─────────────────────────────────────────────────────────

  /// Thrown when a child-mode request cannot be refreshed and the UI should
  /// return to the lock screen so the parent can re-issue a token.
  static TgApiError get childSessionExpired => TgApiError(
        401,
        AppL10n.current.apiChildSessionExpired,
      );

  Future<Map<String, dynamic>> createChildSession(
    int childId, {
    String surface = 'habit',
  }) async {
    final session = await ensureSession();
    final token = session.token;
    // The server derives the child's calendar day from this offset rather
    // than trusting a date string — moving the device clock forward no longer
    // buys a fresh daily budget.
    final offset = DateTime.now().timeZoneOffset.inMinutes;
    final uri = Uri.parse('$_baseUrl/api/value-tracking/child-sessions')
        .replace(queryParameters: {
      'child_id': '$childId',
      'surface': surface,
      'tz_offset_minutes': '$offset',
    });
    final resp = await _http
        .post(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  // ── Family media agreement ───────────────────────────────────────────────

  Future<Map<String, dynamic>> fetchSuggestedClauses(int childId) async {
    return _guard(() async {
      final session = await ensureSession();
      final uri = Uri.parse(
              '$_baseUrl/api/children/$childId/agreement/clauses/suggested')
          .replace(queryParameters: _langParam());
      final resp = await _http
          .get(uri, headers: _authHeaders(session.token))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    });
  }

  /// The parent's one-screen view of a child's day, assembled server-side so
  /// the numbers being compared come from the same instant.
  Future<Map<String, dynamic>> fetchChildDay(int childId) async {
    return _guard(() async {
      final session = await ensureSession();
      final offset = DateTime.now().timeZoneOffset.inMinutes;
      // `lang` so the mission title reaches an English parent in English
      // where the bank has a translation (the endpoint has accepted it since
      // it shipped; this call never sent it).
      final uri = Uri.parse('$_baseUrl/api/children/$childId/today')
          .replace(queryParameters: {
        'tz_offset_minutes': '$offset',
        ..._langParam(),
      });
      final resp = await _http
          .get(uri, headers: _authHeaders(session.token))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    });
  }

  Future<Map<String, dynamic>?> fetchAgreement(int childId) async {
    return _guard(() async {
      final session = await ensureSession();
      final uri = Uri.parse('$_baseUrl/api/children/$childId/agreement');
      final resp = await _http
          .get(uri, headers: _authHeaders(session.token))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      final body = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      return body['agreement'] as Map<String, dynamic>?;
    });
  }

  Future<Map<String, dynamic>> saveAgreementDraft(
      int childId, List<Map<String, dynamic>> clauses) async {
    final session = await ensureSession();
    final uri = Uri.parse('$_baseUrl/api/children/$childId/agreement');
    final resp = await _http
        .post(uri,
            headers: {..._authHeaders(session.token),
                      'Content-Type': 'application/json'},
            body: jsonEncode({'clauses': clauses}))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<void> signAgreementAsParent(int childId) async {
    final session = await ensureSession();
    final uri = Uri.parse('$_baseUrl/api/children/$childId/agreement/sign');
    final resp = await _http
        .post(uri, headers: _authHeaders(session.token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
  }

  Future<Map<String, dynamic>?> fetchChildAgreement(String childToken) async {
    return _guard(() async {
      final uri = Uri.parse('$_baseUrl/api/value-tracking/child-mode/agreement');
      final resp = await _http
          .get(uri, headers: _childAuthHeaders(childToken))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      final body = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      return body['agreement'] as Map<String, dynamic>?;
    });
  }

  Future<void> acknowledgeClause(
      {required String childToken, required int clauseId}) async {
    final uri = Uri.parse(
            '$_baseUrl/api/value-tracking/child-mode/agreement/acknowledge')
        .replace(queryParameters: {'clause_id': '$clauseId'});
    final resp = await _http
        .post(uri, headers: _childAuthHeaders(childToken))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
  }

  /// Returns true once both signatures are in and the agreement is active.
  Future<bool> signAgreementAsChild(String childToken) async {
    final uri =
        Uri.parse('$_baseUrl/api/value-tracking/child-mode/agreement/sign');
    final resp = await _http
        .post(uri, headers: _childAuthHeaders(childToken))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    final body = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    return body['activated'] as bool? ?? false;
  }

  /// Report that the child is still on the surface, and learn what is left.
  ///
  /// Returns null when the session is over — budget spent, reaped, or already
  /// closed. That is not an error to retry: the caller closes the surface.
  Future<Map<String, dynamic>?> childHeartbeat({
    required String childToken,
    required int sessionId,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/value-tracking/child-mode/heartbeat')
        .replace(queryParameters: {'session_id': '$sessionId'});
    final resp = await _http
        .post(uri, headers: _childAuthHeaders(childToken))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode == 403 || resp.statusCode == 404) return null;
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<void> endChildSession({
    required String childToken,
    required int sessionId,
    String reason = 'completed',
  }) async {
    final uri = Uri.parse('$_baseUrl/api/value-tracking/child-mode/session-end')
        .replace(queryParameters: {
      'session_id': '$sessionId',
      'reason': reason,
    });
    await _http
        .post(uri, headers: _childAuthHeaders(childToken))
        .timeout(AppConfig.httpTimeout);
  }

  // ── Missions ─────────────────────────────────────────────────────────────
  //
  // The backend for these shipped complete and tested with no screen anywhere
  // in the app calling them: the child was assigned a mission every day and
  // never saw one. These four methods are the missing wire.

  /// Today's single card, or null when the child's band has no mission bank.
  ///
  /// Every band from 4-6 to 16-18 has a bank as of 2026-08-21 (7-9 was the
  /// only one when this was written), so an empty result is now the exception
  /// rather than the rule — but it is still a state to render, not an error to
  /// report: the youngest band has no bank by design.
  Future<Map<String, dynamic>?> fetchChildMission(String childToken) async {
    return _guard(() async {
      final uri = Uri.parse('$_baseUrl/api/value-tracking/child-mode/mission/today')
          .replace(queryParameters: {
        'tz_offset_minutes': '${DateTime.now().timeZoneOffset.inMinutes}',
        ..._langParam(),
      });
      final resp = await _http
          .get(uri, headers: _childAuthHeaders(childToken))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      final body = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      return body['mission'] as Map<String, dynamic>?;
    });
  }

  /// The child says they did it. Returns false when the card was already
  /// settled — which is not worth an error dialog aimed at a seven-year-old.
  Future<bool> claimChildMission({
    required String childToken,
    required int missionId,
  }) async {
    return _guard(() async {
      final uri = Uri.parse('$_baseUrl/api/value-tracking/child-mode/mission/claim')
          .replace(queryParameters: {'mission_id': '$missionId'});
      final resp = await _http
          .post(uri, headers: _childAuthHeaders(childToken))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode == 409) return false;
      if (resp.statusCode != 200) throw _wrap(resp);
      return true;
    });
  }

  /// Every claimed-but-unconfirmed card across all of this device's children.
  Future<List<Map<String, dynamic>>> fetchPendingMissions() async {
    return _guard(() async {
      final session = await ensureSession();
      final uri = Uri.parse('$_baseUrl/api/children/missions/pending')
          .replace(queryParameters: _langParam());
      final resp = await _http
          .get(uri, headers: _authHeaders(session.token))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      final body = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      return (body['pending'] as List<dynamic>? ?? const [])
          .cast<Map<String, dynamic>>();
    });
  }

  /// Settle a batch. One call for the whole evening — the asynchronous
  /// confirmation loop is the point, and a per-card round trip would undo it.
  Future<int> confirmMissions(List<Map<String, dynamic>> items) async =>
      (await settleMissions(items)).settled;

  /// [confirmMissions], plus what the confirmed cards earned.
  ///
  /// Prayer Journey cards ride the same evening loop (MOBILE_API §11.4.7) and
  /// the server keeps no coin ledger: `coins` lists each confirmed program card
  /// with its value, for the app to credit on the device. Older servers do not
  /// send the key, and bank missions never carry coins.
  Future<({int settled, List<Map<String, dynamic>> coins})> settleMissions(
      List<Map<String, dynamic>> items) async {
    return _guard(() async {
      final session = await ensureSession();
      final uri = Uri.parse('$_baseUrl/api/children/missions/confirm');
      final resp = await _http
          .post(uri,
              headers: {..._authHeaders(session.token),
                'Content-Type': 'application/json'},
              body: jsonEncode({'items': items}))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      final body = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      final coins = (body['coins'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .toList();
      return (settled: body['settled'] as int? ?? 0, coins: coins);
    });
  }

  // ── Family programs (MOBILE_API §11, backend schema v34) ────────────────
  //
  // Ramadan, the Prayer Journey and the proactive milestones. Every call sends
  // the family's UTC offset — it decides their date (the Ramadan day turns at
  // *their* midnight) and the server remembers it for the milestone push, which
  // is never sent to a device that never reported one — and the UI language.
  // A server older than v34 answers 404 to all of it; the screens treat that
  // as "not offered" and hide their entry points.

  /// `tz_offset_minutes` + `lang` — the query every programs call carries.
  Map<String, String> _programsQuery([Map<String, String>? extra]) => {
        'tz_offset_minutes': '${DateTime.now().timeZoneOffset.inMinutes}',
        ..._langParam(),
        ...?extra,
      };

  Future<Map<String, dynamic>> _programsCall(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? query,
  }) {
    return _guard(() async {
      final session = await ensureSession();
      final uri = Uri.parse('$_baseUrl$path')
          .replace(queryParameters: _programsQuery(query));
      final headers = _authHeaders(session.token);
      final encoded = body == null ? null : jsonEncode(body);
      final http.Response resp;
      switch (method) {
        case 'GET':
          resp = await _http.get(uri, headers: headers).timeout(AppConfig.httpTimeout);
        case 'POST':
          resp = await _http
              .post(uri, headers: headers, body: encoded ?? '{}')
              .timeout(AppConfig.httpTimeout);
        case 'PUT':
          resp = await _http
              .put(uri, headers: headers, body: encoded ?? '{}')
              .timeout(AppConfig.httpTimeout);
        case 'DELETE':
          resp = await _http.delete(uri, headers: headers).timeout(AppConfig.httpTimeout);
        default:
          throw ArgumentError.value(method, 'method');
      }
      if (resp.statusCode != 200) throw _wrap(resp);
      return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    });
  }

  /// `GET /api/programs` — what applies to each child today. 404 on a server
  /// that has no programs; callers read that as "hide the entry points".
  Future<Map<String, dynamic>> fetchPrograms() =>
      _programsCall('GET', '/api/programs');

  /// `GET /api/children/{id}/ramadan/today`. No `features` is sent: this build
  /// has no weekly-plan screen, so the after-Ramadan week that promises one
  /// must come back with its fallback text (MOBILE_API §11.3.2).
  Future<Map<String, dynamic>> fetchRamadanToday(int childId) =>
      _programsCall('GET', '/api/children/$childId/ramadan/today');

  /// `GET /api/children/{id}/ramadan/days/{day}` — any day 1–30.
  Future<Map<String, dynamic>> fetchRamadanDay(int childId, int day) =>
      _programsCall('GET', '/api/children/$childId/ramadan/days/$day');

  /// `POST /api/programs/ramadan/marks` — tick or untick a family «تمّ».
  Future<Map<String, dynamic>> setRamadanMark({
    required String mark,
    int? day,
    bool done = true,
    int? choiceIndex,
  }) =>
      _programsCall('POST', '/api/programs/ramadan/marks', body: {
        'mark': mark,
        'day': ?day,
        'done': done,
        'choice_index': ?choiceIndex,
      });

  /// `GET /api/children/{id}/ramadan/fasting` — the ladder and its guidance.
  Future<Map<String, dynamic>> fetchFastingLadder(int childId) =>
      _programsCall('GET', '/api/children/$childId/ramadan/fasting');

  /// `PUT /api/children/{id}/ramadan/fasting` — a step and/or puberty.
  Future<Map<String, dynamic>> updateFasting(
    int childId, {
    String? stepKey,
    bool? reachedPuberty,
  }) =>
      _programsCall('PUT', '/api/children/$childId/ramadan/fasting', body: {
        'step_key': ?stepKey,
        'reached_puberty': ?reachedPuberty,
      });

  /// `POST /api/children/{id}/ramadan/fasting/practice` — "practised their
  /// step today". `done: false` takes it back; a day not practised is simply
  /// not recorded.
  Future<Map<String, dynamic>> recordFastingPractice(
    int childId, {
    int? day,
    bool done = true,
  }) =>
      _programsCall('POST', '/api/children/$childId/ramadan/fasting/practice',
          body: {'day': ?day, 'done': done});

  /// `PUT /api/programs/ramadan/settings` — the family's own moon sighting.
  /// [resetMonthDays] sends `month_days: null` (back to the server's length).
  Future<Map<String, dynamic>> updateRamadanSettings({
    int? startShiftDays,
    int? monthDays,
    bool resetMonthDays = false,
  }) {
    final body = <String, dynamic>{'start_shift_days': ?startShiftDays};
    if (resetMonthDays) {
      body['month_days'] = null;
    } else if (monthDays != null) {
      body['month_days'] = monthDays;
    }
    return _programsCall('PUT', '/api/programs/ramadan/settings', body: body);
  }

  /// `GET /api/programs/ramadan/recap` — «رمضان عائلتنا».
  Future<Map<String, dynamic>> fetchRamadanRecap({int? hijriYear}) =>
      _programsCall('GET', '/api/programs/ramadan/recap',
          query: {if (hijriYear != null) 'hijri_year': '$hijriYear'});

  /// `GET /api/children/{id}/prayer-journey`.
  Future<Map<String, dynamic>> fetchPrayerJourney(int childId) =>
      _programsCall('GET', '/api/children/$childId/prayer-journey');

  /// `POST /api/children/{id}/prayer-journey/enrol`.
  Future<Map<String, dynamic>> enrolPrayerJourney(
    int childId, {
    String? track,
    int? startStage,
    bool restart = false,
  }) =>
      _programsCall('POST', '/api/children/$childId/prayer-journey/enrol',
          body: {
            'track': ?track,
            'start_stage': ?startStage,
            if (restart) 'restart': true,
          });

  /// `PUT /api/children/{id}/prayer-journey/stage` — forward one, back any.
  Future<Map<String, dynamic>> setPrayerJourneyStage(int childId, int stage) =>
      _programsCall('PUT', '/api/children/$childId/prayer-journey/stage',
          body: {'stage': stage});

  /// `POST /api/children/{id}/prayer-journey/graduate`.
  Future<Map<String, dynamic>> graduatePrayerJourney(int childId) =>
      _programsCall('POST', '/api/children/$childId/prayer-journey/graduate');

  /// `DELETE /api/children/{id}/prayer-journey` — stop it.
  Future<Map<String, dynamic>> stopPrayerJourney(int childId) =>
      _programsCall('DELETE', '/api/children/$childId/prayer-journey');

  /// `GET /api/children/{id}/milestones`.
  Future<Map<String, dynamic>> fetchMilestones(int childId) =>
      _programsCall('GET', '/api/children/$childId/milestones');

  /// `GET /api/children/{id}/milestones/{key}` — the push's deep link.
  Future<Map<String, dynamic>> fetchMilestone(int childId, String key) =>
      _programsCall('GET',
          '/api/children/$childId/milestones/${Uri.encodeComponent(key)}');

  /// Child mode: today's prayer tasks (Child-Bearer, live screen session).
  Future<Map<String, dynamic>> fetchChildPrayerToday(String childToken) {
    return _guard(() => _childPrayerCall(
          childToken,
          (token) => _http
              .get(
                Uri.parse('$_baseUrl/api/value-tracking/child-mode/prayer/today')
                    .replace(queryParameters: _programsQuery()),
                headers: _childAuthHeaders(token),
              )
              .timeout(AppConfig.httpTimeout),
        ));
  }

  /// Child mode: «صلّيتها». Recorded at once; the parent confirms tonight.
  Future<Map<String, dynamic>> claimChildPrayer({
    required String childToken,
    required String taskId,
  }) {
    return _guard(() => _childPrayerCall(
          childToken,
          (token) => _http
              .post(
                Uri.parse('$_baseUrl/api/value-tracking/child-mode/prayer/claim')
                    .replace(queryParameters: _programsQuery({'task_id': taskId})),
                headers: _childAuthHeaders(token),
              )
              .timeout(AppConfig.httpTimeout),
        ));
  }

  /// One child-mode programs request, with the habit surface's recovery: a
  /// 401 first renews the child token from the parent's session (as
  /// [fetchChildTodayHabits] does) and replays once. Only when that fails is
  /// the 401 reported — [childSessionExpired] — and the caller hides the card.
  /// A 401 is never a recorded claim, so replaying a claim cannot double it.
  Future<Map<String, dynamic>> _childPrayerCall(
    String childToken,
    Future<http.Response> Function(String token) send,
  ) async {
    var resp = await send(childToken);
    if (resp.statusCode == 401) {
      final refreshed = await _refreshChildTokenOrFail();
      if (refreshed == null) throw childSessionExpired;
      resp = await send(refreshed);
      if (resp.statusCode == 401) throw childSessionExpired;
    }
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  // ── Internet licence ─────────────────────────────────────────────────────

  /// The next situation to think about. The payload carries no outcome flags —
  /// the server strips them, because a response that includes the answer is an
  /// answer key sitting in the client.
  Future<Map<String, dynamic>> fetchChildLicense(String childToken) async {
    return _guard(() async {
      final uri =
          Uri.parse('$_baseUrl/api/value-tracking/child-mode/license/today')
              .replace(queryParameters: _langParam());
      final resp = await _http
          .get(uri, headers: _childAuthHeaders(childToken))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    });
  }

  /// Record a choice. Returns nothing about right or wrong, deliberately.
  Future<void> answerLicenseScenario({
    required String childToken,
    required String scenarioKey,
    required String choiceKey,
  }) async {
    return _guard(() async {
      final uri =
          Uri.parse('$_baseUrl/api/value-tracking/child-mode/license/answer')
              .replace(queryParameters: {
        'scenario_key': scenarioKey,
        'choice_key': choiceKey,
        ..._langParam(),
      });
      final resp = await _http
          .post(uri, headers: _childAuthHeaders(childToken))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
    });
  }

  Future<Map<String, dynamic>> fetchLicenseSummary(int childId) async {
    return _guard(() async {
      final session = await ensureSession();
      final uri = Uri.parse('$_baseUrl/api/children/$childId/license')
          .replace(queryParameters: _langParam());
      final resp = await _http
          .get(uri, headers: _authHeaders(session.token))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
      return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    });
  }

  Future<void> recordLicenseTalk(int childId, String levelKey) async {
    await _licensePost(childId, 'talked', levelKey);
  }

  /// Throws on 409 — the server refuses a grant before the practice is done
  /// and the talk is recorded, and the UI shows that refusal rather than
  /// hiding the button.
  Future<void> grantLicenseLevel(int childId, String levelKey) async {
    await _licensePost(childId, 'grant', levelKey);
  }

  Future<void> _licensePost(int childId, String action, String levelKey) async {
    return _guard(() async {
      final session = await ensureSession();
      final uri = Uri.parse('$_baseUrl/api/children/$childId/license/$action');
      final resp = await _http
          .post(uri,
              headers: {..._authHeaders(session.token),
                'Content-Type': 'application/json'},
              body: jsonEncode({'level_key': levelKey}))
          .timeout(AppConfig.httpTimeout);
      if (resp.statusCode != 200) throw _wrap(resp);
    });
  }

  Future<Map<String, dynamic>> createChildWebClaim(int childId) async {
    final session = await ensureSession();
    final token = session.token;
    final uri = Uri.parse('$_baseUrl/api/value-tracking/child-web-claims')
        .replace(queryParameters: {'child_id': '$childId'});
    final resp = await _http
        .post(uri, headers: _authHeaders(token))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchChildTodayHabits({required String childToken}) async {
    final uri = Uri.parse('$_baseUrl/api/value-tracking/child-mode/today');
    final resp = await _http
        .get(uri, headers: _childAuthHeaders(childToken))
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode == 401) {
      final refreshed = await _refreshChildTokenOrFail();
      if (refreshed != null) {
        return fetchChildTodayHabits(childToken: refreshed);
      }
      throw childSessionExpired;
    }
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createChildHabitEvent({
    required String childToken,
    required Map<String, dynamic> body,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/value-tracking/child-mode/events');
    final resp = await _http
        .post(
          uri,
          headers: _childAuthHeaders(childToken),
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode == 401) {
      final refreshed = await _refreshChildTokenOrFail();
      if (refreshed != null) {
        return createChildHabitEvent(childToken: refreshed, body: body);
      }
      throw childSessionExpired;
    }
    if (resp.statusCode != 200) throw _wrap(resp);
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  /// Tries to silently refresh the child token using the stored parent token.
  /// Returns the new child token, or null if the parent session is also gone.
  ///
  /// Renews for the child **holding the phone** — the one child mode was
  /// entered for — not the parent's active child: the Prayer Journey hands
  /// the phone to the journey's child without making them the active child,
  /// and renewing for the active one replayed the claim on the other child's
  /// journey and switched the whole child surface to them.
  Future<String?> _refreshChildTokenOrFail() =>
      _childTokenRenewal ??= _renewChildToken()
          .whenComplete(() => _childTokenRenewal = null);

  Future<String?> _renewChildToken() async {
    try {
      final childId = await _childModeChildId();
      if (childId == null) return null;
      final session = await _auth.readSession();
      if (session.$1 == null) return null;
      final newSession = await createChildSession(childId);
      final token = newSession['token'] as String?;
      if (token == null) return null;
      await _auth.writeChildToken(token);
      return token;
    } catch (_) {
      return null;
    }
  }

  /// The child whose surface is open, as child mode stored it on entry
  /// ([kChildModeChildIdKey]). Falls back to the active child only when none is
  /// stored — the habit surface's behaviour before this existed.
  Future<int?> _childModeChildId() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = prefs.getInt(kChildModeChildIdKey);
      if (stored != null) return stored;
    } catch (_) {
      // No preferences: fall back below.
    }
    return onNeedActiveChildId?.call() ?? _auth.readActiveChildId();
  }

  // ── Internals ────────────────────────────────────────────────────────

  /// `?lang=` for the current UI language, or nothing.
  ///
  /// A helper rather than four copies of the same two lines: this exact
  /// omission is why 170 translated lessons sat on disk unread until
  /// 2026-08-13 — the files existed, the parameter did not, and English users
  /// read Arabic for months. Every content read goes through here.
  Map<String, String> _langParam() {
    final lang = uiLanguage;
    return (lang != null && lang.isNotEmpty) ? {'lang': lang} : const {};
  }

  /// Run a request and turn transport failures into TgApiError.
  ///
  /// `streamQuery` has done this since it was written; nothing else has. So
  /// every other method threw raw TimeoutException / SocketException /
  /// ClientException straight past the `on TgApiError` handlers the screens
  /// use — and a screen that catches only TgApiError leaves `_loading = true`
  /// when the wifi drops. Six child-surface screens had that shape, which
  /// turns "no signal" into a spinner with no way out, on a surface a child
  /// is holding.
  ///
  /// Wrapped at this layer rather than in each screen: there is one place to
  /// forget, and it is this one.
  Future<T> _guard<T>(Future<T> Function() send) async {
    try {
      return await send();
    } on TgApiError {
      rethrow;
    } on TimeoutException {
      throw TgApiError(null, AppL10n.current.apiTimeout);
    } on SocketException catch (e) {
      throw TgApiError(null, AppL10n.current.apiConnectionFailed,
          raw: e.message);
    } on http.ClientException catch (e) {
      // Thrown when a connection dies mid-response; not a SocketException.
      throw TgApiError(null, AppL10n.current.apiConnectionFailed,
          raw: e.message);
    }
  }

  Map<String, String> _authHeaders(String token) => {
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
        'Authorization': 'Bearer $token',
      };

  Map<String, String> _childAuthHeaders(String childToken) => {
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
        'Authorization': 'Child-Bearer $childToken',
      };

  TgStreamEvent? _parseFrame(String eventName, String dataText) {
    Object? json;
    try {
      json = jsonDecode(dataText);
    } catch (_) {
      // Malformed data; ignore the frame.
      return null;
    }
    if (json is! Map<String, dynamic>) return null;
    final m = json;

    switch (eventName) {
      case 'token':
        final delta = m['delta'];
        if (delta is String && delta.isNotEmpty) {
          return TgTokenEvent(delta);
        }
        return null;
      case 'done':
        try {
          return TgDoneEvent(AssistantReply.fromJson(m));
        } catch (_) {
          return TgStreamError(AppL10n.current.apiIncompleteResponse);
        }
      case 'error':
        return TgStreamError(
          (m['detail'] as String?) ?? AppL10n.current.apiServerError,
          fromServer: true,
        );
      case 'turn':
        final id = m['message_id'];
        return id is int ? TgTurnEvent(id) : null;
      default:
        return null;
    }
  }

  TgApiError _wrap(http.Response resp) {
    return _wrapStatus(resp.statusCode, utf8.decode(resp.bodyBytes), resp.headers);
  }

  TgApiError _wrapStreamed(int status, Map<String, String> headers) {
    return _wrapStatus(status, '', headers);
  }

  TgApiError _wrapStatus(int status, String body, Map<String, String> headers) {
    String message;
    String? code;
    Map<String, dynamic>? details;
    String? raw;
    try {
      final j = jsonDecode(body);
      if (j is Map && _isProxyProblem(j)) {
        // Cloudflare's own error page, not our server: its `detail` is about
        // Cloudflare's origin, in English, for an engineer.
        message = AppL10n.current.apiHttpError('$status');
        raw = _clip(body);
      } else if (j is Map && j['detail'] is String) {
        message = j['detail'] as String;
      } else if (j is Map && j['detail'] is Map) {
        details = Map<String, dynamic>.from(j['detail'] as Map);
        final error = details['error'];
        if (error is String) {
          // `{"detail": {"error": "<code>", ...}}` — the programs contract.
          // Screens map these codes to their own words (§11.6).
          code = error;
          message = AppL10n.current.apiHttpError('$status');
        } else {
          // `{"detail": {"code": "<code>", "message": "<Arabic to show>",
          // "message_en": ...}}` — §9's branchable errors, e.g. a child
          // deletion refused with `device_proof_required` /
          // `device_proof_cooldown`. The server writes these for the parent;
          // show them rather than "HTTP 403".
          final c = details['code'];
          code = c is String && c.isNotEmpty ? c : null;
          message = _detailMessage(details) ??
              AppL10n.current.apiHttpError('$status');
        }
      } else {
        message = AppL10n.current.apiHttpError('$status');
      }
    } catch (_) {
      // Not JSON: an HTML page from a proxy, or plain text. Never the message.
      message = AppL10n.current.apiHttpError('$status');
      raw = body.isEmpty ? null : _clip(body);
    }

    Duration? retryAfter;
    final ra = headers['retry-after'] ?? headers['Retry-After'];
    if (ra != null) {
      final secs = int.tryParse(ra);
      if (secs != null) retryAfter = Duration(seconds: secs);
    }

    return TgApiError(status, message,
        retryAfter: retryAfter, code: code, details: details, raw: raw);
  }

  /// An RFC 9457 problem page from the proxy in front of us (Cloudflare sends
  /// one to JSON clients for 52x and friends). Our API never sends these keys.
  static bool _isProxyProblem(Map j) =>
      j.containsKey('ray_id') ||
      j.containsKey('cloudflare_error') ||
      (j['type'] is String &&
          (j['type'] as String).contains('cloudflare'));

  static String _clip(String s) =>
      s.length <= 500 ? s : '${s.substring(0, 500)}…';

  /// The detail's message in the app's language. The server writes Arabic in
  /// `message` and, where it has one, English in `message_en`. An English
  /// reader with no `message_en` gets null — the caller's generic line — not
  /// a sentence they cannot read: the memory routes' refusals (§9) are
  /// Arabic-only today.
  static String? _detailMessage(Map<String, dynamic> details) {
    String? pick(String key) {
      final v = details[key];
      return v is String && v.trim().isNotEmpty ? v.trim() : null;
    }

    return uiLanguage == 'en' ? pick('message_en') : pick('message');
  }

  /// Close the underlying HTTP client. Safe to call multiple times.
  void close() {
    if (_ownsHttpClient) _raw.close();
  }
}

/// Replays a request once with a fresh session when the server answers 401
/// to a parent `Bearer` token.
///
/// Tokens expire after a long idle now (audit H5). Only the chat and a few
/// providers knew how to recover from a 401 — every other screen would have
/// shown an error until the app was reinstalled. One place instead: any 401
/// to a parent Bearer means the token was not accepted (soft-protected routes
/// drop a stale token and then refuse the anonymous call), so mint and retry.
///
/// Not replayed: child-mode (`Child-Bearer`) calls, the mint itself, and
/// streamed/multipart bodies that cannot be sent twice.
class _SessionRecoveringClient extends http.BaseClient {
  _SessionRecoveringClient(this._inner, this._recover);

  final http.Client _inner;
  final Future<String?> Function(String rejectedToken) _recover;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final auth = request.headers['Authorization'];
    final isMint = request.method == 'POST' &&
        request.url.path.endsWith('/api/chat/sessions');
    if (auth == null ||
        !auth.startsWith('Bearer ') ||
        isMint ||
        request is! http.Request) {
      return _inner.send(request);
    }
    final replay = http.Request(request.method, request.url)
      ..headers.addAll(request.headers)
      ..bodyBytes = request.bodyBytes
      ..followRedirects = request.followRedirects
      ..maxRedirects = request.maxRedirects
      ..persistentConnection = request.persistentConnection;

    final response = await _inner.send(request);
    if (response.statusCode != 401) return response;

    final fresh = await _recover(auth.substring('Bearer '.length));
    if (fresh == null) return response;
    await response.stream.drain<void>();
    replay.headers['Authorization'] = 'Bearer $fresh';
    return _inner.send(replay);
  }

  @override
  void close() => _inner.close();
}
