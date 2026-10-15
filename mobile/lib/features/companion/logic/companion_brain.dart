/// «نور يتذكّر» — which one line Noor says when the parent opens «اليوم».
///
/// Pure and deterministic: the same inputs give the same line, no randomness
/// and nothing invented. Every line comes from real data and ends in at most
/// one act, so Today changes every day *for a reason* and always asks for
/// exactly one north-star act.
///
/// Priority (plan §2, «عقل نور»):
///   1. a child's mission waiting for the parent's word (bands 4–18);
///   2. a lesson promise that has fallen due («كيف جرت؟»);
///   3. a server follow-up that has fallen due (then the Today card hides);
///   4. something Noor noticed — a Prayer Journey stage ready, the Journey
///      opening for a child near seven, a milestone due, a birth month he
///      does not know yet, then the Ramadan countdown at 30/14/7/1 days, or
///      «هلّ هلال رمضان» in the month's first nights (once a Hijri year);
///   5. the week's rhythm — Monday's plan reveal; Friday's harvest of the
///      week's lanterns («حصاد الجمعة», phase 3);
///   6. a greeting for the time of day, rotated by date.
///
/// Anti-nag (also plan §2): one line per open; at most two *questions* (2–3)
/// a day; once-only moments never repeat; a line the parent hid stays hidden
/// for the day; quiet mode («وضع هادئ») only greets.
library;

import '../data/companion_store.dart';

enum TimeSlot { dawn, morning, noon, evening, night }

TimeSlot slotOf(DateTime t) {
  final h = t.hour;
  if (h >= 4 && h < 7) return TimeSlot.dawn;
  if (h >= 7 && h < 12) return TimeSlot.morning;
  if (h >= 12 && h < 16) return TimeSlot.noon;
  if (h >= 16 && h < 21) return TimeSlot.evening;
  return TimeSlot.night;
}

/// How Noor looks while saying it — maps to NoorFaceState in the widget.
enum CompanionMood { calm, awake, happy, night }

enum CompanionKind {
  missionsWaiting,
  promiseDue,
  followupDue,
  prayerAdvance,
  prayerInvite,
  milestoneDue,
  birthMonthAsk,
  ramadanCountdown,
  ramadanStart,
  seasonStart,
  mondayPlan,
  fridayHarvest,
  firstDay,
  greeting,
}

/// What the chips under the line do.
enum CompanionAction {
  confirmMissions,
  outcomeWorked,
  outcomeDidntWork,
  outcomeDidntTry,
  openRamadan,
  openPrayerJourney,
  openChildJourney,
  editChild,
  openHarvest,
  openFamilyRoad,
}

/// What /api/programs says about the active child, flattened for the brain.
class ChildNotices {
  const ChildNotices({
    this.prayerEligible = false,
    this.prayerEnrolled = false,
    this.prayerAdvance = false,
    this.ageYears,
    this.ageFromBirthMonth = false,
    this.milestonesDue = 0,
    this.needsBirthMonth = false,
  });

  /// The Prayer Journey has a track for this child (server decides).
  final bool prayerEligible;
  final bool prayerEnrolled;

  /// The server suggests the next stage (parent confirms — never automatic).
  final bool prayerAdvance;
  final int? ageYears;
  final bool ageFromBirthMonth;
  final int milestonesDue;

  /// Milestones need a birth month the profile does not have.
  final bool needsBirthMonth;
}

/// The server follow-up as the brain needs it (kept free of the model class
/// so the brain stays a pure-Dart unit).
class DueFollowup {
  const DueFollowup({
    required this.id,
    required this.childId,
    required this.step,
    this.source = 'chat',
  });
  final int id;
  final int childId;
  final String step;
  final String source;
}

class CompanionInputs {
  const CompanionInputs({
    required this.now,
    required this.memory,
    this.childId,
    this.childName,
    this.missionsWaiting = 0,
    this.missionsChildName,
    this.dueFollowups = const [],
    this.ramadanDaysUntil,
    this.ramadanYear,
    this.ramadanDay,
    this.hasWeeklyPlan = false,
    this.weekActs = 0,
    this.firstDay = false,
    this.notices = const ChildNotices(),
    this.seasonMonth,
    this.seasonDay,
    this.seasonYear,
  });

