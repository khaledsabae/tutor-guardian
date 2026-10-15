import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../api/tg_client.dart';
import '../../../core/analytics.dart';
import '../../../state/chat_notifier.dart';
import '../models/habit_models.dart';
import '../services/child_mode_secure_storage.dart';

final childModeProvider = StateNotifierProvider<ChildModeNotifier, ChildModeState>(
  (ref) => ChildModeNotifier(ref.read(tgClientProvider)),
);

/// Stable error codes surfaced through [ChildModeState.error].
/// The UI maps these to localized messages; anything else is shown raw.
const kChildModeErrorPinRequired = 'child_mode_pin_required';
const kChildModeErrorPinIncorrect = 'child_mode_pin_incorrect';
const kChildModeErrorSessionExpired = 'child_mode_session_expired';

/// The day's time is spent. Not an error — the UI shows a closing screen.
const kChildModeBudgetSpent = 'child_mode_budget_spent';

/// No signed family agreement yet, so the only surface that opens is the
/// agreement itself. The child-mode screen renders it rather than an error.
const kChildModeAgreementRequired = 'child_mode_agreement_required';

/// The server refused this surface for this child's age band
/// (`surface_not_allowed`). The hand-over gate filters by the same policy, so
/// this should not happen — but a stale profile, or a policy tightened after
/// the build shipped, still can, and a parent who just typed their PIN gets a
/// calm sentence rather than «فشل الدخول لوضع الطفل».
const kChildModeSurfaceNotAllowed = 'child_mode_surface_not_allowed';

/// Two heartbeats in a row failed to reach the server, so the surface closes.
///
/// The budget is enforced server-side, which is only true while the client is
/// talking to the server. A child in aeroplane mode with the app open is a
/// child with no limit at all, so losing contact ends the session here rather
/// than waiting to be told. Two failures rather than one absorbs a single
/// dropped request on a train.
const kChildModeOffline = 'child_mode_offline';
const _kMaxHeartbeatFailures = 2;

/// The session is over and the device is waiting for a parent: the hand-back
/// screen, with no reason to give beyond «أعِد الجهاز إلى أهلك».
///
/// Where a restart lands when child mode was on (see [ChildModeNotifier.restore]),
/// and where the mission card's "I'm going" leaves the device before it closes
/// the app. Not an error, and never a way out — that is the frame's Exit,
/// behind the parent's PIN.
const kChildModeHandedBack = 'child_mode_handed_back';

/// Runs [ChildModeNotifier.restore] once per launch.
///
/// The boot screen waits on this before it builds anything of the parent's.
/// restore() used to be fired from the parent app's own build, so the first
/// frame after a restart was the parent's app whatever restore() went on to
/// decide — and a route a child pushed from it in that moment would have
/// stayed on top of the child surface that replaced it.
///
/// Bounded by [kChildModeRestoreTimeout]: secure storage that never answers
/// (a wedged keystore) must not leave every launch on the splash forever.
/// Past it the parent's app opens — the same as a storage read that fails.
final childModeRestoreProvider = FutureProvider<void>(
  (ref) => ref
      .read(childModeProvider.notifier)
      .restore()
      .timeout(kChildModeRestoreTimeout, onTimeout: () {}),
);

/// How long a launch waits for the last run's child mode before giving up.
const kChildModeRestoreTimeout = Duration(seconds: 4);

/// [ChildModeState.copyWith]'s "leave the corner as it is" — so that a new
/// hand-over can also set it back to null, which `??` cannot.
const Object _keepCorner = Object();

class ChildModeState {
  const ChildModeState({
    this.active = false,
    this.loading = false,
    this.error,
    this.childId,
    this.day,
    this.submittedHabits = const {},
    this.sessionId,
    this.surface = 'habit',
    this.remainingSeconds,
    this.exitRitual = false,
    this.agreementAwaitsChild = false,
    this.cornerBand,
  });

  final bool active;
  final bool loading;
  final String? error;
  final int? childId;
  final HabitDay? day;
  final Set<String> submittedHabits;

