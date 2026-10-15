// «عيدكم مبارك» (نور والقناديل phase 5): on the first open of Eid, once a
// Hijri year, a quiet moment over Today — Noor happy, the lanterns lighting,
// and the way to the family's own card. Still under reduce-motion. Kept by
// Noor's switches (the server's kill switch, «وضع هادئ»), and never over a
// running tour or another tab.
import 'package:almorabbi/features/companion/data/companion_store.dart';
import 'package:almorabbi/features/companion/widgets/noor_face.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/programs/data/programs_models.dart';
import 'package:almorabbi/features/programs/screens/ramadan_recap_screen.dart';
import 'package:almorabbi/features/programs/widgets/eid_moment.dart';
import 'package:almorabbi/features/tour/tour_controller.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/main.dart' show appConfigProvider;
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'programs_support.dart';

/// `/api/programs` on a day of the 1448 season ([seasonJson]: Eid on
/// 2027-03-10), as the server would locate it.
Map<String, dynamic> _on(
  String state, {
  String date = '2027-03-10',
  bool recap = true,
  int hijriYear = 1448,
}) {
  final j = programsJson(state: state, day: null, recap: recap);
  return {
    ...j,
    'date': date,
    'ramadan': {
      ...(j['ramadan'] as Map<String, dynamic>),
      'season': {...seasonJson(), 'hijri_year': hijriYear},
    },
  };
}

ProgramsOverview _overview(Map<String, dynamic> j) =>
    ProgramsOverview.fromJson(j);

const _title = 'عيدكم مبارك';

Future<ProviderContainer> _pump(
  WidgetTester tester, {
  required Map<String, dynamic> programs,
  Map<String, Object> prefs = const {},
  bool reduce = false,
  bool dark = false,
  bool tour = false,
  bool onScreen = true,
  Map<String, dynamic> config = const {},
}) async {
  SharedPreferences.setMockInitialValues(prefs);
  final p = await SharedPreferences.getInstance();
  final client = FakeProgramsClient()..programs = programs;
  final container = ProviderContainer(
    overrides: [
      tgClientProvider.overrideWithValue(client),
      sharedPreferencesProvider.overrideWith((_) async => p),
      appConfigProvider.overrideWith((_) async => config),
    ],
  );
  addTearDown(container.dispose);
  if (tour) container.read(tourControllerProvider.notifier).start(3);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: const Locale('ar'),
        theme: dark ? AppTheme.dark() : AppTheme.light(),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: reduce),
          child: child!,
        ),
        home: Scaffold(
          body: TickerMode(
            enabled: onScreen,
            child: const EidMomentGate(child: Text('TODAY')),
          ),
        ),
      ),
    ),
  );
  // Memory and /api/programs resolve, then the post-frame show.
  await tester.pump();
  await tester.pump();
  await tester.pump();
  return container;
}

