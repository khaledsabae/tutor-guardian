/// Adhkar rotation — the content pool must actually be reachable.
///
/// The scheduler picks items by index from `familyAdhkar`. Two defects made
/// that pointless, and both are cheap to pin:
///
///  1. the rotation index was read from SharedPreferences but never written
///     back, so every reschedule restarted at the same place and only the
///     first 14 items of each pool were ever delivered;
///  2. day 0 was pushed to tomorrow when its hour had already passed, landing
///     on the same instant as day 1 — two notifications at once.
///
/// The scheduler itself needs platform channels, so these tests verify the
/// pure arithmetic it now uses rather than mocking the plugin.
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/adhkar/data/family_adhkar.dart';

/// Mirrors `NotificationService.scheduleDaily`'s day-anchored selection.
int indexForDay(int seed, int epochDay, int dayOffset, int poolSize) =>
    (seed + epochDay + dayOffset) % poolSize;

void main() {
  final morningPool = familyAdhkar
      .where((c) => c.kind == 'hadith' || c.kind == 'verse')
      .length;
  final eveningPool =
      familyAdhkar.where((c) => c.kind == 'hadith' || c.kind == 'tip').length;

  group('content pool', () {
    test('is large enough to be worth rotating', () {
      // Was `greaterThan(500)`, and it passed on 730 items that were really
      // 267: one hadith repeated 223 times and 124 tips repeated to 365, each
      // copy padded with a visible «(رقم N)» counter. Counting rows rewarded
      // the padding, so the bar is now set against the real pools.
      expect(morningPool, greaterThan(100));
      expect(eveningPool, greaterThan(100));
    });

    test('no item is a padded copy of another', () {
      // The counter suffix made 465 duplicates look distinct. Strip it before
      // comparing, or this passes on exactly the data it exists to reject.
      final counter = RegExp(r'\s*\(\s*(?:حديث|نصيحة|أثر|رقم)[^)]*رقم[^)]*\)\s*$');
      final seen = <String, int>{};
      for (var i = 0; i < familyAdhkar.length; i++) {
        final core = familyAdhkar[i].text.replaceAll(counter, '').trim();
        expect(seen.containsKey(core), isFalse,
            reason: 'item $i duplicates item ${seen[core]}: '
                '"${core.substring(0, core.length.clamp(0, 50))}"');
        seen[core] = i;
      }
    });

    test('no item shows a bare counter to the user', () {
      final counter = RegExp(r'\(\s*(?:حديث|نصيحة|أثر|رقم)[^)]*رقم[^)]*\)');
      for (var i = 0; i < familyAdhkar.length; i++) {
        expect(counter.hasMatch(familyAdhkar[i].text), isFalse,
            reason: 'item $i leaks a placeholder counter into the notification');
      }
    });

    test('no kind is stamped with a single blanket source', () {
      // 223 hadith once shared one invented isnad, «صحيح — رواه الترمذي وأبو
      // داود», with no hadith number. One source across a whole kind is the
      // signature of an attribution nobody checked.
      final byKind = <String, Set<String>>{};
      final countByKind = <String, int>{};
      for (final c in familyAdhkar) {
        byKind.putIfAbsent(c.kind, () => <String>{}).add(c.source);
        countByKind[c.kind] = (countByKind[c.kind] ?? 0) + 1;
      }
      byKind.forEach((kind, sources) {
        if ((countByKind[kind] ?? 0) >= 10) {
          expect(sources.length, greaterThan(1),
              reason: '$kind: all ${countByKind[kind]} items cite '
                  '"${sources.first}"');
        }
      });
    });

    test('every item has text and a source', () {
      // A notification body is "text — source"; an empty source renders a
      // dangling dash to the user.
      for (var i = 0; i < familyAdhkar.length; i++) {
        expect(familyAdhkar[i].text.trim(), isNotEmpty, reason: 'item $i');
        expect(familyAdhkar[i].source.trim(), isNotEmpty, reason: 'item $i');
      }
    });

    test('every item has a kind the scheduler recognises', () {
      // An unknown kind silently drops the item from both pools.
      const known = {'hadith', 'verse', 'tip'};
      for (var i = 0; i < familyAdhkar.length; i++) {
        expect(known, contains(familyAdhkar[i].kind), reason: 'item $i');
      }
    });
  });

  group('rotation', () {
    test('a full year of days never repeats within the morning pool', () {
      // This is the regression that mattered: with the old counter the same
      // 14 items came back forever.
      final seen = <int>{};
      for (var day = 0; day < morningPool; day++) {
        seen.add(indexForDay(0, day, 0, morningPool));
      }
      expect(seen.length, morningPool);
    });

    test('consecutive days give consecutive, distinct items', () {
      const epochDay = 2000;
      final a = indexForDay(0, epochDay, 0, morningPool);
      final b = indexForDay(0, epochDay + 1, 0, morningPool);
      expect(a, isNot(b));
    });

    test('rescheduling on the same day is idempotent', () {
      // Opening the app repeatedly must not advance the rotation — that was
      // the whole reason for anchoring to the calendar day.
      const epochDay = 2000;
      final first = [
        for (var d = 0; d < 14; d++) indexForDay(0, epochDay, d, morningPool)
      ];
      final second = [
        for (var d = 0; d < 14; d++) indexForDay(0, epochDay, d, morningPool)
      ];
      expect(first, second);
    });

    test('the 14 scheduled days are all different items', () {
      const epochDay = 2000;
      final scheduled = {
        for (var d = 0; d < 14; d++) indexForDay(0, epochDay, d, morningPool)
      };
      expect(scheduled.length, 14);
    });

    test('a stored seed shifts the sequence without breaking it', () {
      const epochDay = 2000;
      expect(
        indexForDay(5, epochDay, 0, morningPool),
        indexForDay(0, epochDay + 5, 0, morningPool),
      );
    });
  });

  group('scheduling instants', () {
    // Reproduces the base-date arithmetic: one base, then +dayOffset.
    List<DateTime> slots(DateTime now, int hour, int days) {
      var base = DateTime(now.year, now.month, now.day, hour);
      if (base.isBefore(now)) base = base.add(const Duration(days: 1));
      return [for (var d = 0; d < days; d++) base.add(Duration(days: d))];
    }

    test('no two slots share an instant when the hour has already passed', () {
      // 09:00 now, 06:00 reminder — the case that used to double-book.
      final now = DateTime(2026, 7, 25, 9);
      final s = slots(now, 6, 14);
      expect(s.toSet().length, 14);
      expect(s.first.isAfter(now), isTrue);
    });

    test('no two slots share an instant when the hour is still ahead', () {
      final now = DateTime(2026, 7, 25, 5);
      final s = slots(now, 6, 14);
      expect(s.toSet().length, 14);
      expect(s.first.day, 25);
    });

    test('slots are strictly increasing', () {
      final s = slots(DateTime(2026, 7, 25, 9), 6, 14);
      for (var i = 1; i < s.length; i++) {
        expect(s[i].isAfter(s[i - 1]), isTrue);
      }
    });
  });
}
