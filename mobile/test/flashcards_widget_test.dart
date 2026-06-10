// Flashcards screen widget tests — P0.1 media players.
//
// Same strategy as program_widget_test.dart: override [tgClientProvider]
// with a fake whose getAssetContent returns canned deck JSON, then assert
// the viewer renders cards, flips on tap, and paginates.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/program/models/flashcard_deck.dart';
import 'package:almorabbi/features/program/screens/flashcards_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';

class _FakeAssetClient extends TgClient {
  Map<String, Map<String, dynamic>> assetContent = {};

  @override
  Future<Map<String, dynamic>> getAssetContent(String assetId) async {
    final json = assetContent[assetId];
    if (json == null) throw const TgApiError(404, 'not found');
    return json;
  }
}

Map<String, dynamic> _deckJson(String id, List<List<String>> cards) => {
      'id': id,
      'kind': 'flashcards',
      'title': 'Islamic Flashcards',
      'cards': [
        for (final c in cards) {'front': c[0], 'back': c[1]},
      ],
    };

Widget _wrap(Widget child, _FakeAssetClient fake) => ProviderScope(
      overrides: [tgClientProvider.overrideWithValue(fake)],
      child: MaterialApp(
        home: Directionality(textDirection: TextDirection.rtl, child: child),
      ),
    );

void main() {
  group('FlashcardDeck model', () {
    test('parses cards and splits back into bullet points', () {
      final deck = FlashcardDeck.fromJson(
        _deckJson('d1', [
          ['سؤال؟', 'نقطة أولى | نقطة ثانية | نقطة ثالثة'],
        ]),
      );
      expect(deck.cards.length, 1);
      expect(deck.cards.first.backPoints, hasLength(3));
      expect(deck.cards.first.backPoints[1], 'نقطة ثانية');
    });
  });

  group('FlashcardsScreen', () {
    testWidgets('renders first card front and progress', (tester) async {
      final fake = _FakeAssetClient();
      fake.assetContent['d1'] = _deckJson('d1', [
        ['ما هو الرفق؟', 'قيمة نبوية | تبني الثقة'],
        ['سؤال تاني؟', 'إجابة تانية'],
      ]);

      await tester.pumpWidget(
        _wrap(const FlashcardsScreen(deckIds: ['d1']), fake),
      );
      await tester.pumpAndSettle();

      expect(find.text('ما هو الرفق؟'), findsOneWidget);
      expect(find.text('البطاقة 1 من 2'), findsOneWidget);
    });

    testWidgets('tap flips card to show answer points', (tester) async {
      final fake = _FakeAssetClient();
      fake.assetContent['d1'] = _deckJson('d1', [
        ['ما هو الرفق؟', 'قيمة نبوية | تبني الثقة'],
      ]);

      await tester.pumpWidget(
        _wrap(const FlashcardsScreen(deckIds: ['d1']), fake),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byType(FlipCard));
      await tester.pumpAndSettle();

      expect(find.text('قيمة نبوية'), findsOneWidget);
      expect(find.text('تبني الثقة'), findsOneWidget);
    });

    testWidgets('merges multiple decks and skips failed ones',
        (tester) async {
      final fake = _FakeAssetClient();
      fake.assetContent['d1'] = _deckJson('d1', [
        ['سؤال أ؟', 'إجابة أ'],
      ]);
      // 'd2' missing → repository returns null → deck skipped silently.

      await tester.pumpWidget(
        _wrap(const FlashcardsScreen(deckIds: ['d1', 'd2']), fake),
      );
      await tester.pumpAndSettle();

      expect(find.text('البطاقة 1 من 1'), findsOneWidget);
      expect(find.text('سؤال أ؟'), findsOneWidget);
    });

    testWidgets('empty decks show friendly empty state', (tester) async {
      final fake = _FakeAssetClient();

      await tester.pumpWidget(
        _wrap(const FlashcardsScreen(deckIds: ['missing']), fake),
      );
      await tester.pumpAndSettle();

      expect(
        find.text('لا توجد بطاقات متاحة لهذا الدرس حالياً'),
        findsOneWidget,
      );
    });
  });
}
