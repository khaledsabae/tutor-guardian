/// «قناديل الأسبوع» — `GET /api/family/week` (MOBILE_API §12) as the app
/// reads it.
///
/// One lantern per **local day** that holds at least one parenting act —
/// seven at most. The server decides what counts (the same registry the
/// weekly report reads) and never sends worship: nothing here adds or drops
/// a kind, so the lanterns and the report agree.
///
/// Decoding is additive like the rest of the API models: an unknown `kind`
/// is kept (drawn as a plain lantern, counted as «another step»), a
/// malformed act is skipped, a missing number is zero.
library;

import '../../child_memory/data/memory_models.dart'
    show parseServerDate, parseServerTime;

/// The act kinds §12 promises are stable.
abstract final class ActKind {
  static const lesson = 'lesson';
  static const question = 'question';
  static const followup = 'followup';
  static const mission = 'mission';
  static const planTick = 'plan_tick';
  static const habit = 'habit';
  static const challenge = 'challenge';

  /// Any kind this build does not know yet.
  static const other = 'other';

  /// The order the harvest's summary lists them in.
  static const ordered = <String>[
    lesson,
    question,
    followup,
    mission,
    planTick,
    habit,
    challenge,
    other,
  ];

  static String normalise(String kind) =>
      ordered.contains(kind) ? kind : other;
}

class FamilyAct {
  const FamilyAct({
    required this.kind,
    required this.at,
    this.childId,
    this.title,
  });

  /// As the server sent it (see [ActKind.normalise] for the summary).
  final String kind;

  /// UTC instant.
  final DateTime at;

  /// Null for the family's own acts (a question).
  final int? childId;

  /// Curriculum text in the asked language, or null.
  final String? title;

  /// The calendar day of the act on this phone — the lantern it lights.
  DateTime get localDay {
    final l = at.toLocal();
    return DateTime(l.year, l.month, l.day);
  }

  static FamilyAct? fromJson(Object? raw) {
    if (raw is! Map) return null;
    final kind = raw['kind'];
    final at = parseServerTime(raw['at']);
    if (kind is! String || kind.isEmpty || at == null) return null;
    final child = raw['child_id'];
    final title = raw['title'];
    return FamilyAct(
      kind: kind,
      at: at,
      childId: child is int ? child : null,
      title: title is String && title.trim().isNotEmpty ? title.trim() : null,
    );
  }
}

class FamilyWeek {
  const FamilyWeek({
    required this.acts,
    this.weekStart,
    this.litThisWeek = false,
    this.litWeeksTotal = 0,
    this.last8 = const [],
  });

  /// Monday of the family's local ISO week, as the server computed it.
  final DateTime? weekStart;

  /// This week's acts, oldest first.
  final List<FamilyAct> acts;
  final bool litThisWeek;

  /// «أسابيع مضيئة»: every week ever lit, up to this one. Never resets on
  /// the server; only deleting the acts themselves lowers it.
  final int litWeeksTotal;

  /// The last eight weeks, oldest first (this week last). Only the lit ones
  /// may ever be drawn — an unlit week is not a missed one.
  final List<({DateTime weekStart, bool lit})> last8;

  /// The days that have a lantern, oldest first — seven at most.
  List<DateTime> get litDays {
    final days = <DateTime>{for (final a in acts) a.localDay}.toList()
      ..sort();
    return days.length > 7 ? days.sublist(days.length - 7) : days;
  }

  /// How many lanterns burn this week.
  int get lanterns => litDays.length;

  /// The week's acts grouped by local day, oldest day first.
  List<(DateTime, List<FamilyAct>)> get byDay {
    final map = <DateTime, List<FamilyAct>>{};
    for (final a in acts) {
      (map[a.localDay] ??= []).add(a);
    }
    final days = map.keys.toList()..sort();
    return [for (final d in days) (d, map[d]!)];
  }

  /// Acts per kind, in [ActKind.ordered] order, unknown kinds as `other`;
  /// kinds with no act are left out.
  Map<String, int> get countsByKind {
    final counts = <String, int>{};
    for (final a in acts) {
      final k = ActKind.normalise(a.kind);
      counts[k] = (counts[k] ?? 0) + 1;
    }
    return {
      for (final k in ActKind.ordered)
        if ((counts[k] ?? 0) > 0) k: counts[k]!,
    };
  }

  /// `week_start` as the server wrote it — the key the device remembers
  /// which lanterns it has already shown under.
  String get weekKey {
    final d = weekStart;
    if (d == null) return '';
    return '${d.year.toString().padLeft(4, '0')}-'
        '${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
  }

  factory FamilyWeek.fromJson(Map<String, dynamic> j) {
    final total = j['lit_weeks_total'];
    return FamilyWeek(
      weekStart: parseServerDate(j['week_start']),
      acts: [
        for (final a in (j['acts'] is List ? j['acts'] as List : const []))
          ?FamilyAct.fromJson(a),
      ]..sort((a, b) => a.at.compareTo(b.at)),
      litThisWeek: j['lit_this_week'] == true,
      litWeeksTotal: total is num && total > 0 ? total.toInt() : 0,
      last8: [
        for (final w in (j['last_8'] is List ? j['last_8'] as List : const []))
          if (w is Map && parseServerDate(w['week_start']) != null)
            (weekStart: parseServerDate(w['week_start'])!, lit: w['lit'] == true),
      ],
    );
  }
}
