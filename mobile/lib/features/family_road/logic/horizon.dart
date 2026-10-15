/// «على الأفق» — the gates ahead on «درب {الاسم}» (عالم الأسرة).
///
/// Pure and deterministic, like Noor's brain: the same server answers give
/// the same gates, nothing is invented, and every gate leads to one act. A
/// gate is something real that is coming for this family and this child —
/// the next path, a milestone the server says is due or near, seven years
/// old, Ramadan — never a task left undone. There is no «فاتك» gate and no
/// gate that counts worship.
///
/// The road opens on what is ahead, because the empty road is the risk:
/// most families have done one lesson or none, so a road that began with
/// what was done would open empty. The horizon is never empty while the
/// server knows a Ramadan, a path or a milestone.
library;

/// What a gate is, and so where its button goes.
enum GateKind {
  /// The next path to begin («المسار التالي») → its page.
  nextPath,

  /// A milestone the server says is due now → its card.
  milestoneDue,

  /// The month of Ramadan itself → the family's Ramadan.
  ramadanNow,

  /// Ramadan ahead (`days_until_start`) → the family's Ramadan.
  ramadan,

  /// Seven years old, from a real birth month → the Prayer Journey.
  ageSeven,

  /// The nearest upcoming milestone → its card.
  milestone,

  /// No birth month yet: the dated gates cannot be placed → edit the child.
  birthMonth;

  /// The GA4 spelling (a small closed set).
  String get wire => switch (this) {
    GateKind.nextPath => 'next_path',
    GateKind.milestoneDue => 'milestone_due',
    GateKind.ramadanNow => 'ramadan_now',
    GateKind.ramadan => 'ramadan',
    GateKind.ageSeven => 'age_seven',
    GateKind.milestone => 'milestone',
    GateKind.birthMonth => 'birth_month',
  };
}

class HorizonGate {
  const HorizonGate({
    required this.kind,
    this.days,
    this.months,
    this.title,
    this.pathId,
    this.milestoneKey,
    this.ramadanDay,
  });

  final GateKind kind;

  /// Days until it, when dated (0 = now).
  final int? days;

  /// Whole months until it, for the age gates.
  final int? months;

  /// Server text in the reader's language: a path or milestone title.
  final String? title;
  final String? pathId;
  final String? milestoneKey;

  /// The day of the month while Ramadan is on.
  final int? ramadanDay;

  /// Whether the «على الأفق» strip on Today may name it: a gate with a time
  /// on it. The next path is already ① on Today, and the birth month is a
  /// question, not a horizon.
  bool get onStrip =>
      kind != GateKind.nextPath && kind != GateKind.birthMonth;

  @override
  String toString() => 'HorizonGate(${kind.wire}, days: $days)';
}

/// What the server said about the active child, flattened for the horizon.
class HorizonChild {
  const HorizonChild({
    this.ageMonths,
    this.ageFromBirthMonth = false,
    this.band,
    this.prayerEligible = false,
    this.milestonesDue = 0,
    this.needsBirthMonth = false,
  });

  final int? ageMonths;
  final bool ageFromBirthMonth;
  final String? band;
  final bool prayerEligible;
  final int milestonesDue;
  final bool needsBirthMonth;
}

/// One milestone as the horizon needs it.
class HorizonMilestone {
  const HorizonMilestone({
    required this.key,
    required this.title,
    required this.state,
    this.dueOn,
  });

  final String key;
  final String title;

  /// `due | upcoming | library | past`.
  final String state;
  final DateTime? dueOn;
}

class HorizonInputs {
  const HorizonInputs({
    required this.today,
    this.child = const HorizonChild(),
    this.ramadanState,
    this.ramadanDaysUntil,
    this.ramadanDay,
    this.milestones = const [],
    this.nextPathId,
    this.nextPathTitle,
  });

  /// The family's local date (time is ignored).
  final DateTime today;
  final HorizonChild child;

  /// `upcoming | ramadan | eid | after | off_season`, or null (no server).
  final String? ramadanState;
  final int? ramadanDaysUntil;
  final int? ramadanDay;
  final List<HorizonMilestone> milestones;
  final String? nextPathId;
  final String? nextPathTitle;
}

/// Seven: when the Prayer Journey's own content begins in earnest.
const kSevenMonths = 84;

/// The age gate shows from two years before it — further off it is not a
/// horizon yet, only a date.
const kAgeHorizonMonths = 24;

