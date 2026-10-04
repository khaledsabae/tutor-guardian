/// Typed views of the family-programs payloads (MOBILE_API §11).
///
/// Every string a screen renders comes from these payloads — the server picks
/// the right piece for a child on a day, in the reader's language — so the
/// models only shape the JSON; they never make content up. Parsing is lenient
/// on purpose: the contract is additive ("clients must ignore unknown
/// fields"), and a field the server stops sending must degrade to "not shown",
/// never to a crash on a parent's phone.
library;

// ── Lenient readers ─────────────────────────────────────────────────────────

String? _str(Object? v) => v is String && v.trim().isNotEmpty ? v : null;
int? _int(Object? v) =>
    v is num ? v.toInt() : (v is String ? int.tryParse(v) : null);
bool _bool(Object? v) => v == true;
Map<String, dynamic>? _map(Object? v) =>
    v is Map ? Map<String, dynamic>.from(v) : null;
List<Map<String, dynamic>> _maps(Object? v) => v is List
    ? v.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList()
    : const [];
List<String> _strings(Object? v) =>
    v is List ? v.map(_str).whereType<String>().toList() : const [];
DateTime? _date(Object? v) => v is String ? DateTime.tryParse(v) : null;

// ── Shared pieces ───────────────────────────────────────────────────────────

/// `{basis, band, months, years}` — how the server aged the child.
class ProgramAge {
  const ProgramAge({required this.basis, this.band, this.months, this.years});

  /// `birth_month` or `age_group`.
  final String basis;
  final String? band;
  final int? months;
  final int? years;

  bool get fromBirthMonth => basis == 'birth_month';

  factory ProgramAge.fromJson(Map<String, dynamic>? j) => ProgramAge(
    basis: _str(j?['basis']) ?? 'age_group',
    band: _str(j?['band']),
    months: _int(j?['months']),
    years: _int(j?['years']),
  );
}

/// A hadith card. Rendered only from here — never quoted anywhere else.
class EvidenceCard {
  const EvidenceCard({
    required this.id,
    required this.kind,
    required this.textAr,
    required this.source,
    this.context,
    this.meaning,
  });

  final String id;
  final String kind;
  final String textAr;
  final String source;
  final String? context;

  /// English only: the meaning, shown under a label saying so.
  final String? meaning;

  static List<EvidenceCard> listFrom(Object? v) => [
    for (final j in _maps(v))
      if (_str(j['text_ar']) != null && _str(j['source']) != null)
        EvidenceCard(
          id: _str(j['id']) ?? '',
          kind: _str(j['kind']) ?? 'hadith',
          textAr: j['text_ar'] as String,
          source: j['source'] as String,
          context: _str(j['context']),
          meaning: _str(j['meaning']),
        ),
  ];
}

/// A Quran reference — the verse text comes from the bundled mushaf.
class QuranRef {
  const QuranRef({
    required this.surah,
    required this.from,
    required this.to,
    this.topic,
  });

  final int surah;
  final int from;
  final int to;
  final String? topic;

  static QuranRef? fromJson(Object? v) {
    final j = _map(v);
    final surah = _int(j?['surah']);
    final from = _int(j?['from']);
    if (j == null || surah == null || from == null) return null;
    if (surah < 1 || surah > 114 || from < 1) return null;
    final to = _int(j['to']) ?? from;
    return QuranRef(
      surah: surah,
      from: from,
      to: to < from ? from : to,
      topic: _str(j['topic']),
    );
  }

  static List<QuranRef> listFrom(Object? v) => [
    for (final j in (v is List ? v : const [])) ?QuranRef.fromJson(j),
  ];
}

/// `{text, evidence}` — a note for the parent with its hadith cards.
class ParentNote {
  const ParentNote({required this.text, this.evidence = const []});
  final String text;
  final List<EvidenceCard> evidence;

  static ParentNote? fromJson(Object? v) {
    final j = _map(v);
    final text = _str(j?['text']);
    if (text == null) return null;
    return ParentNote(
      text: text,
      evidence: EvidenceCard.listFrom(j!['evidence']),
    );
  }
}

/// Program links into existing app screens.
class ProgramLinks {
  const ProgramLinks({
    this.programIds = const [],
    this.pathIds = const [],
    this.lessonIds = const [],
    this.storyIds = const [],
    this.features = const [],
  });

  final List<String> programIds;
  final List<String> pathIds;
  final List<String> lessonIds;
  final List<String> storyIds;
  final List<String> features;

  bool get isEmpty =>
      programIds.isEmpty &&
      pathIds.isEmpty &&
      lessonIds.isEmpty &&
      storyIds.isEmpty &&
      features.isEmpty;

  factory ProgramLinks.fromJson(Object? v) {
    final j = _map(v);
    return ProgramLinks(
      programIds: _strings(j?['program_ids']),
      pathIds: _strings(j?['path_ids']),
      lessonIds: _strings(j?['lesson_ids']),
      storyIds: _strings(j?['story_ids']),
      features: _strings(j?['features']),
    );
  }
}

// ── GET /api/programs ───────────────────────────────────────────────────────

/// The family's Ramadan calendar (with its own sighting applied).
class RamadanSeason {
  const RamadanSeason({
    required this.hijriYear,
    required this.startsOn,
    required this.days,
    required this.eidOn,
    this.bridgeEndsOn,
    this.startSource = 'estimate',
    this.daysConfirmed = false,
    this.shiftDays = 0,
  });

  final int hijriYear;
  final DateTime startsOn;
  final int days;
  final DateTime eidOn;
  final DateTime? bridgeEndsOn;

  /// `configured` once announced; `estimate` until then.
  final String startSource;
  final bool daysConfirmed;

  /// The family's own sighting: −1, 0 or +1 days.
  final int shiftDays;

  bool get isEstimate => startSource != 'configured';

  static RamadanSeason? fromJson(Object? v) {
    final j = _map(v);
    final year = _int(j?['hijri_year']);
    final start = _date(j?['starts_on']);
    final eid = _date(j?['eid_on']);
    if (j == null || year == null || start == null || eid == null) return null;
    return RamadanSeason(
      hijriYear: year,
      startsOn: start,
      days: _int(j['days']) ?? 30,
      eidOn: eid,
      bridgeEndsOn: _date(j['bridge_ends_on']),
      startSource: _str(j['start_source']) ?? 'estimate',
      daysConfirmed: _bool(j['days_confirmed']),
      shiftDays: _int(j['shift_days']) ?? 0,
    );
  }
}

