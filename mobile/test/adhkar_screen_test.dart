/// The adhkar browser's one hard rule: nothing is shown without its citation.
///
/// The pack is guarded at commit time by four checkers in `ops/tools/` that
/// insist every hadith names its book and number and every verse names its
/// surah and ayah. That work only reaches the user if the widget renders the
/// field. These tests assert the data end of that contract and the filtering
/// the screen relies on.
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/adhkar/data/family_adhkar.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    await FamilyAdhkar.load();
  });

  test('the pack actually loaded', () {
    // Guard the premise: every assertion below is vacuous on an empty list.
    expect(FamilyAdhkar.isLoaded, isTrue);
    expect(FamilyAdhkar.items.length, greaterThan(200));
  });

  test('every item carries a non-empty source', () {
    final unsourced =
        FamilyAdhkar.items.where((c) => c.source.trim().isEmpty).toList();
    expect(unsourced, isEmpty,
        reason: 'items without a citation: ${unsourced.map((c) => c.id)}');
  });

  test('every item carries a topic and text', () {
    for (final c in FamilyAdhkar.items) {
      expect(c.text.trim(), isNotEmpty, reason: c.id);
      expect(c.topic.trim(), isNotEmpty, reason: c.id);
    }
  });

  test('the three kinds the screen filters by are the only kinds present', () {
    // The chips offer verse / hadith / tip. A fourth kind appearing in the
    // pack would be invisible behind every filter except «الكل».
    final kinds = FamilyAdhkar.items.map((c) => c.kind).toSet();
    expect(kinds, {'verse', 'hadith', 'tip'});
  });

  test('each filter chip has something to show', () {
    for (final kind in ['verse', 'hadith', 'tip']) {
      expect(FamilyAdhkar.items.where((c) => c.kind == kind), isNotEmpty,
          reason: 'no items of kind $kind');
    }
  });

  test('ids are unique — the screen keys nothing off list position', () {
    final ids = FamilyAdhkar.items.map((c) => c.id).toList();
    expect(ids.toSet().length, ids.length);
  });

  test('search matches text, topic and source', () {
    // The screen filters with plain `contains` over these three fields; this
    // pins that each of them is actually populated well enough to search.
    bool matches(String q) => FamilyAdhkar.items.any((c) =>
        c.text.contains(q) || c.topic.contains(q) || c.source.contains(q));

    expect(matches('سورة'), isTrue); // sources of verses
    expect(matches('الصلاة'), isTrue); // common in text and topics
  });

  test('parse works without an asset bundle', () {
    const raw = '''
{"items":[{"id":"t_999","kind":"tip","text":"نص","source":"مصدر","topic":"موضوع"}]}
''';
    final parsed = FamilyAdhkar.parse(raw);
    expect(parsed, hasLength(1));
    expect(parsed.single.source, 'مصدر');
  });
}
