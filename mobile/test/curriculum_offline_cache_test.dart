// The curriculum has to survive losing the network.
//
// The app was online-only: a parent opening it on the metro, or on a phone out
// of data, got an error where their child's paths should be. The repository
// now keeps the last successful response and serves it when the failure says
// nothing about the content.
//
// The line that matters is *which* failures qualify. A dropped connection or a
// 5xx says nothing about the lesson, so yesterday's copy is the better answer.
// A 404 says the thing is gone — serving a cached copy there would be a lie.

import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/core/failures.dart';
import 'package:almorabbi/features/program/data/curriculum_cache.dart';

Map<String, dynamic> _payload(String title) => {
      'paths': [
        {'id': 'p1', 'title': title}
      ]
    };

void main() {
  late CurriculumCache cache;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    cache = CurriculumCache(prefs: await SharedPreferences.getInstance());
  });

  group('staleDataBeatsError', () {
    test('a dropped connection or a sick server: yes', () {
      expect(staleDataBeatsError(const SocketException('no route')), isTrue);
      expect(staleDataBeatsError(TimeoutException('slow')), isTrue);
      expect(staleDataBeatsError(const TgApiError(null, 'x')), isTrue);
      expect(staleDataBeatsError(const TgApiError(503, 'x')), isTrue);
    });

    test('a 404 or a bug: no — stale data would be a lie', () {
      expect(staleDataBeatsError(const TgApiError(404, 'gone')), isFalse);
      expect(staleDataBeatsError(const TgApiError(422, 'bad')), isFalse);
      expect(staleDataBeatsError(const FormatException('bad json')), isFalse);
    });
  });

  group('CurriculumCache', () {
    test('returns what was written', () async {
      await cache.write('k', _payload('المسار'));
      expect(await cache.read('k'), _payload('المسار'));
    });

    test('an unknown key is null, not an error', () async {
      expect(await cache.read('never-written'), isNull);
    });

    test('a later write replaces the earlier one', () async {
      await cache.write('k', _payload('قديم'));
      await cache.write('k', _payload('جديد'));
      expect((await cache.read('k'))!['paths'][0]['title'], 'جديد');
    });

    test('a corrupt entry reads as absent rather than throwing', () async {
      SharedPreferences.setMockInitialValues({
        'curriculum_cache.k': 'not json at all',
      });
      final c = CurriculumCache(prefs: await SharedPreferences.getInstance());
      expect(await c.read('k'), isNull);
    });

    test('readFresh refuses an entry older than staleAfter', () async {
      final old = DateTime.now()
          .toUtc()
          .subtract(CurriculumCache.staleAfter + const Duration(days: 1));
      SharedPreferences.setMockInitialValues({
        'curriculum_cache.k':
            '{"saved_at":"${old.toIso8601String()}","payload":{"paths":[]}}',
      });
      final c = CurriculumCache(prefs: await SharedPreferences.getInstance());

      // Too old to call fresh — but still the best answer when the alternative
      // is an error, so read() keeps serving it.
      expect(await c.readFresh('k'), isNull);
      expect(await c.read('k'), isNotNull);
    });
  });
}
