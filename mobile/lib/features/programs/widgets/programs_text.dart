/// One-line summaries shared by the Home card and the programs list, so the
/// two never describe the same state in different words.
library;

import 'package:flutter/widgets.dart';

import '../../../l10n/app_localizations.dart';
import '../data/programs_models.dart';

/// "Ramadan in 12 days" · "Day 3 of 30" · "Eid Mubarak…" · "After Ramadan:
/// week 2". Null when there is nothing to say (off season, no season).
String? ramadanStatusLine(BuildContext context, RamadanOverview ramadan) {
  final l10n = AppLocalizations.of(context);
  final season = ramadan.season;
  if (season == null) return null;
  switch (ramadan.state) {
    case RamadanState.upcoming:
      final days = ramadan.daysUntilStart;
      return days == null ? null : l10n.ramadanCountdown(days);
    case RamadanState.ramadan:
      final day = ramadan.day;
      return day == null ? null : l10n.ramadanDayOf(day, season.days);
    case RamadanState.eid:
      return l10n.programsRamadanEid;
    case RamadanState.after:
      final week = ramadan.afterWeek;
      return week == null ? null : l10n.programsRamadanAfterWeek(week);
    case RamadanState.offSeason:
      return null;
  }
}

/// Where a child stands on the Prayer Journey — never as a shortfall.
String prayerStatusLine(AppLocalizations l10n, PrayerOverview prayer) {
  if (prayer.enrolled) {
    if (prayer.canGraduate) return l10n.programsPrayerCanGraduate;
    if (prayer.pendingConfirmations > 0) {
      return l10n.programsPrayerPending(prayer.pendingConfirmations);
    }
    if (prayer.advanceSuggested) return l10n.programsPrayerAdvance;
    final track = prayer.track;
    if (track == PrayerTrack.journey && prayer.stage != null) {
      // The overview carries no stage count, so no "of N" here.
      return l10n.prayerStageN(prayer.stage!);
    }
    return prayerTrackName(l10n, track);
  }
  return l10n.programsPrayerNotStarted(
    prayerTrackName(l10n, prayer.eligibleTrack),
  );
}

/// The track's short name, for list rows (screens use the server's titles).
String prayerTrackName(AppLocalizations l10n, PrayerTrack? track) =>
    switch (track) {
      PrayerTrack.preparation => l10n.prayerTrackPreparation,
      PrayerTrack.ownership => l10n.prayerTrackOwnership,
      _ => l10n.prayerTrackJourney,
    };