  /// `hijri_season.month` from /api/programs (`rajab` · `shaban` ·
  /// `dhul_hijjah`), its day and Hijri year — «سماوات المواسم».
  final String? seasonMonth;
  final int? seasonDay;
  final int? seasonYear;

  final ChildNotices notices;

  final DateTime now;
  final CompanionMemory memory;

  /// The active child; null before one exists.
  final int? childId;

  /// The child's real name, or null when it is still the default «طفلي».
  final String? childName;

  /// Claimed-but-unconfirmed missions across the family.
  final int missionsWaiting;

  /// When exactly one child is waiting, whose mission it is.
  final String? missionsChildName;

  final List<DueFollowup> dueFollowups;

  /// `ramadan.days_until_start` from /api/programs, when upcoming.
  final int? ramadanDaysUntil;

  /// The Hijri/Gregorian season id the countdown belongs to (once-only key).
  final int? ramadanYear;

  /// `ramadan.day` from /api/programs while the month is on (1–30), with
  /// the family's own sighting already applied by the server.
  final int? ramadanDay;
  final bool hasWeeklyPlan;

  /// This week's lantern-lighting acts (`/api/family/week`); 0 when there
  /// are none or the server has no lanterns — then Friday has no harvest.
  final int weekActs;

  /// The coins login streak has not left day one.
  final bool firstDay;
}

class CompanionLine {
  const CompanionLine({
    required this.key,
    required this.kind,
    required this.mood,
    this.actions = const [],
    this.name,
    this.step,
    this.count,
    this.ramadanDays,
    this.variant = 1,
    this.promise,
    this.followup,
    this.onceOnly = false,
    this.season,
  });

  /// The season a [CompanionKind.seasonStart] line names.
  final String? season;

  /// Stable id: anti-nag bookkeeping, analytics, hide-for-today.
  final String key;
  final CompanionKind kind;
  final CompanionMood mood;
  final List<CompanionAction> actions;

  /// Display values the widget feeds into the localized sentence.
  final String? name;
  final String? step;
  final int? count;
  final int? ramadanDays;

  /// Which of the four rotated greeting lines (1–4).
  final int variant;

  /// The promise a [CompanionKind.promiseDue] line asks about.
  final Promise? promise;

  /// The follow-up a [CompanionKind.followupDue] line hosts. While set, the
  /// Today follow-up card hides — the question is asked once, here.
  final DueFollowup? followup;

  /// Mark the key seen as soon as it is shown (countdowns, Monday reveal).
  final bool onceOnly;

  bool get isQuestion =>
      kind == CompanionKind.promiseDue || kind == CompanionKind.followupDue;
}

const maxQuestionsPerDay = 2;
const _countdownDays = {30, 14, 7, 1};

/// «هلّ هلال رمضان» may speak on the month's first nights — the moon is
/// called هلال for its first nights — so a family that did not open on day
/// one, or whose day one went to a notice above it, still hears it once.
const kRamadanStartDays = 3;

/// «دخل شهر …» speaks on days 2–4 of a season the server *derived* — a day
/// later than Ramadan's line, so a derived first day that is really the last
/// day of the month before never makes Noor say the month has come early.
const kSeasonLineFirstDay = 2;
const kSeasonLineLastDay = 4;
const kSeasonMonths = {'rajab', 'shaban', 'dhul_hijjah'};
const _outcomeActions = [
  CompanionAction.outcomeWorked,
  CompanionAction.outcomeDidntWork,
  CompanionAction.outcomeDidntTry,
];