/// `upcoming | ramadan | eid | after | off_season`.
enum RamadanState {
  upcoming,
  ramadan,
  eid,
  after,
  offSeason;

  static RamadanState fromWire(String? s) => switch (s) {
    'upcoming' => RamadanState.upcoming,
    'ramadan' => RamadanState.ramadan,
    'eid' => RamadanState.eid,
    'after' => RamadanState.after,
    _ => RamadanState.offSeason,
  };
}

class RamadanOverview {
  const RamadanOverview({
    required this.state,
    this.season,
    this.day,
    this.daysUntilStart,
    this.afterWeek,
    this.recapAvailable = false,
  });

  final RamadanState state;
  final RamadanSeason? season;
  final int? day;
  final int? daysUntilStart;
  final int? afterWeek;
  final bool recapAvailable;

  /// Worth a card at all: a season the server knows, not yet over.
  bool get isActive => season != null && state != RamadanState.offSeason;

  factory RamadanOverview.fromJson(Object? v) {
    final j = _map(v);
    return RamadanOverview(
      state: RamadanState.fromWire(_str(j?['state'])),
      season: RamadanSeason.fromJson(j?['season']),
      day: _int(j?['day']),
      daysUntilStart: _int(j?['days_until_start']),
      afterWeek: _int(j?['after_week']),
      recapAvailable: _bool(j?['recap_available']),
    );
  }
}

/// `preparation | journey | ownership`.
enum PrayerTrack {
  preparation,
  journey,
  ownership;

  String get wire => name;

  static PrayerTrack? fromWire(String? s) => switch (s) {
    'preparation' => PrayerTrack.preparation,
    'journey' => PrayerTrack.journey,
    'ownership' => PrayerTrack.ownership,
    _ => null,
  };
}

class PrayerOverview {
  const PrayerOverview({
    this.eligibleTrack,
    this.enrolled = false,
    this.track,
    this.stage,
    this.advanceSuggested = false,
    this.canGraduate = false,
    this.pendingConfirmations = 0,
  });

  /// Null = the Journey is not for this child — hide it.
  final PrayerTrack? eligibleTrack;
  final bool enrolled;
  final PrayerTrack? track;
  final int? stage;
  final bool advanceSuggested;
  final bool canGraduate;
  final int pendingConfirmations;

  factory PrayerOverview.fromJson(Object? v) {
    final j = _map(v);
    return PrayerOverview(
      eligibleTrack: PrayerTrack.fromWire(_str(j?['eligible_track'])),
      enrolled: _bool(j?['enrolled']),
      track: PrayerTrack.fromWire(_str(j?['track'])),
      stage: _int(j?['stage']),
      advanceSuggested: _bool(j?['advance_suggested']),
      canGraduate: _bool(j?['can_graduate']),
      pendingConfirmations: _int(j?['pending_confirmations']) ?? 0,
    );
  }
}

class ChildPrograms {
  const ChildPrograms({
    required this.childId,
    required this.age,
    this.ramadanVariantBand,
    this.prayer = const PrayerOverview(),
    this.milestonesDue = 0,
    this.needsProfile = const [],
    this.milestonesServed = true,
  });

  final int childId;
  final ProgramAge age;
  final String? ramadanVariantBand;
  final PrayerOverview prayer;
  final int milestonesDue;

  /// `birth_month` / `gender` — what the profile lacks for milestones.
  final List<String> needsProfile;

  /// False when the server could not read the milestones file right now: the
  /// section comes back `null` ("each program stands alone") — hide it.
  final bool milestonesServed;

  bool get needsBirthMonth => needsProfile.contains('birth_month');

  factory ChildPrograms.fromJson(Map<String, dynamic> j) {
    final miles = _map(j['milestones']);
    return ChildPrograms(
      childId: _int(j['child_id']) ?? -1,
      age: ProgramAge.fromJson(_map(j['age'])),
      ramadanVariantBand: _str(_map(j['ramadan'])?['variant_band']),
      // A null section reads as "not for this child": hidden, never an error.
      prayer: PrayerOverview.fromJson(j['prayer_journey']),
      milestonesDue: _int(miles?['due']) ?? 0,
      needsProfile: _strings(miles?['needs_profile']),
      milestonesServed: miles != null,
    );
  }
}

/// `GET /api/programs`.
class ProgramsOverview {
  const ProgramsOverview({
    required this.date,
    required this.ramadan,
    required this.children,
    this.serverFeatures = const [],
    this.unavailable = const [],
  });

  final DateTime? date;
  final RamadanOverview ramadan;
  final List<ChildPrograms> children;
  final List<String> serverFeatures;

  /// Programs whose file the server cannot read right now
  /// (`ramadan_family` · `prayer_journey` · `milestones`). Their sections are
  /// null; the others are served as usual.
  final List<String> unavailable;

  static const kAllPrograms = {'ramadan_family', 'prayer_journey', 'milestones'};

  /// At least one program is served — otherwise there is nothing to enter.
  bool get anyServed => !kAllPrograms.every(unavailable.contains);

  ChildPrograms? forChild(int? childId) {
    if (childId == null) return null;
    for (final c in children) {
      if (c.childId == childId) return c;
    }
    return null;
  }

  factory ProgramsOverview.fromJson(Map<String, dynamic> j) => ProgramsOverview(
    date: _date(j['date']),
    ramadan: RamadanOverview.fromJson(j['ramadan']),
    children: [
      for (final c in _maps(j['children']))
        if (_int(c['child_id']) != null) ChildPrograms.fromJson(c),
    ],
    serverFeatures: _strings(j['server_features']),
    unavailable: _strings(j['unavailable']),
  );
}

// ── Ramadan ─────────────────────────────────────────────────────────────────

class FamilyChallenge {
  const FamilyChallenge({
    required this.title,
    this.steps = const [],
    this.minutes,
    this.cost,
    this.atHome,
    this.when,
    this.materials = const [],
  });

  final String title;
  final List<String> steps;
  final int? minutes;
  final String? cost;
  final bool? atHome;

  /// When in the day — e.g. `at_iftar`, `after_iftar`. Shown only when known.
  final String? when;
  final List<String> materials;

  static FamilyChallenge? fromJson(Object? v) {
    final j = _map(v);
    final title = _str(j?['title']);
    if (title == null) return null;
    return FamilyChallenge(
      title: title,
      steps: _strings(j!['steps']),
      minutes: _int(j['minutes']),
      cost: _str(j['cost']),
      atHome: j['at_home'] is bool ? j['at_home'] as bool : null,
      when: _str(j['when']),
      materials: _strings(j['materials']),
    );
  }
}

