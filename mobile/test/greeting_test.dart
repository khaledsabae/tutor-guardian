/// Time-aware greeting and AppBar title («النصوص», phase 1).
///
/// The hour picks صباح/مساء and ☀️/🌙; a first-day login streak drops the
/// «مستمرة» — a journey that has not started cannot be continuing. The
/// functions take the clock as a parameter, so these tests pin behaviour,
/// not the hour they happen to run at.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/home/greeting.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

void main() {
  group('the clock', () {
    test('the sun is up from 6:00 to 17:59', () {
      expect(sunIsUp(DateTime(2026, 1, 1, 6)), isTrue);
      expect(sunIsUp(DateTime(2026, 1, 1, 12)), isTrue);
      expect(sunIsUp(DateTime(2026, 1, 1, 17, 59)), isTrue);
      expect(sunIsUp(DateTime(2026, 1, 1, 18)), isFalse);
      expect(sunIsUp(DateTime(2026, 1, 1, 5, 59)), isFalse);
      expect(sunIsUp(DateTime(2026, 1, 1, 23)), isFalse);
    });

    test('morning runs from before dawn to late afternoon', () {
      expect(isMorning(DateTime(2026, 1, 1, 4)), isTrue);
      expect(isMorning(DateTime(2026, 1, 1, 9)), isTrue);
      expect(isMorning(DateTime(2026, 1, 1, 15, 59)), isTrue);
      expect(isMorning(DateTime(2026, 1, 1, 16)), isFalse);
      expect(isMorning(DateTime(2026, 1, 1, 22)), isFalse);
    });
  });

  group('the copy each hour produces', () {
    testWidgets('picks a locale', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          locale: const Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const Scaffold(body: SizedBox()),
        ),
      );
      final l10n = AppLocalizations.of(
          tester.element(find.byType(Scaffold).first));

      final morning = DateTime(2026, 1, 1, 9);
      final evening = DateTime(2026, 1, 1, 21);

      // A continuing journey says صباح/مساء and keeps «مستمرة».
      expect(greetingFor(l10n, 'سارة', morning, firstDay: false),
          'صباح الخير 🌤️\nرحلة سارة مستمرة');
      expect(greetingFor(l10n, 'سارة', evening, firstDay: false),
          'مساء الخير 🌙\nرحلة سارة مستمرة');

      // Day one says so, and never claims continuity.
      expect(greetingFor(l10n, 'سارة', morning, firstDay: true),
          'صباح الخير 🌤️\nاليوم أول يوم في رحلة سارة');
      expect(greetingFor(l10n, 'سارة', evening, firstDay: true),
          'مساء الخير 🌙\nاليوم أول يوم في رحلة سارة');

      // The AppBar title follows the sun, not the greeting's clock.
      expect(todayTitle(l10n, DateTime(2026, 1, 1, 12)), 'اليوم ☀️');
      expect(todayTitle(l10n, DateTime(2026, 1, 1, 20)), 'اليوم 🌙');
    });
  });
}