void main() {
  group('when Eid is (the server decides)', () {
    test('the day itself, then its second and third days — no later', () {
      expect(eidDayOf(_overview(_on('eid'))), 1);
      expect(eidDayOf(_overview(_on('after', date: '2027-03-11'))), 2);
      expect(eidDayOf(_overview(_on('after', date: '2027-03-12'))), 3);
      expect(eidDayOf(_overview(_on('after', date: '2027-03-13'))), isNull);
      expect(eidDayOf(_overview(_on('after', date: '2027-04-01'))), isNull);
    });

    test('never in the month, before it, or off-season', () {
      for (final s in ['upcoming', 'ramadan', 'off_season']) {
        expect(eidDayOf(_overview(_on(s))), isNull, reason: s);
      }
    });

    test('a server without a season, or without a date, says nothing', () {
      final noSeason = programsJson(state: 'eid', withSeason: false);
      expect(eidDayOf(_overview(noSeason)), isNull);
      final noDate = {..._on('after', date: '2027-03-11'), 'date': null};
      expect(eidDayOf(_overview(noDate)), isNull);
    });

    test('the key is per Hijri year', () {
      expect(eidMomentKey(1448), 'eid:1448');
    });
  });

  group('the moment over Today', () {
    testWidgets('Eid: it opens once, Noor happy, the words, the card link', (
      tester,
    ) async {
      await _pump(tester, programs: _on('eid'));
      expect(find.byKey(const ValueKey('eid_moment')), findsOneWidget);
      expect(find.text(_title), findsOneWidget);
      expect(find.text('كل عام وأنتم بخير.'), findsOneWidget);
      expect(find.byKey(const ValueKey('eid_moment_recap')), findsOneWidget);
      final face = tester.widget<NoorFace>(find.byType(NoorFace));
      expect(face.state, NoorFaceState.happy);
      // Recorded as it shows: once means once.
      final prefs = await SharedPreferences.getInstance();
      expect(CompanionStore(prefs).read().seenKeys, contains('eid:1448'));

      await tester.tap(find.byKey(const ValueKey('eid_moment_close')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('eid_moment')), findsNothing);
      expect(find.text('TODAY'), findsOneWidget);
    });

    testWidgets('once a Hijri year: not again that Eid, back the next', (
      tester,
    ) async {
      await _pump(tester, programs: _on('eid'));
      expect(find.text(_title), findsOneWidget);
      final prefs = await SharedPreferences.getInstance();
      final seen = prefs.getString('noor.seen.v1')!;

      // Reopened the same day, and on the second day of Eid.
      for (final day in [_on('eid'), _on('after', date: '2027-03-11')]) {
        await tester.pumpWidget(const SizedBox());
        await _pump(tester, programs: day, prefs: {'noor.seen.v1': seen});
        expect(find.text(_title), findsNothing);
      }

      // Next year's Eid.
      await tester.pumpWidget(const SizedBox());
      await _pump(
        tester,
        programs: _on('eid', hijriYear: 1449),
        prefs: {'noor.seen.v1': seen},
      );
      expect(find.text(_title), findsOneWidget);
    });

    testWidgets('a family that first opens on the second day still gets it', (
      tester,
    ) async {
      await _pump(tester, programs: _on('after', date: '2027-03-11'));
      expect(find.text(_title), findsOneWidget);
    });

    testWidgets('not in the month, and not once the days of Eid are over', (
      tester,
    ) async {
      for (final j in [
        _on('ramadan'),
        _on('upcoming'),
        _on('after', date: '2027-03-13'),
      ]) {
        await tester.pumpWidget(const SizedBox());
        await _pump(tester, programs: j);
        expect(find.text(_title), findsNothing);
      }
    });

    testWidgets('reduce-motion: every lantern lit from the first frame, '
        'nothing moving', (tester) async {
      await _pump(tester, programs: _on('eid'), reduce: true);
      expect(find.byKey(const ValueKey('eid_moment')), findsOneWidget);
      final state = tester.state<EidMomentState>(find.byType(EidMoment));
      expect(state.lit, 1);
      expect(state.lighting, isFalse);
      final face = tester.state<NoorFaceWidgetState>(find.byType(NoorFace));
      expect(face.cycling, isFalse);
      // No fade-in of the dialog either.
      expect(tester.hasRunningAnimations, isFalse);
      await tester.pump(const Duration(milliseconds: 400));
      expect(state.lit, 1);
      expect(tester.hasRunningAnimations, isFalse);
    });

    testWidgets(
      'with motion: the lanterns light one after another, then rest',
      (tester) async {
        await _pump(tester, programs: _on('eid'));
        final state = tester.state<EidMomentState>(find.byType(EidMoment));
        expect(state.lighting, isTrue);
        expect(state.lit, lessThan(1));
        // The middle lantern lights before the ends.
        expect(
          EidLanternsPainter.litOf(2, .3),
          greaterThan(EidLanternsPainter.litOf(0, .3)),
        );
        await tester.pump(kEidLightDuration);
        await tester.pump(const Duration(milliseconds: 50));
        expect(state.lit, 1);
        expect(state.lighting, isFalse);
        for (var i = 0; i < 5; i++) {
          expect(EidLanternsPainter.litOf(i, 1), 1, reason: 'lantern $i');
          expect(EidLanternsPainter.litOf(i, 0), 0, reason: 'lantern $i');
        }
      },
    );

    testWidgets('the card link opens «رمضان عائلتنا»', (tester) async {
      await _pump(tester, programs: _on('eid'));
      await tester.tap(find.byKey(const ValueKey('eid_moment_recap')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('eid_moment')), findsNothing);
      expect(find.byType(RamadanRecapScreen), findsOneWidget);
    });

    testWidgets('no card yet: no link, only the greeting and close', (
      tester,
    ) async {
      await _pump(tester, programs: _on('eid', recap: false));
      expect(find.text(_title), findsOneWidget);
      expect(find.byKey(const ValueKey('eid_moment_recap')), findsNothing);
      expect(find.byKey(const ValueKey('eid_moment_close')), findsOneWidget);
    });

    testWidgets('dark page: the same emerald paper card', (tester) async {
      await _pump(tester, programs: _on('eid'), dark: true, reduce: true);
      expect(find.text(_title), findsOneWidget);
      final card = tester.widget<Container>(
        find
            .descendant(
              of: find.byKey(const ValueKey('eid_moment')),
              matching: find.byType(Container),
            )
            .first,
      );
      expect(
        (card.decoration! as BoxDecoration).color,
        const Color(0xFF0F6B5C),
      );
    });

    testWidgets('«وضع هادئ» and the server kill switch keep it closed', (
      tester,
    ) async {
      await _pump(
        tester,
        programs: _on('eid'),
        prefs: {'noor.quiet_mode': true},
      );
      expect(find.text(_title), findsNothing);
      await tester.pumpWidget(const SizedBox());
      await _pump(
        tester,
        programs: _on('eid'),
        config: {'noor_header_enabled': false},
      );
      expect(find.text(_title), findsNothing);
    });

    testWidgets('it waits for a running tour to end', (tester) async {
      final container = await _pump(tester, programs: _on('eid'), tour: true);
      expect(find.text(_title), findsNothing);
      container.read(tourControllerProvider.notifier).stop();
      await tester.pump();
      await tester.pump();
      expect(find.text(_title), findsOneWidget);
    });

    testWidgets('only while Today is the tab on screen', (tester) async {
      await _pump(tester, programs: _on('eid'), onScreen: false);
      expect(find.text(_title), findsNothing);
      final prefs = await SharedPreferences.getInstance();
      expect(
        CompanionStore(prefs).read().seenKeys,
        isNot(contains('eid:1448')),
      );
    });
  });
}
