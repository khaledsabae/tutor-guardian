// «السماء» on «اليوم»: the hour picks the sky, the night has at most twelve
// stars and no sun, and a dark page never gets a glaring pastel card. In
// Ramadan (phase 5) the maghrib and night skies hang a lantern string — and
// no other sky, and no sky outside the month.
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

int _lanterns(
  SkyTime time,
  Brightness b, {
  bool ramadan = true,
  Size size = const Size(360, 160),
  TextDirection dir = TextDirection.rtl,
}) {
  final painter = SkyPainter(
    paper: SkyPaper.of(time, b),
    time: time,
    textDirection: dir,
    ramadan: ramadan,
  );
  final recorder = ui.PictureRecorder();
  painter.paint(Canvas(recorder), size);
  recorder.endRecording().dispose();
  return painter.lanternsPainted;
}

SkyPainter _painterIn(WidgetTester tester) =>
    tester
            .widget<CustomPaint>(
              find.descendant(
                of: find.byType(SkyBand),
                matching: find.byType(CustomPaint),
              ),
            )
            .painter!
        as SkyPainter;

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

  group('Ramadan skin (phase 5)', () {
    test('in Ramadan: lanterns at maghrib and at night, light and dark', () {
      for (final b in Brightness.values) {
        expect(_lanterns(SkyTime.night, b), kMaxSkyLanterns, reason: '$b');
        expect(
          _lanterns(SkyTime.maghrib, b),
          inInclusiveRange(1, kMaxSkyLanterns),
          reason: '$b',
        );
      }
    });

    test('never by day or at dawn, Ramadan or not', () {
      for (final b in Brightness.values) {
        for (final t in [SkyTime.dawn, SkyTime.day]) {
          expect(_lanterns(t, b), 0, reason: '$t $b');
        }
      }
    });

    test('outside Ramadan no sky has a lantern', () {
      for (final b in Brightness.values) {
        for (final t in SkyTime.values) {
          expect(_lanterns(t, b, ramadan: false), 0, reason: '$t $b');
        }
      }
    });

    test('no lantern hangs in front of the low maghrib sun, either side', () {
      // At 400 wide the end lantern falls on the sun (64 in from the far end).
      for (final dir in TextDirection.values) {
        expect(
          _lanterns(
            SkyTime.maghrib,
            Brightness.light,
            size: const Size(400, 160),
            dir: dir,
          ),
          kMaxSkyLanterns - 1,
          reason: '$dir',
        );
        expect(
          _lanterns(
            SkyTime.night,
            Brightness.light,
            size: const Size(400, 160),
            dir: dir,
          ),
          kMaxSkyLanterns,
          reason: '$dir',
        );
      }
    });

    test('the night keeps its stars under the lanterns', () {
      for (final b in Brightness.values) {
        final painter = SkyPainter(
          paper: SkyPaper.of(SkyTime.night, b),
          time: SkyTime.night,
          textDirection: TextDirection.rtl,
          ramadan: true,
        );
        final recorder = ui.PictureRecorder();
        painter.paint(Canvas(recorder), const Size(360, 160));
        recorder.endRecording().dispose();
        expect(painter.starsPainted, inInclusiveRange(1, kMaxSkyStars));
      }
    });

    for (final b in Brightness.values) {
      testWidgets('the band passes Ramadan to its sky, and still no words '
          '(${b.name})', (tester) async {
        Future<SkyPainter> pump(DateTime now, bool ramadan) async {
          await tester.pumpWidget(
            MaterialApp(
              theme: ThemeData(brightness: b),
              home: Scaffold(
                body: SkyBand(
                  now: now,
                  ramadan: ramadan,
                  child: const Text('BUBBLE'),
                ),
              ),
            ),
          );
          return _painterIn(tester);
        }

        final night = DateTime(2027, 2, 9, 21);
        final maghrib = DateTime(2027, 2, 9, 17);
        final day = DateTime(2027, 2, 9, 10);
        for (final now in [night, maghrib]) {
          final p = await pump(now, true);
          expect(p.ramadan, isTrue);
          expect(p.lanternsPainted, greaterThan(0), reason: '$now');
          expect(find.byType(Text), findsOneWidget);
        }
        expect((await pump(day, true)).lanternsPainted, 0);
        for (final now in [night, maghrib]) {
          expect((await pump(now, false)).lanternsPainted, 0, reason: '$now');
        }
      });
    }
  });
}
