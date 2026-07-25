/// Invariants for the «المزيد» hub.
///
/// The hub is the app's index of everything outside the daily loop, so a tile
/// that resolves to a missing translation or a duplicate destination is a
/// navigation dead end — the exact failure this restructure set out to remove.
/// The classic version of that mistake is adding a tile and forgetting the
/// `.arb` key, which only shows up as a crash on the device.
library;

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/hub/data/hub_catalog.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

void main() {
  // Both shipped locales: a key can exist in Arabic and be missing in English.
  final locales = {
    'ar': lookupAppLocalizations(const Locale('ar')),
    'en': lookupAppLocalizations(const Locale('en')),
  };

  // The routine/habit tile's label legitimately differs by age band, so both
  // sides of that branch get exercised.
  const ageGroups = ['4-6', '10-12', ''];

  test('the catalog is not empty', () {
    expect(kHubGroups, isNotEmpty);
    for (final group in kHubGroups) {
      expect(group.items, isNotEmpty, reason: 'group "${group.id}" has no items');
    }
  });

  test('every group title resolves in every locale', () {
    for (final entry in locales.entries) {
      for (final group in kHubGroups) {
        final title = group.title(entry.value);
        expect(title, isNotEmpty,
            reason: 'group "${group.id}" has no ${entry.key} title');
      }
    }
  });

  test('every item label resolves in every locale and age band', () {
    for (final entry in locales.entries) {
      for (final group in kHubGroups) {
        for (final item in group.items) {
          for (final age in ageGroups) {
            final label = item.label(entry.value, age);
            expect(label, isNotEmpty,
                reason: '"${item.id}" has no ${entry.key} label (age "$age")');
          }
        }
      }
    }
  });

  test('every item builds a named route', () {
    for (final group in kHubGroups) {
      for (final item in group.items) {
        final route = item.route();
        expect(route.settings.name, isNotNull,
            reason: '"${item.id}" builds an unnamed route');
        expect(route.settings.name, isNotEmpty,
            reason: '"${item.id}" builds an empty-named route');
      }
    }
  });

  test('item ids are unique across the whole hub', () {
    // They are analytics keys — a duplicate silently merges two tiles' taps.
    final seen = <String, String>{};
    for (final group in kHubGroups) {
      for (final item in group.items) {
        final clash = seen[item.id];
        expect(clash, isNull,
            reason: 'item id "${item.id}" appears in both "$clash" and '
                '"${group.id}"');
        seen[item.id] = group.id;
      }
    }
  });

  test('group ids are unique', () {
    final ids = kHubGroups.map((g) => g.id).toList();
    expect(ids.toSet().length, ids.length, reason: 'duplicate group id');
  });

  test('no destination appears twice', () {
    // Two tiles opening the same screen means one of them is mislabelled.
    final seen = <String, String>{};
    for (final group in kHubGroups) {
      for (final item in group.items) {
        final name = item.route().settings.name!;
        final clash = seen[name];
        expect(clash, isNull,
            reason: '"${item.id}" and "$clash" both open "$name"');
        seen[name] = item.id;
      }
    }
  });

  test('every item has an emoji', () {
    for (final group in kHubGroups) {
      for (final item in group.items) {
        expect(item.emoji, isNotEmpty, reason: '"${item.id}" has no emoji');
      }
    }
  });
}