  /// The open screen session. Null means no surface is running.
  final int? sessionId;

  /// Which surface this session was opened for.
  ///
  /// The server has always taken a surface and budgeted each one separately;
  /// the app only ever asked for `habit`, so every screen a child could reach
  /// billed the same line. Carrying it in the state is what lets a screen know
  /// which surface it is, and lets the router below send the child to it.
  final String surface;

  /// Seconds left on this surface, as the server last reported them.
  ///
  /// Shown to the child as a shortening bar or a candle, never as a number —
  /// a countdown in digits is a thing to bargain with.
  final int? remainingSeconds;

  /// The last minute has started: wind down, do not cut off.
  final bool exitRitual;

  /// A parent has signed a draft agreement and the child has not.
  ///
  /// The signing screen was reachable only when the server *refused* a
  /// surface, and that refusal lives behind AGREEMENT_REQUIRED — off, and
  /// staying off. So a parent could sign, hand over the device, and the child
  /// would land on the habit screen having never seen the agreement. This is
  /// the door that does not need the gate.
  final bool agreementAwaitsChild;

  /// «ركن الطفل»: the child's band when this hand-over opened the corner —
  /// one paper scene holding a story, a game and the day's task — rather than
  /// a single surface. Null for every other hand-over.
  ///
  /// Client-only. The server still sees plain surfaces (`story`, `game`,
  /// `mission`), opened one after another through [switchSurface]; this is
  /// what keeps the child in the corner while they change underneath it.
  /// The band is kept rather than a flag so the corner shows exactly what the
  /// gate checked against the policy.
  final String? cornerBand;

  /// Whether the child is in the corner.
  bool get corner => cornerBand != null;

  ChildModeState copyWith({
    bool? active,
    bool? loading,
    String? error,
    int? childId,
    HabitDay? day,
    Set<String>? submittedHabits,
    int? sessionId,
    String? surface,
    int? remainingSeconds,
    bool? exitRitual,
    bool? agreementAwaitsChild,
    Object? cornerBand = _keepCorner,
  }) =>
      ChildModeState(
        cornerBand: identical(cornerBand, _keepCorner)
            ? this.cornerBand
            : cornerBand as String?,
        active: active ?? this.active,
        loading: loading ?? this.loading,
        error: error,
        childId: childId ?? this.childId,
        day: day ?? this.day,
        submittedHabits: submittedHabits ?? this.submittedHabits,
        sessionId: sessionId ?? this.sessionId,
        surface: surface ?? this.surface,
        remainingSeconds: remainingSeconds ?? this.remainingSeconds,
        exitRitual: exitRitual ?? this.exitRitual,
        agreementAwaitsChild:
            agreementAwaitsChild ?? this.agreementAwaitsChild,
      );

  bool isSubmitted(String habitName) => submittedHabits.contains(habitName);
}

enum StageOutcome { committed, undone, failed }

/// What became of a staged log, and the streak milestone it crossed if any.
class StageResult {
  const StageResult(this.outcome, {this.milestone});

  final StageOutcome outcome;
  final int? milestone;
}

class _Staged {
  _Staged(this.item, this.status);

  final HabitItem item;
  final String status;
  final Completer<StageResult> done = Completer<StageResult>();
  Timer? timer;
}

class ChildModeNotifier extends StateNotifier<ChildModeState> {
  ChildModeNotifier(this._client) : super(const ChildModeState());

  final TgClient _client;

  /// How long a child's tap stays undoable before it is sent (UX_UI_ROADMAP
  /// G3). The server is submit-only for children, so undo cannot be a delete:
  /// the log waits here, and Undo means it is never sent.
  static const undoWindow = Duration(seconds: 5);

  final Map<String, _Staged> _staged = {};

