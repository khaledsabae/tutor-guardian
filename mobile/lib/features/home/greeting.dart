/// Time-aware greeting copy («نور والقناديل» phase 1 — النصوص).
///
/// The greeting used to be one string for every hour of the day, and it told
/// a parent on their very first evening that a journey «مستمرة» — a journey
/// that had not started. The hour decides صباح/مساء; the coins login streak
/// decides whether this is day one, in which case the line says so plainly
/// instead of claiming continuity. Callers pass `DateTime.now()`; tests pass
/// a fixed clock, which is the point of keeping these pure.
library;

import '../../../l10n/app_localizations.dart';

/// Whether the AppBar's sun is still up — ☀️ from 6:00 to 17:59, 🌙 after.
bool sunIsUp(DateTime now) => now.hour >= 6 && now.hour < 18;

/// Whether the greeting says صباح. Morning runs until 15:59; «مساء الخير»
/// from the afternoon onward is how the greeting reads naturally in Arabic
/// even before the sky darkens.
bool isMorning(DateTime now) => now.hour >= 4 && now.hour < 16;

/// The greeting line for [name]: morning or evening, continuing or — when
/// [firstDay] is true, i.e. the daily-login streak has not left day one —
/// an honest «اليوم أول يوم» with no «مستمرة» in it.
String greetingFor(
  AppLocalizations l10n,
  String name,
  DateTime now, {
  required bool firstDay,
}) {
  final morning = isMorning(now);
  if (firstDay) {
    return morning
        ? l10n.greetingMorningFirst(name)
        : l10n.greetingEveningFirst(name);
  }
  return morning
      ? l10n.greetingMorningName(name)
      : l10n.greetingEveningName(name);
}

/// The Today AppBar title: ☀️ by day, 🌙 by night. The original `todaySun`
/// key stays (Maestro selects by key); this picks between its two
/// time-of-day values.
String todayTitle(AppLocalizations l10n, DateTime now) =>
    sunIsUp(now) ? l10n.todaySunDay : l10n.todaySunNight;
