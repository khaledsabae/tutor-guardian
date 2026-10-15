// «السماء» on «اليوم»: the hour picks the sky, the night has at most twelve
// stars and no sun, and a dark page never gets a glaring pastel card.
import 'dart:ui' as ui;

import 'package:almorabbi/features/home/widgets/sky_band.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

int _paint(SkyTime time, Brightness b, {Size size = const Size(360, 160)}) {
  final painter = SkyPainter(
    paper: SkyPaper.of(time, b),
    time: time,
    textDirection: TextDirection.rtl,
  );
  final recorder = ui.PictureRecorder();
  painter.paint(Canvas(recorder), size);
  recorder.endRecording().dispose();
  return painter.starsPainted;
}

void main() {
  test('the hour picks the sky', () {
    SkyTime at(int h) => skyTimeOf(DateTime(2026, 10, 14, h, 30));
    expect(at(3), SkyTime.night);
    expect(at(5), SkyTime.dawn);
    expect(at(9), SkyTime.day);
    expect(at(15), SkyTime.day);
    expect(at(17), SkyTime.maghrib);
    expect(at(20), SkyTime.night);
  });

  test('stars only at night, twelve at most; no sun at night', () {
    for (final b in Brightness.values) {
      expect(_paint(SkyTime.night, b), inInclusiveRange(1, kMaxSkyStars));
      expect(SkyPaper.of(SkyTime.night, b).sun, isNull);
      for (final t in [SkyTime.dawn, SkyTime.day, SkyTime.maghrib]) {
        expect(_paint(t, b), 0, reason: '$t $b');
        expect(SkyPaper.of(t, b).sun, isNotNull);
      }
    }
  });

  test('on a dark page every sky is cut from deep paper', () {
    for (final t in SkyTime.values) {
      final sky = SkyPaper.of(t, Brightness.dark).sky;
      expect(sky.computeLuminance(), lessThan(.05), reason: '$t');
    }
  });

  testWidgets('the sky frames its child and carries no words of its own', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SkyBand(
            now: DateTime(2026, 10, 14, 21),
            child: const Text('BUBBLE'),
          ),
        ),
      ),
    );
    expect(find.text('BUBBLE'), findsOneWidget);
    expect(find.byType(Text), findsOneWidget);
  });
}
