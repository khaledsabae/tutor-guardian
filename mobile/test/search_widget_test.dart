// Search feature tests — model parsing + screen behaviour.
//
// Overrides tgClientProvider with a fake whose searchCurriculum returns
// canned results, then drives the SearchScreen.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/program/models/search_result.dart';
import 'package:almorabbi/features/program/screens/search_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';

class _FakeSearchClient extends TgClient {
  String? lastQuery;
  List<Map<String, dynamic>> results = [];

  @override
  Future<Map<String, dynamic>> searchCurriculum(String query,
      {int limit = 20}) async {
    lastQuery = query;
    return {'query': query, 'count': results.length, 'results': results};
  }
}

Map<String, dynamic> _lesson(String id, String title) => {
      'type': 'lesson',
      'id': id,
      'title': title,
      'snippet': 'مقتطف عن $title',
      'age_group': '7-9',
      'domain': 'medical',
      'path_id': 'path_x',
    };

Widget _wrap(Widget child, _FakeSearchClient fake) => ProviderScope(
      overrides: [tgClientProvider.overrideWithValue(fake)],
      child: MaterialApp(
        home: Directionality(textDirection: TextDirection.rtl, child: child),
      ),
    );

void main() {
  group('SearchResult model', () {
    test('parses type + fields', () {
      final r = SearchResult.fromJson(_lesson('l1', 'القلق'));
      expect(r.type, SearchResultType.lesson);
      expect(r.id, 'l1');
      expect(r.title, 'القلق');
      expect(r.ageGroup, '7-9');
    });

    test('unknown type degrades gracefully', () {
      final r = SearchResult.fromJson({'type': 'weird', 'id': 'x'});
      expect(r.type, SearchResultType.unknown);
    });
  });

  group('SearchScreen', () {
    testWidgets('short query shows hint, no fetch', (tester) async {
      final fake = _FakeSearchClient();
      await tester.pumpWidget(_wrap(const SearchScreen(), fake));
      await tester.pumpAndSettle();

      expect(find.textContaining('حرفين على الأقل'), findsOneWidget);
      expect(fake.lastQuery, isNull);
    });

    testWidgets('typing a query renders results', (tester) async {
      final fake = _FakeSearchClient();
      fake.results = [_lesson('l1', 'الاكتئاب والقلق'), _lesson('l2', 'النوم')];

      await tester.pumpWidget(_wrap(const SearchScreen(), fake));
      await tester.enterText(find.byType(TextField), 'القلق');
      // wait past the 350ms debounce + async
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();

      expect(fake.lastQuery, 'القلق');
      expect(find.text('الاكتئاب والقلق'), findsOneWidget);
      expect(find.text('النوم'), findsOneWidget);
    });

    testWidgets('no results shows empty message', (tester) async {
      final fake = _FakeSearchClient();
      fake.results = [];

      await tester.pumpWidget(_wrap(const SearchScreen(), fake));
      await tester.enterText(find.byType(TextField), 'xyzق');
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();

      expect(find.textContaining('لا نتائج'), findsOneWidget);
    });
  });
}