  /// Show [item] as logged now; send it once [undoWindow] passes.
  ///
  /// Replaces a confirmation dialog on every check-in: one tap instead of
  /// two, and a mistaken tap is still recoverable.
  ///
  /// Null when the habit is already logged or waiting — a second tap before
  /// the card redrew. Nothing happened, so there is nothing to report.
  Future<StageResult>? stage(HabitItem item, String status) {
    final name = item.habitName;
    if (state.isSubmitted(name) || _staged.containsKey(name)) return null;
    final staged = _Staged(item, status);
    staged.timer = Timer(undoWindow, () => _commit(name));
    _staged[name] = staged;
    state = state.copyWith(
      error: state.error,
      submittedHabits: {...state.submittedHabits, name},
    );
    return staged.done.future;
  }

  /// Take back a staged log. False once it has already been sent.
  bool undo(String habitName) {
    final staged = _staged.remove(habitName);
    if (staged == null) return false;
    staged.timer?.cancel();
    state = state.copyWith(
      error: state.error,
      submittedHabits: {...state.submittedHabits}..remove(habitName),
    );
    staged.done.complete(const StageResult(StageOutcome.undone));
    return true;
  }

  /// Send every staged log now — before a session closes, so a tap made in
  /// the last five seconds is not lost with the child token.
  Future<void> flushStaged() async {
    for (final name in _staged.keys.toList()) {
      _staged[name]?.timer?.cancel();
      await _commit(name);
    }
  }

  Future<void> _commit(String name) async {
    final staged = _staged.remove(name);
    if (staged == null) return;
    final before = state.day?.streak ?? const HabitStreak();
    final ok = await _send(staged.item, staged.status);
    if (!mounted) {
      staged.done.complete(StageResult(
          ok ? StageOutcome.committed : StageOutcome.failed));
      return;
    }
    if (!ok) {
      state = state.copyWith(
        error: state.error,
        submittedHabits: {...state.submittedHabits}..remove(name),
      );
      staged.done.complete(const StageResult(StageOutcome.failed));
      return;
    }
    int? milestone;
    final day = state.day;
    if (day != null && staged.status != HabitStatus.missed.wireName) {
      final after = before.withEffortToday();
      milestone = streakMilestoneCrossed(before.days, after.days);
      state = state.copyWith(error: state.error, day: day.withStreak(after));
    }
    staged.done.complete(
        StageResult(StageOutcome.committed, milestone: milestone));
  }

  /// After a restart: if a child had the device, they still have it.
  ///
  /// The "child mode is on" flag survives the process; the session id does
  /// not, so nothing can heartbeat and nothing is being counted. That much was
  /// always true, and restore() used to answer it by ending child mode — which
  /// opened the parent's app, the assistant, settings and every child's
  /// profile, with no PIN. A child on the hand-back screen («أعِد الجهاز إلى
  /// أهلك») only had to force-close the app and open it again; so did a child
  /// whose time ran out, whose connection dropped, or who swiped the app away
  /// in the middle of a session.
  ///
  /// Now a restart lands on the hand-back screen. Child mode stays on, on
  /// screen and on disk; no surface runs, so nothing is unmetered; and the way
  /// out is the frame's Exit, behind the parent's PIN — the same as every
  /// other child surface.
  ///
  /// The old token is not asked about. Alive or dead on the server, the answer
  /// is the same screen, so a network round trip could only add a spinner in
  /// front of it — and its 401 handling renewed the token, opening a fresh
  /// session only to abandon it. The exit is local (the PIN is checked on the
  /// device, and there is no session to end), so a dead token or no
  /// connection at all never keeps a parent out.
  ///
  /// The one exception is a device with no PIN to check: nothing could ever
  /// open that lock, so child mode ends rather than brick the app.
  Future<void> restore() async {
    // A session opened in this process outranks anything left on disk.
    if (state.active) return;
    if (!await isChildModeActive()) return;
    if (!await hasChildModePin()) {
      await _leaveChildMode();
      return;
    }
    // May be null (the id is in preferences, the flag in secure storage, and
    // only one of them survives an iOS reinstall). Exit does not need it, so
    // failing to read it is no reason to open the parent's app.
    int? childId;
    try {
      childId = await _loadChildId();
    } catch (_) {
      childId = null;
    }
    if (state.active) return;
    state = ChildModeState(
      active: true,
      childId: childId,
      error: kChildModeHandedBack,
    );
  }

