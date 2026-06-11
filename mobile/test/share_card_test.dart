// Share card tests (P1 #2) — ShareableTipCard rendering.
// Added in review (the original commit shipped without tests).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/models.dart';
import 'package:almorabbi/features/program/widgets/shareable_tip_card.dart';

DailyTip _tip(String text) => DailyTip(
      id: 't1',
      ageGroup: '7-9',
      domain: 'medical',
      text: text,
      timeOfDay: 'morning',
      tags: const [],
      isPublished: true,
    );

void main() {
  group('ShareableTipCard', () {
    testWidgets('renders the tip text and app branding', (tester) async {
      // The card is 1080×1080 — give the test a large surface so it
      // lays out without overflow during the pump.
      tester.view.physicalSize = const Size(1200, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.rtl,
          child: ShareableTipCard(
            tip: _tip('اقرأ لطفلك كل ليلة قبل النوم'),
            childName: 'سارة',
          ),
        ),
      );

      expect(find.text('اقرأ لطفلك كل ليلة قبل النوم'), findsOneWidget);
      expect(find.text('المربي الذكي'), findsOneWidget);
    });

    testWidgets('exposes a fixed square capture size', (tester) async {
      expect(ShareableTipCard.size.width, ShareableTipCard.size.height);
      expect(ShareableTipCard.size.width, greaterThanOrEqualTo(1080));
    });
  });
}
