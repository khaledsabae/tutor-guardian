/// Phase 8-C — local-only reflection notes.
///
/// Backed by [SharedPreferences]. One note per lesson, capped at
/// [kMaxNoteLength] characters. The structure is intentionally
/// simple — a single JSON map keyed by lesson_id. If the project
/// ever needs cross-device sync, this module is the only thing to
/// swap (the [ReflectionEntry] model stays the same).
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class ReflectionEntry {
  final String lessonId;
  final String text;
  final DateTime createdAt;
  final DateTime updatedAt;

  const ReflectionEntry({
    required this.lessonId,
    required this.text,
    required this.createdAt,
    required this.updatedAt,
  });

  Map<String, dynamic> toJson() => {
        'lesson_id': lessonId,
        'text': text,
        'created_at': createdAt.toUtc().toIso8601String(),
        'updated_at': updatedAt.toUtc().toIso8601String(),
      };

  factory ReflectionEntry.fromJson(Map<String, dynamic> json) {
    return ReflectionEntry(
      lessonId: json['lesson_id'] as String,
      text: (json['text'] as String?) ?? '',
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  ReflectionEntry copyWith({String? text, DateTime? updatedAt}) {
    return ReflectionEntry(
      lessonId: lessonId,
      text: text ?? this.text,
      createdAt: createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}

class ReflectionStorage {
  ReflectionStorage(this._prefs);

  /// The maximum length the UI will accept. The backend equivalent
  /// (if we ever add one) should mirror this.
  static const int kMaxNoteLength = 500;

  /// Storage key. ONE map for the whole device — reflection notes
  /// are not scoped per child (the parent writes them, the child
  /// doesn't see the app). If the user switches devices, they lose
  /// their notes — that's the local-only trade-off documented in
  /// the privacy policy.
  static const String _kReflections = 'tg.reflections.v1';

  final SharedPreferences _prefs;

  /// Read all reflections as a `lesson_id → entry` map.
  Map<String, ReflectionEntry> loadAll() {
    final raw = _prefs.getString(_kReflections);
    if (raw == null || raw.isEmpty) return {};
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      return {
        for (final e in decoded.values)
          (e as Map<String, dynamic>)['lesson_id'] as String:
              ReflectionEntry.fromJson(e),
      };
    } catch (_) {
      // Corrupted entry — start fresh rather than crash the screen.
      return {};
    }
  }

  Future<void> upsert(ReflectionEntry entry) async {
    final all = loadAll();
    all[entry.lessonId] = entry;
    await _persist(all);
  }

  Future<void> delete(String lessonId) async {
    final all = loadAll();
    if (all.remove(lessonId) != null) {
      await _persist(all);
    }
  }

  Future<void> clearAll() async {
    await _prefs.remove(_kReflections);
  }

  Future<void> _persist(Map<String, ReflectionEntry> all) async {
    final raw = jsonEncode({
      for (final e in all.values) e.lessonId: e.toJson(),
    });
    await _prefs.setString(_kReflections, raw);
  }
}
