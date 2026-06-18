/// «رحلة الطفل» — local-only, per-child milestone log (Phase 1).
///
/// Backed by [SharedPreferences]. Unlike reflection notes (which are
/// device-global), the journey IS scoped per child: the store is a
/// `Map<childId, Map<milestoneKey, MilestoneEntry>>` persisted as one
/// JSON blob under [_kJourney]. Each entry is a milestone the parent
/// has marked for that child — a spiritual milestone from the catalogue
/// (`journey_milestones.dart`) or a custom note. If the project ever
/// needs cross-device sync, this module is the only thing to swap.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class MilestoneEntry {
  final int childId;

  /// The catalogue key (e.g. `first_prayer`) or `custom_<ts>` for a
  /// parent-authored milestone. Doubles as the per-child map key, so a
  /// catalogue milestone is logged at most once per child.
  final String key;
  final String title;
  final String emoji;
  final String note;
  final DateTime achievedAt;

  const MilestoneEntry({
    required this.childId,
    required this.key,
    required this.title,
    required this.emoji,
    this.note = '',
    required this.achievedAt,
  });

  Map<String, dynamic> toJson() => {
        'child_id': childId,
        'key': key,
        'title': title,
        'emoji': emoji,
        'note': note,
        'achieved_at': achievedAt.toUtc().toIso8601String(),
      };

  factory MilestoneEntry.fromJson(Map<String, dynamic> json) {
    return MilestoneEntry(
      childId: (json['child_id'] as num).toInt(),
      key: json['key'] as String,
      title: (json['title'] as String?) ?? '',
      emoji: (json['emoji'] as String?) ?? '🌟',
      note: (json['note'] as String?) ?? '',
      achievedAt: DateTime.parse(json['achieved_at'] as String),
    );
  }

  MilestoneEntry copyWith({String? note, DateTime? achievedAt}) {
    return MilestoneEntry(
      childId: childId,
      key: key,
      title: title,
      emoji: emoji,
      note: note ?? this.note,
      achievedAt: achievedAt ?? this.achievedAt,
    );
  }
}

class JourneyStore {
  JourneyStore(this._prefs);

  /// Max length for the optional milestone note (mirrors reflections).
  static const int kMaxNoteLength = 300;

  static const String _kJourney = 'tg.journey.v1';

  final SharedPreferences _prefs;

  /// All milestones logged for one child, keyed by milestone key.
  Map<String, MilestoneEntry> loadForChild(int childId) {
    return _loadAll()[childId.toString()] ?? <String, MilestoneEntry>{};
  }

  Future<MilestoneEntry> upsert(MilestoneEntry entry) async {
    final all = _loadAll();
    final cid = entry.childId.toString();
    final forChild = all[cid] ?? <String, MilestoneEntry>{};
    forChild[entry.key] = entry;
    all[cid] = forChild;
    await _persist(all);
    return entry;
  }

  Future<void> delete(int childId, String key) async {
    final all = _loadAll();
    final cid = childId.toString();
    final forChild = all[cid];
    if (forChild != null && forChild.remove(key) != null) {
      all[cid] = forChild;
      await _persist(all);
    }
  }

  Future<void> clearAll() async {
    await _prefs.remove(_kJourney);
  }

  Map<String, Map<String, MilestoneEntry>> _loadAll() {
    final raw = _prefs.getString(_kJourney);
    if (raw == null || raw.isEmpty) return {};
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      return {
        for (final child in decoded.entries)
          child.key: {
            for (final m in (child.value as Map<String, dynamic>).entries)
              m.key: MilestoneEntry.fromJson(m.value as Map<String, dynamic>),
          },
      };
    } catch (_) {
      // Corrupted blob — start fresh rather than crash the screen.
      return {};
    }
  }

  Future<void> _persist(Map<String, Map<String, MilestoneEntry>> all) async {
    final raw = jsonEncode({
      for (final child in all.entries)
        child.key: {
          for (final m in child.value.entries) m.key: m.value.toJson(),
        },
    });
    await _prefs.setString(_kJourney, raw);
  }
}
