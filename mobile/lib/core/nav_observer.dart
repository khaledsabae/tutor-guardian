/// Navigation observer — the "where do users get lost?" probe.
///
/// Multiple users reported getting lost inside the app. Rather than guess which
/// of the ~40 screens are the problem, this observer watches every push/pop and
/// classifies how each visit *ended*:
///
///   * [ExitKind.bounce]  — opened and backed straight out. The misleading
///                          affordance is on the screen they came *from*.
///   * [ExitKind.deadEnd] — stayed a while, then left without ever navigating
///                          onward. The screen itself offered nothing to do.
///
/// Because [AppRoutes] stamps every route with a `Screens.*` name, this single
/// class names all destinations without any per-screen instrumentation.
///
/// Everything here is best-effort and wrapped in try/catch: an observer that
/// throws would take down navigation itself.
library;

import 'dart:async';

import 'package:flutter/gestures.dart';
import 'package:flutter/widgets.dart';

import 'analytics.dart';
import 'app_routes.dart';

/// How a screen visit ended.
enum ExitKind { bounce, deadEnd, none }

/// A visit shorter than this reads as "opened it, wasn't what I wanted".
const kBounceThresholdMs = 3000;

/// No touch for this long means the user is reading — or stuck.
const kIdleThresholdMs = 20000;

/// Only every Nth visit arms an idle timer, to keep event volume sane.
const kIdleSampleRate = 5;

/// Pops closer together than this are one continuous back-hammer, not two
/// separate decisions.
const kBackHammerWindowMs = 2000;

/// Classifies how a visit ended. Pure — the unit tests drive this directly
/// with synthetic timings rather than a real Navigator.
ExitKind classifyExit({required int dwellMs, required int childPushCount}) {
  if (dwellMs < kBounceThresholdMs) return ExitKind.bounce;
  if (childPushCount == 0) return ExitKind.deadEnd;
  return ExitKind.none;
}

class _Visit {
  _Visit(this.route, this.name, this.enteredAtMs);

  final Route<dynamic> route;
  final String name;
  final int enteredAtMs;

  /// How many screens were opened *from* this one. Zero on exit means the user
  /// found no way forward.
  int childPushCount = 0;
  Timer? idleTimer;
}

/// Attach once, via `MaterialApp.navigatorObservers`.
class TgNavObserver extends NavigatorObserver {
  final List<_Visit> _stack = [];
  int _visitCounter = 0;
  int _lastPopMs = 0;
  int _consecutivePops = 0;

  /// Timestamp of the last pointer-down anywhere in the app. Fed by the global
  /// `Listener` in main.dart so idle detection sees taps that never reach a
  /// widget with a callback.
  static int _lastTapMs = 0;

  static void recordTap(PointerDownEvent _) {
    _lastTapMs = DateTime.now().millisecondsSinceEpoch;
  }

  static int get _now => DateTime.now().millisecondsSinceEpoch;

  /// Dialogs, bottom sheets and other popups are not destinations — counting
  /// them would drown the real screens. Unnamed page routes are ignored too:
  /// a name is what makes an event comparable across releases.
  String? _nameOf(Route<dynamic>? route) {
    if (route is! PageRoute) return null;
    final name = route.settings.name;
    if (name == null || name.isEmpty) return null;
    // MaterialApp's `home:` route is named '/' by the framework.
    return name == '/' ? Screens.root : name;
  }

  void _enter(Route<dynamic> route, String name) {
    if (_stack.isNotEmpty) _stack.last.childPushCount++;
    final visit = _Visit(route, name, _now);
    _stack.add(visit);
    _armIdleTimer(visit);
    unawaited(Analytics.screenView(name, _stack.length));
  }

  void _armIdleTimer(_Visit visit) {
    _visitCounter++;
    if (_visitCounter % kIdleSampleRate != 0) return;
    visit.idleTimer = Timer(
      const Duration(milliseconds: kIdleThresholdMs),
      () {
        try {
          // Only report if nothing was touched during the whole window.
          if (_now - _lastTapMs < kIdleThresholdMs) return;
          if (_stack.isEmpty || _stack.last != visit) return;
          unawaited(Analytics.idleDwell(visit.name, _now - visit.enteredAtMs));
        } catch (_) {
          // never let instrumentation break navigation
        }
      },
    );
  }

  /// Removes [route]'s visit wherever it sits in the stack and reports how it
  /// ended. Returns the depth the stack had *before* the removal.
  int _exit(Route<dynamic> route, {required bool report}) {
    final index = _stack.indexWhere((v) => identical(v.route, route));
    if (index == -1) return _stack.length;

    final depthBefore = _stack.length;
    final visit = _stack.removeAt(index);
    visit.idleTimer?.cancel();
    if (!report) return depthBefore;

    final dwellMs = _now - visit.enteredAtMs;
    final kind = classifyExit(
      dwellMs: dwellMs,
      childPushCount: visit.childPushCount,
    );
    switch (kind) {
      case ExitKind.bounce:
        final from = index > 0 ? _stack[index - 1].name : Screens.root;
        unawaited(Analytics.screenBounce(visit.name, dwellMs, from));
      case ExitKind.deadEnd:
        unawaited(Analytics.deadEnd(visit.name, dwellMs));
      case ExitKind.none:
        break;
    }
    return depthBefore;
  }

  /// Detects back-hammering: several quick pops in a row that land on the root.
  ///
  /// Note this also fires on a programmatic `popUntil(isFirst)` — deep links do
  /// that — but those are rare enough not to distort the signal.
  void _checkBackToRoot(int depthBefore) {
    final now = _now;
    _consecutivePops =
        (now - _lastPopMs <= kBackHammerWindowMs) ? _consecutivePops + 1 : 1;
    _lastPopMs = now;
    if (_consecutivePops >= 2 && depthBefore >= 3 && _stack.length <= 1) {
      unawaited(Analytics.backToRoot(depthBefore));
      _consecutivePops = 0;
    }
  }

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    try {
      final name = _nameOf(route);
      if (name != null) _enter(route, name);
    } catch (_) {
      // never let instrumentation break navigation
    }
  }

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    try {
      if (_nameOf(route) == null) return;
      final depthBefore = _exit(route, report: true);
      _checkBackToRoot(depthBefore);
    } catch (_) {
      // never let instrumentation break navigation
    }
  }

  @override
  void didRemove(Route<dynamic> route, Route<dynamic>? previousRoute) {
    try {
      // Silently removed (e.g. pushAndRemoveUntil) — the user did not choose to
      // leave, so classifying the exit would be misleading.
      if (_nameOf(route) != null) _exit(route, report: false);
    } catch (_) {
      // never let instrumentation break navigation
    }
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    try {
      if (oldRoute != null && _nameOf(oldRoute) != null) {
        _exit(oldRoute, report: false);
      }
      if (newRoute != null) {
        final name = _nameOf(newRoute);
        if (name != null) _enter(newRoute, name);
      }
    } catch (_) {
      // never let instrumentation break navigation
    }
  }
}
