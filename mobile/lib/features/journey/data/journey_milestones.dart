/// «رحلة الطفل» — the spiritual-milestone catalogue (Phase 1, local).
///
/// A curated, ordered list of Islamic milestones a parent can mark for
/// their child. NOT generated — calm, encouraging tone («ما شاء الله»),
/// never medical, never age-gated baby advice. Pillar 2 (developmental,
/// age-derived from the curriculum) lands in a later phase; the
/// `first_surah` milestone will link to Quran memorization tracking
/// (Phase 4).
///
/// The catalogue itself moved to `assets/content/journey/milestones.ar.json`
/// on 2026-08-13 (`ops/tools/extract_app_content.py`); this file keeps the
/// model, the badge mapping and the reward-id rule, which are code.
library;

import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;

class JourneyMilestone {
  final String key;
  final String title;
  final String description;
  final String emoji;

  /// Optional, gentle, DEVELOPMENTAL-only "what if it's late" note shown
  /// under a suggested milestone. Never medical, never a diagnosis —
  /// always routes to «استشر مختصًا» for the few items that warrant it.
  final String? concernNote;

  const JourneyMilestone({
    required this.key,
    required this.title,
    required this.description,
    required this.emoji,
    this.concernNote,
  });
}

/// The milestone catalogue, loaded once at startup from
/// `assets/content/journey/milestones.ar.json`.
///
/// `main()` awaits [load] before `runApp`, so [spiritualMilestones] and
/// [developmentalMilestonesFor] stay synchronous for the widgets that read
/// them during a build.
class JourneyMilestones {
  JourneyMilestones._();

  static const asset = 'assets/content/journey/milestones.ar.json';

  static List<JourneyMilestone> _spiritual = const [];
  static Map<String, List<JourneyMilestone>> _developmental = const {};
  static bool _loaded = false;

  static bool get isLoaded => _loaded;

  static Future<void> load() async {
    if (_loaded) return;
    parse(await rootBundle.loadString(asset));
    _loaded = true;
  }

  /// Split out so tests can exercise the parse without an asset bundle.
  static void parse(String raw) {
    final json = jsonDecode(raw) as Map<String, dynamic>;
    _spiritual = [
      for (final m in (json['spiritual'] as List<dynamic>))
        _fromJson(m as Map<String, dynamic>),
    ];
    _developmental = {
      for (final entry in (json['developmental'] as Map<String, dynamic>).entries)
        entry.key: [
          for (final m in (entry.value as List<dynamic>))
            _fromJson(m as Map<String, dynamic>),
        ],
    };
  }

  static JourneyMilestone _fromJson(Map<String, dynamic> m) => JourneyMilestone(
        key: m['key'] as String,
        title: m['title'] as String,
        description: m['description'] as String,
        emoji: m['emoji'] as String,
        concernNote: m['concern_note'] as String?,
      );

  /// Test seam. Nothing in the app calls this.
  static void resetForTesting() {
    _spiritual = const [];
    _developmental = const {};
    _loaded = false;
  }
}

/// Display order = a rough spiritual-growth sequence; the parent is free
/// to mark them in any order.
List<JourneyMilestone> get spiritualMilestones => JourneyMilestones._spiritual;

/// A spiritual milestone by key, or null if the pack did not load.
///
/// Callers used to reach for `spiritualMilestones.firstWhere(…)` against a
/// `const` list, where a match was guaranteed by the compiler. It is an asset
/// now, so the guarantee is gone and `firstWhere` would throw where the old
/// code could not.
JourneyMilestone? spiritualMilestone(String key) {
  for (final m in JourneyMilestones._spiritual) {
    if (m.key == key) return m;
  }
  return null;
}

/// Reward id namespaced per child so each child's milestone is rewarded
/// exactly once (the device-wide coins ledger dedups by id).
String journeyRewardId(int childId, String milestoneKey) =>
    'journey:$childId:$milestoneKey';

/// The 9 spiritual milestones that ship with a custom badge illustration
/// (assets/images/milestones/`<key>`.png). Developmental + custom milestones
/// have no badge and fall back to their emoji.
const Set<String> _badgeMilestoneKeys = {
  'shahada',
  'first_dua',
  'first_prayer',
  'keeps_prayer',
  'first_surah',
  'first_fast',
  'good_manner',
  'helped_others',
  'quran_khatma',
};

/// Asset path for a milestone's badge illustration, or null if it has none
/// (the caller then shows [JourneyMilestone.emoji] / [MilestoneEntry.emoji]).
String? milestoneBadgeAsset(String key) {
  if (!_badgeMilestoneKeys.contains(key)) return null;
  // Unified brand set (logo-centric) — replaces the old PNGs.
  const branded = {
    'first_prayer', 'first_surah', 'first_fast',
    'first_dua', 'good_manner', 'helped_others',
    'keeps_prayer', 'quran_khatma', 'shahada',
  };
  if (branded.contains(key)) {
    if ({'first_prayer', 'first_surah', 'first_fast'}.contains(key)) {
      return 'assets/images/generated/milestone_first_$key.webp';
    }
    return 'assets/images/generated/badge_$key.webp';
  }
  return 'assets/images/milestones/$key.png';
}

/// Developmental milestones for a child's age band. `0-3` is the legacy
/// alias for `prenatal-1`. Returns `[]` for unknown bands.
///
/// Bands come from the `development` domain of the curriculum. Keys are
/// `dev_*`-prefixed to share the per-child store with the spiritual ones
/// without colliding. The handful of `concernNote`s are gentle,
/// developmental, never medical.
List<JourneyMilestone> developmentalMilestonesFor(String? ageGroup) {
  if (ageGroup == null) return const [];
  final band = ageGroup == '0-3' ? 'prenatal-1' : ageGroup;
  return JourneyMilestones._developmental[band] ?? const [];
}
