/// Data shapes for «المربّي يعرف ابنك» — MOBILE_API.md §9–§10.
///
/// Decoding is additive (unknown fields are ignored, missing ones fall back),
/// the same rule as `models/api_models.dart`: a newer server may add fields,
/// and an older build must keep reading what it understands.
library;

/// A server timestamp as a UTC instant.
///
/// Every timestamp in §9–§10 is ISO 8601 UTC with `Z`. One older line of the
/// contract still describes SQLite's own `YYYY-MM-DD HH:MM:SS`; that shape is
/// UTC too. An omitted offset is never local time here — reading it as local
/// would move a 72-hour pause by the family's UTC offset.
DateTime? parseServerTime(Object? raw) {
  if (raw is! String) return null;
  var s = raw.trim();
  if (s.isEmpty) return null;
  if (_zoneless.hasMatch(s)) s = '${s.replaceFirst(' ', 'T')}Z';
  return DateTime.tryParse(s)?.toUtc();
}

final RegExp _zoneless =
    RegExp(r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$');

/// A calendar date the server computed on the family's clock (`2026-10-05`):
/// a day, not an instant, so it is kept as a local date with no zone shift.
DateTime? parseServerDate(Object? raw) {
  if (raw is! String) return null;
  final m = RegExp(r'^(\d{4})-(\d{2})-(\d{2})').firstMatch(raw.trim());
  if (m == null) return null;
  return DateTime(int.parse(m[1]!), int.parse(m[2]!), int.parse(m[3]!));
}

int? _int(Object? v) => v is num ? v.toInt() : (v is String ? int.tryParse(v) : null);
String _str(Object? v) => v is String ? v : '';
String? _strOrNull(Object? v) => v is String && v.isNotEmpty ? v : null;

/// The categories a fact can have, in the order the screen lists them.
abstract final class FactCategory {
  static const temperament = 'temperament';
  static const challenge = 'challenge';
  static const goal = 'goal';
  static const triedStrategy = 'tried_strategy';
  static const outcome = 'outcome';
  static const healthNote = 'health_note';
  static const school = 'school';
  static const worship = 'worship';
  static const other = 'other';

  static const all = <String>[
    temperament,
    challenge,
    goal,
    triedStrategy,
    outcome,
    healthNote,
    school,
    worship,
    other,
  ];
}

/// How a follow-up went — the four answers, in the order they are offered.
abstract final class FollowupOutcome {
  static const worked = 'worked';
  static const partly = 'partly';
  static const didntWork = 'didnt_work';
  static const didntTry = 'didnt_try';

  static const all = <String>[worked, partly, didntWork, didntTry];
}

/// One thing the assistant knows about a child (§9.3).
class MemoryFact {
  const MemoryFact({
    required this.id,
    required this.childId,
    required this.category,
    required this.fact,
    required this.source,
    required this.status,
    required this.lang,
    this.confidence,
    this.createdAt,
    this.updatedAt,
  });

  final int id;
  final int childId;
  final String category;

  /// Stored with a placeholder for the child's name («طفلي», "my child") —
  /// see `placeholder_names.dart` for the on-device swap.
  final String fact;

  /// `chat` · `followup` · `parent_manual`.
  final String source;

  /// `active` · `pending` · `rejected`.
  final String status;

  /// `ar` · `en` — the script the fact is written in.
  final String lang;
  final double? confidence;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  bool get isActive => status == 'active';
  bool get isPending => status == 'pending';
  bool get isRejected => status == 'rejected';

  factory MemoryFact.fromJson(Map<String, dynamic> j) => MemoryFact(
        id: _int(j['id']) ?? 0,
        childId: _int(j['child_id']) ?? 0,
        category: FactCategory.all.contains(j['category'])
            ? j['category'] as String
            : FactCategory.other,
        fact: _str(j['fact']),
        source: _str(j['source']),
        status: _str(j['status']).isEmpty ? 'active' : j['status'] as String,
        lang: _str(j['lang']).isEmpty ? 'ar' : j['lang'] as String,
        confidence: (j['confidence'] as num?)?.toDouble(),
        createdAt: parseServerTime(j['created_at']),
        updatedAt: parseServerTime(j['updated_at']),
      );
}

/// The device's memory switch and this session's proof (§9.2).
class MemorySettings {
  const MemorySettings({
    required this.enabled,
    this.collecting = false,
    this.proven = false,
    this.cooldownUntil,
  });

  /// The parent's switch (server default: on).
  final bool enabled;

  /// On AND a memory build AND this session proven.
  final bool collecting;

  /// Whether this session may open the memory screen now.
  final bool proven;

  /// Protected routes are paused until then (push-token cooldown).
  final DateTime? cooldownUntil;

  factory MemorySettings.fromJson(Map<String, dynamic> j) => MemorySettings(
        enabled: j['enabled'] != false,
        collecting: j['collecting'] == true,
        proven: j['proven'] == true,
        cooldownUntil: parseServerTime(j['cooldown_until']),
      );
}

/// `GET /api/children/{id}/memory`.
class ChildMemory {
  const ChildMemory({
    required this.childId,
    required this.facts,
    this.settings,
    this.maxFactChars = 160,
    this.maxFacts = 40,
  });

  final int childId;

  /// Newest first, as sent — rejected ones included (the screen hides them).
  final List<MemoryFact> facts;
  final MemorySettings? settings;
  final int maxFactChars;
  final int maxFacts;

  /// Health notes the assistant suggested, waiting for the parent's yes/no.
  List<MemoryFact> get pending => [
        for (final f in facts)
          if (f.isPending) f,
      ];

  /// What the assistant uses, grouped in [FactCategory.all] order.
  Map<String, List<MemoryFact>> get activeByCategory {
    final out = <String, List<MemoryFact>>{};
    for (final c in FactCategory.all) {
      final inCat = [
        for (final f in facts)
          if (f.isActive && f.category == c) f,
      ];
      if (inCat.isNotEmpty) out[c] = inCat;
    }
    return out;
  }

  factory ChildMemory.fromJson(Map<String, dynamic> j) {
    final limits = j['limits'] is Map ? j['limits'] as Map : const {};
    return ChildMemory(
      childId: _int(j['child_id']) ?? 0,
      facts: [
        for (final f in (j['facts'] as List? ?? const []))
          if (f is Map) MemoryFact.fromJson(Map<String, dynamic>.from(f)),
      ],
      settings: j['settings'] is Map
          ? MemorySettings.fromJson(Map<String, dynamic>.from(j['settings']))
          : null,
      maxFactChars: _int(limits['max_fact_chars']) ?? 160,
      maxFacts: _int(limits['max_facts']) ?? 40,
    );
  }
}

/// «جرّبت النصيحة؟ نفعت؟» (§9.4).
class Followup {
  const Followup({
    required this.id,
    required this.childId,
    required this.strategy,
    required this.status,
    this.topic = 'other',
    this.lang = 'ar',
    this.dueAt,
    this.outcome,
    this.note,
    this.createdAt,
    this.answeredAt,
  });

  final int id;
  final int childId;

  /// The advice being followed up, with the child's placeholder.
  final String strategy;

  /// `pending` → `answered` | `dismissed` | `expired`.
  final String status;
  final String topic;
  final String lang;
  final DateTime? dueAt;
  final String? outcome;
  final String? note;
  final DateTime? createdAt;
  final DateTime? answeredAt;

  bool get isPending => status == 'pending';

  factory Followup.fromJson(Map<String, dynamic> j) => Followup(
        id: _int(j['id']) ?? 0,
        childId: _int(j['child_id']) ?? 0,
        strategy: _str(j['strategy']),
        status: _str(j['status']).isEmpty ? 'pending' : j['status'] as String,
        topic: _str(j['topic']).isEmpty ? 'other' : j['topic'] as String,
        lang: _str(j['lang']).isEmpty ? 'ar' : j['lang'] as String,
        dueAt: parseServerTime(j['due_at']),
        outcome: _strOrNull(j['outcome']),
        note: _strOrNull(j['note']),
        createdAt: parseServerTime(j['created_at']),
        answeredAt: parseServerTime(j['answered_at']),
      );
}

/// What `POST /followups/{id}/answer` returns.
class FollowupAnswer {
  const FollowupAnswer({
    required this.followup,
    this.fact,
    this.noteDropped = false,
  });

  final Followup followup;
  final MemoryFact? fact;

  /// The note was something memory never keeps — discarded; say so gently.
  final bool noteDropped;

  factory FollowupAnswer.fromJson(Map<String, dynamic> j) => FollowupAnswer(
        followup: Followup.fromJson(
            Map<String, dynamic>.from(j['followup'] as Map? ?? const {})),
        fact: j['fact'] is Map
            ? MemoryFact.fromJson(Map<String, dynamic>.from(j['fact']))
            : null,
        noteDropped: j['note_dropped'] == true,
      );
}

/// One line of the weekly plan (an action or the worship act).
class PlanItem {
  const PlanItem({required this.key, required this.text});
  final String key;
  final String text;

  static PlanItem? fromJson(Object? raw) {
    if (raw is! Map) return null;
    final text = _str(raw['text']).trim();
    if (text.isEmpty) return null;
    return PlanItem(key: _str(raw['key']), text: text);
  }
}

/// The plan's lesson — a real curriculum lesson for the child's band.
class PlanLesson {
  const PlanLesson({
    required this.id,
    required this.title,
    this.pathId,
    this.estimatedMinutes,
    this.completed = false,
  });

  final String id;
  final String title;
  final String? pathId;
  final int? estimatedMinutes;
  final bool completed;

  static PlanLesson? fromJson(Object? raw) {
    if (raw is! Map) return null;
    final id = _str(raw['id']);
    if (id.isEmpty) return null;
    return PlanLesson(
      id: id,
      title: _str(raw['title']),
      pathId: _strOrNull(raw['path_id']),
      estimatedMinutes: _int(raw['estimated_minutes']),
      completed: raw['completed'] == true,
    );
  }
}

/// This ISO week's plan for one child (§9.5).
class WeeklyPlan {
  const WeeklyPlan({
    required this.childId,
    required this.week,
    required this.focusTitle,
    required this.actions,
    this.weekStart,
    this.lang = 'ar',
    this.band,
    this.focusTopic,
    this.focusReason,
    this.focusReasonText,
    this.worship,
    this.lesson,
    this.adaptedFromOutcomes = false,
  });

  final int childId;

  /// `2026-W41`.
  final String week;

  /// Monday of the parent's local ISO week, as the server computed it — the
  /// week boundary is the server's, not recomputed here.
  final DateTime? weekStart;
  final String lang;
  final String? band;
  final String? focusTopic;
  final String focusTitle;

  /// `parent_challenge` · `memory` · `age_default`.
  final String? focusReason;
  final String? focusReasonText;
  final List<PlanItem> actions;
  final PlanItem? worship;
  final PlanLesson? lesson;
  final bool adaptedFromOutcomes;

  /// The first day after this plan's week, on the family's calendar.
  DateTime? get nextWeekStart => weekStart?.add(const Duration(days: 7));

  /// A plan a parent can act on: a focus and at least one action.
  bool get isUsable => focusTitle.trim().isNotEmpty && actions.isNotEmpty;

  factory WeeklyPlan.fromJson(Map<String, dynamic> j) {
    final focus = j['focus'] is Map ? j['focus'] as Map : const {};
    return WeeklyPlan(
      childId: _int(j['child_id']) ?? 0,
      week: _str(j['week']),
      weekStart: parseServerDate(j['week_start']),
      lang: _str(j['lang']).isEmpty ? 'ar' : j['lang'] as String,
      band: _strOrNull(j['band']),
      focusTopic: _strOrNull(focus['topic']),
      focusTitle: _str(focus['title']),
      focusReason: _strOrNull(focus['reason']),
      focusReasonText: _strOrNull(focus['reason_text']),
      actions: [
        for (final a in (j['actions'] as List? ?? const []))
          ?PlanItem.fromJson(a),
      ],
      worship: PlanItem.fromJson(j['worship']),
      lesson: PlanLesson.fromJson(j['lesson']),
      adaptedFromOutcomes: j['adapted_from_outcomes'] == true,
    );
  }
}

/// `GET /api/device-proof` (§9.0.1).
class DeviceProofStatus {
  const DeviceProofStatus({
    required this.proven,
    this.provenAt,
    this.pushRegistered = false,
    this.cooldownUntil,
    this.deletionPausedUntil,
  });

  final bool proven;
  final DateTime? provenAt;
  final bool pushRegistered;

  /// Every protected route paused until then (an unvouched token change).
  final DateTime? cooldownUntil;

  /// Account and child deletion paused until then (either kind of pause).
  final DateTime? deletionPausedUntil;

  factory DeviceProofStatus.fromJson(Map<String, dynamic> j) =>
      DeviceProofStatus(
        proven: j['proven'] == true,
        provenAt: parseServerTime(j['proven_at']),
        pushRegistered: j['push_registered'] == true,
        cooldownUntil: parseServerTime(j['cooldown_until']),
        deletionPausedUntil: parseServerTime(j['deletion_paused_until']),
      );
}

/// What `DELETE /api/privacy/account` reports (§10).
class AccountDeletionResult {
  const AccountDeletionResult({
    required this.devices,
    required this.signedIn,
    this.deletedAt,
  });

  /// How many devices were erased (this one included).
  final int devices;

  /// Whether a confirmed Google link carried the deletion to the identity.
  final bool signedIn;
  final DateTime? deletedAt;

  factory AccountDeletionResult.fromJson(Map<String, dynamic> j) =>
      AccountDeletionResult(
        devices: _int(j['devices']) ?? 1,
        signedIn: j['signed_in'] == true,
        deletedAt: parseServerTime(j['deleted_at']),
      );
}