/// The child's own role for the day, by age.
class ChildVariant {
  const ChildVariant({
    required this.text,
    this.band,
    this.addressedTo = 'parent',
  });

  final String text;
  final String? band;

  /// `parent` (0-3, 4-6: the child does not read) or `child` (7-9 up).
  final String addressedTo;

  bool get forChild => addressedTo == 'child';

  static ChildVariant? fromJson(Object? v) {
    final j = _map(v);
    final text = _str(j?['text']);
    if (text == null) return null;
    return ChildVariant(
      text: text,
      band: _str(j!['band']),
      addressedTo: _str(j['addressed_to']) ?? 'parent',
    );
  }
}

class RamadanQuran {
  const RamadanQuran({this.together, this.themeRef, this.parentJuz});

  /// A short surah the family repeats over two days to memorise it.
  final QuranRef? together;

  /// A passage tied to the day's theme, or null.
  final QuranRef? themeRef;

  /// The parents' optional khatma: today's juz.
  final int? parentJuz;

  bool get isEmpty => together == null && themeRef == null && parentJuz == null;

  factory RamadanQuran.fromJson(Object? v) {
    final j = _map(v);
    return RamadanQuran(
      together: QuranRef.fromJson(j?['together']),
      themeRef: QuranRef.fromJson(j?['theme_ref']),
      parentJuz: _int(j?['parent_juz']),
    );
  }
}

/// One day of the month — the same shape for today and for any day 1–30.
class RamadanDayContent {
  const RamadanDayContent({
    required this.day,
    required this.title,
    this.phase,
    this.key,
    this.familyChallenge,
    this.parentNote,
    this.variant,
    this.quran = const RamadanQuran(),
    this.storyId,
    this.lastTen = false,
    this.oddNight = false,
    this.mayNotOccur = false,
    this.tracks = const [],
    this.familyWordChoices = const [],
  });

  final int day;
  final String title;
  final String? phase;
  final String? key;
  final FamilyChallenge? familyChallenge;
  final ParentNote? parentNote;
  final ChildVariant? variant;
  final RamadanQuran quran;

  /// Into the bundled stories; null = no story today.
  final String? storyId;
  final bool lastTen;

  /// The evening of this day is an odd night of the last ten.
  final bool oddNight;

  /// Day 30 — the month may end at 29.
  final bool mayNotOccur;

  /// Which «تمّ» toggles this day has.
  final List<String> tracks;

  /// Day 28 only: the eight words the family picks from. Never free text.
  final List<String> familyWordChoices;

  static RamadanDayContent? fromJson(Object? v) {
    final j = _map(v);
    final day = _int(j?['day']);
    final title = _str(j?['title']);
    if (j == null || day == null || title == null) return null;
    return RamadanDayContent(
      day: day,
      title: title,
      phase: _str(j['phase']),
      key: _str(j['key']),
      familyChallenge: FamilyChallenge.fromJson(j['family_challenge']),
      parentNote: ParentNote.fromJson(j['parent_note']),
      variant: ChildVariant.fromJson(j['variant']),
      quran: RamadanQuran.fromJson(j['quran']),
      storyId: _str(j['story_id']),
      lastTen: _bool(j['last_ten']),
      oddNight: _bool(j['odd_night']),
      mayNotOccur: _bool(j['may_not_occur']),
      tracks: _strings(j['tracks']),
      familyWordChoices: _strings(j['family_word_choices']),
    );
  }
}

/// The family's «تمّ» for a day — only ticks, never a "missed".
class RamadanMarks {
  const RamadanMarks({
    this.ticks = const {},
    this.familyWord,
    this.familyWordIndex,
  });

  final Map<String, bool> ticks;
  final String? familyWord;
  final int? familyWordIndex;

  bool isDone(String mark) => ticks[mark] == true;

  static RamadanMarks? fromJson(Object? v) {
    final j = _map(v);
    if (j == null) return null;
    final ticks = <String, bool>{};
    for (final e in j.entries) {
      if (e.value is bool) ticks[e.key] = e.value as bool;
    }
    final word = _map(j['family_word']);
    return RamadanMarks(
      ticks: ticks,
      familyWord: _str(word?['word']),
      familyWordIndex: _int(word?['choice_index']),
    );
  }
}

class FastingStepSummary {
  const FastingStepSummary({
    required this.key,
    required this.label,
    this.until,
    this.approxHours,
    this.maxDaysPerWeek,
  });

  final String key;
  final String label;
  final String? until;
  final int? approxHours;
  final int? maxDaysPerWeek;

  static FastingStepSummary? fromJson(Object? v) {
    final j = _map(v);
    final key = _str(j?['key']);
    if (j == null || key == null) return null;
    return FastingStepSummary(
      key: key,
      label: _str(j['label']) ?? key,
      until: _str(j['until']),
      approxHours: _int(j['approx_hours']),
      maxDaysPerWeek: _int(j['max_days_per_week']),
    );
  }
}

/// The ladder's state inside today's card (no steps, no guidance).
class FastingSummary {
  const FastingSummary({
    this.ladderBand,
    this.fasts,
    this.reachedPuberty = false,
    this.currentStep,
    this.practisedToday = false,
    this.practisedThisWeek = 0,
    this.restSuggested = false,
  });

  final String? ladderBand;

  /// `no | partial | partial_to_full | full_supported`.
  final String? fasts;
  final bool reachedPuberty;
  final FastingStepSummary? currentStep;
  final bool practisedToday;

  /// A count that only goes up within the week.
  final int practisedThisWeek;

  /// The step's own weekly cap is reached: tomorrow is a rest day. Care, not a score.
  final bool restSuggested;

  bool get noFasting => fasts == 'no';

  static FastingSummary? fromJson(Object? v) {
    final j = _map(v);
    if (j == null) return null;
    return FastingSummary(
      ladderBand: _str(j['ladder_band']),
      fasts: _str(j['fasts']),
      reachedPuberty: _bool(j['reached_puberty']),
      currentStep: FastingStepSummary.fromJson(j['current_step']),
      practisedToday: _bool(j['practised_today']),
      practisedThisWeek: _int(j['practised_this_week']) ?? 0,
      restSuggested: _bool(j['rest_suggested']),
    );
  }
}

