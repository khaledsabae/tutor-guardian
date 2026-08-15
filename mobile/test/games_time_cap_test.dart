/// The four games had no clock in them at all.
///
/// The only way out of a level was answering every question or losing three
/// lives, and a child who did neither could sit there indefinitely while the
/// server-side session quietly expired underneath. These tests cover the three
/// things that changed: the cap comes from the server, the surface ends when
/// it runs out, and what the child is offered at that moment is a way outside
/// rather than another round.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:almorabbi/features/games/shared/edu_game_models.dart';
import 'package:almorabbi/features/games/shared/edu_game_shell.dart';
import 'package:almorabbi/features/routine/providers/child_mode_providers.dart';
import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

/// A notifier seeded with a session already open, so a test can say "this
/// child has N seconds left" without a server.
class _StubChildMode extends ChildModeNotifier {
  _StubChildMode(ChildModeState initial) : super(_NullClient()) {
    state = initial;
  }

  int endSessionCalls = 0;
  String? lastReason;

  @override
  Future<void> endSession({String reason = 'completed', String? code}) async {
    endSessionCalls++;
    lastReason = reason;
  }
}

/// The runner never touches the network in these tests; the cap arrives
/// through state, and finishing is local.
class _NullClient implements TgClient {
  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

const _theme = EduGameTheme(
  id: 'test_game',
  name: 'لعبة الاختبار',
  heroEmoji: '🎲',
  description: 'لعبة للاختبار',
  backgroundColor: Colors.white,
  surfaceColor: Colors.white,
  accentColor: Colors.teal,
  textColor: Colors.black,
);

List<EduQuestion> _questions(int count) => List.generate(
      count,
      (i) => EduQuestion(
        id: 'q$i',
        question: 'سؤال $i',
        options: const [
          EduOption(text: 'صح', isCorrect: true, key: 'a'),
          EduOption(text: 'غلط', isCorrect: false, key: 'b'),
        ],
      ),
    );

Widget _harness({
  required _StubChildMode notifier,
  required List<EduQuestion> questions,
  void Function(EduGameResult)? onComplete,
}) {
  return ProviderScope(
    overrides: [
      childModeProvider.overrideWith((ref) => notifier),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('ar'),
      home: EduGameRunner(
        theme: _theme,
        level: 1,
        questions: questions,
        onComplete: onComplete ?? (_) {},
      ),
    ),
  );
}

void main() {
  group('the cap comes from the server', () {
    testWidgets('a running session ends the level when its seconds run out',
        (tester) async {
      final notifier = _StubChildMode(const ChildModeState(
        active: true,
        childId: 1,
        sessionId: 99,
        remainingSeconds: 3,
      ));

      await tester.pumpWidget(_harness(notifier: notifier, questions: _questions(20)));
      await tester.pump();

      // Still playing well before the cap.
      await tester.pump(const Duration(seconds: 2));
      expect(find.byType(AlertDialog), findsNothing);

      // And stopped after it, without the child answering anything.
      await tester.pump(const Duration(seconds: 2));
      await tester.pumpAndSettle();
      expect(find.byType(AlertDialog), findsOneWidget);
    });

    testWidgets('no session means no cap — a parent playing is not on a clock',
        (tester) async {
      final notifier = _StubChildMode(const ChildModeState());
      await tester.pumpWidget(_harness(notifier: notifier, questions: _questions(20)));
      await tester.pump(const Duration(minutes: 30));
      expect(find.byType(AlertDialog), findsNothing);
    });

    // These two are one assertion split in half: the same three seconds must
    // end a short session and not a long one. A ten-minute constant compiled
    // into the client would make them agree, and a limit the client owns is a
    // limit the client can edit.
    testWidgets('two seconds of allowance ends after three', (tester) async {
      final notifier = _StubChildMode(const ChildModeState(
        active: true, childId: 1, sessionId: 1, remainingSeconds: 2));
      await tester.pumpWidget(_harness(notifier: notifier, questions: _questions(20)));
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();
      expect(find.byType(AlertDialog), findsOneWidget);
    });

    testWidgets('ten minutes of allowance does not', (tester) async {
      final notifier = _StubChildMode(const ChildModeState(
        active: true, childId: 1, sessionId: 2, remainingSeconds: 600));
      await tester.pumpWidget(_harness(notifier: notifier, questions: _questions(20)));
      await tester.pump(const Duration(seconds: 3));
      expect(find.byType(AlertDialog), findsNothing);
    });
  });

  group('the exit ritual', () {
    testWidgets('offers one way out, and it is outside', (tester) async {
      final notifier = _StubChildMode(const ChildModeState(
        active: true, childId: 1, sessionId: 5, remainingSeconds: 2));

      await tester.pumpWidget(_harness(notifier: notifier, questions: _questions(20)));
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();

      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      expect(find.text(l10n.gameClosingTitle), findsOneWidget);
      expect(find.text(l10n.gameClosingMission), findsOneWidget);
      expect(find.text(l10n.gameClosingLeave), findsOneWidget);
    });

    testWidgets('no replay and no next level when the budget ended it',
        (tester) async {
      // The extension is the point: offering "play again" at the moment the
      // day's time runs out teaches that the limit was a suggestion.
      final notifier = _StubChildMode(const ChildModeState(
        active: true, childId: 1, sessionId: 5, remainingSeconds: 2));

      await tester.pumpWidget(_harness(notifier: notifier, questions: _questions(20)));
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();

      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      expect(find.text(l10n.eduGameTryAgain), findsNothing);
      expect(find.text(l10n.eduGameNextLevel), findsNothing);
    });

    testWidgets('the closing screen cannot be dismissed by tapping away',
        (tester) async {
      final notifier = _StubChildMode(const ChildModeState(
        active: true, childId: 1, sessionId: 5, remainingSeconds: 2));

      await tester.pumpWidget(_harness(notifier: notifier, questions: _questions(20)));
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();

      await tester.tapAt(const Offset(10, 10));
      await tester.pumpAndSettle();
      expect(find.byType(AlertDialog), findsOneWidget);
    });

    testWidgets('closing the surface tells the server it is over',
        (tester) async {
      final notifier = _StubChildMode(const ChildModeState(
        active: true, childId: 1, sessionId: 5, remainingSeconds: 2));

      await tester.pumpWidget(_harness(notifier: notifier, questions: _questions(20)));
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();

      expect(notifier.endSessionCalls, 1);
      expect(notifier.lastReason, 'budget_exhausted');
    });

    testWidgets('a level finished normally still offers the usual result',
        (tester) async {
      // Only the budget ending swaps the dialog. Finishing a level on your own
      // terms, with time left, is a success and reads like one.
      final notifier = _StubChildMode(const ChildModeState(
        active: true, childId: 1, sessionId: 5, remainingSeconds: 600));

      await tester.pumpWidget(_harness(notifier: notifier, questions: _questions(1)));
      await tester.pump();

      await tester.tap(find.text('صح'));
      await tester.pump(const Duration(seconds: 2));
      await tester.pumpAndSettle();

      final l10n = await AppLocalizations.delegate.load(const Locale('ar'));
      expect(find.text(l10n.gameClosingTitle), findsNothing);
      expect(notifier.endSessionCalls, 0);
    });
  });
}
