import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/tools/data/tasbeeh_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<TasbeehStore> store([Map<String, Object> seed = const {}]) async {
    SharedPreferences.setMockInitialValues(seed);
    return TasbeehStore(await SharedPreferences.getInstance());
  }

  test('first run starts at zero with the 33 target', () async {
    final s = await store();
    final state = s.load();
    expect(state.count, 0);
    expect(state.target, 33);
    expect(state.isComplete, isFalse);
  });

  test('a count survives being saved and reloaded', () async {
    final s = await store();
    await s.save(const TasbeehState(count: 17, target: 100));
    final again = TasbeehStore(await SharedPreferences.getInstance()).load();
    expect(again.count, 17);
    expect(again.target, 100);
  });

  test('free counting persists as a null target, not as a fallback to 33',
      () async {
    final s = await store();
    await s.save(const TasbeehState(count: 5, target: null));
    final again = s.load();
    expect(again.target, isNull);
    expect(again.count, 5);
    // No target means it can never read as complete.
    expect(again.isComplete, isFalse);
  });

  test('isComplete triggers at the target and stays true past it', () {
    expect(const TasbeehState(count: 32, target: 33).isComplete, isFalse);
    expect(const TasbeehState(count: 33, target: 33).isComplete, isTrue);
    expect(const TasbeehState(count: 34, target: 33).isComplete, isTrue);
  });

  test('corrupt stored JSON falls back to the initial state', () async {
    final s = await store({'tg.tasbeeh.v1': 'not json at all'});
    expect(s.load().count, 0);
    expect(s.load().target, 33);
  });

  test('a negative stored count is clamped, not carried', () async {
    final s = await store({'tg.tasbeeh.v1': '{"count":-4,"target":33}'});
    expect(s.load().count, 0);
  });

  test('an unknown target degrades to free counting', () async {
    // A target this build does not offer — written by a future version, or by
    // a hand edit. Snapping the user to 33 would silently change what they
    // were counting toward.
    final s = await store({'tg.tasbeeh.v1': '{"count":9,"target":7}'});
    expect(s.load().target, isNull);
    expect(s.load().count, 9);
  });
}
