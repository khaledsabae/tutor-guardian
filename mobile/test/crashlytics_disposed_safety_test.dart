// Regression tests for crashlytics issues caused by stale/disposed state.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/story_models.dart';
import 'package:almorabbi/features/program/screens/bedtime_routine_screen.dart';
import 'package:almorabbi/features/program/screens/story_bookshelf_screen.dart';

Widget _wrap(Widget child) => MaterialApp(
      home: Directionality(textDirection: TextDirection.rtl, child: child),
    );

Story get _fakeStory => Story(
      id: 'test-story',
      title: 'Test',
      description: 'Test story',
      coverImage: 'assets/images/test.png',
      themeColor: '0xFF0D9488',
      pages: const [],
    );

void main() {
  group('BedtimeRoutineScreen star animation', () {
    testWidgets('entering and quickly leaving screen does not crash',
        (tester) async {
      await tester.pumpWidget(
        _wrap(BedtimeRoutineScreen(story: _fakeStory)),
      );
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
    });
  });

  group('StoryBookshelfScreen star animation', () {
    testWidgets('entering and quickly leaving screen does not crash',
        (tester) async {
      await tester.pumpWidget(
        _wrap(const StoryBookshelfScreen()),
      );
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
    });
  });
}
