/// «صورة حيّة» experiment (2026-10-24, Khaled): do children like the
/// stories more with living pictures — the camera following the narrator —
/// or with the same paintings standing still?
///
///  * Each device is in one arm for good: `motion` or `static`, from a hash
///    of its device id, while `/api/app-config` → `story_motion_mode` is
///    "ab" (the default, and what a missing field or no network mean). The
///    server can put everyone in one arm ("motion" / "static") — the
///    month-end switch, no release needed. The last mode the server said is
///    kept for offline launches.
///  * Both arms read the same paintings with the same narration and the
///    same lit sentence; only the picture's motion differs. A device with
///    the system's reduce-motion on always sees it still, and its events say
///    so (`reduce_motion`), so the analysis leaves it out.
///  * Events (no PII — a device id, a bundled story id, a language, page
///    numbers, a 1–3 rating) go to GA4 and to the backend
///    (POST /api/stories/events), where the weekly report reads them.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../api/tg_client.dart';
import '../../../core/analytics.dart';
import '../../../main.dart' show appConfigProvider;
import '../../../state/chat_notifier.dart' show tgClientProvider;

const kStoryArms = ['motion', 'static'];
const kStoryMotionModeKey = 'tg.story_motion_mode';

/// The arm a device is in. [mode] is the server's `story_motion_mode`;
/// anything but "motion" / "static" means "ab". Without a device id there is
/// nothing stable to split on, so the picture keeps still.
String resolveStoryMotionArm({String? mode, String? deviceId}) {
  final m = mode?.trim().toLowerCase();
  if (m == 'motion' || m == 'static') return m!;
  if (deviceId == null || deviceId.isEmpty) return 'static';
  return fnv1a32('story_motion:$deviceId').isEven ? 'motion' : 'static';
}

/// FNV-1a, 32 bit — stable across runs, platforms and app versions (Dart's
/// own hashCode is not).
int fnv1a32(String s) {
  var h = 0x811c9dc5;
  for (final b in utf8.encode(s)) {
    h ^= b;
    h = (h * 0x01000193) & 0xffffffff;
  }
  return h;
}

/// The server's mode, remembered for offline launches; "ab" when it never
/// said.
Future<String> storyMotionMode(Future<Map<String, dynamic>> config) async {
  // Listen before the first await, so a failed config is handled here and
  // never surfaces as an uncaught error.
  // (The config fetch has its own HTTP timeout.)
  final settled = config.then<Map<String, dynamic>?>(
    (c) => c,
    onError: (Object _) => null,
  );
  final prefs = await SharedPreferences.getInstance();
  try {
    final cfg = await settled;
    if (cfg == null) return prefs.getString(kStoryMotionModeKey) ?? 'ab';
    final raw = cfg['story_motion_mode'];
    final mode = raw is String && kStoryArms.contains(raw) ? raw : 'ab';
    await prefs.setString(kStoryMotionModeKey, mode);
    return mode;
  } catch (_) {
    return prefs.getString(kStoryMotionModeKey) ?? 'ab';
  }
}

final storyMotionArmProvider = FutureProvider<String>((ref) async {
  final mode = await storyMotionMode(ref.watch(appConfigProvider.future));
  String? deviceId;
  try {
    deviceId = await ref.read(tgClientProvider).experimentDeviceId();
  } catch (_) {}
  return resolveStoryMotionArm(mode: mode, deviceId: deviceId);
});

/// Where a story's events go. Injected into the reader so tests see them.
typedef StoryEventSink =
    void Function(String name, Map<String, Object?> params);

/// GA4 and the backend, best effort — an event is never worth an error.
StoryEventSink storyEventsTo(TgClient client) => (name, params) {
  final ga = <String, Object>{
    for (final MapEntry(:key, :value) in params.entries)
      if (value != null) key: value is bool ? (value ? 1 : 0) : value,
  };
  unawaited(Analytics.storyEvent(name, ga));
  unawaited(
    client
        .postStoryEvents([
          {'name': name, ...params},
        ])
        .catchError((Object _) {}),
  );
};

/// «عجبتك الحكاية؟» is asked at most once per story per device.
String storyRatedKey(String storyId) => 'tg.story.rated.$storyId';
