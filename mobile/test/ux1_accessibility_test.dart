// UX-1 accessibility baseline (UX_UI_ROADMAP §5):
//  * custom tap targets are announced as buttons (DS9);
//  * with "remove animations" on, looping animations stop — a loop that keeps
//    scheduling frames is exactly the flicker the setting asks us to avoid;
//  * key surfaces survive a 200% text scale without overflowing.

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/widgets/message_bubble.dart';
import 'package:almorabbi/widgets/ui/bouncy_button.dart';
import 'package:almorabbi/widgets/ui/error_retry_view.dart';
import 'package:almorabbi/widgets/ui/night_sky.dart';
import 'package:almorabbi/widgets/ui/skeleton.dart';

Widget _host(
  Widget child, {
  bool reduceMotion = false,
  double textScale = 1,
  Locale locale = const Locale('ar'),
}) =>
    MaterialApp(
      locale: locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: Builder(
        builder: (context) => MediaQuery(
          data: MediaQuery.of(context).copyWith(
            disableAnimations: reduceMotion,
            textScaler: TextScaler.linear(textScale),
          ),
          child: Scaffold(body: child),
        ),
      ),
    );

AssistantReply _reply() => AssistantReply.fromJson({
      'reply_text': 'x',
      'domain': 'medical',
      'severity': 'خفيف',
      'needs_human_review': false,
      'escalation_target': null,
      'mode': 'llm_generated',
      'session_id': 's1',
    });

void _phone(WidgetTester t) {
  t.view.physicalSize = const Size(360 * 3, 740 * 3);
  t.view.devicePixelRatio = 3;
  addTearDown(t.view.reset);
}

/// Pump through [span] of animation time, then report whether anything is
/// still asking for frames (a running loop always is).
Future<bool> _stillAnimating(WidgetTester t, Duration span) async {
  for (var i = 0; i < span.inMilliseconds ~/ 100; i++) {
    await t.pump(const Duration(milliseconds: 100));
  }
  return t.binding.hasScheduledFrame;
}

void main() {
  group('DS9: custom tap targets are buttons', () {
    testWidgets('BouncyButton is announced as an enabled button', (t) async {
      final handle = t.ensureSemantics();
      await t.pumpWidget(_host(BouncyButton(label: 'ابدأ', onTap: () {})));
      expect(
        t.getSemantics(find.byType(BouncyTap)),
        matchesSemantics(
          isButton: true,
          hasEnabledState: true,
          isEnabled: true,
          hasTapAction: true,
          label: 'ابدأ',
        ),
      );
      handle.dispose();
    });

    testWidgets('an icon-only BouncyTap carries its label', (t) async {
      final handle = t.ensureSemantics();
      await t.pumpWidget(_host(BouncyTap(
        onTap: () {},
        semanticLabel: 'مشاركة',
        child: const Icon(Icons.share),
      )));
      expect(find.bySemanticsLabel('مشاركة'), findsOneWidget);
      handle.dispose();
    });

    testWidgets('a disabled BouncyTap says so', (t) async {
      final handle = t.ensureSemantics();
      await t.pumpWidget(_host(const BouncyTap(child: Text('لاحقاً'))));
      expect(
        t.getSemantics(find.byType(BouncyTap)),
        matchesSemantics(isButton: true, hasEnabledState: true, label: 'لاحقاً'),
      );
      handle.dispose();
    });
  });

  group('reduce motion: loops stop', () {
    testWidgets('the thinking dots loop normally and hold still when reduced',
        (t) async {
      final m = ChatMessageUI(id: '1', role: 'assistant', content: '', isStreaming: true);
      await t.pumpWidget(_host(MessageBubble(message: m)));
      expect(await _stillAnimating(t, const Duration(seconds: 4)), isTrue);

      await t.pumpWidget(_host(MessageBubble(message: m), reduceMotion: true));
      expect(await _stillAnimating(t, const Duration(seconds: 4)), isFalse);
    });

    testWidgets('the loading skeleton shimmers once, not forever', (t) async {
      await t.pumpWidget(_host(const SkeletonList(count: 2), reduceMotion: true));
      expect(await _stillAnimating(t, const Duration(seconds: 3)), isFalse);
    });

    testWidgets('the night sky is still', (t) async {
      await t.pumpWidget(_host(
        const Stack(children: [TwinklingStars(count: 8), FloatingFireflies(count: 5)]),
        reduceMotion: true,
      ));
      // Stars start after a random delay of up to 3 s — past that, still.
      expect(await _stillAnimating(t, const Duration(seconds: 5)), isFalse);
    });
  });

  group('200% text scale: no overflow', () {
    for (final locale in const [Locale('ar'), Locale('en')]) {
      testWidgets('answer bubble with follow-ups (${locale.languageCode})', (t) async {
        _phone(t);
        final m = ChatMessageUI(
          id: '2',
          role: 'assistant',
          content: 'إجابة طويلة نسبياً تمتد على أكثر من سطر واحد لتختبر الالتفاف',
        )..reply = _reply();
        await t.pumpWidget(_host(
          SingleChildScrollView(
            child: MessageBubble(
              message: m,
              followUps: const ['أعطني مثالاً عملياً', 'ماذا لو كان عمره أصغر؟'],
              onFollowUp: (_) {},
              onFeedback: (_) {},
            ),
          ),
          textScale: 2,
          locale: locale,
        ));
        await t.pump(const Duration(seconds: 1));
        expect(t.takeException(), isNull);
      });

      testWidgets('error view (${locale.languageCode})', (t) async {
        _phone(t);
        await t.pumpWidget(_host(
          SingleChildScrollView(
            child: ErrorRetryView(error: TgApiError(null, 'offline'), onRetry: () {}),
          ),
          textScale: 2,
          locale: locale,
        ));
        await t.pump(const Duration(seconds: 1));
        expect(t.takeException(), isNull);
      });

      testWidgets('primary button (${locale.languageCode})', (t) async {
        _phone(t);
        await t.pumpWidget(_host(
          Center(
            child: BouncyButton(
              label: 'ابدأ رحلتك مع طفلك الآن',
              icon: const Icon(Icons.arrow_forward),
              onTap: () {},
            ),
          ),
          textScale: 2,
          locale: locale,
        ));
        expect(t.takeException(), isNull);
      });
    }
  });
}
