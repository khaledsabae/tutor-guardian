/// The converter's claim is narrow and this file is where it gets checked.
///
/// Two different things are tested, and the difference matters:
///
///  * **Internal consistency** — round-trip, month lengths matching the day
///    count of the year. These are absolute: a failure is a bug.
///  * **External agreement** — the published 1 Muharram dates. These are
///    tolerance checks, because the algorithm is arithmetic and the calendar
///    it is compared against is not. The tolerance is asserted as ≤ 1 day, so
///    if someone changes the epoch and the error grows, the test says so
///    instead of quietly accepting a worse converter.
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/tools/data/hijri_date.dart';

void main() {
  group('internal consistency', () {
    test('round-trips every day for 110 years', () {
      var jdn = gregorianToJdn(1950, 1, 1);
      final end = gregorianToJdn(2060, 1, 1);
      var checked = 0;
      while (jdn < end) {
        final g = jdnToGregorian(jdn);
        final h = gregorianToHijri(g);
        final back = hijriToGregorian(h.year, h.month, h.day);
        expect(back, g, reason: 'round-trip broke at $g → $h');
        checked++;
        jdn++;
      }
      // Guard the premise: if the loop silently did nothing, the expects above
      // prove nothing.
      expect(checked, greaterThan(40000));
    });

    test('month lengths sum to the length of the year', () {
      for (var y = 1400; y <= 1480; y++) {
        final table =
            List.generate(12, (i) => hijriMonthLength(y, i + 1)).reduce((a, b) => a + b);
        final span = hijriToJdn(y + 1, 1, 1) - hijriToJdn(y, 1, 1);
        expect(table, span, reason: 'year $y: table $table vs span $span');
        expect(table, isHijriLeapYear(y) ? 355 : 354);
      }
    });

    test('Dhu al-Hijjah gains its 30th day only in a leap year', () {
      expect(hijriMonthLength(1445, 12), 30);
      expect(isHijriLeapYear(1445), isTrue);
      expect(hijriMonthLength(1446, 12), 29);
      expect(isHijriLeapYear(1446), isFalse);
    });
  });

  group('agreement with the published calendar', () {
    // 1 Muharram, as published for these years.
    const newYears = <int, List<int>>{
      1442: [2020, 8, 20],
      1443: [2021, 8, 9],
      1444: [2022, 7, 30],
      1445: [2023, 7, 19],
      1446: [2024, 7, 7],
      1447: [2025, 6, 26],
      1448: [2026, 6, 16],
    };

    test('1 Muharram lands within one day, every year', () {
      newYears.forEach((hy, g) {
        final computed = hijriToJdn(hy, 1, 1);
        final published = gregorianToJdn(g[0], g[1], g[2]);
        expect(
          (computed - published).abs(),
          lessThanOrEqualTo(1),
          reason: '1 Muharram $hy is ${computed - published} days off',
        );
      });
    });

    test('hijriIsApproximate stays true while the maths stays arithmetic', () {
      // The disclosure on the screen is driven by this. If a future change
      // swaps in a real Umm al-Qura table, this test is the reminder that the
      // wording has to change with it.
      expect(hijriIsApproximate, isTrue);
    });
  });

  test('Arabic-Indic digits', () {
    expect(arabicDigits(0), '٠');
    expect(arabicDigits(1448), '١٤٤٨');
    expect(arabicDigits(30), '٣٠');
  });

  test('month names are twelve and indexed from Muharram', () {
    expect(hijriMonthNames, hasLength(12));
    expect(const HijriDate(1448, 1, 1).monthName, 'محرّم');
    expect(const HijriDate(1448, 9, 1).monthName, 'رمضان');
    expect(const HijriDate(1448, 12, 1).monthName, 'ذو الحجة');
  });
}
