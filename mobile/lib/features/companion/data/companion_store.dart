/// What «نور» keeps on the phone («نور يتذكّر», phase 2).
///
/// The server already remembers facts and follow-ups; this is the small,
/// device-only memory the companion needs to behave well:
///   * promises — the lesson step the parent said they would try, and when;
///   * which once-only moments were already shown (a Ramadan countdown day,
///     a Monday reveal), so nothing repeats;
///   * how many questions Noor asked today (anti-nag: two at most);
///   * lines the parent hid for today, and the «وضع هادئ» switch.
///
/// Plain SharedPreferences JSON: nothing here is sensitive beyond what the
/// lesson text already is, and a reinstall that loses it loses nothing the
/// server does not also hold (a promise with a server follow-up is asked back
/// by the follow-up loop either way).
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// The slot the parent picked in the next-step sheet.
enum PromiseSlot {
  tonight('tonight', 1),
  tomorrow('tomorrow', 2),
  week('week', 7);

  const PromiseSlot(this.wire, this.askAfterDays);

  /// The value the server's `when` field takes.
  final String wire;

  /// Days after the promise when Noor asks how it went — the same mapping
  /// as the server's PROMISE_DUE_DAYS, so both ask on the same morning.
  final int askAfterDays;

  static PromiseSlot? fromWire(String? s) {
    for (final v in values) {
      if (v.wire == s) return v;
    }
    return null;
  }
}

/// Calendar day in local time — promises and caps are about days, not hours.
DateTime dayOf(DateTime t) => DateTime(t.year, t.month, t.day);

String _dayKey(DateTime t) {
  final d = dayOf(t);
  return '${d.year}-${d.month.toString().padLeft(2, '0')}-'
      '${d.day.toString().padLeft(2, '0')}';
}

class Promise {
  const Promise({
    required this.id,
    required this.childId,
    required this.step,
    required this.slot,
    required this.madeOn,
    this.lessonId,
    this.followupId,
    this.outcome,
  });

  /// Local id (milliseconds at creation) — also seeds the reminder id.
  final int id;
  final int childId;

  /// The lesson's `try_this`, as the parent read it.
  final String step;
  final PromiseSlot slot;

  /// The local day the promise was made.
  final DateTime madeOn;
  final String? lessonId;

  /// The server follow-up opened for it, when the server accepted it. Then
  /// the answer goes through the follow-up sheet and into memory.
  final int? followupId;

  /// `worked` / `partly` / `didnt_work` / `didnt_try`, once answered.
  final String? outcome;

  DateTime get dueOn => dayOf(madeOn).add(Duration(days: slot.askAfterDays));
  bool get answered => outcome != null;
  bool isDue(DateTime now) => !answered && !dayOf(now).isBefore(dueOn);

  Promise copyWith({int? followupId, String? outcome}) => Promise(
    id: id,
    childId: childId,
    step: step,
    slot: slot,
    madeOn: madeOn,
    lessonId: lessonId,
    followupId: followupId ?? this.followupId,
    outcome: outcome ?? this.outcome,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'child_id': childId,
    'step': step,
    'slot': slot.wire,
    'made_on': _dayKey(madeOn),
    if (lessonId != null) 'lesson_id': lessonId,
    if (followupId != null) 'followup_id': followupId,
    if (outcome != null) 'outcome': outcome,
  };

  static Promise? fromJson(Object? v) {
    if (v is! Map) return null;
    final slot = PromiseSlot.fromWire(v['slot'] as String?);
    final made = DateTime.tryParse('${v['made_on']}');
    final id = v['id'], child = v['child_id'], step = v['step'];
    if (slot == null ||
        made == null ||
        id is! int ||
        child is! int ||
        step is! String ||
        step.isEmpty) {
      return null;
    }
    return Promise(
      id: id,
      childId: child,
      step: step,
      slot: slot,
      madeOn: made,
      lessonId: v['lesson_id'] as String?,
      followupId: v['followup_id'] is int ? v['followup_id'] as int : null,
      outcome: v['outcome'] as String?,
    );
  }
}

/// Everything the brain reads from the device, as one immutable value.
class CompanionMemory {
  const CompanionMemory({
    this.promises = const [],
    this.seenKeys = const {},
    this.questionsByDay = const {},
    this.hiddenByDay = const {},
    this.stopsByDay = const {},
    this.quietMode = false,
  });

  final List<Promise> promises;

  /// Once-only moment keys already shown (e.g. `ramadan:2027:7`).
  final Set<String> seenKeys;

  /// Day key → question line keys shown that day.
  final Map<String, Set<String>> questionsByDay;

  /// Day key → line keys the parent hid that day.
  final Map<String, Set<String>> hiddenByDay;

  /// Day key → «درب اليوم» stops reached that day: `step:<child>`, `ask`,
  /// `mission:<child>`.
  final Map<String, Set<String>> stopsByDay;
  final bool quietMode;

  /// This memory with [keys] treated as not seen yet — for once-only lines
  /// already shown in this run of the app, which must stay put until the
  /// next open (see `heldOnceLinesProvider`).
  CompanionMemory withoutSeen(Set<String> keys) => keys.isEmpty
      ? this
      : CompanionMemory(
          promises: promises,
          seenKeys: seenKeys.difference(keys),
          questionsByDay: questionsByDay,
          hiddenByDay: hiddenByDay,
          stopsByDay: stopsByDay,
          quietMode: quietMode,
        );

