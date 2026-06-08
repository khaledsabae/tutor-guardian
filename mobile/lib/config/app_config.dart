/// App-wide configuration constants.
///
/// The base URL is read from a `--dart-define` so the same APK can target
/// staging/production without code changes. Default points at the local
/// FastAPI dev server (matches the project's `check.sh` / docs).
class AppConfig {
  /// Default = local dev backend (localhost:8090, the project's standard
  /// mobile-ready FastAPI port). Override at build time:
  ///
  ///   flutter build appbundle --release \
  ///     --dart-define=API_BASE_URL=https://tg-api.alsaba.cloud
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8090', // Android emulator → host machine
  );

  /// Network request timeout for non-streaming calls.
  static const Duration httpTimeout = Duration(seconds: 60);

  /// SSE read timeout (must be larger than the LLM's worst-case generation).
  static const Duration streamTimeout = Duration(minutes: 5);

  /// App display labels.
  static const String appName = 'المربي الذكي';
  static const String appShortName = 'المربي';

  /// App version (kept in sync with `pubspec.yaml`).
  static const String appVersion = '1.0.0';
}
