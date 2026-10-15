/// CI-only hooks for the emulator rehearsal — compiled OUT of every build
/// that reaches a family.
///
/// The phase-2 gate of «نور والقناديل» asks the emulator to prove that an
/// interface tick never stops a Qur'an recitation. Nothing in the app sounds
/// while the Quran reader is reciting (the reader has no sound of its own, and
/// leaving it ends the recitation), so a person cannot produce that moment by
/// tapping. The CI runner can, in a build made with
/// `--dart-define=E2E_PROBES=true` — only the `rehearsal-head` APK of
/// `.github/workflows/mobile-e2e.yml`. Each of these plays one tick through
/// the very path a tap takes, [Haptics.selection] → [SoundFx.select]:
///
///  * a change of the system's light/dark mode
///    (`adb shell cmd uimode night yes|no`) — it reaches the app whatever has
///    the input focus, which is why it is the one the runner relies on;
///  * F12 (`adb shell input keyevent KEYCODE_F12`) — only if the key reaches
///    the Flutter view; on run 38714154049 three presses produced no tick.
///
/// Each prints a `tg.e2e:` line to logcat, so a run shows what arrived.
///
/// [kE2eProbes] is a compile-time constant, false unless that define is
/// passed. The release workflows never pass it (e2e/test_workflow.py checks
/// every workflow), and with the constant false the only call site,
/// `if (kE2eProbes) E2eProbes.installIfEnabled()`, is dead code the compiler
/// removes together with everything below.
library;

import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import 'haptics.dart';

/// Whether this build carries the CI probes. False for every build that is
/// not the rehearsal APK.
const bool kE2eProbes = bool.fromEnvironment('E2E_PROBES');

abstract final class E2eProbes {
  /// The key the runner may press for one interface tick.
  static const LogicalKeyboardKey tickKey = LogicalKeyboardKey.f12;

  static bool _installed = false;
  static final _BrightnessProbe _brightness = _BrightnessProbe();

  /// Whether the probes are installed in this process.
  static bool get installed => _installed;

  /// Called once from `main`. A no-op — and compiled away — unless the build
  /// was made with `--dart-define=E2E_PROBES=true`.
  static void installIfEnabled() {
    if (kE2eProbes) install();
  }

  /// Installs both triggers. Only [installIfEnabled] calls it in the app;
  /// tests call it directly to check what the probe does.
  @visibleForTesting
  static void install() {
    if (_installed) return;
    _installed = true;
    HardwareKeyboard.instance.addHandler(_onKey);
    WidgetsBinding.instance.addObserver(_brightness);
    debugPrint('tg.e2e: probes installed (system light/dark change, F12)');
  }

  @visibleForTesting
  static void uninstall() {
    if (!_installed) return;
    _installed = false;
    HardwareKeyboard.instance.removeHandler(_onKey);
    WidgetsBinding.instance.removeObserver(_brightness);
  }

  /// Exactly what a tab tap does (root_scaffold.dart): the selection pulse
  /// and its tick, under the same switch, child-mode and screen-off rules.
  static void _tick(String why) {
    debugPrint('tg.e2e: tick ($why)');
    unawaited(Haptics.selection());
  }

  static bool _onKey(KeyEvent event) {
    if (event is! KeyDownEvent || event.logicalKey != tickKey) return false;
    _tick('F12');
    return true;
  }
}

class _BrightnessProbe with WidgetsBindingObserver {
  @override
  void didChangePlatformBrightness() => E2eProbes._tick('system light/dark change');
}
