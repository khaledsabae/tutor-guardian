// main() must run in exactly one Flutter engine per process.
//
// 2026-10-04: every launch of 1.0.58–1.0.67 ran main() twice. The unused
// `just_audio_background` dependency pulled in `audio_service`, whose Android
// plugin — in onAttachedToActivity — creates its own FlutterEngine and runs
// the default entrypoint in it whenever MainActivity is not one of its
// activities (AudioServicePlugin.getFlutterEngine →
// DartEntrypoint.createDefault()). That headless second app minted its own
// device id on a fresh install, registered the same FCM token, and could leave
// its identity on disk for the next launch: a family whose child "vanished".
//
// Logcat proof from the E2E runs (PR #22): per app process, three Impeller
// contexts (UI engine, audio_service engine, FCM background engine) and
// «Attempted to start a duplicate background isolate» — the second main()
// registering FCM's background handler again.
//
// The E2E logcat gate catches a second entrypoint from ANY plugin at run time
// (e2e/e2e_tool.py, `tg.main` marker); this catches the known one before a
// build exists.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('no audio_service engine unless MainActivity is its activity', () {
    final lock = File('pubspec.lock').readAsStringSync();
    final activity = File(
      'android/app/src/main/kotlin/com/alsaba/almorabbi/MainActivity.kt',
    ).readAsStringSync();

    final hasAudioService =
        RegExp(r'^  audio_service:', multiLine: true).hasMatch(lock);
    final activityUsesItsEngine =
        RegExp(r':\s*AudioService(Fragment)?Activity\b').hasMatch(activity);

    expect(hasAudioService && !activityUsesItsEngine, isFalse,
        reason: 'audio_service is in pubspec.lock (directly or through '
            'just_audio_background) but MainActivity does not extend '
            'AudioServiceFragmentActivity, so the plugin starts a second '
            'engine that runs main() again — see '
            'lib/features/screen_off/audio_tag.dart');
  });

  test('main() prints the marker the E2E gate counts', () {
    final source = File('lib/main.dart').readAsStringSync();
    expect(
      RegExp(r"debugPrint\('tg\.main: entrypoint started'\)")
          .allMatches(source)
          .length,
      1,
      reason: 'e2e/e2e_tool.py fails a run where this line appears twice in '
          'one process; without it the gate checks nothing',
    );
  });
}