  /// Drop out of child mode entirely and clear what is on disk.
  Future<void> _leaveChildMode() async {
    _stopHeartbeat();
    await clearChildMode();
    await _clearChildId();
    state = const ChildModeState();
  }

  /// Prove a parent is holding the device — and, on first use, set the PIN.
  ///
  /// Opens nothing. The hand-over gate asks for the PIN first, plays its doors
  /// while the device is still in parent mode, and only then calls [enter]
  /// with the same PIN: the moment of handing over is not billed to the
  /// child's minutes. [enter] checks the PIN again, so this is never a way in
  /// on its own.
  Future<bool> checkPin(String? pin) async {
    if (pin == null || pin.isEmpty) {
      state = state.copyWith(loading: false, error: kChildModeErrorPinRequired);
      return false;
    }
    if (await hasChildModePin()) {
      if (!await verifyChildModePin(pin)) {
        state = state.copyWith(
          loading: false,
          error: kChildModeErrorPinIncorrect,
        );
        return false;
      }
    } else {
      await setChildModePin(pin);
    }
    return true;
  }

  /// The only way into a child surface.
  ///
  /// Every screen a child can reach goes through here: the PIN proves a parent
  /// opened it, and the session it creates is what the server checks on every
  /// subsequent request. A second entry point that skipped this would be a
  /// child surface with no gate in front of it.
  Future<bool> enter({
    required int childId,
    String? pin,
    String surface = 'habit',
    String? cornerBand,
  }) async {
    state = state.copyWith(loading: true, error: null);
    try {
      if (!await checkPin(pin)) return false;
      final session = await _client.createChildSession(childId, surface: surface);
      // Not a hard cast: this lands inside a catch whose message is rendered
      // verbatim on the PIN screen, so a missing field would show a parent
      // "type 'Null' is not a subtype of type 'String'".
      final token = session['token'] as String?;
      if (token == null) {
        state = state.copyWith(loading: false);
        return false;
      }
      await saveChildToken(token);
      await setChildModeActive(true);
      await _saveChildId(childId);
      state = state.copyWith(
        cornerBand: cornerBand,
        active: true,
        loading: false,
        childId: childId,
        sessionId: session['session_id'] as int?,
        surface: (session['surface'] as String?) ?? surface,
        remainingSeconds: session['allowed_seconds'] as int?,
        exitRitual: false,
        agreementAwaitsChild:
            session['agreement_awaits_child'] as bool? ?? false,
      );
      // No session id means the server has the child surface switched off and
      // handed back a plain token. Nothing to report on, so nothing beats.
      if (session['session_id'] != null) {
        _startHeartbeat(
          intervalSeconds: (session['heartbeat_interval_seconds'] as int?) ?? 30,
        );
      }
      // Only the habit surface renders the habit day. Fetching it for the
      // others costs a round trip a child waits through, and a failure there
      // would write an error code the mission screen would then have to know
      // how to ignore.
      if (state.surface == 'habit') await refresh();
      return true;
    } catch (e) {
      state = state.copyWith(loading: false, error: _classify(e));
      return false;
    }
  }

