// What a parent with no signal actually sees.
//
// Before this, ProgramRepository handed every network failure straight to the
// UI, so opening the app on the metro showed an error where the child's paths
// should be. It now serves the last response the server really gave — but only
// when the failure says nothing about the content.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/program/data/curriculum_cache.dart';
import 'package:almorabbi/features/program/data/program_repository.dart';

Map<String, dynamic> _pathsPayload(String title) => {
      'paths': [
        {
          'id': 'path_4-6_islamic_parenting_bond',
          'title': title,
          'age_group': '4-6',
          'domain': 'islamic_parenting',
        }
      ],
      'total': 1,
    };

/// A client that answers once and then fails however the test asks it to.
class _FlakyClient extends TgClient {
  _FlakyClient({this.payload, this.failure});

  Map<String, dynamic>? payload;
  Object? failure;
  int calls = 0;

  @override
  Future<Map<String, dynamic>> getPathsList({
    String? ageGroup,
    String? domain,
  }) async {
    calls++;
    if (failure != null) throw failure!;
    return payload!;
  }
}

void main() {
  late CurriculumCache cache;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    cache = CurriculumCache(prefs: await SharedPreferences.getInstance());
  });

  test('a successful response is remembered and served when the network drops',
      () async {
    final client = _FlakyClient(payload: _pathsPayload('بناء الرابطة'));
    final repo = ProgramRepository(client, cache: cache);

    final online = await repo.listPaths(ageGroup: '4-6');
    expect(online.paths.single.title, 'بناء الرابطة');

    // The phone loses signal.
    client.failure = const SocketException("Failed host lookup: 'tg-api'");
    final offline = await repo.listPaths(ageGroup: '4-6');

    expect(offline.paths.single.title, 'بناء الرابطة');
    expect(client.calls, 2, reason: 'the network is still tried first');
  });

  test('a 5xx also falls back — the server being unwell says nothing about '
      'the content', () async {
    final client = _FlakyClient(payload: _pathsPayload('الأدب'));
    final repo = ProgramRepository(client, cache: cache);
    await repo.listPaths(ageGroup: '4-6');

    client.failure = const TgApiError(503, 'unavailable');
    final result = await repo.listPaths(ageGroup: '4-6');

    expect(result.paths.single.title, 'الأدب');
  });

  test('a 404 is NOT masked by the cache — the path really is gone', () async {
    final client = _FlakyClient(payload: _pathsPayload('قديم'));
    final repo = ProgramRepository(client, cache: cache);
    await repo.listPaths(ageGroup: '4-6');

    client.failure = const TgApiError(404, 'not found');

    expect(
      () => repo.listPaths(ageGroup: '4-6'),
      throwsA(isA<TgApiError>()),
    );
  });

  test('with nothing cached, the failure reaches the caller', () async {
    final client = _FlakyClient(failure: const SocketException('no route'));
    final repo = ProgramRepository(client, cache: cache);

    expect(
      () => repo.listPaths(ageGroup: '4-6'),
      throwsA(isA<SocketException>()),
    );
  });

  test('each filter is cached separately, so one does not answer for another',
      () async {
    final client = _FlakyClient(payload: _pathsPayload('طب'));
    final repo = ProgramRepository(client, cache: cache);
    await repo.listPaths(ageGroup: '4-6', domain: 'medical');

    client.failure = const SocketException('no route');

    // The same age group with a different domain was never fetched.
    expect(
      () => repo.listPaths(ageGroup: '4-6', domain: 'cyber'),
      throwsA(isA<SocketException>()),
    );
  });

  test('a cached payload this version can no longer read does not mask the '
      'real error', () async {
    // What an app upgrade looks like: yesterday's response, today's model.
    SharedPreferences.setMockInitialValues({
      'curriculum_cache.paths.4-6.all':
          '{"saved_at":"${DateTime.now().toUtc().toIso8601String()}",'
          '"payload":{"paths":[{"id":"p1"}]}}',
    });
    final c = CurriculumCache(prefs: await SharedPreferences.getInstance());
    final repo = ProgramRepository(
      _FlakyClient(failure: const SocketException('no route')),
      cache: c,
    );

    // The cached entry is missing fields the model requires. The caller should
    // see the network failure, not a TypeError from the cache.
    expect(
      () => repo.listPaths(ageGroup: '4-6'),
      throwsA(isA<SocketException>()),
    );
  });

  test('an unavailable cache store does not break a working network', () async {
    // No SharedPreferences mock installed: the plugin throws. A cache is an
    // optimisation, so its absence must never withhold a response the server
    // actually gave. This is what the pre-existing repository tests caught.
    SharedPreferences.setMockInitialValues({});
    final repo = ProgramRepository(
      _FlakyClient(payload: _pathsPayload('يعمل')),
      cache: CurriculumCache(),
    );

    final result = await repo.listPaths(ageGroup: '4-6');

    expect(result.paths.single.title, 'يعمل');
  });
}