/// The line for this open, or null (no active child → the plain greeting).
CompanionLine? pickLine(CompanionInputs i) {
  if (i.childId == null) return null;
  final mem = i.memory;
  final hidden = mem.hiddenOn(i.now);
  final asked = mem.questionsOn(i.now);
  bool open(String key) => !hidden.contains(key);
  // A question already shown today may be shown again (the parent came back
  // to answer it); a new one only while under the daily cap.
  bool mayAsk(String key) =>
      asked.contains(key) || asked.length < maxQuestionsPerDay;

  final greeting = _greeting(i);
  if (mem.quietMode) return greeting;

  // 1 ── a mission waiting for the parent's word.
  if (i.missionsWaiting > 0) {
    final key = 'missions:${dayOf(i.now).toIso8601String()}';
    if (open(key)) {
      return CompanionLine(
        key: key,
        kind: CompanionKind.missionsWaiting,
        mood: CompanionMood.happy,
        count: i.missionsWaiting,
        name: i.missionsChildName,
        actions: const [CompanionAction.confirmMissions],
      );
    }
  }

  // 2 ── a lesson promise for the active child that has fallen due.
  final promises = [
    for (final p in mem.promises)
      if (p.childId == i.childId && p.isDue(i.now)) p,
  ]..sort((a, b) => a.dueOn.compareTo(b.dueOn));
  for (final p in promises) {
    final key = 'promise:${p.id}';
    if (open(key) && mayAsk(key)) {
      return CompanionLine(
        key: key,
        kind: CompanionKind.promiseDue,
        mood: CompanionMood.awake,
        name: i.childName,
        step: p.step,
        promise: p,
        actions: _outcomeActions,
      );
    }
  }

  // 3 ── a server follow-up, unless a promise above already carries it.
  final carried = {
    for (final p in mem.promises)
      if (p.followupId != null) p.followupId!,
  };
  for (final f in i.dueFollowups) {
    if (f.childId != i.childId || carried.contains(f.id)) continue;
    final key = 'followup:${f.id}';
    if (open(key) && mayAsk(key)) {
      return CompanionLine(
        key: key,
        kind: CompanionKind.followupDue,
        mood: CompanionMood.awake,
        name: i.childName,
        step: f.step,
        followup: f,
        actions: _outcomeActions,
      );
    }
  }

  // 4 ── what Noor noticed about this child. Each speaks at most once a
  // month (a stage ready: once a week) — a nudge, never a nag.
  final n = i.notices;
  final month = '${i.now.year}-${i.now.month}';
  final week = dayOf(
    i.now,
  ).subtract(Duration(days: i.now.weekday - 1)).toIso8601String();
  CompanionLine? notice(String key, CompanionKind kind, CompanionAction a) =>
      open(key) && !mem.seenKeys.contains(key)
      ? CompanionLine(
          key: key,
          kind: kind,
          mood: CompanionMood.happy,
          name: i.childName,
          actions: [a],
          onceOnly: true,
        )
      : null;
  final noticed = [
    if (n.prayerEnrolled && n.prayerAdvance)
      notice(
        'prayer-advance:${i.childId}:$week',
        CompanionKind.prayerAdvance,
        CompanionAction.openPrayerJourney,
      ),
    // Seven is when the Journey's own content begins in earnest; a child of
    // six already counts so the family can start gently. Only from a real
    // birth month — an age-band guess is too coarse to say «near seven».
    if (n.prayerEligible &&
        !n.prayerEnrolled &&
        n.ageFromBirthMonth &&
        (n.ageYears == 6 || n.ageYears == 7))
      notice(
        'prayer-invite:${i.childId}:$month',
        CompanionKind.prayerInvite,
        CompanionAction.openPrayerJourney,
      ),
    if (n.milestonesDue > 0)
      notice(
        'milestone:${i.childId}:$month',
        CompanionKind.milestoneDue,
        CompanionAction.openChildJourney,
      ),
    if (n.needsBirthMonth)
      notice(
        'birth-month:${i.childId}:$month',
        CompanionKind.birthMonthAsk,
        CompanionAction.editChild,
      ),
  ].whereType<CompanionLine>();
  if (noticed.isNotEmpty) return noticed.first;

  // 5 ── the Ramadan countdown, on its four days only, once each.
  final d = i.ramadanDaysUntil;
  if (d != null && _countdownDays.contains(d)) {
    final key = 'ramadan:${i.ramadanYear ?? i.now.year}:$d';
    if (open(key) && !mem.seenKeys.contains(key)) {
      return CompanionLine(
        key: key,
        kind: CompanionKind.ramadanCountdown,
        mood: CompanionMood.happy,
        name: i.childName,
        ramadanDays: d,
        actions: const [CompanionAction.openRamadan],
        onceOnly: true,
      );
    }
  }

  // 5 ── and when it comes: «هلّ هلال رمضان», once a Hijri year. In the
  // countdown's place — the countdown is before the month, this is in it,
  // so the two never meet and nothing above moves.
  final day = i.ramadanDay;
  final hijri = i.ramadanYear;
  if (day != null && hijri != null && day >= 1 && day <= kRamadanStartDays) {
    final key = 'ramadan-start:$hijri';
    if (open(key) && !mem.seenKeys.contains(key)) {
      return CompanionLine(
        key: key,
        kind: CompanionKind.ramadanStart,
        mood: CompanionMood.happy,
        name: i.childName,
        actions: const [CompanionAction.openRamadan],
        onceOnly: true,
      );
    }
  }

  // 5 ── «دخل شهر رجب / شعبان / ذي الحجة»: once a Hijri year each, in the
  // Ramadan lines' place: Sha'ban's days 2–4 are 27–28 days before the
  // month, so the seasons never meet the month or its countdown days.
  final sm = i.seasonMonth;
  final sd = i.seasonDay;
  if (sm != null &&
      kSeasonMonths.contains(sm) &&
      sd != null &&
      sd >= kSeasonLineFirstDay &&
      sd <= kSeasonLineLastDay) {
    final key = 'season:$sm:${i.seasonYear ?? i.now.year}';
    if (open(key) && !mem.seenKeys.contains(key)) {
      return CompanionLine(
        key: key,
        kind: CompanionKind.seasonStart,
        mood: CompanionMood.calm,
        name: i.childName,
        season: sm,
        actions: const [CompanionAction.openFamilyRoad],
        onceOnly: true,
      );
    }
  }

  // 6 ── Monday: the week's plan is new.
  if (i.now.weekday == DateTime.monday && i.hasWeeklyPlan) {
    final key = 'monday:${dayOf(i.now).toIso8601String()}';
    if (open(key) && !mem.seenKeys.contains(key)) {
      return CompanionLine(
        key: key,
        kind: CompanionKind.mondayPlan,
        mood: CompanionMood.calm,
        name: i.childName,
        onceOnly: true,
      );
    }
  }

  // 5 ── Friday: the week's harvest — once, and only for a week with
  // lanterns (an empty week is never pointed at).
  if (i.now.weekday == DateTime.friday && i.weekActs > 0) {
    final key = 'harvest:${dayOf(i.now).toIso8601String()}';
    if (open(key) && !mem.seenKeys.contains(key)) {
      return CompanionLine(
        key: key,
        kind: CompanionKind.fridayHarvest,
        mood: CompanionMood.happy,
        name: i.childName,
        count: i.weekActs,
        actions: const [CompanionAction.openHarvest],
        onceOnly: true,
      );
    }
  }

  return greeting;
}

CompanionLine _greeting(CompanionInputs i) {
  final slot = slotOf(i.now);
  if (i.firstDay) {
    return CompanionLine(
      key: 'firstday',
      kind: CompanionKind.firstDay,
      mood: CompanionMood.happy,
      name: i.childName,
    );
  }
  // Rotate by day of year so the line changes daily, but stays put within
  // the day (opening the app twice does not shuffle Noor's words).
  final dayOfYear = dayOf(i.now).difference(DateTime(i.now.year)).inDays;
  final variant = dayOfYear % 4 + 1;
  return CompanionLine(
    key: 'greeting:${slot.name}:$variant',
    kind: CompanionKind.greeting,
    mood: slot == TimeSlot.night ? CompanionMood.night : CompanionMood.calm,
    name: i.childName,
    variant: variant,
  );
}