  /// Move an already-open child session to a different surface.
  ///
  /// This exists because the surfaces are budgeted separately and the app was
  /// spending the wrong one. Screen-off listening is defined by the policy as
  /// *not* screen time — forty-five minutes of audio against its own ledger —
  /// but the player opened inside whatever session was already running, which
  /// was always `habit`. So a story with the display dark was billed as twenty
  /// minutes of screen, and the one surface the whole design rests on was the
  /// one being charged wrongly.
  ///
  /// No PIN. The parent already proved themselves to open the session this is
  /// moving; asking again mid-story would put a PIN pad in front of a child
  /// listening in the dark. The gate that matters is the server's: it checks
  /// the age band, the surface list, and the ledger for the new surface, and
  /// refuses on its own terms.
  ///
  /// Returns false when the server refuses; [error] then holds the reason and
  /// the caller should not open the surface.
  Future<bool> switchSurface(String surface) async {
    final childId = state.childId;
    if (childId == null) return false;
    if (state.surface == surface && state.sessionId != null) return true;

    // Close first. The server supersedes an open session on its own, but doing
    // it explicitly is what makes the old surface's final seconds land on the
    // right ledger rather than on a `superseded` close charged to its grace.
    await endSession(reason: 'completed');
    try {
      final session = await _client.createChildSession(childId, surface: surface);
      state = state.copyWith(
        active: true,
        error: null,
        sessionId: session['session_id'] as int?,
        surface: (session['surface'] as String?) ?? surface,
        remainingSeconds: session['allowed_seconds'] as int?,
        exitRitual: false,
        agreementAwaitsChild:
            session['agreement_awaits_child'] as bool? ?? false,
      );
      final token = session['token'] as String?;
      if (token != null) await saveChildToken(token);
      if (session['session_id'] != null) {
        _startHeartbeat(
          intervalSeconds: (session['heartbeat_interval_seconds'] as int?) ?? 30,
        );
      }
      return true;
    } catch (e) {
      state = state.copyWith(error: _classify(e));
      return false;
    }
  }

  /// A 403 from the session endpoint is the age gate or the day's budget, and
  /// both deserve a calm screen rather than a red error. Anything else is a
  /// real failure and keeps its message.
  String _classify(Object e) {
    final text = e.toString();
    if (text.contains('agreement_required')) {
      return kChildModeAgreementRequired;
    }
    // Before the age gate below: both are 403s from the same check, and this
    // one has a way forward — another surface — where the age gate has none.
    if (text.contains('surface_not_allowed')) {
      return kChildModeSurfaceNotAllowed;
    }
    if (text.contains('age_not_allowed') ||
        text.contains('budget_exhausted')) {
      return kChildModeBudgetSpent;
    }
    return text;
  }

  // ── Heartbeat ────────────────────────────────────────────────────────────

  Timer? _heartbeatTimer;
  int _heartbeatFailures = 0;

  void _startHeartbeat({required int intervalSeconds}) {
    _heartbeatTimer?.cancel();
    _heartbeatFailures = 0;
    _heartbeatTimer = Timer.periodic(
      Duration(seconds: intervalSeconds),
      (_) => unawaited(_beat()),
    );
  }

  /// Report now instead of waiting out the interval.
  ///
  /// Called when a surface comes back to the foreground. The periodic timer
  /// keeps running while backgrounded, but a deeply suspended device can still
  /// miss beats, and the server reaps a session ninety seconds after the last
  /// one — so the first thing to do on resume is find out whether the session
  /// we think we have still exists.
  Future<void> beatNow() => _beat();

  Future<void> _beat() async {
    final sessionId = state.sessionId;
    final token = await getChildToken();
    if (sessionId == null || token == null) {
      _stopHeartbeat();
      return;
    }
    try {
      final result = await _client.childHeartbeat(
        childToken: token,
        sessionId: sessionId,
      );
      _heartbeatFailures = 0;
      if (result == null) {
        // The server closed it. Not a failure — the surface is simply over.
        await endSession(reason: 'completed', code: kChildModeBudgetSpent);
        return;
      }
      state = state.copyWith(
        remainingSeconds: result['remaining_seconds'] as int?,
        exitRitual: result['exit_ritual'] as bool? ?? false,
      );
    } catch (_) {
      _heartbeatFailures++;
      if (_heartbeatFailures >= _kMaxHeartbeatFailures) {
        // Server-side enforcement only holds while we can reach the server.
        await endSession(reason: 'timeout', code: kChildModeOffline);
      }
    }
  }