class RamadanKickoff {
  const RamadanKickoff({
    required this.title,
    this.text,
    this.setupSteps = const [],
  });
  final String title;
  final String? text;
  final List<String> setupSteps;

  static RamadanKickoff? fromJson(Object? v) {
    final j = _map(v);
    final title = _str(j?['title']);
    if (title == null) return null;
    return RamadanKickoff(
      title: title,
      text: _str(j!['text']),
      setupSteps: _strings(j['setup_steps']),
    );
  }
}

class RamadanEid {
  const RamadanEid({
    required this.title,
    this.activities = const [],
    this.parentNote,
    this.variant,
    this.quran = const RamadanQuran(),
    this.evidence = const [],
  });

  final String title;
  final List<String> activities;
  final ParentNote? parentNote;
  final ChildVariant? variant;
  final RamadanQuran quran;
  final List<EvidenceCard> evidence;

  static RamadanEid? fromJson(Object? v) {
    final j = _map(v);
    final title = _str(j?['title']);
    if (title == null) return null;
    return RamadanEid(
      title: title,
      activities: _strings(j!['activities']),
      parentNote: ParentNote.fromJson(j['parent_note']),
      variant: ChildVariant.fromJson(j['variant']),
      quran: RamadanQuran.fromJson(j['quran']),
      evidence: EvidenceCard.listFrom(j['evidence']),
    );
  }
}

class TitledText {
  const TitledText({required this.title, this.text, this.key});
  final String title;
  final String? text;
  final String? key;

  static List<TitledText> listFrom(Object? v) => [
    for (final j in _maps(v))
      if (_str(j['title']) != null)
        TitledText(
          title: j['title'] as String,
          text: _str(j['text']),
          key: _str(j['key']),
        ),
  ];
}

class RamadanBridgeWeek {
  const RamadanBridgeWeek({required this.week, required this.title, this.text});
  final int week;
  final String title;

  /// Already resolved by the server (promise or fallback) — render as is.
  final String? text;

  static RamadanBridgeWeek? fromJson(Object? v) {
    final j = _map(v);
    final week = _int(j?['week']);
    final title = _str(j?['title']);
    if (j == null || week == null || title == null) return null;
    return RamadanBridgeWeek(week: week, title: title, text: _str(j['text']));
  }
}

class RamadanAfter {
  const RamadanAfter({
    required this.title,
    this.text,
    this.keepHabits = const [],
    this.week,
    this.weeks = const [],
    this.links = const ProgramLinks(),
    this.evidence = const [],
  });

  final String title;
  final String? text;
  final List<TitledText> keepHabits;
  final RamadanBridgeWeek? week;
  final List<RamadanBridgeWeek> weeks;
  final ProgramLinks links;
  final List<EvidenceCard> evidence;

  static RamadanAfter? fromJson(Object? v) {
    final j = _map(v);
    final title = _str(j?['title']);
    if (title == null) return null;
    return RamadanAfter(
      title: title,
      text: _str(j!['text']),
      keepHabits: TitledText.listFrom(j['keep_habits']),
      week: RamadanBridgeWeek.fromJson(j['week']),
      weeks: [
        for (final w in (j['weeks'] is List ? j['weeks'] as List : const []))
          ?RamadanBridgeWeek.fromJson(w),
      ],
      links: ProgramLinks.fromJson(j['links']),
      evidence: EvidenceCard.listFrom(j['evidence']),
    );
  }
}

/// `GET /api/children/{id}/ramadan/today`.
class RamadanToday {
  const RamadanToday({
    required this.childId,
    required this.state,
    this.season,
    this.title,
    this.subtitle,
    this.age = const ProgramAge(basis: 'age_group'),
    this.variantBand,
    this.bandsText,
    this.daysUntilStart,
    this.day,
    this.afterWeek,
    this.kickoff,
    this.content,
    this.eid,
    this.after,
    this.marks,
    this.fasting,
    this.recapAvailable = false,
  });

  final int childId;
  final RamadanState state;
  final RamadanSeason? season;
  final String? title;
  final String? subtitle;
  final ProgramAge age;
  final String? variantBand;

  /// Who sees what — shown to the parent.
  final String? bandsText;
  final int? daysUntilStart;
  final int? day;
  final int? afterWeek;
  final RamadanKickoff? kickoff;
  final RamadanDayContent? content;
  final RamadanEid? eid;
  final RamadanAfter? after;
  final RamadanMarks? marks;

  /// Null for prenatal-1 (no ladder at all).
  final FastingSummary? fasting;
  final bool recapAvailable;

  factory RamadanToday.fromJson(Map<String, dynamic> j) => RamadanToday(
    childId: _int(j['child_id']) ?? -1,
    state: RamadanState.fromWire(_str(j['state'])),
    season: RamadanSeason.fromJson(j['season']),
    title: _str(j['title']),
    subtitle: _str(j['subtitle']),
    age: ProgramAge.fromJson(_map(j['age'])),
    variantBand: _str(j['variant_band']),
    bandsText: _str(j['bands_text']),
    daysUntilStart: _int(j['days_until_start']),
    day: _int(j['day']),
    afterWeek: _int(j['after_week']),
    kickoff: RamadanKickoff.fromJson(j['kickoff']),
    content: RamadanDayContent.fromJson(j['content']),
    eid: RamadanEid.fromJson(j['eid']),
    after: RamadanAfter.fromJson(j['after']),
    marks: RamadanMarks.fromJson(j['marks']),
    fasting: FastingSummary.fromJson(j['fasting']),
    recapAvailable: _bool(j['recap_available']),
  );
}

/// `GET /api/children/{id}/ramadan/days/{day}`.
class RamadanDayView {
  const RamadanDayView({
    required this.childId,
    required this.state,
    this.season,
    this.content,
    this.markable = false,
    this.marks,
  });

  final int childId;
  final RamadanState state;
  final RamadanSeason? season;
  final RamadanDayContent? content;

  /// Up to today during the month; the whole month from Eid to the bridge's end.
  final bool markable;
  final RamadanMarks? marks;

  factory RamadanDayView.fromJson(Map<String, dynamic> j) => RamadanDayView(
    childId: _int(j['child_id']) ?? -1,
    state: RamadanState.fromWire(_str(j['state'])),
    season: RamadanSeason.fromJson(j['season']),
    content: RamadanDayContent.fromJson(j['content']),
    markable: _bool(j['markable']),
    marks: RamadanMarks.fromJson(j['marks']),
  );
}

