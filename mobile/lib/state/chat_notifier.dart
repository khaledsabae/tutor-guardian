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
import '../core/analytics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/tg_client.dart';
import 'package:package_info_plus/package_info_plus.dart';
import '../features/program/providers/progress_providers.dart';
import '../models/api_models.dart';
import '../models/enums.dart';
import 'package:almorabbi/l10n/l10n_global.dart';

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

  /// Server id of the question this answer belongs to (the stream's first
  /// `turn` frame; null on servers older than 2026-10). Recovery matches the
  /// stored answer by this, not by the question's text.
  int? turnId;

  /// The stream died on THIS side (connection cut, stall) — the server may
  /// still have finished the answer. Distinct from [error], which any
  /// failure sets (a rating that failed to save included).
  bool interrupted;

  ChatMessageUI({
    required this.id,
    required this.role,
    required this.content,
    this.reply,
    this.isStreaming = false,
    this.error,
    this.feedback,
    this.turnId,
    this.interrupted = false,
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
      turnId: turnId,
      interrupted: interrupted,
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

/// The app-wide [TgClient] ([TgClient.shared]) for widgets and providers.
/// Tests override this.
///
/// It is the same instance services outside Riverpod use, so it is never
/// closed here: closing it on a container dispose would break every other
/// caller for the rest of the process (audit M12).
final tgClientProvider = Provider<TgClient>((ref) {
  final client = TgClient.shared;
  Future<int?> activeChild() async => ref.read(activeChildIdProvider);
  client.onNeedActiveChildId = activeChild;
  ref.onDispose(() {
    if (client.onNeedActiveChildId == activeChild) {
      client.onNeedActiveChildId = null;
    }
  });
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

  // Token batching (UX-2). Each token used to copy the whole message list and
  // re-parse the entire answer's Markdown — quadratic in the answer length,
  // visible as jank on low-end Android for long replies. Deltas now collect
  // here and land in state at most every [_flushEvery].
  static const Duration _flushEvery = Duration(milliseconds: 60);
  final StringBuffer _pendingDelta = StringBuffer();
  Timer? _flushTimer;

  @override
  void dispose() {
    _flushTimer?.cancel();
    _sub?.cancel();
    super.dispose();
  }

  void _flushPending() {
    _flushTimer?.cancel();
    _flushTimer = null;
    final id = _streamingAssistantId;
    if (_pendingDelta.isEmpty || id == null) {
      _pendingDelta.clear();
      return;
    }
    final delta = _pendingDelta.toString();
    _pendingDelta.clear();
    _updateAssistant(id, (m) => m.content = m.content + delta);
  }

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
        errorBanner: AppL10n.current.chatSessionStartFailed(e.message),
      );
    }
  }

  Future<void> _newSession() async {
    String appVersion;
    try {
      final info = await PackageInfo.fromPlatform();
      appVersion = '${info.version}+${info.buildNumber}';
    } catch (_) {
      appVersion = 'unknown';
    }
    final s = await _client.createSession(
      metadata: {'app_version': 'mobile-$appVersion'},
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
        errorBanner: AppL10n.current.chatNewChatFailed(e.message),
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
        errorBanner: AppL10n.current.chatOfflineRetry,
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
    unawaited(Analytics.chatSent());

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
      _failLastTurn(AppL10n.current.chatUnexpectedError('$e'));
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
          case TgTurnEvent(:final messageId):
            _updateAssistant(assistantId, (m) => m.turnId = messageId);
          case TgTokenEvent(:final delta):
            _pendingDelta.write(delta);
            _flushTimer ??= Timer(_flushEvery, _flushPending);
          case TgDoneEvent(:final reply):
            // The reply text is authoritative; drop any batched remainder.
            _flushTimer?.cancel();
            _flushTimer = null;
            _pendingDelta.clear();
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
          case TgStreamError(:final detail, :final fromServer):
            _flushPending();
            // A connection that died here may have left an answer the server
            // went on to finish; an `error` event from the server did not.
            _failLastTurn(detail,
                assistantId: assistantId, interrupted: !fromServer);
            _finishStream();
            if (!completer.isCompleted) completer.complete();
            if (!fromServer) unawaited(_recoverWithBackoff());
        }
      },
      onError: (Object e) {
        _flushPending();
        _finishStream();
        if (!completer.isCompleted) completer.completeError(e);
      },
      onDone: () {
        _flushPending();
        // Stream closed without a terminal event → connection drop.
        final dropped = state.phase == ChatPhase.streaming;
        if (dropped) {
          _failLastTurn(AppL10n.current.chatConnectionInterrupted,
              assistantId: assistantId, interrupted: true);
        }
        _finishStream();
        if (!completer.isCompleted) completer.complete();
        if (dropped) unawaited(_recoverWithBackoff());
      },
    );

    return completer.future;
  }

  void _finishStream() {
    _flushTimer?.cancel();
    _flushTimer = null;
    _pendingDelta.clear();
    _sub?.cancel();
    _sub = null;
    _streamCompleter = null;
    _streamingAssistantId = null;
  }

  /// Stop the current generation, keeping whatever was streamed so far.
  ///
  /// [notifyServer] (the Stop button) also tells the server to stop: without
  /// it, a closed stream looks like the app going to the background and the
  /// server finishes the answer the parent just rejected. Only sent when the
  /// server has named this turn — the stop then cannot hit a newer one.
  /// Sending a new question needs no stop: the server cuts the old turn itself.
  void stopStreaming({bool notifyServer = false}) {
    // Keep what the reader already received, including the unflushed tail.
    _flushPending();
    final id = _streamingAssistantId;
    final completer = _streamCompleter;
    final sid = state.sessionId;
    final turnId = id == null
        ? null
        : state.messages
            .firstWhere((m) => m.id == id,
                orElse: () => ChatMessageUI(id: '', role: '', content: ''))
            .turnId;
    if (notifyServer && sid != null && turnId != null) {
      unawaited(_client.stopAnswer(sid, messageId: turnId));
    }
    _sub?.cancel();
    _sub = null;
    _streamCompleter = null;
    _streamingAssistantId = null;
    if (id != null) {
      _updateAssistant(id, (m) {
        m
          ..isStreaming = false
          ..content = m.content.isEmpty ? AppL10n.current.chatResponseStopped : m.content
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

  void _failLastTurn(String message,
      {String? assistantId, bool interrupted = false}) {
    final targetId = assistantId ??
        [...state.messages]
            .lastWhere((m) => m.role == 'assistant', orElse: () => state.messages.last)
            .id;
    _updateAssistant(targetId, (m) {
      m
        ..isStreaming = false
        ..interrupted = interrupted
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
          ..error = AppL10n.current.chatRatingSaveFailed(e.message);
      });
    }
  }

  // ── Manual retry (Phase 3 retry button) ────────────────────────────

  Future<void> retryLastTurn() async {
    // The server may have finished the cut answer on its own; generating it
    // again would store a second, different answer to the same question.
    if (await _recoverOnce()) return;
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
        errorBanner: AppL10n.current.chatOpenFailed(e.message),
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
              // An answer still waiting for its first word is not saved: on a
              // cold start it would come back as an empty bubble.
              .where((m) =>
                  !(m.role == 'assistant' && m.isStreaming && m.content.isEmpty))
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

  /// Called by the screen's lifecycle observer when the app goes inactive or
  /// to the background. Saves the conversation — and deliberately leaves a
  /// streaming answer running.
  ///
  /// It used to stop the stream here. `inactive` fires for the notification
  /// shade, a system dialog, the app switcher and a screen lock, so a parent
  /// who glanced at WhatsApp while waiting came back to a few words and
  /// «تم الإيقاف»: 23 of 290 questions in September 2026 ended that way,
  /// most 2–10 seconds into the answer. The stream now keeps going; if the
  /// OS cuts the connection anyway, [onAppResumed] fetches the answer the
  /// server finished on its own.
  void onAppPaused() {
    unawaited(_persistLocal());
  }

  /// Called by the screen's lifecycle observer when the app is back.
  void onAppResumed() {
    unawaited(_recoverWithBackoff());
  }

  bool _recovering = false;

  /// Keep looking for the answer of a cut turn for about a minute: the
  /// server finishes it in the background, which can take a while. One loop
  /// at a time — resume and the stream's own error both start one.
  Future<bool> _recoverWithBackoff() async {
    if (_recovering) return false;
    _recovering = true;
    try {
      return await recoverInterruptedAnswer();
    } finally {
      _recovering = false;
    }
  }

  /// Restore an answer whose stream died on this side.
  ///
  /// Servers since 2026-10 finish an answer after its reader leaves and store
  /// it in place, so the finished text is fetched from the session history,
  /// retried with a growing delay (2, 4, 8, 16, 30 s by default) while it is
  /// being written. The stored answer is found by turn identity: the id the
  /// server gave the question. Without one (an older server), only the
  /// server's LAST question is considered, and only if its answer begins
  /// with what this side already showed. An older server never stored the
  /// answer — it finds nothing usable and the turn keeps its Retry.
  /// Returns true when the turn was restored.
  Future<bool> recoverInterruptedAnswer({
    int attempts = 6,
    Duration retryDelay = const Duration(seconds: 2),
  }) async {
    var delay = retryDelay;
    for (var attempt = 0; attempt < attempts; attempt++) {
      if (attempt > 0) {
        await Future<void>.delayed(delay);
        final next = delay * 2;
        delay = next > const Duration(seconds: 30) ? const Duration(seconds: 30) : next;
      }
      if (!mounted || _interruptedTurn() == null) return false;
      if (await _recoverOnce()) return true;
    }
    return false;
  }

  /// One look at the server for the cut turn's answer.
  Future<bool> _recoverOnce() async {
    if (!mounted) return false;
    final turn = _interruptedTurn();
    final sid = state.sessionId;
    if (turn == null || sid == null) return false;
    final SessionHistory history;
    try {
      history = await _client.getHistory(sid);
    } catch (_) {
      return false; // offline right after resuming — the loop tries again
    }
    if (!mounted) return false;
    final answer = _serverAnswerFor(history.messages, turn);
    // The parent may have retried or asked again while we were fetching.
    final now = _interruptedTurn();
    if (answer == null || now == null || now.assistantId != turn.assistantId) {
      return false;
    }
    _updateAssistant(turn.assistantId, (m) {
      m
        ..content = answer.content
        ..isStreaming = false
        ..interrupted = false
        ..error = null;
    });
    state = state.copyWith(
      phase: ChatPhase.idle,
      turnCount: state.turnCount + 1,
      clearBanner: true,
    );
    unawaited(_persistLocal());
    return true;
  }

  /// The last question and its assistant bubble, when that answer was cut on
  /// this side. Null while a stream is live, for an answer the parent
  /// stopped, and for any other kind of error (a rating that failed to save
  /// is not a lost answer).
  ({String question, String assistantId, int? turnId, String partial})?
      _interruptedTurn() {
    if (state.phase == ChatPhase.streaming || state.phase == ChatPhase.waiting) {
      return null;
    }
    final msgs = state.messages;
    final u = msgs.lastIndexWhere((m) => m.role == 'user');
    if (u < 0 || u + 1 >= msgs.length) return null;
    final reply = msgs[u + 1];
    if (reply.role != 'assistant' || reply.isStreaming || !reply.interrupted) {
      return null;
    }
    return (
      question: msgs[u].content,
      assistantId: reply.id,
      turnId: reply.turnId,
      partial: reply.content,
    );
  }

  /// The server's stored answer to [turn], or null.
  ChatMessage? _serverAnswerFor(
    List<ChatMessage> server,
    ({String question, String assistantId, int? turnId, String partial}) turn,
  ) {
    int q;
    if (turn.turnId != null && server.any((m) => m.id != null)) {
      q = server.indexWhere((m) => m.role == 'user' && m.id == turn.turnId);
    } else {
      // No turn id: only the server's LAST question can be this one.
      q = server.lastIndexWhere((m) => m.role == 'user');
      if (q < 0 || server[q].content.trim() != turn.question.trim()) return null;
    }
    if (q < 0) return null;
    ChatMessage? answer;
    for (var i = q + 1; i < server.length; i++) {
      final m = server[i];
      if (m.role == 'user') break; // the next turn — not ours
      if (m.role == 'assistant') {
        answer = m;
        break;
      }
    }
    if (answer == null || answer.content.trim().isEmpty) return null;
    if (answer.modeWire == 'error' || answer.modeWire == 'interrupted') return null;
    if (turn.turnId == null) {
      // Same text is not proof of the same turn: the answer must continue
      // what this side already showed.
      String squash(String s) => s.replaceAll(RegExp(r'\s+'), '');
      if (!squash(answer.content).startsWith(squash(turn.partial))) return null;
    }
    return answer;
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
