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

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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

  /// Append the user's message and kick off streaming.
  Future<void> sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;
    if (state.phase == ChatPhase.waiting ||
        state.phase == ChatPhase.streaming) {
      return; // ignore taps while a turn is in flight
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
    final events = _client.streamQuery(query);
    await for (final ev in events) {
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
          return;
        case TgStreamError(:final detail):
          _failLastTurn(detail, assistantId: assistantId);
          return;
      }
    }
    // Stream ended without a terminal event: treat as stream error.
    if (state.phase == ChatPhase.streaming) {
      _failLastTurn('انقطع الاتصال قبل اكتمال الرد.', assistantId: assistantId);
    }
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
}
