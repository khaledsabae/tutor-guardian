// UX-2 rest (UX_UI_ROADMAP C6, C8 and §2.2): the "Sources (n)" disclosure
// under a grounded answer, and the behaviour-type field folded from a
// permanent bar above the chat into a context chip in the composer.

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/screens/chat_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/widgets/message_bubble.dart';

Map<String, dynamic> _json({Object? metadata}) => {
      'reply_text': 'x', 'domain': 'medical', 'severity': 'خفيف',
      'needs_human_review': false, 'escalation_target': null,
      'mode': 'llm_generated', 'session_id': 's',
      'metadata': metadata,
    };

Widget _host(Widget child) => MaterialApp(
      locale: const Locale('en'),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

const _answer = 'Keep a calm routine.\n\n**📚 المصدر: UNICEF · CDC**';

void main() {
  group('sources', () {
    test('parsed from metadata.sources: strings only, trimmed, capped at 4', () {
      final r = AssistantReply.fromJson(_json(metadata: {
        'sources': [' UNICEF ', '', 7, 'CDC', 'A', 'B', 'C'],
      }));
      expect(r.sources, ['UNICEF', 'CDC', 'A', 'B']);
    });

    test('absent on an older backend → empty', () {
      expect(AssistantReply.fromJson(_json()).sources, isEmpty);
      expect(AssistantReply.fromJson(_json(metadata: {'top_rerank': 1})).sources,
          isEmpty);
    });

    test('stripSourceLines drops only the 📚 lines', () {
      expect(stripSourceLines(_answer), 'Keep a calm routine.');
      expect(stripSourceLines('a\n> 📚 المصدر: X\nb'), 'a\nb');
      expect(stripSourceLines('no sources here'), 'no sources here');
    });

    testWidgets('collapsed row replaces the inline line and expands on tap',
        (t) async {
      final m = ChatMessageUI(id: '1', role: 'assistant', content: _answer)
        ..reply = AssistantReply.fromJson(
            _json(metadata: {'sources': ['UNICEF', 'CDC']}));
      await t.pumpWidget(_host(MessageBubble(message: m)));

      expect(find.text('Sources (2)'), findsOneWidget);
      expect(find.textContaining('📚'), findsNothing);
      expect(find.text('• UNICEF'), findsNothing);

      await t.tap(find.text('Sources (2)'));
      await t.pumpAndSettle();
      expect(find.text('• UNICEF'), findsOneWidget);
      expect(find.text('• CDC'), findsOneWidget);
    });

    testWidgets('no structured sources → no row, inline line kept', (t) async {
      final m = ChatMessageUI(id: '2', role: 'assistant', content: _answer)
        ..reply = AssistantReply.fromJson(_json());
      await t.pumpWidget(_host(MessageBubble(message: m)));
      expect(find.textContaining('Sources ('), findsNothing);
      expect(find.textContaining('📚'), findsOneWidget);
    });
  });

  group('context chip (C6)', () {
    // The chat's boot splash animates forever, so pumpAndSettle never returns.
    Future<void> settle(WidgetTester t) async {
      for (var i = 0; i < 5; i++) {
        await t.pump(const Duration(milliseconds: 200));
      }
    }

    Future<ProviderContainer> pumpChat(WidgetTester t) async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      await OnboardingStorage(prefs).markOnboardingCompleted();
      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(_NullClient()),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ]);
      await container.read(sharedPreferencesProvider.future);
      addTearDown(container.dispose);
      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          locale: Locale('en'),
          home: ChatScreen(),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
        ),
      ));
      await t.pump(const Duration(milliseconds: 100));
      await t.pump(const Duration(milliseconds: 100));
      return container;
    }

    testWidgets('no permanent field; set, show and clear from the composer',
        (t) async {
      final container = await pumpChat(t);
      final l10n = AppLocalizations.of(t.element(find.byType(ChatScreen)));

      // The old bar was a labelled field above the conversation.
      expect(find.widgetWithText(TextFormField, l10n.chatBehaviorOptional),
          findsNothing);
      expect(find.byType(InputChip), findsNothing);

      await t.tap(find.byTooltip(l10n.chatContextAdd));
      await settle(t);
      await t.enterText(
          find.widgetWithText(TextField, l10n.chatBehaviorOptional), ' tantrums ');
      await t.tap(find.text(l10n.chatContextDone));
      await settle(t);

      expect(container.read(chatNotifierProvider).behaviorType, 'tantrums');
      expect(find.widgetWithText(InputChip, 'tantrums'), findsOneWidget);

      await t.tap(find.byTooltip(l10n.chatContextClear));
      await settle(t);
      expect(container.read(chatNotifierProvider).behaviorType, '');
      expect(find.byType(InputChip), findsNothing);
    });
  });
}

/// Bootstrap fails harmlessly; the composer is what is under test.
class _NullClient extends TgClient {
  _NullClient() : super.forTesting(baseUrl: 'http://test');

  @override
  Future<SessionResponse> createSession({Map<String, dynamic>? metadata}) async =>
      throw const TgApiError(500, 'fake-error');

  @override
  Future<String?> currentSessionId() async => throw const TgApiError(500, 'fake-error');

  @override
  Future<SessionHistory> getHistory(String sessionId) async =>
      throw const TgApiError(500, 'fake-error');
}