class FastingStep {
  const FastingStep({
    required this.key,
    required this.label,
    this.until,
    this.approxHours,
    this.minAgeYears,
    this.maxDaysPerWeek,
    this.advanceWhen,
    this.text,
    this.eligible = true,
  });

  final String key;
  final String label;
  final String? until;
  final int? approxHours;
  final int? minAgeYears;
  final int? maxDaysPerWeek;
  final String? advanceWhen;
  final String? text;

  /// False when the child's known age is below [minAgeYears].
  final bool eligible;

  static List<FastingStep> listFrom(Object? v) => [
    for (final j in _maps(v))
      if (_str(j['key']) != null)
        FastingStep(
          key: j['key'] as String,
          label: _str(j['label']) ?? j['key'] as String,
          until: _str(j['until']),
          approxHours: _int(j['approx_hours']),
          minAgeYears: _int(j['min_age_years']),
          maxDaysPerWeek: _int(j['max_days_per_week']),
          advanceWhen: _str(j['advance_when']),
          text: _str(j['text']),
          eligible: j['eligible'] is bool ? j['eligible'] as bool : true,
        ),
  ];
}

/// The safety half of the ladder screen — always shown.
class FastingGuidance {
  const FastingGuidance({
    this.title,
    this.principles = const [],
    this.doctorFirst = const [],
    this.stopSigns = const [],
    this.stopAction,
    this.urgentSigns = const [],
    this.urgentAction,
    this.tips = const [],
    this.evidence = const [],
  });

  final String? title;
  final List<String> principles;
  final List<String> doctorFirst;
  final List<String> stopSigns;
  final String? stopAction;
  final List<String> urgentSigns;
  final String? urgentAction;
  final List<String> tips;
  final List<EvidenceCard> evidence;

  factory FastingGuidance.fromJson(Object? v) {
    final j = _map(v);
    return FastingGuidance(
      title: _str(j?['title']),
      principles: _strings(j?['principles']),
      doctorFirst: _strings(j?['doctor_first']),
      stopSigns: _strings(j?['stop_signs']),
      stopAction: _str(j?['stop_action']),
      urgentSigns: _strings(j?['urgent_signs']),
      urgentAction: _str(j?['urgent_action']),
      tips: _strings(j?['tips']),
      evidence: EvidenceCard.listFrom(j?['evidence']),
    );
  }
}

/// `GET /api/children/{id}/ramadan/fasting` (and the PUT, without guidance).
class FastingLadder {
  const FastingLadder({
    required this.childId,
    required this.state,
    this.season,
    this.day,
    this.age = const ProgramAge(basis: 'age_group'),
    this.ladderBand,
    this.fasts,
    this.summary,
    this.reachedPuberty = false,
    this.currentStep,
    this.steps = const [],
    this.practisedToday = false,
    this.practisedThisWeek = 0,
    this.restSuggested = false,
    this.guidance,
    this.climbed,
  });

  final int childId;
  final RamadanState state;
  final RamadanSeason? season;
  final int? day;
  final ProgramAge age;
  final String? ladderBand;
  final String? fasts;
  final String? summary;
  final bool reachedPuberty;
  final FastingStepSummary? currentStep;
  final List<FastingStep> steps;
  final bool practisedToday;
  final int practisedThisWeek;
  final bool restSuggested;
  final FastingGuidance? guidance;

  /// Present on a PUT response only.
  final bool? climbed;

  bool get noFasting => fasts == 'no';

  /// Practice is recorded only during the month, and only on a set step.
  bool get canPractise =>
      state == RamadanState.ramadan && currentStep != null && !noFasting;

  factory FastingLadder.fromJson(Map<String, dynamic> j) => FastingLadder(
    childId: _int(j['child_id']) ?? -1,
    state: RamadanState.fromWire(_str(j['state'])),
    season: RamadanSeason.fromJson(j['season']),
    day: _int(j['day']),
    age: ProgramAge.fromJson(_map(j['age'])),
    ladderBand: _str(j['ladder_band']),
    fasts: _str(j['fasts']),
    summary: _str(j['summary']),
    reachedPuberty: _bool(j['reached_puberty']),
    currentStep: FastingStepSummary.fromJson(j['current_step']),
    steps: FastingStep.listFrom(j['steps']),
    practisedToday: _bool(j['practised_today']),
    practisedThisWeek: _int(j['practised_this_week']) ?? 0,
    restSuggested: _bool(j['rest_suggested']),
    guidance: j['guidance'] is Map
        ? FastingGuidance.fromJson(j['guidance'])
        : null,
    climbed: j['climbed'] is bool ? j['climbed'] as bool : null,
  );
}

/// One counter on the recap.
class RecapMetric {
  const RecapMetric({required this.key, required this.label, this.value});
  final String key;
  final String label;

  /// An int, or a word (the family's Ramadan word).
  final Object? value;

  String get display => value == null ? '' : '$value';

  static List<RecapMetric> listFrom(Object? v) => [
    for (final j in _maps(v))
      if (_str(j['key']) != null && _str(j['label']) != null)
        RecapMetric(
          key: j['key'] as String,
          label: j['label'] as String,
          value: j['value'],
        ),
  ];
}

/// The shareable card — the only thing that leaves the phone.
class RecapCard {
  const RecapCard({
    required this.headline,
    this.title,
    this.lines = const [],
    this.closing,
    this.shareText,
  });

  final String? title;
  final String headline;

  /// Already filtered by `min_to_show` on the server — never re-add a line.
  final List<String> lines;
  final String? closing;

  /// Carries the family's invite link, so installs are credited to them.
  final String? shareText;

  static RecapCard? fromJson(Object? v) {
    final j = _map(v);
    final headline = _str(j?['headline']);
    if (headline == null) return null;
    return RecapCard(
      title: _str(j!['title']),
      headline: headline,
      lines: [for (final line in _maps(j['lines'])) ?_str(line['text'])],
      closing: _str(j['closing']),
      shareText: _str(j['share_text']),
    );
  }
}

/// `GET /api/programs/ramadan/recap`.
class RamadanRecap {
  const RamadanRecap({
    required this.hijriYear,
    this.available = false,
    this.availableOn,
    this.card,
    this.progress = const [],
    this.familyOnly = const [],
    this.privacy,
  });

  final int? hijriYear;
  final bool available;
  final DateTime? availableOn;

  /// Null before Eid.
  final RecapCard? card;

  /// In-app counters, all month.
  final List<RecapMetric> progress;

  /// The children's fasting — inside the app only, never on the card.
  final List<RecapMetric> familyOnly;
  final String? privacy;

