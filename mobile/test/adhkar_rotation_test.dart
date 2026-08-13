/// Adhkar rotation — the content pool must actually be reachable.
///
/// The scheduler picks items by index from `familyAdhkar`. Three defects made
/// that pointless, and all three are cheap to pin:
///
///  1. the rotation index was read from SharedPreferences but never written
///     back, so every reschedule restarted at the same place and only the
///     first 14 items of each pool were ever delivered;
///  2. day 0 was pushed to tomorrow when its hour had already passed, landing
///     on the same instant as day 1 — two notifications at once;
///  3. the pool was filtered by `kind` per slot, so a 'tip' could only ever
///     arrive in the evening. When the two slots collapsed into one on
///     2026-08-13, keeping either filter would have made a whole kind
///     unreachable.
///
/// The scheduler itself needs platform channels, so these tests verify the
/// pure arithmetic it now uses rather than mocking the plugin.
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/adhkar/data/family_adhkar.dart';

/// Mirrors `NotificationService.scheduleDaily`'s day-anchored selection.
///
/// The `seed` parameter is gone with the stored index it read: it was never
/// written by any shipped build, so it was 0 on every install.
int indexForDay(int epochDay, int dayOffset, int poolSize) =>
    (epochDay + dayOffset) % poolSize;

/// Mirrors the payload `_scheduleSpecific` writes and the suffix
/// `_handleNotificationTap` reads back off it.
String payloadFor(ParentingContent content) => 'adhkar_${content.id}';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // The pool is an asset pack now. `main()` awaits this before
  // `NotificationService.init()`, which schedules out of it.
  setUpAll(() async => FamilyAdhkar.load());

  // One pool: the whole list, unfiltered. That is what makes every item
  // reachable from a single daily slot. `late` because the pack is loaded in
  // setUpAll, not at import.
  late final int pool = familyAdhkar.length;

  group('content pool', () {
    test('is large enough to be worth rotating', () {
      // Was `greaterThan(500)`, and it passed on 730 items that were really
      // 267: one hadith repeated 223 times and 124 tips repeated to 365, each
      // copy padded with a visible «(رقم N)» counter. Counting rows rewarded
      // the padding, so the bar is now set against the real pools.
      expect(pool, greaterThan(100));
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

  group('stable ids', () {
    // Notifications are queued up to 14 days ahead and the OS keeps that queue
    // across app updates, so the payload has to survive a pack that changed
    // underneath it. It used to be the list index: adding one verse shifted
    // every item below it, and a queued notification showing one ayah would
    // open another. The id is now what travels.
    test('every item has a unique, non-numeric id', () {
      final seen = <String>{};
      for (var i = 0; i < familyAdhkar.length; i++) {
        final id = familyAdhkar[i].id;
        expect(id.trim(), isNotEmpty, reason: 'item $i has no id');
        expect(int.tryParse(id), isNull,
            reason: 'id "$id" parses as an int — the tap handler would take '
                'it for a legacy index');
        expect(seen.add(id), isTrue, reason: 'duplicate id "$id"');
      }
      expect(seen.length, familyAdhkar.length);
    });

    test('an id says what kind of item it is', () {
      const prefixes = {'verse': 'v_', 'hadith': 'h_', 'tip': 't_'};
      for (final c in familyAdhkar) {
        expect(c.id, startsWith(prefixes[c.kind]!), reason: c.id);
      }
    });

    test('a payload resolves back to the item that was scheduled', () {
      // Reproduces the tap handler over a pack whose order has changed: the
      // item is found by id, so it is still the one the notification showed.
      final scheduled = familyAdhkar[7];
      final payload = payloadFor(scheduled);
      expect(payload.startsWith('adhkar_'), isTrue);

      final shuffled = familyAdhkar.reversed.toList();
      final suffix = payload.substring('adhkar_'.length);
      expect(int.tryParse(suffix), isNull);
      final resolved = shuffled.firstWhere((c) => c.id == suffix);
      expect(resolved.text, scheduled.text);
      expect(resolved.source, scheduled.source);
    });

    test('a legacy numeric payload is still an index, for one release', () {
      // Builds up to v1.0.39 queued `adhkar_<index>` 14 days out. Those are in
      // flight when this build lands, so the old reading has to keep working.
      const legacy = 'adhkar_12';
      final suffix = legacy.substring('adhkar_'.length);
      final idx = int.tryParse(suffix);
      expect(idx, 12);
      expect(idx! < familyAdhkar.length, isTrue);
    });
  });

  group('rotation', () {
    test('every item in the pool is reachable', () {
      // The regression that mattered: with the old counter the same 14 items
      // came back forever. With one unfiltered pool a full walk must now touch
      // all 281 items exactly once — the two-slot version reached all 281 in
      // the union, but never a tip in the morning or a verse in the evening.
      final seen = {for (var d = 0; d < pool; d++) indexForDay(d, 0, pool)};
      expect(seen.length, pool);
      expect(seen, equals({for (var i = 0; i < pool; i++) i}));
    });

    test('the single pool excludes no kind', () {
      final kinds = {
        for (var d = 0; d < pool; d++) familyAdhkar[indexForDay(d, 0, pool)].kind
      };
      expect(kinds, containsAll({'hadith', 'verse', 'tip'}));
    });

    test('consecutive days give consecutive, distinct items', () {
      const epochDay = 2000;
      expect(indexForDay(epochDay, 0, pool),
          isNot(indexForDay(epochDay + 1, 0, pool)));
    });

    test('rescheduling on the same day is idempotent', () {
      // Opening the app repeatedly must not advance the rotation — that was
      // the whole reason for anchoring to the calendar day.
      const epochDay = 2000;
      final first = [for (var d = 0; d < 14; d++) indexForDay(epochDay, d, pool)];
      final second = [for (var d = 0; d < 14; d++) indexForDay(epochDay, d, pool)];
      expect(first, second);
    });

    test('the 14 scheduled days are all different items', () {
      const epochDay = 2000;
      final scheduled = {
        for (var d = 0; d < 14; d++) indexForDay(epochDay, d, pool)
      };
      expect(scheduled.length, 14);
    });
  });

  group('notification ids', () {
    // Mirrors the constants in notification_service.dart, per this file's rule
    // about not importing the scheduler. The retired ranges must stay clear of
    // the live one: _purgeRetiredSlots cancels them unconditionally on first
    // launch, so an overlap would cancel live slots on every install.
    const dailyBase = 1000;
    const retiredEveningBase = 2000;
    const retiredWird = 3000;

    test('the live range cannot collide with a retired one', () {
      expect(dailyBase + 30, lessThanOrEqualTo(retiredEveningBase));
      expect(retiredWird, isNot(inInclusiveRange(dailyBase, dailyBase + 29)));
      expect(retiredWird,
          isNot(inInclusiveRange(retiredEveningBase, retiredEveningBase + 29)));
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
