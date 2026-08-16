/// The mission card, the evening confirmation, and the surfaces around them.
///
/// The backend for all of this shipped complete and tested with nothing in the
/// app calling it — a child was assigned a mission every day and never shown
/// one. So the tests that matter here are about the wiring: that a surface
/// reaches its screen, that a session bills the right ledger, and that the
/// buttons do what the constitution says they do.
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/app_routes.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/features/routine/widgets/quiet_time_bar.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('the surface travels from the entry point', () {
    test('a session defaults to habit and carries whatever it was opened for',
        () {
      // The server has always budgeted each surface separately; the app only
      // ever asked for `habit`, so every screen a child could reach billed the
      // same twenty minutes. The state has to hold the surface for anything
      // else to be possible.
      const state = ChildModeState();
      expect(state.surface, 'habit');
      expect(state.copyWith(surface: 'mission').surface, 'mission');
      expect(state.copyWith(surface: 'screen_off').surface, 'screen_off');
    });

    test('copyWith without a surface keeps the running one', () {
      // The heartbeat calls copyWith on every beat with only the remaining
      // seconds. If that reset the surface, a mission session would silently
      // become a habit session thirty seconds in.
      const state = ChildModeState(surface: 'screen_off');
      expect(state.copyWith(remainingSeconds: 120).surface, 'screen_off');
    });

    test('the lock screen route accepts a surface', () {
      // The only way into a child surface is enter(), and the only caller of
      // enter() is this screen. A route that cannot carry the surface means
      // every surface is `habit` no matter which button was pressed.
      final route = AppRoutes.childModeLock<void>(
          childId: 1, childName: 'x', surface: 'mission');
      expect(route.settings.name, 'child_mode_lock');
    });
  });

  group('the quiet clock', () {
    Widget wrap(ChildModeState state) => ProviderScope(
          overrides: [
            childModeProvider.overrideWith((ref) => _FixedChildMode(state)),
          ],
          child: const MaterialApp(home: Scaffold(body: QuietTimeBar())),
        );

    testWidgets('draws nothing when there is no session', (tester) async {
      // An empty bar reads as "your time is up", which is a different and
      // wrong statement from "you are not in a session".
      await tester.pumpWidget(wrap(const ChildModeState()));
      expect(find.byType(LinearProgressIndicator), findsNothing);
    });

    testWidgets('draws a bar once a session is running', (tester) async {
      await tester.pumpWidget(wrap(
          const ChildModeState(active: true, sessionId: 7, remainingSeconds: 600)));
      await tester.pump();
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
    });

    testWidgets('shows the time as a bar, never as a number', (tester) async {
      // Rule 7, and plan item 1.3d. A countdown in digits is a thing to
      // bargain with: "five more minutes" is only a sentence a child can say
      // if they can read the five.
      await tester.pumpWidget(wrap(
          const ChildModeState(active: true, sessionId: 7, remainingSeconds: 600)));
      await tester.pump();
      final digits = find.byWidgetPredicate((w) =>
          w is Text && w.data != null && RegExp(r'\d').hasMatch(w.data!));
      expect(digits, findsNothing);
    });
  });

  group('routes exist and are reachable', () {
    // route_registry_test proves every factory has a caller. These prove the
    // specific ones this work added resolve to the screens intended.
    test('the pending-missions route is named', () {
      expect(AppRoutes.pendingMissions().settings.name, 'pending_missions');
    });

    test('the off-screen alternatives route is named', () {
      expect(AppRoutes.offscreenActivities().settings.name,
          'offscreen_activities');
    });

    test('the screen-off picker route is named', () {
      expect(AppRoutes.screenOffPicker().settings.name, 'screen_off_picker');
    });

    test('the player takes a playlist as well as a single source', () {
      // everyayah serves one file per verse, so a surah is a playlist. Without
      // this the Qur'an source could only ever play one verse.
      final route = AppRoutes.screenOffPlayer(
          title: 'x', source: '', playlist: const ['a', 'b']);
      expect(route.settings.name, 'screen_off_player');
    });
  });

  group('the digest tap has somewhere to land', () {
    test('the deep-link handler knows /missions', () {
      // The push carries data.link = "/missions". A payload the client cannot
      // route registers as a delivered notification that opens the home screen
      // — which is how 29,194 pushes once showed 810 opens.
      final source =
          File('lib/features/deeplink/deep_link_handler.dart').readAsStringSync();
      expect(source, contains("path == '/missions'"));
      expect(source, contains('AppRoutes.pendingMissions()'));
    });

    test('the server actually sends that link', () {
      final digest =
          File('../backend/app/services/mission_digest.py').readAsStringSync();
      expect(digest, contains('"link": "/missions"'));
    });
  });

  group('background audio is turned on, not merely depended on', () {
    // just_audio_background sat in pubspec.yaml since sprint 2 with no init
    // call and no service declared, so playback was silenced within seconds of
    // the screen going dark — in the one mode built entirely around that.
    test('the package is initialised at startup', () {
      final main = File('lib/main.dart').readAsStringSync();
      expect(main, contains('JustAudioBackground.init('));
    });

    test('the manifest declares the media service and its permission', () {
      final manifest =
          File('android/app/src/main/AndroidManifest.xml').readAsStringSync();
      expect(manifest, contains('com.ryanheise.audioservice.AudioService'));
      expect(manifest, contains('foregroundServiceType="mediaPlayback"'));
      expect(manifest,
          contains('android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK'));
    });

    test('the player tags its source so the service can raise a notification',
        () {
      // just_audio_background throws without a MediaItem tag, so an untagged
      // source is a crash rather than a silent degradation.
      final player =
          File('lib/features/screen_off/screen_off_player_screen.dart')
              .readAsStringSync();
      expect(player, contains('tag: _mediaItem'));
      expect(player, contains("switchSurface('screen_off')"));
    });
  });

  group('the off-screen alternatives are real content', () {
    test('every band the age gate can refuse has activities', () {
      // The under-2 refusal carried three activities inside its own message
      // text as a stopgap. A gate whose exit is an empty screen is still a
      // dead end.
      final raw = File('assets/data/offscreen_activities.json').readAsStringSync();
      for (final band in ['under-2', '2-3', '4-6', '7-9']) {
        expect(raw, contains('"$band"'), reason: '$band has no section');
      }
    });
  });
}

/// A notifier parked in a fixed state, so the widget can be rendered without a
/// live session. The real one only reaches these states through the network.
class _FixedChildMode extends ChildModeNotifier {
  _FixedChildMode(ChildModeState fixed) : super(TgClient()) {
    state = fixed;
  }
}