  factory RamadanRecap.fromJson(Map<String, dynamic> j) => RamadanRecap(
    hijriYear: _int(j['hijri_year']),
    available: _bool(j['available']),
    availableOn: _date(j['available_on']),
    card: RecapCard.fromJson(j['card']),
    progress: RecapMetric.listFrom(j['progress']),
    familyOnly: RecapMetric.listFrom(j['family_only']),
    privacy: _str(j['privacy']),
  );
}

// ── Prayer Journey ──────────────────────────────────────────────────────────

class PrayerCovenant {
  const PrayerCovenant({this.coinsTarget, this.examples = const []});
  final int? coinsTarget;
  final List<String> examples;

  static PrayerCovenant? fromJson(Object? v) {
    final j = _map(v);
    if (j == null) return null;
    return PrayerCovenant(
      coinsTarget: _int(j['coins_target']),
      examples: _strings(j['examples']),
    );
  }
}

class PrayerConfirmation {
  const PrayerConfirmation({this.how, this.countsWhen});
  final String? how;
  final String? countsWhen;

  static PrayerConfirmation? fromJson(Object? v) {
    final j = _map(v);
    if (j == null) return null;
    final how = _str(j['how']);
    final counts = _str(j['counts_when']);
    if (how == null && counts == null) return null;
    return PrayerConfirmation(how: how, countsWhen: counts);
  }
}

/// A stage of the twelve weeks, or the ownership track — both parent-facing.
class PrayerStage {
  const PrayerStage({
    required this.title,
    this.stage,
    this.key,
    this.goal,
    this.text,
    this.weekFrom,
    this.weekTo,
    this.parentAssignments = const [],
    this.confirmation,
    this.encouragement = const [],
    this.ifStruggling,
    this.covenant,
    this.lessonIds = const [],
    this.pathIds = const [],
    this.quran = const [],
    this.evidence = const [],
    this.journeyMilestoneKey,
    this.activities = const [],
  });

  final int? stage;
  final String? key;
  final String title;
  final String? goal;
  final String? text;
  final int? weekFrom;
  final int? weekTo;

  /// What the parent does this stage.
  final List<String> parentAssignments;
  final PrayerConfirmation? confirmation;

  /// Sentences the parent says to the child.
  final List<String> encouragement;
  final String? ifStruggling;
  final PrayerCovenant? covenant;
  final List<String> lessonIds;
  final List<String> pathIds;
  final List<QuranRef> quran;
  final List<EvidenceCard> evidence;
  final String? journeyMilestoneKey;

  /// The preparation track's activities (4-6).
  final List<TitledText> activities;

  static PrayerStage? fromJson(Object? v) {
    final j = _map(v);
    final title = _str(j?['title']);
    if (title == null) return null;
    final assignments = [
      for (final a in _maps(j!['parent_assignments'])) ?_str(a['text']),
    ];
    return PrayerStage(
      stage: _int(j['stage']),
      key: _str(j['key']),
      title: title,
      goal: _str(j['goal']),
      text: _str(j['text']),
      weekFrom: _int(j['week_from']),
      weekTo: _int(j['week_to']),
      parentAssignments: assignments,
      confirmation: PrayerConfirmation.fromJson(j['confirmation']),
      encouragement: _strings(j['encouragement']),
      ifStruggling: _str(j['if_struggling']),
      covenant: PrayerCovenant.fromJson(j['covenant']),
      lessonIds: _strings(j['lesson_ids']),
      pathIds: _strings(j['path_ids']),
      quran: QuranRef.listFrom(j['quran']),
      evidence: EvidenceCard.listFrom(j['evidence']),
      journeyMilestoneKey: _str(j['journey_milestone_key']),
      activities: TitledText.listFrom(j['activities']),
    );
  }
}

class PrayerTaskCount {
  const PrayerTaskCount({
    this.recorded = 0,
    this.confirmed = 0,
    this.slotsLeft,
  });
  final int recorded;
  final int confirmed;
  final int? slotsLeft;

  factory PrayerTaskCount.fromJson(Object? v) {
    final j = _map(v);
    return PrayerTaskCount(
      recorded: _int(j?['recorded']) ?? 0,
      confirmed: _int(j?['confirmed']) ?? 0,
      slotsLeft: _int(j?['slots_left']),
    );
  }
}

/// A child task, as the parent sees it (with counts).
class PrayerTask {
  const PrayerTask({
    required this.taskId,
    required this.title,
    this.instruction,
    this.estimatedMinutes,
    this.needsParent = false,
    this.coins = 0,
    this.perWeek,
    this.perDay = 1,
    this.weekLimit,
    this.today = const PrayerTaskCount(),
    this.thisWeek = const PrayerTaskCount(),
  });

  final String taskId;
  final String title;
  final String? instruction;
  final int? estimatedMinutes;
  final bool needsParent;
  final int coins;

  /// A goal, not a condition.
  final int? perWeek;
  final int perDay;
  final int? weekLimit;
  final PrayerTaskCount today;
  final PrayerTaskCount thisWeek;

  static List<PrayerTask> listFrom(Object? v) => [
    for (final j in _maps(v))
      if (_str(j['task_id']) != null && _str(j['title']) != null)
        PrayerTask(
          taskId: j['task_id'] as String,
          title: j['title'] as String,
          instruction: _str(j['instruction']),
          estimatedMinutes: _int(j['estimated_minutes']),
          needsParent: _bool(j['needs_parent']),
          coins: _int(j['coins']) ?? 0,
          perWeek: _int(j['per_week']),
          perDay: _int(j['per_day']) ?? 1,
          weekLimit: _int(j['week_limit']),
          today: PrayerTaskCount.fromJson(j['today']),
          thisWeek: PrayerTaskCount.fromJson(j['this_week']),
        ),
  ];
}

class PrayerEnrolment {
  const PrayerEnrolment({
    required this.track,
    this.stage,
    this.status,
    this.startedOn,
    this.week,
  });

  final PrayerTrack track;
  final int? stage;
  final String? status;
  final DateTime? startedOn;
  final int? week;

  static PrayerEnrolment? fromJson(Object? v) {
    final j = _map(v);
    final track = PrayerTrack.fromWire(_str(j?['track']));
    if (j == null || track == null) return null;
    return PrayerEnrolment(
      track: track,
      stage: _int(j['stage']),
      status: _str(j['status']),
      startedOn: _date(j['started_on']),
      week: _int(j['week']),
    );
  }
}

