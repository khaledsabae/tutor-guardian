/// Hijri ⇄ Gregorian conversion.
///
/// **What this is, precisely.** The tabular ("arithmetic" / Kuwaiti) Islamic
/// calendar: a 30-year cycle of 11 leap years, months alternating 30 and 29
/// days. It is deterministic, offline, and reversible.
///
/// **What it is not.** It is not Umm al-Qura, and it is not moon sighting.
/// A real month begins when the crescent is seen, and the Saudi civil calendar
/// is set from its own published table. Against either of those this arithmetic
/// can land a day early or a day late, and near the start of Ramadan or an Eid
/// that one day is the whole question.
///
/// So the screen that uses this says so, in words, next to the result. A
/// converter that quietly presents an arithmetic estimate as the date is worse
/// than no converter: the user cannot tell they are being approximated at.
/// [hijriIsApproximate] exists so that disclosure cannot be forgotten by a
/// future caller — it is a fact about this algorithm, not a UI preference.
library;

/// This conversion is arithmetic, not observational. Always true here; kept as
/// a named constant so the disclosure in the UI has something to point at.
const bool hijriIsApproximate = true;

/// Arabic names of the Hijri months, index 0 = Muharram.
const List<String> hijriMonthNames = <String>[
  'محرّم',
  'صفر',
  'ربيع الأول',
  'ربيع الآخر',
  'جمادى الأولى',
  'جمادى الآخرة',
  'رجب',
  'شعبان',
  'رمضان',
  'شوّال',
  'ذو القعدة',
  'ذو الحجة',
];

/// A date on the Hijri calendar.
class HijriDate {
  final int year;

  /// 1..12, Muharram = 1.
  final int month;

  /// 1..30.
  final int day;

  const HijriDate(this.year, this.month, this.day);

  String get monthName => hijriMonthNames[month - 1];

  @override
  String toString() => '$year-$month-$day';

  @override
  bool operator ==(Object other) =>
      other is HijriDate &&
      other.year == year &&
      other.month == month &&
      other.day == day;

  @override
  int get hashCode => Object.hash(year, month, day);
}

// Epoch offset, chosen by measurement rather than by convention.
//
// The textbook constant for this formula family is 1948439. Checked against
// the published 1 Muharram dates for 1442–1448 AH, that constant runs a full
// day late on every one of the seven. 1948438 lands exactly on four of them
// and one day early on the other three — so the worst case drops from "always
// off" to "off by one, sometimes". That is as close as arithmetic gets to a
// calendar that is ultimately set by sighting; the remaining day is what the
// disclosure on the screen is for.
const int _islamicEpochJdn = 1948438;

/// Julian Day Number for a Gregorian date at noon.
int gregorianToJdn(int year, int month, int day) {
  final a = (14 - month) ~/ 12;
  final y = year + 4800 - a;
  final m = month + 12 * a - 3;
  return day +
      (153 * m + 2) ~/ 5 +
      365 * y +
      y ~/ 4 -
      y ~/ 100 +
      y ~/ 400 -
      32045;
}

/// Gregorian date for a Julian Day Number.
DateTime jdnToGregorian(int jdn) {
  final a = jdn + 32044;
  final b = (4 * a + 3) ~/ 146097;
  final c = a - (146097 * b) ~/ 4;
  final d = (4 * c + 3) ~/ 1461;
  final e = c - (1461 * d) ~/ 4;
  final m = (5 * e + 2) ~/ 153;
  final day = e - (153 * m + 2) ~/ 5 + 1;
  final month = m + 3 - 12 * (m ~/ 10);
  final year = 100 * b + d - 4800 + m ~/ 10;
  return DateTime(year, month, day);
}

/// True when [year] is a leap year in the 30-year tabular cycle (355 days).
///
/// The eleven leap years of the cycle are the "Kuwaiti"/civil set, which is
/// also what most tabular implementations use.
bool isHijriLeapYear(int year) {
  // ((11 * year) + 14) mod 30 < 11
  final r = ((11 * year) + 14) % 30;
  return (r < 0 ? r + 30 : r) < 11;
}

/// Days in a Hijri month: 30 for odd months, 29 for even, plus one for Dhu
/// al-Hijjah in a leap year.
int hijriMonthLength(int year, int month) {
  if (month.isOdd) return 30;
  if (month == 12 && isHijriLeapYear(year)) return 30;
  return 29;
}

/// Julian Day Number for a Hijri date.
int hijriToJdn(int year, int month, int day) {
  return day +
      (29.5 * (month - 1)).ceil() +
      (year - 1) * 354 +
      (3 + 11 * year) ~/ 30 +
      _islamicEpochJdn;
}

/// Converts a Gregorian [date] to its Hijri equivalent.
HijriDate gregorianToHijri(DateTime date) {
  final jdn = gregorianToJdn(date.year, date.month, date.day);

  // Estimate the year, then walk it into place. The closed-form estimate can
  // be off by one around a year boundary; correcting by comparison is shorter
  // and safer than trying to make the estimate exact.
  var year = ((30 * (jdn - _islamicEpochJdn) + 10646) ~/ 10631);
  while (hijriToJdn(year, 1, 1) > jdn) {
    year--;
  }
  while (hijriToJdn(year + 1, 1, 1) <= jdn) {
    year++;
  }

  var month = 1;
  while (month < 12 && hijriToJdn(year, month + 1, 1) <= jdn) {
    month++;
  }

  final day = jdn - hijriToJdn(year, month, 1) + 1;
  return HijriDate(year, month, day);
}

/// Converts a Hijri date to its Gregorian equivalent.
DateTime hijriToGregorian(int year, int month, int day) =>
    jdnToGregorian(hijriToJdn(year, month, day));

/// Renders [n] in Arabic-Indic digits.
String arabicDigits(int n) {
  const d = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
  final neg = n < 0;
  final s = n.abs().toString().split('').map((c) => d[int.parse(c)]).join();
  return neg ? '-$s' : s;
}
