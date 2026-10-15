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
///   4. something Noor noticed — the Ramadan countdown at 30/14/7/1 days;
///   5. the week's rhythm — Monday's plan reveal;
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
  ramadanCountdown,
  mondayPlan,
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
    this.hasWeeklyPlan = false,
    this.firstDay = false,
  });

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
  final bool hasWeeklyPlan;

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
  });

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

  // 4 ── the Ramadan countdown, on its four days only, once each.
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

  // 5 ── Monday: the week's plan is new.
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
