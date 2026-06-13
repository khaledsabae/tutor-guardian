/// Riverpod state holder for the chat screen.
///
/// Owns:
///   * The list of in-memory [ChatMessageUI] bubbles (user + assistant).
///   * The currently selected [AgeGroup] / [Severity] / behavior_type text.
///   * The streaming state (`idle` / `waiting` / `streaming` / `error`).
///
/// All network calls go through [TgClient]. The notifier is responsible for
/// transparent session recovery (401/404 → re-create then retry once) and
/// for replacing accumulated token deltas with the authoritative
/// `done.reply_text` when the SSE stream terminates.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/tg_client.dart';
import '../models/api_models.dart';
import '../models/enums.dart';

/// Single bubble rendered by `MessageBubble`.
class ChatMessageUI {
  /// Local id — useful for keys / list diffing.
  final String id;

  /// "user" or "assistant".
  final String role;

  /// The text shown in the bubble. For assistant messages this is updated
  /// token-by-token during streaming and replaced with the authoritative
  /// `reply_text` when the server emits `event: done`.
  ///
  /// Marked non-final because we mutate it in place during streaming
  /// (the in-place mutation lets us avoid rebuilding the list on every
  /// token — copyWith + spread on every delta would be expensive).
  String content;

  /// The final `AssistantReply` (null while streaming or for user messages).
  AssistantReply? reply;

  /// True while tokens are still arriving.
  bool isStreaming;

  /// Per-message error to show inline (network failure mid-stream, etc.).
  String? error;

  /// Whether the user has voted on this assistant turn (for the 👍/👎 UI).
  String? feedback; // "up" | "down" | null

  ChatMessageUI({
    required this.id,
    required this.role,
    required this.content,
    this.reply,
    this.isStreaming = false,
    this.error,
    this.feedback,
  });

  ChatMessageUI copyWith({
    String? content,
    AssistantReply? reply,
    bool? isStreaming,
    String? error,
    String? feedback,
    bool clearError = false,
    bool clearFeedback = false,
  }) {
    return ChatMessageUI(
      id: id,
      role: role,
      content: content ?? this.content,
      reply: reply ?? this.reply,
      isStreaming: isStreaming ?? this.isStreaming,
      error: clearError ? null : (error ?? this.error),
      feedback: clearFeedback ? null : (feedback ?? this.feedback),
    );
  }
}

enum ChatPhase { idle, waiting, streaming, error }

@immutable
class ChatState {
  final List<ChatMessageUI> messages;
  final AgeGroup ageGroup;
  final Severity severity;
  final String behaviorType;
  final ChatPhase phase;
  final String? sessionId;
  final int turnCount;
  final String? errorBanner;

  const ChatState({
    this.messages = const [],
    this.ageGroup = AgeGroup.defaultValue,
    this.severity = Severity.defaultValue,
    this.behaviorType = '',
    this.phase = ChatPhase.idle,
    this.sessionId,
    this.turnCount = 0,
    this.errorBanner,
  });

  ChatState copyWith({
    List<ChatMessageUI>? messages,
    AgeGroup? ageGroup,
    Severity? severity,
    String? behaviorType,
    ChatPhase? phase,
    String? sessionId,
    int? turnCount,
    String? errorBanner,
    bool clearBanner = false,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      ageGroup: ageGroup ?? this.ageGroup,
      severity: severity ?? this.severity,
      behaviorType: behaviorType ?? this.behaviorType,
      phase: phase ?? this.phase,
      sessionId: sessionId ?? this.sessionId,
      turnCount: turnCount ?? this.turnCount,
      errorBanner: clearBanner ? null : (errorBanner ?? this.errorBanner),
    );
  }
}

/// Provider for the singleton [TgClient]. Tests can override this.
final tgClientProvider = Provider<TgClient>((ref) {
  final client = TgClient();
  ref.onDispose(client.close);
  return client;
});

/// Main chat state notifier.
class ChatNotifier extends StateNotifier<ChatState> {
  ChatNotifier(this._client) : super(const ChatState());

  final TgClient _client;
  int _localId = 0;

  // Active stream handle — lets the user stop/interrupt generation.
  StreamSubscription<TgStreamEvent>? _sub;
  Completer<void>? _streamCompleter;
  String? _streamingAssistantId;

  static const _kSnapshotKey = 'tg.chat_snapshot';

