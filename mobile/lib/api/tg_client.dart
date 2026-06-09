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
import 'package:uuid/uuid.dart';

import '../config/app_config.dart';
import '../models/api_models.dart';

/// Raised for any non-recoverable HTTP failure the UI should display.
class TgApiError implements Exception {
  final int? statusCode;
  final String message;
  final Duration? retryAfter;

  const TgApiError(this.statusCode, this.message, {this.retryAfter});

  @override
  String toString() => 'TgApiError(${statusCode ?? '?'}): $message';
}

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
  const TgStreamError(this.detail);
}

/// Single source of truth for the device id, session id, and bearer token.
/// Persisted in `flutter_secure_storage` (Android Keystore).
class _AuthStore {
  _AuthStore(this._storage);

  static const _kDeviceId = 'tg_device_id';
  static const _kSessionId = 'tg_session_id';
  static const _kToken = 'tg_token';

  final FlutterSecureStorage _storage;
  final Uuid _uuid = const Uuid();

  String? _cachedDeviceId;
  String? _cachedSessionId;
  String? _cachedToken;

  Future<String> getOrCreateDeviceId() async {
    if (_cachedDeviceId != null) return _cachedDeviceId!;
    final existing = await _storage.read(key: _kDeviceId);
    if (existing != null && existing.isNotEmpty) {
      _cachedDeviceId = existing;
      return existing;
    }
    final fresh = _uuid.v4();
    await _storage.write(key: _kDeviceId, value: fresh);
    _cachedDeviceId = fresh;
    return fresh;
  }

  Future<void> setSession({required String sessionId, required String token}) async {
    _cachedSessionId = sessionId;
    _cachedToken = token;
    await _storage.write(key: _kSessionId, value: sessionId);
    await _storage.write(key: _kToken, value: token);
  }

  Future<(String?, String?)> readSession() async {
    if (_cachedSessionId != null && _cachedToken != null) {
      return (_cachedSessionId!, _cachedToken!);
    }
    final sid = await _storage.read(key: _kSessionId);
    final tok = await _storage.read(key: _kToken);
    _cachedSessionId = sid;
    _cachedToken = tok;
    return (sid, tok);
  }

  Future<void> clearSession() async {
    _cachedSessionId = null;
    _cachedToken = null;
    await _storage.delete(key: _kSessionId);
    await _storage.delete(key: _kToken);
  }
}

/// The Tutor Guardian API client.
class TgClient {
  TgClient({http.Client? httpClient, FlutterSecureStorage? storage})
      : _http = httpClient ?? http.Client(),
        _auth = _AuthStore(storage ?? const FlutterSecureStorage()),
        _ownsHttpClient = httpClient == null,
        _baseUrlOverride = null;

  /// Test-only constructor that bypasses [AppConfig.apiBaseUrl].
  @visibleForTesting
  TgClient.forTesting({
    required String baseUrl,
    http.Client? httpClient,
    FlutterSecureStorage? storage,
  })  : _http = httpClient ?? http.Client(),
        _auth = _AuthStore(storage ?? const FlutterSecureStorage()),
        _ownsHttpClient = httpClient == null,
        _baseUrlOverride = baseUrl;

  final http.Client _http;
  final _AuthStore _auth;
  final bool _ownsHttpClient;
  final String? _baseUrlOverride;

  String get _baseUrl => _baseUrlOverride ?? AppConfig.apiBaseUrl;

  // ── Public surface ────────────────────────────────────────────────────

  /// Create a new session (server returns a fresh `session_id` + bearer
  /// token). The token is persisted for the lifetime of the install.
  Future<SessionResponse> createSession({
    Map<String, dynamic>? metadata,
  }) async {
    final deviceId = await _auth.getOrCreateDeviceId();
    final body = <String, dynamic>{
      'device_id': deviceId,
      if (metadata != null) 'metadata': metadata,
    };

    final resp = await _http
        .post(
          Uri.parse('$_baseUrl/api/chat/sessions'),
          headers: {'Content-Type': 'application/json; charset=utf-8'},
          body: jsonEncode(body),
        )
        .timeout(AppConfig.httpTimeout);

    if (resp.statusCode != 201) {
      throw _wrapStreamed(resp.statusCode, const {});
    }

    final parsed =
        SessionResponse.fromJson(jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>);
    await _auth.setSession(sessionId: parsed.sessionId, token: parsed.token);
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
      throw const TgApiError(401, 'لا توجد جلسة نشطة. أنشئ جلسة أولاً.');
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
      throw const TgApiError(null, 'انتهت مهلة الاتصال بالخادم.');
    } on SocketException catch (e) {
      throw TgApiError(null, 'تعذّر الاتصال بالخادم: ${e.message}');
    }

    if (response.statusCode != 200) {
      throw _wrapStreamed(response.statusCode, response.headers);
    }

    // Parse SSE byte-by-byte. Frame = `event: <name>\ndata: <json>\n\n`.
    String currentEvent = 'message';
    final dataBuffer = StringBuffer();

