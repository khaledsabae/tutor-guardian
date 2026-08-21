/// A language with no pack must fall back to Arabic, never to nothing.
///
/// The daily reminder is scheduled straight out of this pack. If a lookup for
/// `family_adhkar.fr.json` returned an empty list instead of falling back,
/// `scheduleDaily` would queue nothing at all and 38% of users would silently
/// lose the reminder — which is the exact failure that was just fixed for a
/// different reason, and it must not come back through the content door.
///
/// Only `family_adhkar.ar.json` exists today. This test is what makes adding an
/// English one a drop-in: the language argument already flows, so the change is
/// the asset and nothing else.
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/adhkar/data/family_adhkar.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('a language with no pack still gets a full Arabic pack', () async {
    final items = await FamilyAdhkar.load(language: 'fr');

    expect(items, isNotEmpty,
        reason: 'an empty pack means scheduleDaily queues nothing');
    expect(items.length, greaterThan(200));
    expect(items.map((i) => i.kind).toSet(), containsAll(['verse', 'hadith', 'tip']));
  });

  test('the asset path is derived from the language, not hard-coded', () {
    expect(FamilyAdhkar.assetFor('ar'), FamilyAdhkar.asset);
    expect(FamilyAdhkar.assetFor('en'),
        'assets/content/adhkar/family_adhkar.en.json');
  });
}