  String _nextId() => 'm${++_localId}';

  // ── Settings (Phase 3 settings bar) ──────────────────────────────────

  void setAgeGroup(AgeGroup g) =>
      state = state.copyWith(ageGroup: g);

  void setSeverity(Severity s) =>
      state = state.copyWith(severity: s);

  void setBehaviorType(String t) =>
      state = state.copyWith(behaviorType: t);

  // ── Session lifecycle (Phase 4) ──────────────────────────────────────

  /// Initialise: try to resume an existing session, otherwise create one.
  /// Called once on app start (Phase 4 wires this to the bootstrap).
  Future<void> bootstrap() async {
    try {
      final existing = await _client.currentSessionId();
      if (existing != null) {
        state = state.copyWith(sessionId: existing);
        // Best-effort: rehydrate history. If 404, the client already
        // cleared the local copy and we fall back to a new session.
        try {
          final hist = await _client.getHistory(existing);
          var msgs = hist.messages
              .map((m) => ChatMessageUI(
                    id: _nextId(),
                    role: m.role,
                    content: m.content,
                  ))
              .toList();
          // Prefer the local snapshot when it carries more (e.g. a partial
          // answer the user left mid-stream that the server never stored).
          final local = await _loadLocal(existing);
          if (local != null && local.length > msgs.length) {
            msgs = local;
          }
          state = state.copyWith(
            messages: msgs,
            turnCount: msgs.where((m) => m.role == 'user').length,
          );
          return;
        } on TgApiError {
          // fall through to a new session
        }
      }
      await _newSession();
    } on TgApiError catch (e) {
      state = state.copyWith(
        phase: ChatPhase.error,
        errorBanner: 'تعذّر بدء جلسة: ${e.message}',
      );
    }
  }

  Future<void> _newSession() async {
    final s = await _client.createSession(
      metadata: {'app_version': 'mobile-1.0.0'},
    );
    state = state.copyWith(
      sessionId: s.sessionId,
      messages: const [],
      turnCount: 0,
      clearBanner: true,
      phase: ChatPhase.idle,
    );
  }

  /// User-tapped "Start a new conversation" button.
  Future<void> startNewConversation() async {
    await _client.endSession();
    try {
      await _newSession();
    } on TgApiError catch (e) {
      state = state.copyWith(
        phase: ChatPhase.error,
        errorBanner: 'تعذّر بدء محادثة جديدة: ${e.message}',
      );
    }
  }

  // ── Sending a turn ──────────────────────────────────────────────────

  /// Returns true if the device is currently online. The chat screen
  /// uses this to short-circuit `sendMessage` and surface a friendlier
  /// "غير متصل" banner instead of letting the HTTP layer fail.
  bool isOnline() {
    // We can't await a stream from inside the notifier synchronously,
    // so callers pass the latest value in via [setOnline]. If no value
    // has been seeded yet, default to true (the user just opened the
    // app — let the request try).
    return _isOnline ?? true;
  }

  bool? _isOnline;
  void setOnline(bool value) {
    _isOnline = value;
  }

  /// Append the user's message and kick off streaming.
  Future<void> sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;
    // If a turn is still streaming, interrupt it (keeping the partial)
    // so the user can ask a new question without waiting.
    if (state.phase == ChatPhase.streaming) {
      stopStreaming();
    } else if (state.phase == ChatPhase.waiting) {
      return; // a request is in flight but not yet streaming — let it land
    }

    // Short-circuit if the device is offline — better UX than waiting
    // for a TCP timeout. (Phase 5: offline handling.)
    if (!isOnline()) {
      state = state.copyWith(
        phase: ChatPhase.error,
        errorBanner: 'غير متصل بالإنترنت. تحقّق من الاتصال وأعد المحاولة.',
      );
      return;
    }

    // Append user bubble immediately.
    final userMsg = ChatMessageUI(
      id: _nextId(),
      role: 'user',
      content: trimmed,
    );
    final placeholder = ChatMessageUI(
      id: _nextId(),
      role: 'assistant',
      content: '',
      isStreaming: true,
    );
    state = state.copyWith(
      messages: [...state.messages, userMsg, placeholder],
      phase: ChatPhase.streaming,
      clearBanner: true,
    );

