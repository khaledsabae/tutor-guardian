/// CI-only hooks for the emulator rehearsal — compiled OUT of every build
/// that reaches a family.
///
/// The phase-2 gate of «نور والقناديل» asks the emulator to prove that an
/// interface tick never stops a Qur'an recitation. Nothing in the app sounds
/// while the Quran reader is reciting (the reader has no sound of its own, and
/// leaving it ends the recitation), so a person cannot produce that moment by
/// tapping. The CI runner can: in a build made with
/// `--dart-define=E2E_PROBES=true` — only the `rehearsal-head` APK of
/// `.github/workflows/mobile-e2e.yml` — pressing F12
/// (`adb shell input keyevent KEYCODE_F12`) plays one tick through the very
/// path a tap takes: [Haptics.selection] → [SoundFx.select].
///
/// [kE2eProbes] is a compile-time constant, false unless that define is
/// passed. The release workflows never pass it (e2e/test_workflow.py checks
/// every workflow), and with the constant false the only call site,
/// `if (kE2eProbes) E2eProbes.install()`, is dead code the compiler removes
/// together with everything below.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'haptics.dart';

/// Whether this build carries the CI probes. False for every build that is
/// not the rehearsal APK.
const bool kE2eProbes = bool.fromEnvironment('E2E_PROBES');

abstract final class E2eProbes {
  /// The key the runner presses for one interface tick.
  static const LogicalKeyboardKey tickKey = LogicalKeyboardKey.f12;

  static bool _installed = false;

  /// Whether the key handler is installed in this process.
  static bool get installed => _installed;

  /// Called once from `main`. A no-op — and compiled away — unless the build
  /// was made with `--dart-define=E2E_PROBES=true`.
  static void installIfEnabled() {
    if (kE2eProbes) install();
  }

  /// Installs the key handler. Only [installIfEnabled] calls it in the app;
  /// tests call it directly to check what the probe does.
  @visibleForTesting
  static void install() {
    if (_installed) return;
    _installed = true;
    HardwareKeyboard.instance.addHandler(_onKey);
  }

  @visibleForTesting
  static void uninstall() {
    if (!_installed) return;
    _installed = false;
    HardwareKeyboard.instance.removeHandler(_onKey);
  }

  static bool _onKey(KeyEvent event) {
    if (event is! KeyDownEvent || event.logicalKey != tickKey) return false;
    // Exactly what a tab tap does (root_scaffold.dart): the selection pulse
    // and its tick, subject to the same switch, child mode and screen-off
    // rules.
    unawaited(Haptics.selection());
    return true;
  }
}