  Set<String> questionsOn(DateTime now) =>
      questionsByDay[_dayKey(now)] ?? const {};
  Set<String> hiddenOn(DateTime now) => hiddenByDay[_dayKey(now)] ?? const {};
  Set<String> stopsOn(DateTime now) => stopsByDay[_dayKey(now)] ?? const {};
}

class CompanionStore {
  CompanionStore(this._prefs);

  final SharedPreferences _prefs;

  static const _kPromises = 'noor.promises.v1';
  static const _kSeen = 'noor.seen.v1';
  static const _kQuestions = 'noor.questions.v1';
  static const _kHidden = 'noor.hidden.v1';
  static const _kStops = 'noor.stops.v1';
  static const _kQuiet = 'noor.quiet_mode';

  /// Answered promises older than this are dropped; unanswered ones expire
  /// with the server's follow-ups (21 days) so nothing asks forever.
  static const keepDays = 21;

  CompanionMemory read({DateTime? now}) {
    final today = dayOf(now ?? DateTime.now());
    final promises =
        <Promise>[for (final p in _list(_kPromises)) ?Promise.fromJson(p)]
            .where((p) => today.difference(dayOf(p.madeOn)).inDays <= keepDays)
            .toList();
    return CompanionMemory(
      promises: promises,
      seenKeys: {
        for (final s in _list(_kSeen))
          if (s is String) s,
      },
      questionsByDay: _dayMap(_kQuestions, today),
      hiddenByDay: _dayMap(_kHidden, today),
      stopsByDay: _dayMap(_kStops, today),
      quietMode: _prefs.getBool(_kQuiet) ?? false,
    );
  }

  Future<Promise> addPromise({
    required int childId,
    required String step,
    required PromiseSlot slot,
    String? lessonId,
    DateTime? now,
  }) async {
    final at = now ?? DateTime.now();
    final p = Promise(
      id: at.millisecondsSinceEpoch,
      childId: childId,
      step: step,
      slot: slot,
      madeOn: dayOf(at),
      lessonId: lessonId,
    );
    final all =
        read(now: at).promises
            // One open promise per lesson: picking a new slot replaces the old.
            .where(
              (o) => o.answered || o.lessonId == null || o.lessonId != lessonId,
            )
            .toList()
          ..add(p);
    await _savePromises(all);
    return p;
  }

  Future<void> linkFollowup(int promiseId, int followupId) =>
      _updatePromise(promiseId, (p) => p.copyWith(followupId: followupId));

  Future<void> answer(int promiseId, String outcome) =>
      _updatePromise(promiseId, (p) => p.copyWith(outcome: outcome));

  /// A server follow-up was answered elsewhere (the sheet, a push): close
  /// the promise that carried it so Noor does not ask twice.
  Future<void> answerByFollowup(int followupId, String outcome) async {
    final all = read().promises;
    if (!all.any((p) => p.followupId == followupId && !p.answered)) return;
    await _savePromises([
      for (final p in all)
        p.followupId == followupId && !p.answered
            ? p.copyWith(outcome: outcome)
            : p,
    ]);
  }

  Future<void> markSeen(String key) async {
    final s = {
      for (final x in _list(_kSeen))
        if (x is String) x,
    }..add(key);
    // Bounded: a moment key is only ever checked for the current season.
    final kept = s.length > 200 ? s.skip(s.length - 200).toList() : s.toList();
    await _prefs.setString(_kSeen, jsonEncode(kept));
  }

  Future<void> markQuestionShown(String key, {DateTime? now}) =>
      _addToDay(_kQuestions, key, now ?? DateTime.now());

  Future<void> hideForToday(String key, {DateTime? now}) =>
      _addToDay(_kHidden, key, now ?? DateTime.now());

  /// A «درب اليوم» stop reached on this device today. Idempotent.
  Future<void> markStop(String key, {DateTime? now}) async {
    final t = now ?? DateTime.now();
    if (read(now: t).stopsOn(t).contains(key)) return;
    await _addToDay(_kStops, key, t);
  }

  Future<void> setQuietMode(bool on) => _prefs.setBool(_kQuiet, on);

  // ── plumbing ────────────────────────────────────────────────────────

  Future<void> _updatePromise(int id, Promise Function(Promise) f) async {
    await _savePromises([
      for (final p in read().promises) p.id == id ? f(p) : p,
    ]);
  }

  Future<void> _savePromises(List<Promise> all) => _prefs.setString(
    _kPromises,
    jsonEncode([for (final p in all) p.toJson()]),
  );

  List<dynamic> _list(String key) {
    final raw = _prefs.getString(key);
    if (raw == null) return const [];
    try {
      final v = jsonDecode(raw);
      return v is List ? v : const [];
    } catch (_) {
      return const [];
    }
  }

  /// Only today's entry matters; older days are dropped on the next write.
  Map<String, Set<String>> _dayMap(String key, DateTime today) {
    final raw = _prefs.getString(key);
    if (raw == null) return const {};
    try {
      final v = jsonDecode(raw);
      if (v is! Map) return const {};
      final k = _dayKey(today);
      final list = v[k];
      return list is List
          ? {
              k: {
                for (final x in list)
                  if (x is String) x,
              },
            }
          : const {};
    } catch (_) {
      return const {};
    }
  }

  Future<void> _addToDay(String key, String item, DateTime now) async {
    final k = _dayKey(now);
    final current = _dayMap(key, now)[k] ?? <String>{};
    await _prefs.setString(
      key,
      jsonEncode({
        k: [...current, item],
      }),
    );
  }
}
