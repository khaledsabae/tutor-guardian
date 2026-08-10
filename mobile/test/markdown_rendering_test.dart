// Every assistant reply is rendered as Markdown, so the renderer is on the
// app's most-used path. flutter_markdown was discontinued upstream and this
// moved to flutter_markdown_plus, the maintained fork the pub listing points
// to. The API matched, which is exactly the situation where a swap gets waved
// through without anyone checking that Arabic still renders.
//
// These assert what a parent actually sees: their text, in the right
// direction, with the formatting the model sent.

import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _host(String markdown) => MaterialApp(
      locale: const Locale('ar'),
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: Scaffold(body: MarkdownBody(data: markdown)),
      ),
    );

void main() {
  testWidgets('renders Arabic prose as-is', (tester) async {
    const arabic = 'ابنك في هذا العمر يحتاج إلى روتين ثابت قبل النوم.';
    await tester.pumpWidget(_host(arabic));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.textContaining('روتين ثابت'), findsOneWidget);
  });

  testWidgets('keeps right-to-left direction', (tester) async {
    await tester.pumpWidget(_host('نص عربي'));
    await tester.pumpAndSettle();

    final direction = Directionality.of(
      tester.element(find.textContaining('نص عربي')),
    );
    expect(direction, TextDirection.rtl);
  });

  testWidgets('renders the formatting the model actually emits',
      (tester) async {
    // Bold, a bullet list and a source line — the shape of a real reply.
    const reply = '''
**الخلاصة:** ثبّت موعد النوم.

- أطفئ الشاشات قبل ساعة
- اقرأ قصة قصيرة

📚 المصدر: دليل النوم''';

    await tester.pumpWidget(_host(reply));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.textContaining('ثبّت موعد النوم'), findsOneWidget);
    expect(find.textContaining('أطفئ الشاشات'), findsOneWidget);
    expect(find.textContaining('المصدر'), findsOneWidget);
    // The ** markers must be consumed by the renderer, not shown to the reader.
    expect(find.textContaining('**'), findsNothing);
  });

  testWidgets('an empty reply does not throw', (tester) async {
    await tester.pumpWidget(_host('…'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