    // Ensure we have a session (may have expired).
    String? sid = state.sessionId;
    if (sid == null) {
      try {
        final s = await _client.ensureSession();
        sid = s.sessionId;
        state = state.copyWith(sessionId: s.sessionId);
      } on TgApiError catch (e) {
        _failLastTurn(e.message);
        return;
      }
    }

    final query = AssistantQuery(
      ageGroup: state.ageGroup,
      severity: state.severity,
      behaviorType: state.behaviorType.isEmpty ? null : state.behaviorType,
      messageText: trimmed,
      sessionId: sid,
    );

    try {
      await _stream(query, placeholder.id);
    } on TgApiError catch (e) {
      // 401/404 → drop session, create a new one, retry exactly once.
      if (e.statusCode == 401 || e.statusCode == 404) {
        await _client.endSession();
        try {
          final s = await _client.createSession();
          state = state.copyWith(sessionId: s.sessionId);
          final retry = AssistantQuery(
            ageGroup: query.ageGroup,
            severity: query.severity,
            behaviorType: query.behaviorType,
            messageText: query.messageText,
            sessionId: s.sessionId,
          );
          await _stream(retry, placeholder.id);
          return;
        } on TgApiError catch (inner) {
          _failLastTurn(inner.message);
          return;
        }
      }
      _failLastTurn(e.message);
    } catch (e) {
      _failLastTurn('خطأ غير متوقع: $e');
    }
  }

  Future<void> _stream(AssistantQuery query, String assistantId) async {
    // Listen explicitly (instead of `await for`) so the user can cancel
    // mid-stream via [stopStreaming]. The returned future resolves when
    // the stream terminates OR is stopped, and rethrows TgApiError so the
    // 401/404 retry path in sendMessage still works.
    final completer = Completer<void>();
    _streamCompleter = completer;
    _streamingAssistantId = assistantId;

    _sub = _client.streamQuery(query).listen(
      (ev) {
        switch (ev) {
          case TgTokenEvent(:final delta):
            _updateAssistant(assistantId, (m) {
              m.content = m.content + delta;
            });
          case TgDoneEvent(:final reply):
            _updateAssistant(assistantId, (m) {
              m
                ..content = reply.replyText
                ..reply = reply
                ..isStreaming = false
                ..error = null;
            });
            state = state.copyWith(
              phase: ChatPhase.idle,
              turnCount: state.turnCount + 1,
            );
            _finishStream();
            unawaited(_persistLocal());
            if (!completer.isCompleted) completer.complete();
          case TgStreamError(:final detail):
            _failLastTurn(detail, assistantId: assistantId);
            _finishStream();
            if (!completer.isCompleted) completer.complete();
        }
      },
      onError: (Object e) {
        _finishStream();
        if (!completer.isCompleted) completer.completeError(e);
      },
      onDone: () {
        // Stream closed without a terminal event → connection drop.
        if (state.phase == ChatPhase.streaming) {
          _failLastTurn('انقطع الاتصال قبل اكتمال الرد.',
              assistantId: assistantId);
        }
        _finishStream();
        if (!completer.isCompleted) completer.complete();
      },
    );

    return completer.future;
  }

  void _finishStream() {
    _sub?.cancel();
    _sub = null;
    _streamCompleter = null;
    _streamingAssistantId = null;
  }

  /// Stop the current generation, keeping whatever was streamed so far.
  void stopStreaming() {
    final id = _streamingAssistantId;
    final completer = _streamCompleter;
    _sub?.cancel();
    _sub = null;
    _streamCompleter = null;
    _streamingAssistantId = null;
    if (id != null) {
      _updateAssistant(id, (m) {
        m
          ..isStreaming = false
          ..content = m.content.isEmpty ? '⏹️ تم إيقاف الرد.' : m.content
          ..error = null;
      });
    }
    state = state.copyWith(phase: ChatPhase.idle);
    unawaited(_persistLocal());
    // Unblock sendMessage's awaiting future without throwing.
    if (completer != null && !completer.isCompleted) completer.complete();
  }

  void _updateAssistant(
    String id,
    void Function(ChatMessageUI m) mutate,
  ) {
    final msgs = [...state.messages];
    final idx = msgs.indexWhere((m) => m.id == id);
    if (idx < 0) return;
    final updated = msgs[idx].copyWith();
    mutate(updated);
    msgs[idx] = updated;
    state = state.copyWith(messages: msgs);
  }

  void _failLastTurn(String message, {String? assistantId}) {
    final targetId = assistantId ??
        [...state.messages]
            .lastWhere((m) => m.role == 'assistant', orElse: () => state.messages.last)
            .id;
    _updateAssistant(targetId, (m) {
      m
        ..isStreaming = false
        ..error = message;
    });
    state = state.copyWith(phase: ChatPhase.error, errorBanner: message);
  }

  // ── Feedback (Phase 3 thumbs up/down) ───────────────────────────────

  Future<void> submitFeedback(String assistantId, String rating) async {
    // Update UI immediately for snappy feedback.
    _updateAssistant(assistantId, (m) => m.feedback = rating);
    try {
      await _client.sendFeedback(
        rating: rating,
        sessionId: state.sessionId,
      );
    } on TgApiError catch (e) {
      // Roll back the UI and show a banner.
      _updateAssistant(assistantId, (m) {
        m
          ..feedback = null
          ..error = 'تعذّر حفظ التقييم: ${e.message}';
      });
    }
  }

  // ── Manual retry (Phase 3 retry button) ────────────────────────────

  Future<void> retryLastTurn() async {
    final lastUserIdx = state.messages
        .lastIndexWhere((m) => m.role == 'user' && m.error == null);
    if (lastUserIdx < 0) return;
    final text = state.messages[lastUserIdx].content;
    // Drop the failed assistant turn, if any.
    final truncated = state.messages.sublist(0, lastUserIdx + 1);
    state = state.copyWith(messages: truncated);
    await sendMessage(text);
  }

  // ── History drawer ───────────────────────────────────────────────────

  /// The device's past conversations for the history drawer.
  Future<List<ChatSessionSummary>> loadSessionList() async {
    try {
      return await _client.listSessions();
    } catch (_) {
      return const [];
    }
  }

  /// Open a past conversation in place of the current one.
  Future<void> switchToSession(String sessionId) async {
    if (sessionId == state.sessionId) return;
    if (state.phase == ChatPhase.streaming) stopStreaming();
    state = state.copyWith(
      sessionId: sessionId,
      messages: const [],
      phase: ChatPhase.idle,
      clearBanner: true,
    );
    try {
      final hist = await _client.getHistory(sessionId);
      final msgs = hist.messages
          .map((m) => ChatMessageUI(
                id: _nextId(),
                role: m.role,
                content: m.content,
              ))
          .toList();
      state = state.copyWith(
        messages: msgs,
        turnCount: msgs.where((m) => m.role == 'user').length,
      );
      await _persistLocal();
    } on TgApiError catch (e) {
      state = state.copyWith(
        phase: ChatPhase.error,
        errorBanner: 'تعذّر فتح المحادثة: ${e.message}',
      );
    }
  }

  // ── Local snapshot (survives backgrounding / kill mid-answer) ─────────

  /// Write the current conversation to disk. The server only persists an
  /// assistant turn on `done`, so a partial answer would otherwise be lost
  /// when the user leaves the app mid-generation.
  Future<void> _persistLocal() async {
    final sid = state.sessionId;
    if (sid == null) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        _kSnapshotKey,
        jsonEncode({
          'session_id': sid,
          'messages': state.messages
              .map((m) => {
                    'role': m.role,
                    'content': m.content,
                    'feedback': m.feedback,
                  })
              .toList(),
        }),
      );
    } catch (_) {
      // best-effort — never block the UI on persistence
    }
  }

  /// Called by the screen's lifecycle observer when the app is paused.
  /// Finalizes any in-flight stream and saves the conversation.
  void onAppPaused() {
    if (state.phase == ChatPhase.streaming) {
      stopStreaming(); // keeps the partial answer, persists it
    } else {
      unawaited(_persistLocal());
    }
  }

  Future<List<ChatMessageUI>?> _loadLocal(String sid) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_kSnapshotKey);
      if (raw == null) return null;
      final data = jsonDecode(raw) as Map<String, dynamic>;
      if (data['session_id'] != sid) return null;
      return (data['messages'] as List)
          .map((m) => ChatMessageUI(
                id: _nextId(),
                role: m['role'] as String,
                content: m['content'] as String,
                feedback: m['feedback'] as String?,
              ))
          .toList();
    } catch (_) {
      return null;
    }
  }
}