    final lineStream = response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter());

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
      throw const TgApiError(401, 'لا توجد جلسة نشطة. أنشئ جلسة أولاً.');
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
  Future<SessionHistory> getHistory(String sessionId) async {
    final (sid, tok) = await _auth.readSession();
    if (tok == null) {
      throw const TgApiError(401, 'لا توجد جلسة نشطة.');
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
      throw const TgApiError(404, 'الجلسة غير موجودة على الخادم.');
    }
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return SessionHistory.fromJson(
      jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>,
    );
  }

  /// Submit 👍/👎 for the current turn.
  Future<void> sendFeedback({
    required String rating, // "up" | "down"
    String? comment,
    String? sessionId,
  }) async {
    final (sid, tok) = await _auth.readSession();
    if (tok == null) {
      throw const TgApiError(401, 'لا توجد جلسة نشطة.');
    }
    final body = <String, dynamic>{
      'rating': rating,
      if (comment != null && comment.isNotEmpty) 'comment': comment,
      if (sessionId != null) 'session_id': sessionId,
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
      throw const TgApiError(401, 'انتهت صلاحية الجلسة.');
    }
    if (resp.statusCode != 201) {
      throw _wrapStreamed(resp.statusCode, const {});
    }
  }

  // ── Lifecycle helpers used by the chat notifier ──────────────────────

  /// Returns a (sessionId, token) pair, creating a session if none exists.
  Future<SessionResponse> ensureSession() async {
    final (sid, tok) = await _auth.readSession();
    if (sid != null && tok != null) {
      return SessionResponse(sessionId: sid, token: tok);
    }
    return createSession();
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
  //   GET /api/program/daily-tip?age_group=&time_of_day=
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
    final qs = includeLessons ? {'include': 'lessons'} : const <String, String>{};
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
    final uri = Uri.parse('$_baseUrl/api/program/lessons/$lessonId');
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getLessonAssets(String lessonId) async {
    final uri = Uri.parse('$_baseUrl/api/program/lesson-assets/$lessonId');
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getDailyTip({
    required String ageGroup,
    String? timeOfDay,
  }) async {
    final qs = <String, String>{'age_group': ageGroup};
    if (timeOfDay != null && timeOfDay.isNotEmpty) qs['time_of_day'] = timeOfDay;
    final uri = Uri.parse(
      '$_baseUrl/api/program/daily-tip',
    ).replace(queryParameters: qs);
    final resp = await _http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  // ── Children + progress (Phase 5) ──────────────────────────────────────
  //
  // All three require a Bearer token (set by [_AuthHeaders] on the
  // POST/PATCH, the GET is also auth-protected). The token is
  // pulled from `_auth.readSession()` exactly like the chat endpoints.

  Future<SessionResponse> _ensureSessionForProgress() async {
    return ensureSession();
  }

  Future<Map<String, dynamic>> createChild({
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
  }) async {
    final (_, token) = await _auth.readSession();
    if (token == null) {
      throw const TgApiError(401, 'مطلوب جلسة لإنشاء ملف طفل.');
    }
    final body = <String, dynamic>{
      'name': name,
      'age_group': ageGroup,
      if (gender != null) 'gender': gender,
      if (avatarEmoji != null) 'avatar_emoji': avatarEmoji,
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
    final (_, token) = await _auth.readSession();
    if (token == null) {
      throw const TgApiError(401, 'مطلوب جلسة لقراءة التقدّم.');
    }
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
  }) async {
    final (_, token) = await _auth.readSession();
    if (token == null) {
      throw const TgApiError(401, 'مطلوب جلسة لتسجيل التقدّم.');
    }
    final resp = await _http
        .patch(
          Uri.parse('$_baseUrl/api/program/lessons/$lessonId/progress'),
          headers: _authHeaders(token),
          body: jsonEncode({'status': status}),
        )
        .timeout(AppConfig.httpTimeout);
    if (resp.statusCode != 200) {
      throw _wrap(resp);
    }
    return jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  }

  // ── Phase 7 — list / update / reset ───────────────────────────────────

  Future<Map<String, dynamic>> listChildren() async {
    final (_, token) = await _auth.readSession();
    if (token == null) {
      throw const TgApiError(401, 'مطلوب جلسة لعرض الأطفال.');
    }
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
  }) async {
    final (_, token) = await _auth.readSession();
    if (token == null) {
      throw const TgApiError(401, 'مطلوب جلسة لتعديل ملف الطفل.');
    }
    final body = <String, dynamic>{};
    if (name != null) body['name'] = name;
    if (ageGroup != null) body['age_group'] = ageGroup;
    if (gender != null) body['gender'] = gender;
    if (avatarEmoji != null) body['avatar_emoji'] = avatarEmoji;
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

  Future<Map<String, dynamic>> resetChildProgress(int childId) async {
    final (_, token) = await _auth.readSession();
    if (token == null) {
      throw const TgApiError(401, 'مطلوب جلسة لإعادة التعيين.');
    }
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
  }

  // ── Internals ────────────────────────────────────────────────────────

  Map<String, String> _authHeaders(String token) => {
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
        'Authorization': 'Bearer $token',
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
          return const TgStreamError('استجابة الخادم غير مكتملة.');
        }
      case 'error':
        return TgStreamError(
          (m['detail'] ?? 'حدث خطأ في الخادم.') as String,
        );
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
    try {
      final j = jsonDecode(body);
      if (j is Map && j['detail'] is String) {
        message = j['detail'] as String;
      } else {
        message = 'خطأ HTTP $status';
      }
    } catch (_) {
      message = body.isEmpty ? 'خطأ HTTP $status' : body;
    }

    Duration? retryAfter;
    final ra = headers['retry-after'] ?? headers['Retry-After'];
    if (ra != null) {
      final secs = int.tryParse(ra);
      if (secs != null) retryAfter = Duration(seconds: secs);
    }

    return TgApiError(status, message, retryAfter: retryAfter);
  }

  /// Close the underlying HTTP client. Safe to call multiple times.
  void close() {
    if (_ownsHttpClient) _http.close();
  }
}
