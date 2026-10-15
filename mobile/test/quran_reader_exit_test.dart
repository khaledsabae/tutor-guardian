// Leaving the Quran reader saves where the parent stopped, and throws
// nothing. Until 2026-10-15 every exit threw «Cannot use "ref" after the
// widget was disposed» from dispose() — the CI rehearsal's logcat gate caught
// it after its sound check closed the reader — and the final save never ran.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/quran/providers/quran_providers.dart';
import 'package:almorabbi/features/quran/screens/surah_reading_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/theme/bundled_fonts.dart';

final _quran = <String, List<dynamic>>{
  '1': [
    for (var v = 1; v <= 7; v++) {'chapter': 1, 'verse': v, 'text': 'آية $v'},
  ],
  '2': [
    for (var v = 1; v <= 7; v++) {'chapter': 2, 'verse': v, 'text': 'آية $v'},
  ],
};

void main() {
  setUpAll(configureBundledFonts);

  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('back from the reader: no error, and the place is saved',
      (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final navigator = GlobalKey<NavigatorState>();
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        navigatorKey: navigator,
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const Scaffold(body: SizedBox()),
      ),
    ));
    navigator.currentState!.push(MaterialPageRoute<void>(
      builder: (_) => SurahReadingScreen(
        chapterNumber: 2,
        initialVerse: 3,
        quranData: _quran,
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.byType(SurahReadingScreen), findsOneWidget);

    navigator.currentState!.pop();
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byType(SurahReadingScreen), findsNothing);
    final saved = container.read(lastReadProvider).valueOrNull;
    expect((saved?.chapter, saved?.verse), (2, 3));
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getInt('quran_last_read_chapter'), 2);
    expect(prefs.getInt('quran_last_read_verse'), 3);
  });
}