  void _stopHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
  }

  /// Close the running surface. [code] is what the UI renders — a quiet
  /// closing screen, never an error dialog.
  Future<void> endSession({String reason = 'completed', String? code}) async {
    _stopHeartbeat();
    await flushStaged();
    final sessionId = state.sessionId;
    final token = await getChildToken();
    if (sessionId != null && token != null) {
      try {
        await _client.endChildSession(
          childToken: token,
          sessionId: sessionId,
          reason: reason,
        );
      } catch (_) {
        // The server reaps sessions that stop reporting, so a failed close is
        // recovered without us. Never block the child's exit on the network.
      }
    }
    // Constructed rather than copyWith: copyWith uses `??`, so passing null
    // for sessionId would keep the closed session's id and the next entry
    // would heartbeat against a session that is already over.
    state = ChildModeState(
      active: state.active,
      childId: state.childId,
      day: state.day,
      submittedHabits: state.submittedHabits,
      sessionId: null,
      surface: state.surface,
      remainingSeconds: 0,
      exitRitual: false,
      error: code,
      cornerBand: state.cornerBand,
    );
  }

  @override
  void dispose() {
    _stopHeartbeat();
    for (final staged in _staged.values) {
      staged.timer?.cancel();
    }
    super.dispose();
  }

  /// Close the session and leave the device on the hand-back screen.
  ///
  /// For a surface that ends with the app closing — the mission card's "I'm
  /// going". It used to leave child mode without a PIN, on the reasoning that
  /// the child was leaving rather than gaining access. But the launcher icon
  /// is right there: the next launch opened the parent's app, and the mission
  /// card's Back gesture took the same exit. Child mode stays on instead, and
  /// whoever opens the app next meets the hand-back screen.
  Future<void> handBack() =>
      endSession(reason: 'completed', code: kChildModeHandedBack);

  Future<bool> exit(String pin) async {
    final ok = await verifyChildModePin(pin);
    if (!ok) return false;
    await endSession(reason: 'parent_exit');
    await clearChildMode();
    await _clearChildId();
    state = const ChildModeState();
    return true;
  }

  Future<void> refresh() async {
    final token = await getChildToken();
    if (token == null) {
      _sessionExpired();
      return;
    }
    state = state.copyWith(loading: true);
    try {
      final raw = await _client.fetchChildTodayHabits(childToken: token);
      final day = HabitDay.fromJson(raw);
      state = state.copyWith(
        loading: false,
        day: day,
        submittedHabits: {
          for (final e in day.events)
            if (e.status != HabitStatus.missed) e.habitName,
          // Still inside their undo window: not on the server yet.
          ..._staged.keys,
        },
      );
    } on TgApiError catch (e) {
      if (e.statusCode == 401) {
        _sessionExpired();
      } else {
        state = state.copyWith(loading: false, error: e.toString());
      }
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  Future<bool> submit(HabitItem item, String status) async {
    if (state.isSubmitted(item.habitName)) return false;
    return _send(item, status);
  }

  Future<bool> _send(HabitItem item, String status) async {
    final token = await getChildToken();
    if (token == null) return false;
    try {
      await _client.createChildHabitEvent(
        childToken: token,
        body: {
          'category': item.category.wireName,
          'habit_name': item.habitName,
          'status': status,
          'device_timestamp': DateTime.now().toUtc().toIso8601String(),
        },
      );
      state = state.copyWith(
        submittedHabits: {...state.submittedHabits, item.habitName},
      );
      unawaited(Analytics.habitCheckIn(status));
      return true;
    } on TgApiError catch (e) {
      if (e.statusCode == 401) {
        _sessionExpired();
      } else {
        state = state.copyWith(error: e.toString());
      }
      return false;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  /// The server no longer accepts the child's token: the session behind it is
  /// over, and so is the surface.
  ///
  /// This used to clear child mode, which flipped the root to the parent's
  /// app with no PIN — so a token that expired under a child handed them the
  /// whole app. Child mode stays on; the screen asks for the device back, and
  /// the way out is the parent's PIN, which needs no token at all.
  void _sessionExpired() {
    _stopHeartbeat();
    state = ChildModeState(
      active: true,
      childId: state.childId,
      surface: state.surface,
      error: kChildModeErrorSessionExpired,
      cornerBand: state.cornerBand,
    );
  }

  Future<int?> _loadChildId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt(kChildModeChildIdKey);
  }

  Future<void> _saveChildId(int childId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(kChildModeChildIdKey, childId);
  }

  Future<void> _clearChildId() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(kChildModeChildIdKey);
  }
}
