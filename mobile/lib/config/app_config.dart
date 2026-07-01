import 'package:flutter/foundation.dart' show kReleaseMode;

/// App-wide configuration constants.
///
/// The base URL is read from a `--dart-define` so the same APK can target
/// staging/production without code changes. When no define is passed,
/// release builds target production and debug builds target the local
/// FastAPI dev server (matches the project's `check.sh` / docs).
class AppConfig {
  static const String _definedBaseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: '');

  /// Release default = production API. Debug default = local dev backend
  /// (10.0.2.2 is the Android-emulator alias for the host machine).
  /// Override either at build time:
  ///
  ///   flutter build appbundle --release \
  ///     --dart-define=API_BASE_URL=https://staging.example.com
  static const String apiBaseUrl = _definedBaseUrl != ''
      ? _definedBaseUrl
      : (kReleaseMode
          ? 'https://tg-api.alsaba.cloud'
          : 'http://10.0.2.2:8090');

  /// Network request timeout for non-streaming calls.
  static const Duration httpTimeout = Duration(seconds: 60);

  /// SSE read timeout (must be larger than the LLM's worst-case generation).
  static const Duration streamTimeout = Duration(minutes: 5);

  /// App display labels.
  static const String appName = 'المربي الذكي';
  static const String appShortName = 'المربي';

  /// App version (kept in sync with `pubspec.yaml` — bump on every release).
  static const String appVersion = '1.0.24';
}
