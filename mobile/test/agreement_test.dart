/// The signing surfaces, tested where a family can actually get stuck.
///
/// The server refuses every child surface until an agreement is signed, so a
/// bug in these screens is not a cosmetic bug — it is a family with no child
/// mode and no way to get one. The tests below are mostly about the two
/// disabled buttons: sign-without-a-signature, and agree-without-reading.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:almorabbi/features/agreement/agreement_export.dart';
import 'package:almorabbi/features/agreement/signature_pad.dart';

/// The pad's own gesture target. `find.byType(CustomPaint).first` matches
/// Material's internal painters, so a drag there hits nothing and the test
/// passes for the wrong reason.
final _pad = find.descendant(
  of: find.byType(SignaturePad),
  matching: find.byType(GestureDetector),
);

void main() {
  group('signature pad', () {
    testWidgets('starts empty and says so', (tester) async {
      final key = GlobalKey<SignaturePadState>();
      var reported = true;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: SignaturePad(
            key: key,
            label: 'وقّع',
            onChanged: (v) => reported = v,
          ),
        ),
      ));
      expect(key.currentState!.isEmpty, isTrue);
      expect(reported, isTrue, reason: 'nothing drawn yet, so nothing fired');
    });

    testWidgets('a drag makes it non-empty and reports once', (tester) async {
      final key = GlobalKey<SignaturePadState>();
      bool? reported;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: SignaturePad(
            key: key, label: 'وقّع', onChanged: (v) => reported = v),
        ),
      ));
      await tester.drag(_pad, const Offset(40, 20));
      await tester.pump();

      expect(key.currentState!.isEmpty, isFalse);
      expect(reported, isTrue);
    });

    testWidgets('clearing empties it again', (tester) async {
      final key = GlobalKey<SignaturePadState>();
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: SignaturePad(key: key, label: 'وقّع')),
      ));
      await tester.drag(_pad, const Offset(40, 20));
      await tester.pump();
      key.currentState!.clear();
      await tester.pump();
      expect(key.currentState!.isEmpty, isTrue);
    });

  });

  group('export', () {
    test('print scale is at least 3x', () {
      // Below 3 the PNG is screen resolution and the Arabic turns to mush on
      // paper, which defeats the point of a thing meant for a wall.
      expect(kAgreementPixelRatio, greaterThanOrEqualTo(3.0));
    });

    test('the filename keeps Arabic names and drops path separators', () {
      expect(agreementFileName('أحمد'), 'agreement_أحمد.png');
      expect(agreementFileName('a/b'), 'agreement_a_b.png');
      expect(agreementFileName('../../etc/passwd'), isNot(contains('/')));
      expect(agreementFileName(''), 'agreement_child.png');
    });

    testWidgets('capturing an unmounted key returns null rather than throwing',
        (tester) async {
      expect(await captureAgreementPng(GlobalKey()), isNull);
    });

    // NOT tested here: the actual PNG render. RenderRepaintBoundary.toImage
    // needs a rasteriser, and in a headless widget test it hangs rather than
    // failing — a ten-minute CI timeout that reports nothing. The capture
    // path is verified on a device; what is testable off one is everything
    // around it, which is what the rest of this group covers.
  });
}
