import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/main.dart';

/// The gate used to fall open on any fetch failure, so builds below the
/// minimum kept running whenever the config call timed out. It must now fall
/// back to the last confirmed minimum instead.
void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('a successful fetch caches the minimum build number', () async {
    final prefs = await SharedPreferences.getInstance();

    final config = await resolveAppConfig(
      fetch: () async => {'minimum_build_number': 81, 'store_url': 'x'},
      prefs: prefs,
    );

    expect(config['minimum_build_number'], 81);
    expect(prefs.getInt(kCachedMinBuildKey), 81);
  });

  test('a failed fetch still enforces the last confirmed minimum', () async {
    final prefs = await SharedPreferences.getInstance();
    await resolveAppConfig(
      fetch: () async => {'minimum_build_number': 81},
      prefs: prefs,
    );

    final config = await resolveAppConfig(
      fetch: () async => throw Exception('timeout'),
      prefs: prefs,
    );

    expect(config['minimum_build_number'], 81);
  });

  test('a failed fetch with no cache rethrows so first launch stays open',
      () async {
    final prefs = await SharedPreferences.getInstance();

    expect(
      () => resolveAppConfig(
        fetch: () async => throw Exception('timeout'),
        prefs: prefs,
      ),
      throwsException,
    );
  });

  test('a lowered minimum overwrites the cache', () async {
    final prefs = await SharedPreferences.getInstance();
    await resolveAppConfig(
      fetch: () async => {'minimum_build_number': 81},
      prefs: prefs,
    );

    await resolveAppConfig(
      fetch: () async => {'minimum_build_number': 70},
      prefs: prefs,
    );

    expect(prefs.getInt(kCachedMinBuildKey), 70);
  });
}