class PrayerAdvancement {
  const PrayerAdvancement({
    this.daysInStage = 0,
    this.stagePlannedDays,
    this.nextStage,
    this.advanceSuggested = false,
    this.advanceSuggestedOn,
    this.canGraduate = false,
    this.graduationAvailableOn,
  });

  final int daysInStage;
  final int? stagePlannedDays;
  final int? nextStage;
  final bool advanceSuggested;
  final DateTime? advanceSuggestedOn;
  final bool canGraduate;
  final DateTime? graduationAvailableOn;

  static PrayerAdvancement? fromJson(Object? v) {
    final j = _map(v);
    if (j == null) return null;
    return PrayerAdvancement(
      daysInStage: _int(j['days_in_stage']) ?? 0,
      stagePlannedDays: _int(j['stage_planned_days']),
      nextStage: _int(j['next_stage']),
      advanceSuggested: _bool(j['advance_suggested']),
      advanceSuggestedOn: _date(j['advance_suggested_on']),
      canGraduate: _bool(j['can_graduate']),
      graduationAvailableOn: _date(j['graduation_available_on']),
    );
  }
}

class PrayerGraduation {
  const PrayerGraduation({
    this.title,
    this.text,
    this.certificateText,
    this.covenant,
    this.journeyMilestoneKeys = const [],
    this.evidence = const [],
  });

  final String? title;

  /// Parent-only.
  final String? text;

  /// For the child, printed on the certificate.
  final String? certificateText;
  final PrayerCovenant? covenant;
  final List<String> journeyMilestoneKeys;
  final List<EvidenceCard> evidence;

  factory PrayerGraduation.fromJson(Object? v) {
    final j = _map(v);
    return PrayerGraduation(
      title: _str(j?['title']),
      text: _str(j?['text']),
      certificateText: _str(j?['certificate_text']),
      covenant: PrayerCovenant.fromJson(j?['covenant']),
      journeyMilestoneKeys: _strings(j?['journey_milestone_keys']),
      evidence: EvidenceCard.listFrom(j?['evidence']),
    );
  }
}

class StageOutline {
  const StageOutline({
    required this.stage,
    required this.title,
    this.goal,
    this.weekFrom,
    this.weekTo,
  });
  final int stage;
  final String title;
  final String? goal;
  final int? weekFrom;
  final int? weekTo;

  static List<StageOutline> listFrom(Object? v) => [
    for (final j in _maps(v))
      if (_int(j['stage']) != null && _str(j['title']) != null)
        StageOutline(
          stage: _int(j['stage'])!,
          title: j['title'] as String,
          goal: _str(j['goal']),
          weekFrom: _int(j['week_from']),
          weekTo: _int(j['week_to']),
        ),
  ];
}

/// `GET /api/children/{id}/prayer-journey` (and every change's response).
class PrayerJourney {
  const PrayerJourney({
    required this.childId,
    this.title,
    this.subtitle,
    this.age = const ProgramAge(basis: 'age_group'),
    this.eligibleTrack,
    this.allowedTracks = const [],
    this.bandsText,
    this.enrolment,
    this.basis,
    this.principles = const [],
    this.rewardPolicy,
    this.dailyCap,
    this.stages = const [],
    this.graduation = const PrayerGraduation(),
    this.graduatedOn,
    this.stage,
    this.preparation,
    this.ownership,
    this.tasks = const [],
    this.advancement,
    this.pendingConfirmations = 0,
    this.coinsConfirmedInStage,
    this.covenantTarget,
  });

  final int childId;
  final String? title;
  final String? subtitle;
  final ProgramAge age;
  final PrayerTrack? eligibleTrack;
  final List<PrayerTrack> allowedTracks;
  final String? bandsText;
  final PrayerEnrolment? enrolment;
  final ParentNote? basis;
  final List<String> principles;
  final String? rewardPolicy;
  final int? dailyCap;
  final List<StageOutline> stages;
  final PrayerGraduation graduation;
  final DateTime? graduatedOn;
  final PrayerStage? stage;
  final PrayerStage? preparation;
  final PrayerStage? ownership;
  final List<PrayerTask> tasks;
  final PrayerAdvancement? advancement;
  final int pendingConfirmations;
  final int? coinsConfirmedInStage;
  final int? covenantTarget;

  bool get enrolled => enrolment != null;
  bool get eligible => eligibleTrack != null || allowedTracks.isNotEmpty;

  factory PrayerJourney.fromJson(Map<String, dynamic> j) {
    final reward = _map(j['reward_policy']);
    final coins = _map(j['coins']);
    return PrayerJourney(
      childId: _int(j['child_id']) ?? -1,
      title: _str(j['title']),
      subtitle: _str(j['subtitle']),
      age: ProgramAge.fromJson(_map(j['age'])),
      eligibleTrack: PrayerTrack.fromWire(_str(j['eligible_track'])),
      allowedTracks: [
        for (final t in _strings(j['allowed_tracks'])) ?PrayerTrack.fromWire(t),
      ],
      bandsText: _str(j['bands_text']),
      enrolment: PrayerEnrolment.fromJson(j['enrolment']),
      basis: ParentNote.fromJson(j['basis']),
      principles: _strings(j['principles']),
      rewardPolicy: _str(reward?['text']),
      dailyCap: _int(reward?['daily_cap']),
      stages: StageOutline.listFrom(j['stages']),
      graduation: PrayerGraduation.fromJson(j['graduation']),
      graduatedOn: _date(j['graduated_on']),
      stage: PrayerStage.fromJson(j['stage']),
      preparation: PrayerStage.fromJson(j['preparation']),
      ownership: PrayerStage.fromJson(j['ownership']),
      tasks: PrayerTask.listFrom(j['tasks']),
      advancement: PrayerAdvancement.fromJson(j['advancement']),
      pendingConfirmations: _int(j['pending_confirmations']) ?? 0,
      coinsConfirmedInStage: _int(coins?['confirmed_in_stage']),
      covenantTarget: _int(coins?['covenant_target']),
    );
  }
}

/// A task as the child sees it in child mode — no stage, no parent text.
class ChildPrayerTask {
  const ChildPrayerTask({
    required this.taskId,
    required this.title,
    this.instruction,
    this.coins = 0,
    this.needsParent = false,
    this.perDay = 1,
    this.recordedToday = 0,
    this.slotsLeftToday = 1,
    this.recordedThisWeek = 0,
  });

