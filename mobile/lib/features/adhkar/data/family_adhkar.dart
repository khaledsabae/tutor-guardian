/// Family parenting content — Qur'an verses, hadith and practical parenting
/// tips used for the daily notifications.
///
/// 281 items: 142 verses, 124 tips and 15 hadith. They live in
/// `assets/content/adhkar/family_adhkar.ar.json` (moved out of this file on
/// 2026-08-13 by `ops/tools/extract_app_content.py`, which proved the move
/// byte-for-byte). Every verse is checked against the mushaf on each commit by
/// `ops/tools/check_quran_citations.py`; the pack is checked for padding and
/// blanket attribution by `ops/tools/check_adhkar_integrity.py`. Those guards
/// now read the JSON — the content moved, the gate did not open.
///
/// **Hadith are from Sahih al-Bukhari and Sahih Muslim only**, quoted as the
/// matn alone with the book and number, and checked against
/// `ops/tools/check_hadith_citations.py` on every commit. Restricting the
/// source to the two Sahihs takes the grading question — which is scholarship,
/// not string work — off the table, and leaves wording and number, which a
/// machine can verify. Where a quote is shortened it stays one contiguous run
/// of the narration; the checker rejects anything stitched.
///
/// This list previously claimed 730 unique items and held 267: one hadith text
/// repeated 223 times, each copy made "unique" by a visible «(حديث رقم N)»
/// counter and stamped with the same invented isnad, «صحيح — رواه الترمذي
/// وأبو داود». Those 223 went out as daily notifications attributing words to
/// the Prophet ﷺ with a fabricated chain. Two users reported it on 2026-08-03
/// and 2026-08-07 and nobody was listening, because the feedback alerts had
/// never been configured.
///
/// Nothing here is generated. A hadith enters only by being found verbatim in
/// one of the two Sahihs.
library;

import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;

class ParentingContent {
  /// Stable, permanent handle — `v_014_040`, `h_003`, `t_001`.
  ///
  /// Not a list index. Notifications are queued up to 14 days ahead and carry
  /// this in their payload, so the tap handler resolves what was *scheduled*
  /// rather than whatever now sits at that position. Reordering the pack used
  /// to mean a queued notification opening a different verse than the one it
  /// showed.
  final String id;
  final String text;
  final String source;
  final String topic;

  /// 'hadith' | 'verse' | 'tip'
  final String kind;

  const ParentingContent({
    required this.id,
    required this.text,
    required this.source,
    required this.topic,
    required this.kind,
  });

  factory ParentingContent.fromJson(Map<String, dynamic> json) =>
      ParentingContent(
        id: json['id'] as String,
        text: json['text'] as String,
        source: json['source'] as String,
        topic: json['topic'] as String,
        kind: json['kind'] as String,
      );
}

/// The parenting-content pack, loaded once at startup.
///
/// `main()` awaits [load] before `runApp`, and before
/// `NotificationService.init()` — which schedules from it. Everything that
/// reads [items] runs after that, so the getter stays synchronous and the
/// scheduler keeps its plain index arithmetic over a settled list.
///
/// The structured provenance in the JSON (numeric surah/ayah, hadith
/// book/number) is deliberately not mirrored here: the app never needs it, and
/// the guards read the file directly.
class FamilyAdhkar {
  FamilyAdhkar._();

  static const asset = 'assets/content/adhkar/family_adhkar.ar.json';

  static List<ParentingContent> _items = const [];
  static bool _loaded = false;

  static List<ParentingContent> get items => _items;
  static bool get isLoaded => _loaded;

  static Future<List<ParentingContent>> load() async {
    if (_loaded) return _items;
    final raw = await rootBundle.loadString(asset);
    _items = parse(raw);
    _loaded = true;
    return _items;
  }

  /// Split out so tests can exercise the parse without an asset bundle.
  static List<ParentingContent> parse(String raw) {
    final json = jsonDecode(raw) as Map<String, dynamic>;
    return [
      for (final item in (json['items'] as List<dynamic>))
        ParentingContent.fromJson(item as Map<String, dynamic>),
    ];
  }

  /// Test seam. Nothing in the app calls this.
  static void resetForTesting() {
    _items = const [];
    _loaded = false;
  }
}

/// The canonical Arabic list, in pack order.
///
/// Order is load-bearing: the daily rotation indexes into it, so a reorder
/// changes which day shows which item. It is the JSON file's order.
List<ParentingContent> get familyAdhkar => FamilyAdhkar.items;
