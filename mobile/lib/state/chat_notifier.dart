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
import '../core/failures.dart';

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
  ChatNotifier(
    this._client, {
    this.recoveryDelay = const Duration(seconds: 2),
    this.recoveryDeadline = answerDeadline,
    this.activeChildId,
  }) : super(const ChatState());

  final TgClient _client;
  int _localId = 0;

  /// The child the parent is asking about right now — read at send time so a
  /// switch of child between two questions is honoured. Sent as `child_id`
  /// (MOBILE_API §9.1): the server's only reliable way to know which child's
  /// memory an answer may use and learn from.
  final int? Function()? activeChildId;

  /// The longest the server may still be writing an answer after its reader
  /// left: its per-answer deadline (LLM_STREAM_DEADLINE_S, 300 s) plus the
  /// classification and retrieval before the first token.
  static const Duration answerDeadline = Duration(seconds: 330);

  /// The longest gap between two looks while an answer is being written.
  static const Duration maxRecoveryGap = Duration(seconds: 30);

  /// First gap of the recovery back-off; it doubles up to [maxRecoveryGap].
  final Duration recoveryDelay;

  /// How long recovery keeps looking for an answer that may still come.
  final Duration recoveryDeadline;

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
    _closeStopping();
    _wakeRecovery();
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
          var msgs = _bubblesFrom(hist.messages);
          // Prefer the local snapshot when it carries more (e.g. a partial
          // answer the user left mid-stream that the server never stored).
          final local = await _loadLocal(existing);
          if (local != null && local.length > hist.messages.length) {
            msgs = local;
          }
          state = state.copyWith(
            messages: msgs,
            turnCount: msgs.where((m) => m.role == 'user').length,
          );
          // The app was killed (or the OS dropped it) mid-answer: the server
          // may still be writing it.
          if (_interruptedTurn() != null) {
            _cutAt ??= DateTime.now();
            unawaited(_recoverWithBackoff());
          }
          return;
        } on TgApiError {
          // fall through to a new session
        }
      }
      await _newSession();
    } on TgApiError catch (e) {
      state = state.copyWith(
        phase: ChatPhase.error,
        errorBanner: AppL10n.current.chatSessionStartFailed(
            describeFailure(AppL10n.current, e)),
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
        errorBanner: AppL10n.current.chatNewChatFailed(
            describeFailure(AppL10n.current, e)),
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
        _failLastTurn(describeFailure(AppL10n.current, e));
        return;
      }
    }

    final query = AssistantQuery(
      ageGroup: state.ageGroup,
      severity: state.severity,
      behaviorType: state.behaviorType.isEmpty ? null : state.behaviorType,
      messageText: trimmed,
      sessionId: sid,
      childId: activeChildId?.call(),
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
            childId: query.childId,
          );
          await _stream(retry, placeholder.id);
          return;
        } on TgApiError catch (inner) {
          _failLastTurn(describeFailure(AppL10n.current, inner));
          return;
        }
      }
      _failLastTurn(describeFailure(AppL10n.current, e));
    } catch (e) {
      _failLastTurn(describeFailure(AppL10n.current, e));
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
  /// server finishes the answer the parent just rejected. The stop names the
  /// turn — it cannot hit a newer one — so before the server has named it,
  /// the stream is kept open, unseen, until it does (see [_stopWhenNamed]).
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
    final sub = _sub;
    _sub = null;
    if (notifyServer && sid != null && turnId == null && sub != null) {
      _stopWhenNamed(sub, sid);
    } else {
      if (notifyServer && sid != null && turnId != null) {
        unawaited(_client.stopAnswer(sid, messageId: turnId));
      }
      sub?.cancel();
    }
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

  /// How long a Stop pressed before the turn was named keeps waiting for it.
  static const Duration _stopNameWait = Duration(seconds: 15);
  StreamSubscription<TgStreamEvent>? _stopping;
  Timer? _stoppingTimer;

  /// Stop pressed before the stream's `turn` frame named the question (T2).
  /// The server could not be told which turn to stop, and a closed stream
  /// looks like the app going to the background: the whole answer was
  /// generated and stored anyway. So the stream stays open — nothing more is
  /// shown — until the frame arrives (servers send it first, at once); then
  /// the stop is sent and the stream closed. A stream that ends, fails,
  /// starts with a token (a server too old to name turns) or stays silent
  /// past [_stopNameWait] is just closed.
  void _stopWhenNamed(StreamSubscription<TgStreamEvent> sub, String sid) {
    _closeStopping();
    _stopping = sub;
    void close() {
      if (identical(_stopping, sub)) _closeStopping();
    }

    sub.onData((ev) {
      if (ev is TgTurnEvent) {
        unawaited(_client.stopAnswer(sid, messageId: ev.messageId));
      }
      close();
    });
    sub.onError((Object _) => close());
    sub.onDone(close);
    _stoppingTimer = Timer(_stopNameWait, close);
  }

  void _closeStopping() {
    _stoppingTimer?.cancel();
    _stoppingTimer = null;
    final sub = _stopping;
    _stopping = null;
    sub?.cancel();
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
    if (interrupted) {
      _cutAt = DateTime.now();
      unawaited(_persistLocal()); // still recoverable after a cold start (T4)
    }
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
          ..error = AppL10n.current.chatRatingSaveFailed(
              describeFailure(AppL10n.current, e));
      });
    }
  }

  // ── Manual retry (Phase 3 retry button) ────────────────────────────

  Future<void> retryLastTurn() async {
    // The server may have finished the cut answer on its own — or still be
    // writing it: generating it again would store a second, different
    // answer to the same question (T6). The look is shared with a recovery
    // already in flight, so a tap during its fetch waits for that answer.
    if (_interruptedTurn() != null) {
      final look = await _lookOnce();
      if (look == _Look.answered) return;
      if (look == _Look.pending && !_pastDeadline()) {
        unawaited(_recoverWithBackoff()); // look again now, then keep looking
        return;
      }
    }
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
      final msgs = _bubblesFrom(hist.messages);
      state = state.copyWith(
        messages: msgs,
        turnCount: msgs.where((m) => m.role == 'user').length,
      );
      await _persistLocal();
      if (_interruptedTurn() != null) unawaited(_recoverWithBackoff());
    } on TgApiError catch (e) {
      state = state.copyWith(
        phase: ChatPhase.error,
        errorBanner: AppL10n.current.chatOpenFailed(
            describeFailure(AppL10n.current, e)),
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
                    // A cut turn stays recoverable across a cold start (T4) —
                    // and so does one still streaming: if the process dies
                    // now, it was cut.
                    if (m.turnId != null) 'turn_id': m.turnId,
                    if (m.interrupted || (m.role == 'assistant' && m.isStreaming))
                      'interrupted': true,
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

  /// Called by the screen's lifecycle observer when the app is back. Wakes
  /// a recovery sleeping through its back-off, or starts one (T5).
  void onAppResumed() {
    unawaited(_recoverWithBackoff());
  }

  // ── Recovering an answer cut on this side ───────────────────────────

  /// The recovery loop in flight — one at a time.
  Future<bool>? _recovery;

  /// The history fetch in flight, shared by the loop and Retry (T6).
  Future<_Look>? _look;

  /// Completes to cut the loop's current back-off short.
  Completer<void>? _wake;

  /// When the current turn was cut: bounds how long it is waited for.
  DateTime? _cutAt;

  /// Look for the cut turn's answer until it is found, is known lost, or
  /// [recoveryDeadline] passes. Resume and the stream's own error both call
  /// this: a loop already running is woken instead of doubled.
  Future<bool> _recoverWithBackoff() {
    final running = _recovery;
    if (running != null) {
      _wakeRecovery();
      return running;
    }
    final loop = recoverInterruptedAnswer();
    _recovery = loop;
    return loop.whenComplete(() {
      if (identical(_recovery, loop)) _recovery = null;
    });
  }

  void _wakeRecovery() {
    final wake = _wake;
    if (wake != null && !wake.isCompleted) wake.complete();
  }

  Future<void> _backOff(Duration gap) {
    final wake = Completer<void>();
    _wake = wake;
    final timer = Timer(gap, () {
      if (!wake.isCompleted) wake.complete();
    });
    return wake.future.whenComplete(() {
      timer.cancel();
      if (identical(_wake, wake)) _wake = null;
    });
  }

  bool _pastDeadline() {
    final cut = _cutAt;
    return cut != null && DateTime.now().difference(cut) > recoveryDeadline;
  }

  /// Restore an answer whose stream died on this side.
  ///
  /// Servers since 2026-10 finish an answer after its reader leaves, in a
  /// row marked 'pending' until it is done, so the finished text is fetched
  /// from the session history, looking again with a growing gap
  /// ([recoveryDelay] doubling up to [maxRecoveryGap]) for as long as the
  /// server may still be writing it (T5 — it gave up after a minute, while
  /// the server may take five). It stops early when the turn is known lost:
  /// a stored fragment or apology, or a newer question after it.
  ///
  /// The stored answer is found by turn identity: the id the server gave
  /// the question. Without one (an older server), only the server's LAST
  /// question is considered, and only if its answer begins with what this
  /// side already showed. An older server never stored the answer — it
  /// finds nothing usable and the turn keeps its Retry.
  /// [attempts] caps the number of looks (tests). Returns true when the
  /// turn was restored.
  Future<bool> recoverInterruptedAnswer({
    int? attempts,
    Duration? retryDelay,
  }) async {
    final until = DateTime.now().add(recoveryDeadline);
    var gap = retryDelay ?? recoveryDelay;
    for (var attempt = 0; attempts == null || attempt < attempts; attempt++) {
      if (attempt > 0) {
        if (DateTime.now().isAfter(until)) break;
        await _backOff(gap);
        final next = gap * 2;
        gap = next > maxRecoveryGap ? maxRecoveryGap : next;
      }
      if (!mounted || _interruptedTurn() == null) return false;
      final look = await _lookOnce();
      if (look == _Look.answered) return true;
      if (look == _Look.cut) break;
    }
    // Nothing is coming (or it stopped being worth the wait): the bubble
    // says so, with its Retry.
    final turn = mounted ? _interruptedTurn() : null;
    if (turn != null) {
      _updateAssistant(turn.assistantId,
          (m) => m.error = AppL10n.current.chatConnectionInterrupted);
    }
    return false;
  }

  /// One look at the server for the cut turn — shared while in flight.
  Future<_Look> _lookOnce() {
    final inFlight = _look;
    if (inFlight != null) return inFlight;
    final look = _fetchTurn();
    _look = look;
    return look.whenComplete(() {
      if (identical(_look, look)) _look = null;
    });
  }

  Future<_Look> _fetchTurn() async {
    final turn = _interruptedTurn();
    final sid = state.sessionId;
    if (turn == null || sid == null) return _Look.cut;
    final SessionHistory history;
    try {
      history = await _client.getHistory(sid);
    } catch (_) {
      return _Look.unknown; // offline right after resuming — look again
    }
    if (!mounted) return _Look.cut;
    // The parent may have retried or asked again while we were fetching.
    final now = _interruptedTurn();
    if (now == null || now.assistantId != turn.assistantId) return _Look.cut;
    final (look, answer) = _serverTurn(history.messages, turn);
    switch (look) {
      case _Look.answered:
        _updateAssistant(turn.assistantId, (m) {
          m
            ..content = answer!.content
            ..isStreaming = false
            ..interrupted = false
            ..error = null;
        });
        state = state.copyWith(
          phase: ChatPhase.idle,
          turnCount: state.turnCount + 1,
          clearBanner: true,
        );
        _cutAt = null;
        unawaited(_persistLocal());
      case _Look.pending:
        _updateAssistant(turn.assistantId,
            (m) => m.error = AppL10n.current.chatAnswerStillComing);
      case _Look.unknown:
      case _Look.cut:
        break;
    }
    return look;
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

  /// What the server's history says about [turn], and its answer if found.
  (_Look, ChatMessage?) _serverTurn(
    List<ChatMessage> server,
    ({String question, String assistantId, int? turnId, String partial}) turn,
  ) {
    int q;
    if (turn.turnId != null && server.any((m) => m.id != null)) {
      q = server.indexWhere((m) => m.role == 'user' && m.id == turn.turnId);
    } else {
      // No turn id: only the server's LAST question can be this one.
      q = server.lastIndexWhere((m) => m.role == 'user');
      if (q < 0 || server[q].content.trim() != turn.question.trim()) {
        return (_Look.unknown, null); // not stored yet — or never will be
      }
    }
    if (q < 0) return (_Look.unknown, null);
    ChatMessage? answer;
    var newerQuestion = false;
    for (var i = q + 1; i < server.length; i++) {
      final m = server[i];
      if (m.role == 'user') {
        newerQuestion = true; // the next turn — not ours
        break;
      }
      if (m.role == 'assistant') {
        answer = m;
        break;
      }
    }
    if (answer == null) {
      // A newer question means this turn was cut before its first word.
      return (newerQuestion ? _Look.cut : _Look.unknown, null);
    }
    if (answer.modeWire == 'pending') return (_Look.pending, null);
    if (answer.content.trim().isEmpty) return (_Look.unknown, null);
    if (answer.modeWire == 'error' || answer.modeWire == 'interrupted') {
      return (_Look.cut, null);
    }
    if (turn.turnId == null) {
      // Same text is not proof of the same turn: the answer must continue
      // what this side already showed.
      String squash(String s) => s.replaceAll(RegExp(r'\s+'), '');
      if (!squash(answer.content).startsWith(squash(turn.partial))) {
        return (_Look.cut, null);
      }
    }
    return (_Look.answered, answer);
  }

  /// Bubbles for a conversation loaded from the server (cold start, the
  /// history drawer). Answers carry their question's id, and a conversation
  /// that ends in an answer still being written ('pending'), a cut fragment
  /// ('interrupted') or an unanswered question ends in an interrupted turn,
  /// with its Retry — recovered when the server may still finish it (T4).
  /// They came back as plain bubbles: a fragment looked like the answer.
  List<ChatMessageUI> _bubblesFrom(List<ChatMessage> server) {
    final out = <ChatMessageUI>[];
    int? questionId;
    for (final m in server) {
      if (m.role == 'user') questionId = m.id;
      out.add(ChatMessageUI(
        id: _nextId(),
        role: m.role,
        content: m.content,
        turnId: m.role == 'assistant' ? questionId : null,
      ));
    }
    if (server.isEmpty) return out;
    final last = server.last;
    final l10n = AppL10n.current;
    if (last.role == 'user') {
      out.add(ChatMessageUI(
        id: _nextId(),
        role: 'assistant',
        content: '',
        turnId: last.id,
        interrupted: true,
        error: l10n.chatAnswerStillComing,
      ));
    } else if (last.modeWire == 'pending' || last.modeWire == 'interrupted') {
      out.last
        ..interrupted = true
        ..error = last.modeWire == 'pending'
            ? l10n.chatAnswerStillComing
            : l10n.chatConnectionInterrupted;
    }
    if (out.last.interrupted) _cutAt = DateTime.now();
    return out;
  }

  Future<List<ChatMessageUI>?> _loadLocal(String sid) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_kSnapshotKey);
      if (raw == null) return null;
      final data = jsonDecode(raw) as Map<String, dynamic>;
      if (data['session_id'] != sid) return null;
      return (data['messages'] as List).map((m) {
        final interrupted = m['interrupted'] == true;
        return ChatMessageUI(
          id: _nextId(),
          role: m['role'] as String,
          content: m['content'] as String,
          feedback: m['feedback'] as String?,
          turnId: m['turn_id'] is int ? m['turn_id'] as int : null,
          interrupted: interrupted,
          error: interrupted ? AppL10n.current.chatConnectionInterrupted : null,
        );
      }).toList();
    } catch (_) {
      return null;
    }
  }
}

/// What the server's history says about a turn cut on this side.
enum _Look {
  /// The finished answer is there (and is now shown).
  answered,

  /// Its row is still being written ('pending', servers since 2026-10).
  pending,

  /// No answer row yet: the server may still be on it — or nothing comes.
  unknown,

  /// Lost for good: a fragment, an apology, a newer question after it.
  cut,
}