  final String taskId;
  final String title;
  final String? instruction;
  final int coins;
  final bool needsParent;
  final int perDay;
  final int recordedToday;

  /// Zero = done for today (✓), never an error.
  final int slotsLeftToday;
  final int recordedThisWeek;

  bool get doneForToday => slotsLeftToday <= 0;

  ChildPrayerTask copyWith({
    int? recordedToday,
    int? slotsLeftToday,
    int? recordedThisWeek,
  }) => ChildPrayerTask(
    taskId: taskId,
    title: title,
    instruction: instruction,
    coins: coins,
    needsParent: needsParent,
    perDay: perDay,
    recordedToday: recordedToday ?? this.recordedToday,
    slotsLeftToday: slotsLeftToday ?? this.slotsLeftToday,
    recordedThisWeek: recordedThisWeek ?? this.recordedThisWeek,
  );

  static List<ChildPrayerTask> listFrom(Object? v) => [
    for (final j in _maps(v))
      if (_str(j['task_id']) != null && _str(j['title']) != null)
        ChildPrayerTask(
          taskId: j['task_id'] as String,
          title: j['title'] as String,
          instruction: _str(j['instruction']),
          coins: _int(j['coins']) ?? 0,
          needsParent: _bool(j['needs_parent']),
          perDay: _int(j['per_day']) ?? 1,
          recordedToday: _int(j['recorded_today']) ?? 0,
          slotsLeftToday: _int(j['slots_left_today']) ?? 0,
          recordedThisWeek: _int(j['recorded_this_week']) ?? 0,
        ),
  ];
}

/// `GET /api/value-tracking/child-mode/prayer/today`.
class ChildPrayerToday {
  const ChildPrayerToday({
    this.enrolled = false,
    this.track,
    this.tasks = const [],
    this.available = true,
  });
  final bool enrolled;
  final PrayerTrack? track;
  final List<ChildPrayerTask> tasks;

  /// False when the program file cannot be read right now — not an error.
  final bool available;

  /// `enrolled: false`, `available: false` (or no tasks) → show nothing.
  bool get hasTasks => available && enrolled && tasks.isNotEmpty;

  factory ChildPrayerToday.fromJson(Map<String, dynamic> j) => ChildPrayerToday(
    enrolled: _bool(j['enrolled']),
    track: PrayerTrack.fromWire(_str(j['track'])),
    tasks: ChildPrayerTask.listFrom(j['tasks']),
    // Absent before the PR #32 review: those servers always served the file.
    available: j['available'] is bool ? j['available'] as bool : true,
  );
}

// ── Milestones ──────────────────────────────────────────────────────────────

class MilestoneCard {
  const MilestoneCard({required this.title, required this.body});
  final String title;
  final String body;

  static List<MilestoneCard> listFrom(Object? v) => [
    for (final j in _maps(v))
      if (_str(j['title']) != null && _str(j['body']) != null)
        MilestoneCard(title: j['title'] as String, body: j['body'] as String),
  ];
}

/// One milestone — every text in it is for the parent.
class Milestone {
  const Milestone({
    required this.key,
    required this.title,
    required this.state,
    this.order,
    this.basis,
    this.dueOn,
    this.alertOn,
    this.medical = false,
    this.alertTitle,
    this.alertBody,
    this.cards = const [],
    this.redFlags = const [],
    this.quran = const [],
    this.evidence = const [],
    this.links = const ProgramLinks(),
    this.seasonName,
  });

  final String key;
  final String title;

  /// `due | upcoming | library | past`.
  final String state;
  final int? order;
  final String? basis;
  final DateTime? dueOn;
  final DateTime? alertOn;

  /// Carries red flags — render them visibly.
  final bool medical;
  final String? alertTitle;
  final String? alertBody;
  final List<MilestoneCard> cards;
  final List<String> redFlags;
  final List<QuranRef> quran;
  final List<EvidenceCard> evidence;
  final ProgramLinks links;
  final String? seasonName;

  static Milestone? fromJson(Object? v) {
    final j = _map(v);
    final key = _str(j?['key']);
    final title = _str(j?['title']);
    if (j == null || key == null || title == null) return null;
    final alert = _map(j['alert']);
    return Milestone(
      key: key,
      title: title,
      state: _str(j['state']) ?? 'library',
      order: _int(j['order']),
      basis: _str(j['basis']),
      dueOn: _date(j['due_on']),
      alertOn: _date(j['alert_on']),
      medical: _bool(j['medical']),
      alertTitle: _str(alert?['title']),
      alertBody: _str(alert?['body']),
      cards: MilestoneCard.listFrom(j['cards']),
      redFlags: _strings(j['red_flags']),
      quran: QuranRef.listFrom(j['quran']),
      evidence: EvidenceCard.listFrom(j['evidence']),
      links: ProgramLinks.fromJson(j['links']),
      seasonName: _str(_map(j['season'])?['name']),
    );
  }

  static List<Milestone> listFrom(Object? v) => [
    for (final j in (v is List ? v : const [])) ?Milestone.fromJson(j),
  ];
}

/// `GET /api/children/{id}/milestones`.
class MilestonesList {
  const MilestonesList({
    required this.childId,
    this.age = const ProgramAge(basis: 'age_group'),
    this.alertPolicy,
    this.pushes = false,
    this.needsProfile = const [],
    this.due = const [],
    this.upcoming = const [],
    this.library = const [],
    this.past = const [],
  });

  final int childId;
  final ProgramAge age;
  final String? alertPolicy;
  final bool pushes;
  final List<String> needsProfile;
  final List<Milestone> due;
  final List<Milestone> upcoming;
  final List<Milestone> library;
  final List<Milestone> past;

  bool get needsBirthMonth => needsProfile.contains('birth_month');
  bool get needsGender => needsProfile.contains('gender');
  bool get isEmpty =>
      due.isEmpty && upcoming.isEmpty && library.isEmpty && past.isEmpty;

  factory MilestonesList.fromJson(Map<String, dynamic> j) {
    final policy = _map(j['alert_policy']);
    return MilestonesList(
      childId: _int(j['child_id']) ?? -1,
      age: ProgramAge.fromJson(_map(j['age'])),
      alertPolicy: _str(policy?['text']),
      pushes: _bool(policy?['pushes']),
      needsProfile: _strings(j['needs_profile']),
      due: Milestone.listFrom(j['due']),
      upcoming: Milestone.listFrom(j['upcoming']),
      library: Milestone.listFrom(j['library']),
      past: Milestone.listFrom(j['past']),
    );
  }
}
