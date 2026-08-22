/// The bug this pins: `tz.local` left at UTC, so a 6 AM reminder fired at 6 AM
/// UTC — 9am in Riyadh, 1pm in Jakarta, 2am on the US east coast, 11pm the
/// evening before in California. Fourteen days were queued correctly every
/// time, which is why it read as working.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import 'package:almorabbi/features/adhkar/services/local_timezone.dart';

void main() {
  setUpAll(tzdata.initializeTimeZones);

  test('a known zone id is used as given', () {
    expect(resolveLocalLocation('Asia/Riyadh', const Duration(hours: 3)).name,
        'Asia/Riyadh');
    expect(resolveLocalLocation('Africa/Cairo', const Duration(hours: 3)).name,
        'Africa/Cairo');
    expect(
        resolveLocalLocation('America/New_York', const Duration(hours: -4)).name,
        'America/New_York');
  });

  test('the resolved zone is not UTC for an offset user', () {
    // The regression itself, stated plainly.
    final riyadh = resolveLocalLocation('Asia/Riyadh', const Duration(hours: 3));
    expect(riyadh.name, isNot('UTC'));
    expect(riyadh.currentTimeZone.offset, const Duration(hours: 3).inMilliseconds);
  });

  test('6 AM in the resolved zone is 6 AM on the wall clock, not 9', () {
    // What the user actually experiences, end to end.
    final riyadh = resolveLocalLocation('Asia/Riyadh', const Duration(hours: 3));
    final scheduled = tz.TZDateTime(riyadh, 2026, 8, 23, 6);
    expect(scheduled.hour, 6);
    // 06:00 +03 is 03:00 UTC. Under the bug it was 06:00 UTC = 09:00 local.
    expect(scheduled.toUtc().hour, 3);
  });

  group('fallback when the name is no use', () {
    test('an unknown id falls back to a zone with the same offset', () {
      // A zone added or renamed after this build's database was published.
      final loc =
          resolveLocalLocation('Mars/Olympus_Mons', const Duration(hours: 3));
      expect(loc.name, isNot('UTC'));
      expect(loc.currentTimeZone.offset, const Duration(hours: 3).inMilliseconds);
    });

    test('a null id falls back to the device offset', () {
      final loc = resolveLocalLocation(null, const Duration(hours: -5));
      expect(loc.currentTimeZone.offset,
          const Duration(hours: -5).inMilliseconds);
    });

    test('an empty id is treated as no id', () {
      final loc = resolveLocalLocation('   ', const Duration(hours: 7));
      expect(loc.currentTimeZone.offset, const Duration(hours: 7).inMilliseconds);
    });

    test('a half-hour offset resolves too', () {
      // India and Iran are not whole hours; an offset match must not assume so.
      final loc =
          resolveLocalLocation(null, const Duration(hours: 5, minutes: 30));
      expect(loc.currentTimeZone.offset,
          const Duration(hours: 5, minutes: 30).inMilliseconds);
    });

    test('a zero offset is UTC without scanning', () {
      expect(resolveLocalLocation(null, Duration.zero).name, 'UTC');
    });

    test('an impossible offset degrades to UTC rather than throwing', () {
      expect(resolveLocalLocation(null, const Duration(hours: 99)).name, 'UTC');
    });

    test('the offset fallback prefers a named region over an Etc/ alias', () {
      final loc = resolveLocalLocation(null, const Duration(hours: 3));
      expect(loc.name, contains('/'));
      expect(loc.name.startsWith('Etc/'), isFalse);
    });
  });

  test('a trimmed id still matches', () {
    expect(resolveLocalLocation(' Asia/Riyadh ', Duration.zero).name,
        'Asia/Riyadh');
  });
}
