/// A language with no pack must fall back to Arabic, never to nothing.
///
/// The daily reminder is scheduled straight out of this pack. If a lookup for
/// `family_adhkar.fr.json` returned an empty list instead of falling back,
/// `scheduleDaily` would queue nothing at all and 38% of users would silently
/// lose the reminder — which is the exact failure that was just fixed for a
/// different reason, and it must not come back through the content door.
///
/// `family_adhkar.en.json` landed on 2026-08-22 — the 124 tips translated, the
/// 142 verses and 15 hadith carried through in Arabic because scripture is not
/// translated. The fallback still matters for every other language.
library;

import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter/widgets.dart' show TextDirection;
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/adhkar/data/family_adhkar.dart';
import 'package:almorabbi/l10n/content_direction.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('the pack reloads when the language changes', () async {
    // The pack is read once before `runApp`, and the parent can change language
    // afterwards. A cache keyed only on "loaded at all" would hand them a
    // fortnight of reminders in the language they just left.
    await FamilyAdhkar.load(language: 'en');
    expect(FamilyAdhkar.loadedLanguage, 'en');
    final english = FamilyAdhkar.items.firstWhere((i) => i.kind == 'tip').text;

    await FamilyAdhkar.load(language: 'ar');
    expect(FamilyAdhkar.loadedLanguage, 'ar');
    final arabic = FamilyAdhkar.items.firstWhere((i) => i.kind == 'tip').text;

    expect(arabic, isNot(english));
  });

  test('a language with no pack still gets a full Arabic pack', () async {
    final items = await FamilyAdhkar.load(language: 'fr');
    expect(FamilyAdhkar.loadedLanguage, 'fr');

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

  test('the English pack is bundled and reaches an English device', () async {
    // The asset is declared by directory in pubspec, so "the file exists in the
    // repo" and "the file is in the app" are different claims. This asserts the
    // second one, through the same call `main()` makes.
    final raw = await rootBundle.loadString(FamilyAdhkar.assetFor('en'));
    final items = FamilyAdhkar.parse(raw);

    expect(items.length, 281);
    final tips = items.where((i) => i.kind == 'tip').toList();
    final scripture = items.where((i) => i.kind != 'tip').toList();
    expect(tips.length, 124);
    expect(scripture.length, 157);

    // Tips read in English…
    final arabicOutsideQuotes = RegExp(r'[\u0600-\u06ff]');
    final quoted = RegExp('«[^»]*»|\u201c[^\u201d]*\u201d');
    for (final tip in tips) {
      expect(arabicOutsideQuotes.hasMatch(tip.text.replaceAll(quoted, '')), isFalse,
          reason: '${tip.id} carries Arabic outside a quotation');
    }

    // …and every ayah and hadith is still Arabic, quoted as revealed and as
    // narrated. An English pack that renders scripture is the one outcome this
    // whole translation was not allowed to produce.
    for (final item in scripture) {
      expect(arabicOutsideQuotes.hasMatch(item.text), isTrue,
          reason: '${item.id} is a ${item.kind} and is no longer Arabic');
    }
  });

  group('an item carries its own direction', () {
    test('an English tip reads left to right', () async {
      final items = await FamilyAdhkar.load(language: 'en');
      final tip = items.firstWhere((i) => i.id == 't_003');
      expect(ContentDirectionality.resolve(text: tip.text), TextDirection.ltr);
    });

    test('an ayah reads right to left in either pack', () async {
      for (final lang in ['ar', 'en']) {
        final items = await FamilyAdhkar.load(language: lang);
        final ayah = items.firstWhere((i) => i.kind == 'verse');
        expect(ContentDirectionality.resolve(text: ayah.text), TextDirection.rtl,
            reason: 'the $lang pack still carries the ayah in Arabic');
      }
    });

    test('a mostly-English tip that quotes a hadith still reads left to right',
        () async {
      // t_044 is the hardest of the eight: an English sentence wrapped around a
      // fully-vowelled ayah. The sentence doing the talking is English.
      final items = await FamilyAdhkar.load(language: 'en');
      final mixed = items.firstWhere((i) => i.id == 't_044');
      expect(ContentDirectionality.resolve(text: mixed.text), TextDirection.ltr);
    });
  });
}


// ── Direction follows the item, not the pack ─────────────────────────────
//
// `_AdhkarCard` pinned `languageCode: 'ar'`, which was correct while the pack
// was Arabic and only Arabic. With the tips in English it rendered them
// right-aligned with the full stop on the wrong side — visible on a Pixel 6 the
// first time the English pack loaded.