// `horizon_to_action_48h`: a parenting act within two days of a horizon tap
// fires once; worship, other events, and acts after 48 hours do not.
import 'package:almorabbi/core/analytics.dart';
import 'package:almorabbi/core/horizon_attribution.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final logged = <(String, Map<String, Object>?)>[];

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    logged.clear();
    Analytics.debugSink = (name, params) => logged.add((name, params));
  });
  tearDown(() => Analytics.debugSink = null);

  List<Map<String, Object>?> fired() => [
    for (final (n, p) in logged)
      if (n == 'horizon_to_action_48h') p,
  ];

  final tap = DateTime(2026, 12, 1, 9);

  test('an act within 48 hours closes the tap, once', () async {
    await HorizonAttribution.recordTap('ramadan', now: tap);
    await HorizonAttribution.onEvent(
      'lesson_completed',
      now: tap.add(const Duration(hours: 30)),
    );
    expect(fired(), [
      {'gate': 'ramadan', 'action': 'lesson_completed', 'hours': 30},
    ]);
    await HorizonAttribution.onEvent(
      'chat_message_sent',
      now: tap.add(const Duration(hours: 31)),
    );
    expect(fired(), hasLength(1));
  });

  test('after 48 hours the tap is forgotten without an event', () async {
    await HorizonAttribution.recordTap('strip', now: tap);
    await HorizonAttribution.onEvent(
      'followup_answered',
      now: tap.add(const Duration(hours: 49)),
    );
    expect(fired(), isEmpty);
    await HorizonAttribution.onEvent(
      'followup_answered',
      now: tap.add(const Duration(hours: 50)),
    );
    expect(fired(), isEmpty);
  });

  test('only parenting acts count — not opening a game or a program mark', () async {
    await HorizonAttribution.recordTap('age_seven', now: tap);
    for (final other in ['game_opened', 'program_action', 'quran_opened']) {
      await HorizonAttribution.onEvent(other, now: tap);
    }
    expect(fired(), isEmpty);
    await HorizonAttribution.onEvent('next_step_committed', now: tap);
    expect(fired().single!['gate'], 'age_seven');
  });

  test('the Analytics wrapper routes acts through it', () async {
    await HorizonAttribution.recordTap('milestone_due');
    await Analytics.lessonCompleted('l1');
    // onEvent runs unawaited from _log; let it finish.
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);
    expect(fired().single!['action'], 'lesson_completed');
  });
}
