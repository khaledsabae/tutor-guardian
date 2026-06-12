// Quiz screen widget tests — P0.1 media players (second of three).
//
// Same pattern as flashcards_widget_test.dart: override tgClientProvider
// with a fake whose getAssetContent returns canned quiz JSON, then assert
// the quiz renders questions, options are tappable, feedback locks in,
// navigation works, and the summary screen renders at the end.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/program/models/quiz_deck.dart';
import 'package:almorabbi/features/program/screens/quiz_screen.dart';
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

Map<String, dynamic> _quizJson(
  String id,
  List<List<Object>> questions,
) {
  return {
    'id': id,
    'kind': 'quizzes',
    'title': 'Parenting Quiz',
    'questions': [
      for (final q in questions)
        {
          'question': q[0] as String,
          'hint': q.length > 4 ? q[4] as String : null,
          'answerOptions': [
            for (var i = 0; i < (q[1] as List).length; i++)
              {
                'text': (q[1] as List)[i] as String,
                'isCorrect': i == (q[2] as int),
                'rationale': i == (q[2] as int)
                    ? 'هذا هو التفسير الصحيح.'
                    : 'هذا غير دقيق في هذا السياق.',
              }
          ],
        }
    ],
  };
}

Widget _wrap(Widget child, _FakeAssetClient fake) => ProviderScope(
      overrides: [tgClientProvider.overrideWithValue(fake)],
      child: MaterialApp(
        home: Directionality(textDirection: TextDirection.rtl, child: child),
      ),
    );

void main() {
  group('QuizDeck model', () {
    test('parses questions and options, marking the correct one', () {
      final deck = QuizDeck.fromAssetContent(_quizJson('q1', [
        [
          'ما هو الرفق؟',
          ['ضعف', 'قيمة نبوية', 'عقاب', 'صراخ'],
          1,
        ],
      ]));
      expect(deck.questions.length, 1);
      expect(deck.questions.first.options.length, 4);
      expect(deck.questions.first.options[1].isCorrect, isTrue);
      expect(deck.questions.first.options[0].isCorrect, isFalse);
    });

    test('tolerates missing rationale and hint', () {
      final deck = QuizDeck.fromAssetContent({
        'id': 'q',
        'title': 'T',
        'questions': [
          {
            'question': 'س؟',
            'answerOptions': [
              {'text': 'إ', 'isCorrect': true}
            ],
          }
        ]
      });
      expect(deck.questions.first.options.length, 1);
      expect(deck.questions.first.hint, isNull);
    });
  });

  group('QuizScreen', () {
    testWidgets('renders first question, progress, and 4 option tiles',
        (tester) async {
      final fake = _FakeAssetClient();
      fake.assetContent['q1'] = _quizJson('q1', [
        [
          'ما هو الرفق؟',
          ['ضعف', 'قيمة نبوية', 'عقاب', 'صراخ'],
          1,
        ],
        [
          'ما نتيجة الرفق؟',
          ['خوف', 'ثقة', 'غضب', 'لا شيء'],
          1,
        ],
      ]);

      await tester.pumpWidget(
        _wrap(const QuizScreen(quizIds: ['q1']), fake),
      );
      await tester.pumpAndSettle();

      expect(find.text('سؤال 1 من 2'), findsOneWidget);
      expect(find.text('ما هو الرفق؟'), findsOneWidget);
      expect(find.text('ضعف'), findsOneWidget);
      expect(find.text('قيمة نبوية'), findsOneWidget);
      expect(find.text('عقاب'), findsOneWidget);
      expect(find.text('صراخ'), findsOneWidget);
    });

    testWidgets('tapping an option locks feedback and shows next button',
        (tester) async {
      final fake = _FakeAssetClient();
      fake.assetContent['q1'] = _quizJson('q1', [
        [
          'ما هو الرفق؟',
          ['ضعف', 'قيمة نبوية', 'عقاب', 'صراخ'],
          1,
        ],
      ]);

      await tester.pumpWidget(
        _wrap(const QuizScreen(quizIds: ['q1']), fake),
      );
      await tester.pumpAndSettle();

      // No next button before answering.
      expect(find.byKey(const Key('quiz_next_button')), findsNothing);

      // Tap on the correct option (option index 1 → "قيمة نبوية").
      final optionFinder = find.ancestor(
        of: find.text('قيمة نبوية'),
        matching: find.byType(InkWell),
      );
      expect(optionFinder, findsOneWidget);
      await tester.tap(optionFinder);
      await tester.pumpAndSettle();

      // After tapping, the next button appears. The button has
      // minimumSize: Size.fromHeight(50) so it's reliably findable.
      expect(find.byKey(const Key('quiz_next_button')), findsOneWidget);
    });

    testWidgets('summary screen shows correct count and retry button',
        (tester) async {
      final fake = _FakeAssetClient();
      fake.assetContent['q1'] = _quizJson('q1', [
        [
          'س1؟',
          ['صحيح', 'خطأ', 'مش متأكد', 'لا أعرف'],
          0,
        ],
      ]);

      await tester.pumpWidget(
        _wrap(const QuizScreen(quizIds: ['q1']), fake),
      );
      await tester.pumpAndSettle();

      // Pick correct option then click next to reach summary.
      await tester.tap(find.text('صحيح').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('عرض النتيجة'));
      // ≥80% plays confetti, whose particle ticker never "settles" —
      // use bounded pumps instead of pumpAndSettle.
      await tester.pump();
      await tester.pump(const Duration(seconds: 2));

      expect(find.text('نتيجتك'), findsOneWidget);
      expect(find.text('1 / 1'), findsOneWidget);
      expect(find.text('100%'), findsOneWidget);
      expect(find.byKey(const Key('quiz_retry_button')), findsOneWidget);
    });

    testWidgets('retry button resets the quiz', (tester) async {
      final fake = _FakeAssetClient();
      fake.assetContent['q1'] = _quizJson('q1', [
        [
          'س1؟',
          ['صحيح', 'خطأ', 'مش متأكد', 'لا أعرف'],
          0,
        ],
        [
          'س2؟',
          ['أ', 'ب', 'ج', 'د'],
          2,
        ],
      ]);

      await tester.pumpWidget(
        _wrap(const QuizScreen(quizIds: ['q1']), fake),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('صحيح').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('السؤال التالي'));
      await tester.pumpAndSettle();

      // Get Q2 wrong, then click to summary.
      await tester.tap(find.text('أ').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('عرض النتيجة'));
      await tester.pump();
      await tester.pump(const Duration(seconds: 2));

      // Now retry.
      await tester.tap(find.byKey(const Key('quiz_retry_button')));
      await tester.pumpAndSettle();

      // Back at Q1.
      expect(find.text('سؤال 1 من 2'), findsOneWidget);
      expect(find.text('س1؟'), findsOneWidget);
    });

    testWidgets('empty/missing decks show friendly empty state',
        (tester) async {
      final fake = _FakeAssetClient();
      await tester.pumpWidget(
        _wrap(const QuizScreen(quizIds: ['missing']), fake),
      );
      await tester.pumpAndSettle();

      expect(
        find.text('لا توجد أسئلة متاحة لهذا الدرس حالياً'),
        findsOneWidget,
      );
    });
  });
}
