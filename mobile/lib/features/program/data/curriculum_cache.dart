/// A last-known-good copy of the curriculum, for when the network is not there.
///
/// The app was online-only: a parent opening it on the metro, or on a phone
/// that has run out of data, saw an error where the paths should be. The
/// curriculum barely changes from one day to the next, so serving yesterday's
/// copy is far better than serving nothing.
///
/// Only responses that already arrived successfully are stored, so a cached
/// entry is always something the server really said.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class CurriculumCache {
  CurriculumCache({SharedPreferences? prefs}) : _injected = prefs;

  static const _prefix = 'curriculum_cache.';

  /// Old enough that the content is likely to have moved on. Nothing is
  /// deleted at this age — it is still served when the alternative is an
  /// error — but [readFresh] refuses it.
  static const staleAfter = Duration(days: 14);

  final SharedPreferences? _injected;

  /// Null when the store is unavailable — a full disk, a platform without the
  /// plugin. Every caller treats that as "no cache" rather than an error: this
  /// is an optimisation, and its failure must never become the reader's.
  Future<SharedPreferences?> get _prefs async {
    if (_injected != null) return _injected;
    try {
      return await SharedPreferences.getInstance();
    } catch (_) {
      return null;
    }
  }

  String _key(String key) => '$_prefix$key';

  Future<void> write(String key, Map<String, dynamic> payload) async {
    try {
      final prefs = await _prefs;
      if (prefs == null) return;
      await prefs.setString(
        _key(key),
        jsonEncode({
          'saved_at': DateTime.now().toUtc().toIso8601String(),
          'payload': payload,
        }),
      );
    } catch (_) {
      // Failing to remember a response is not a reason to withhold it.
    }
  }

  /// The stored copy, however old, or null if there is none.
  Future<Map<String, dynamic>?> read(String key) async {
    final entry = await _readEntry(key);
    return entry?.payload;
  }

  /// The stored copy only if it is younger than [staleAfter].
  Future<Map<String, dynamic>?> readFresh(String key) async {
    final entry = await _readEntry(key);
    if (entry == null) return null;
    return entry.age < staleAfter ? entry.payload : null;
  }

  Future<_CacheEntry?> _readEntry(String key) async {
    final prefs = await _prefs;
    if (prefs == null) return null;
    final raw = prefs.getString(_key(key));
    if (raw == null) return null;
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      final payload = decoded['payload'];
      final savedAt = DateTime.tryParse(decoded['saved_at'] as String? ?? '');
      if (payload is! Map<String, dynamic> || savedAt == null) return null;
      return _CacheEntry(payload, savedAt);
    } catch (_) {
      // A malformed entry is indistinguishable from no entry — the caller
      // falls through to the network either way.
      return null;
    }
  }
}

class _CacheEntry {
  _CacheEntry(this.payload, this.savedAt);

  final Map<String, dynamic> payload;
  final DateTime savedAt;

  Duration get age => DateTime.now().toUtc().difference(savedAt);
}