/// A dated milestone shows from this far off.
const kMilestoneHorizonDays = 540;

/// At most this many gates on the road: a horizon, not a checklist.
const kMaxGates = 4;

/// The milestone that *is* seven years old — not shown twice.
const kPrayerStartKey = 'prayer_start';

/// The gates ahead, nearest first.
List<HorizonGate> horizonGates(HorizonInputs i) {
  final today = DateTime(i.today.year, i.today.month, i.today.day);
  final gates = <HorizonGate>[];
  final c = i.child;

  // The next path: undated, and the nearest of all — it can begin today.
  final pathId = i.nextPathId;
  if (pathId != null && pathId.isNotEmpty) {
    gates.add(
      HorizonGate(
        kind: GateKind.nextPath,
        pathId: pathId,
        title: i.nextPathTitle,
      ),
    );
  }

  // A milestone due now.
  final due = i.milestones.where((m) => m.state == 'due').toList();
  if (c.milestonesDue > 0 || due.isNotEmpty) {
    final first = due.isEmpty ? null : due.first;
    gates.add(
      HorizonGate(
        kind: GateKind.milestoneDue,
        days: 0,
        title: first?.title,
        milestoneKey: first?.key,
      ),
    );
  }

  // Ramadan: the month itself, or the days until it.
  if (i.ramadanState == 'ramadan' && i.ramadanDay != null) {
    gates.add(
      HorizonGate(kind: GateKind.ramadanNow, days: 0, ramadanDay: i.ramadanDay),
    );
  } else if (i.ramadanState == 'upcoming' &&
      i.ramadanDaysUntil != null &&
      i.ramadanDaysUntil! >= 0) {
    gates.add(HorizonGate(kind: GateKind.ramadan, days: i.ramadanDaysUntil));
  }

  // Seven, from a real birth month only — a band is too coarse to date it.
  var sevenShown = false;
  final months = c.ageMonths;
  if (c.ageFromBirthMonth &&
      months != null &&
      months < kSevenMonths &&
      kSevenMonths - months <= kAgeHorizonMonths) {
    final until = kSevenMonths - months;
    gates.add(
      HorizonGate(
        kind: GateKind.ageSeven,
        months: until,
        days: _monthsAhead(today, until).difference(today).inDays,
      ),
    );
    sevenShown = true;
  }

  // The nearest dated milestone ahead.
  final ahead =
      i.milestones
          .where(
            (m) =>
                m.state == 'upcoming' &&
                m.dueOn != null &&
                !(sevenShown && m.key == kPrayerStartKey),
          )
          .map((m) => (m, _day(m.dueOn!).difference(today).inDays))
          .where((e) => e.$2 > 0 && e.$2 <= kMilestoneHorizonDays)
          .toList()
        ..sort((a, b) => a.$2.compareTo(b.$2));
  if (ahead.isNotEmpty) {
    final (m, days) = ahead.first;
    gates.add(
      HorizonGate(
        kind: GateKind.milestone,
        days: days,
        months: (days / 30.44).round(),
        title: m.title,
        milestoneKey: m.key,
      ),
    );
  }

  // Undated first, then by distance; the stable sort keeps the order above
  // between gates at the same distance.
  final sorted = [...gates]
    ..sort((a, b) {
      final da = a.kind == GateKind.nextPath ? -1 : (a.days ?? 0);
      final db = b.kind == GateKind.nextPath ? -1 : (b.days ?? 0);
      return da.compareTo(db);
    });

  // Without a birth month the dated gates cannot be placed: say so, last.
  if (c.needsBirthMonth && !c.ageFromBirthMonth) {
    sorted.add(const HorizonGate(kind: GateKind.birthMonth));
  }
  return sorted.length > kMaxGates ? sorted.sublist(0, kMaxGates) : sorted;
}

/// The gate the «على الأفق» strip names, or null (the strip is not shown).
HorizonGate? stripGate(List<HorizonGate> gates) {
  for (final g in gates) {
    if (g.onStrip) return g;
  }
  return null;
}

DateTime _day(DateTime d) => DateTime(d.year, d.month, d.day);

/// The first of the month [months] months after [from]'s month — when an age
/// in whole months ticks over (the server counts from the birth month).
DateTime _monthsAhead(DateTime from, int months) {
  final total = from.month - 1 + months;
  return DateTime(from.year + total ~/ 12, total % 12 + 1);
}
