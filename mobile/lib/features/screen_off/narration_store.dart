/// A parent's voice, kept on the device.
///
/// The app already generates the story; this records a parent reading it once
/// so a child can hear it in their father's or mother's voice afterwards —
/// including on nights the parent is not there. It turns the app from a
/// substitute for a parent into a bridge to one, which is a different product
/// even though it is a small feature.
///
/// **Nothing here leaves the device.** No upload, no sync, no cloud backup —
/// the last of those is not a promise but a configuration, and it lives in
/// android/app/src/main/res/xml/backup_rules.xml and data_extraction_rules.xml.
/// A promise in a privacy screen that is not also a line in a manifest is a
/// sentence, not a guarantee.
///
/// The index is a plain map in SharedPreferences rather than a database: it is
/// a handful of entries per family and it has to survive the file being
/// deleted from underneath it, which is the interesting case.
library;

import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// The key a story's narration is filed under.
///
/// Two features write into this index — the bookshelf's fourteen written
/// stories and the generated-story screen — and they have to agree on the
/// shape or a recording made by one is invisible to the other. It lives here,
/// beside the store, rather than in either screen.
String narrationKeyFor(String storyId) => 'story_$storyId';

class Narration {
  const Narration({
    required this.storyKey,
    required this.path,
    required this.recordedAt,
  });

  final String storyKey;
  final String path;
  final String recordedAt;

  Map<String, dynamic> toJson() =>
      {'storyKey': storyKey, 'path': path, 'recordedAt': recordedAt};

  factory Narration.fromJson(Map<String, dynamic> j) => Narration(
        storyKey: j['storyKey'] as String,
        path: j['path'] as String,
        recordedAt: j['recordedAt'] as String,
      );
}

class NarrationStore {
  NarrationStore._();
  static final NarrationStore instance = NarrationStore._();

  static const _kIndex = 'narration.index';

  /// Where recordings live. Excluded from backup by name, so the folder is
  /// part of the contract rather than an implementation detail.
  static const folderName = 'narrations';

  Future<Directory> folder() async {
    final docs = await getApplicationDocumentsDirectory();
    final dir = Directory('${docs.path}/$folderName');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  Future<String> pathFor(String storyKey) async {
    final dir = await folder();
    final safe = storyKey.replaceAll(RegExp(r'[^\w-]'), '_');
    return '${dir.path}/$safe.m4a';
  }

  Future<Map<String, Narration>> _read(SharedPreferences p) async {
    final raw = p.getString(_kIndex);
    if (raw == null) return {};
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      return map.map((k, v) =>
          MapEntry(k, Narration.fromJson(v as Map<String, dynamic>)));
    } catch (_) {
      return {};
    }
  }

  Future<void> _write(SharedPreferences p, Map<String, Narration> index) async {
    await p.setString(_kIndex,
        jsonEncode(index.map((k, v) => MapEntry(k, v.toJson()))));
  }

  Future<void> register(String storyKey, String path) async {
    final p = await SharedPreferences.getInstance();
    final index = await _read(p);
    index[storyKey] = Narration(
      storyKey: storyKey,
      path: path,
      recordedAt: DateTime.now().toIso8601String(),
    );
    await _write(p, index);
  }

  /// The recording for a story, or null.
  ///
  /// A file that has vanished — cleared by the OS, deleted by a file manager —
  /// is dropped from the index silently and reported as absent. A child asking
  /// for their father's voice and getting an error dialog is worse than a
  /// child getting the story without it.
  Future<Narration?> find(String storyKey) async {
    final p = await SharedPreferences.getInstance();
    final index = await _read(p);
    final entry = index[storyKey];
    if (entry == null) return null;
    if (!await File(entry.path).exists()) {
      index.remove(storyKey);
      await _write(p, index);
      return null;
    }
    return entry;
  }

  /// Story keys that still have a playable recording behind them.
  Future<Set<String>> available() async {
    final p = await SharedPreferences.getInstance();
    final index = await _read(p);
    final alive = <String>{};
    var pruned = false;
    for (final entry in index.values) {
      if (await File(entry.path).exists()) {
        alive.add(entry.storyKey);
      } else {
        pruned = true;
      }
    }
    if (pruned) {
      index.removeWhere((k, v) => !alive.contains(k));
      await _write(p, index);
    }
    return alive;
  }

  Future<void> delete(String storyKey) async {
    final p = await SharedPreferences.getInstance();
    final index = await _read(p);
    final entry = index.remove(storyKey);
    await _write(p, index);
    if (entry != null) {
      final file = File(entry.path);
      if (await file.exists()) await file.delete();
    }
  }
}
