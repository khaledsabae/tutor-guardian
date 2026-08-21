/// What the tafsir provider must not do, stated as tests.
///
/// The feature exists to put an attributed explanation in front of a parent.
/// Every failure mode below ends with either *attributed text* or *nothing* —
/// there is no path that renders an unattributed claim about what an ayah
/// means, and no path where a missing sabab nuzool is shown as an error.
library;

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/quran/providers/tafsir_providers.dart';
import 'package:almorabbi/state/chat_notifier.dart' show tgClientProvider;

const _attribution =
    'تيسير الكريم الرحمن، عبد الرحمن بن ناصر السعدي (ت. 1376هـ)';

/// Shape copied from a real production response to `/api/tafsir/2/255`.
Map<String, dynamic> _tafsirBody({
  String text = 'نصّ التفسير.',
  String attribution = _attribution,
  String? error,
}) =>
    {
      'surah': 2,
      'ayah': 255,
      'results': [
        {
          'surah': 2,
          'ayah': 255,
          'source': 'saadi',
          'attribution': attribution,
          'text': text,
          'cached': true,
          'error': error,
        },
      ],
      'formatted': '📖 $attribution\n\n$text',
    };

/// Builds a container whose `TgClient` answers from [handler].
ProviderContainer _containerFor(
  Future<http.Response> Function(http.Request req) handler,
) {
  final client = TgClient.forTesting(
    baseUrl: 'http://test',
    httpClient: MockClient(handler),
  );
  final container = ProviderContainer(
    overrides: [tgClientProvider.overrideWithValue(client)],
  );
  addTearDown(container.dispose);
  return container;
}

http.Response _json(Object body, [int status = 200]) => http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('a good response reaches the UI with its attribution intact', () async {
    final container = _containerFor((req) async {
      if (req.url.path.endsWith('/nuzool')) return _json({'detail': 'x'}, 404);
      return _json(_tafsirBody());
    });

    final x = await container.read(ayahExplanationProvider((2, 255)).future);

    expect(x.entries, hasLength(1));
    expect(x.entries.single.attribution, _attribution);
    expect(x.entries.single.text, 'نصّ التفسير.');
    expect(x.entries.single.cached, isTrue);
    expect(x.isEmpty, isFalse);
  });

  test('a 404 on nuzool is an absence, not a failure', () async {
    // Most ayahs have no documented sabab nuzool. If this threw, every one of
    // them would show the parent an error where the tafsir should be.
    final container = _containerFor((req) async {
      if (req.url.path.endsWith('/nuzool')) {
        return _json({'detail': 'لا يتوفر سبب نزول موثّق لهذه الآية'}, 404);
      }
      return _json(_tafsirBody());
    });

    final x = await container.read(ayahExplanationProvider((2, 255)).future);
    expect(x.nuzool, isNull);
    expect(x.entries, hasLength(1)); // the tafsir still arrived
  });

  test('a nuzool that arrives is carried with its attribution', () async {
    final container = _containerFor((req) async {
      if (req.url.path.endsWith('/nuzool')) {
        return _json({
          'surah': 2,
          'ayah': 255,
          'attribution': 'أسباب النزول للواحدي',
          'text': 'سبب النزول.',
          'formatted': 'x',
        });
      }
      return _json(_tafsirBody());
    });

    final x = await container.read(ayahExplanationProvider((2, 255)).future);
    expect(x.nuzool, 'سبب النزول.');
    expect(x.nuzoolAttribution, 'أسباب النزول للواحدي');
  });

  test('an unattributed nuzool is dropped rather than shown', () async {
    final container = _containerFor((req) async {
      if (req.url.path.endsWith('/nuzool')) {
        return _json({'text': 'سبب بلا نسبة.', 'attribution': ''});
      }
      return _json(_tafsirBody());
    });

    final x = await container.read(ayahExplanationProvider((2, 255)).future);
    expect(x.nuzool, isNull);
  });

  test('an entry the backend marked failed is not rendered as tafsir',
      () async {
    final container = _containerFor((req) async {
      if (req.url.path.endsWith('/nuzool')) return _json({}, 404);
      return _json(_tafsirBody(error: 'upstream timed out'));
    });

    final x = await container.read(ayahExplanationProvider((2, 255)).future);
    expect(x.entries, isEmpty);
    expect(x.isEmpty, isTrue);
    // The formatted blob survives as the fallback the sheet falls back to.
    expect(x.formatted, isNotEmpty);
  });

  test('an entry with text but no attribution is dropped', () async {
    final container = _containerFor((req) async {
      if (req.url.path.endsWith('/nuzool')) return _json({}, 404);
      return _json(_tafsirBody(attribution: ''));
    });

    final x = await container.read(ayahExplanationProvider((2, 255)).future);
    expect(x.entries, isEmpty);
  });

  test('a dead tafsir endpoint surfaces as an error, not as empty content',
      () async {
    final container = _containerFor((req) async {
      if (req.url.path.endsWith('/nuzool')) return _json({}, 404);
      return _json({'detail': 'boom'}, 500);
    });

    await expectLater(
      container.read(ayahExplanationProvider((2, 255)).future),
      throwsA(isA<TgApiError>()),
    );
  });

  test('a dead nuzool endpoint does not cost the tafsir', () async {
    final container = _containerFor((req) async {
      if (req.url.path.endsWith('/nuzool')) return _json({'detail': 'x'}, 503);
      return _json(_tafsirBody());
    });

    final x = await container.read(ayahExplanationProvider((2, 255)).future);
    expect(x.entries, hasLength(1));
    expect(x.nuzool, isNull);
  });

  test('the request goes to the public tafsir path for the right ayah',
      () async {
    final seen = <String>[];
    final container = _containerFor((req) async {
      seen.add(req.url.path);
      if (req.url.path.endsWith('/nuzool')) return _json({}, 404);
      return _json(_tafsirBody());
    });

    await container.read(ayahExplanationProvider((18, 10)).future);
    expect(seen, contains('/api/tafsir/18/10'));
    expect(seen, contains('/api/tafsir/18/10/nuzool'));
  });
}
