// «نور يتذكّر» — Noor's line on «اليوم»: what it shows, what its chips do,
// and that it gives way to the plain greeting when it has nothing to say.
import 'dart:io';

import 'package:almorabbi/features/companion/data/companion_store.dart';
import 'package:almorabbi/features/companion/logic/companion_brain.dart';
import 'package:almorabbi/features/companion/providers/companion_providers.dart';
import 'package:almorabbi/features/companion/widgets/noor_today_header.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/widgets/next_step_sheet.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _fallback = Text('FALLBACK');

Future<ProviderContainer> _pump(
  WidgetTester tester,
  CompanionLine? line,
) async {
  SharedPreferences.setMockInitialValues({});
  final prefs = await SharedPreferences.getInstance();
  final container = ProviderContainer(
    overrides: [
      sharedPreferencesProvider.overrideWith((_) async => prefs),
      companionLineProvider.overrideWith((_) => line),
    ],
  );
  addTearDown(container.dispose);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: child!,
        ),
        home: const Scaffold(body: NoorTodayHeader(fallback: _fallback)),
      ),
    ),
  );
  await tester.pump();
  return container;
}

final _promise = Promise(
  id: 1,
  childId: 7,
  step: 'امدح صدقه أولًا',
  slot: PromiseSlot.tonight,
  madeOn: DateTime(2026, 10, 13),
);

void main() {
  testWidgets('no line → the plain greeting row, untouched', (tester) async {
    await _pump(tester, null);
    expect(find.text('FALLBACK'), findsOneWidget);
  });

  testWidgets('a due promise is asked with the step, the name and 3 chips', (
    tester,
  ) async {
    await _pump(
      tester,
      CompanionLine(
        key: 'promise:1',
        kind: CompanionKind.promiseDue,
        mood: CompanionMood.awake,
        name: 'سارة',
        step: _promise.step,
        promise: _promise,
        actions: const [
          CompanionAction.outcomeWorked,
          CompanionAction.outcomeDidntWork,
          CompanionAction.outcomeDidntTry,
        ],
      ),
    );
    expect(find.textContaining('امدح صدقه أولًا'), findsOneWidget);
    expect(find.textContaining('سارة'), findsOneWidget);
    for (final chip in ['نجحت', 'لم تنجح', 'لم أجرّب بعد']) {
      expect(find.text(chip), findsOneWidget);
    }
    expect(find.byTooltip('إخفاء لليوم'), findsOneWidget);
    expect(find.text('FALLBACK'), findsNothing);
  });

  testWidgets('answering a device-only promise thanks the parent in place', (
    tester,
  ) async {
    final c = await _pump(
      tester,
      CompanionLine(
        key: 'promise:1',
        kind: CompanionKind.promiseDue,
        mood: CompanionMood.awake,
        name: 'سارة',
        step: _promise.step,
        promise: _promise,
        actions: const [CompanionAction.outcomeWorked],
      ),
    );
    await c.read(companionMemoryProvider.future);
    await tester.tap(find.text('نجحت'));
    await tester.pump();
    await tester.pump();
    expect(find.textContaining('الحمد لله، نفعت'), findsOneWidget);
  });

  testWidgets('a greeting has no close button and no chips', (tester) async {
    await _pump(
      tester,
      const CompanionLine(
        key: 'greeting:morning:1',
        kind: CompanionKind.greeting,
        mood: CompanionMood.calm,
        name: 'سارة',
      ),
    );
    expect(find.byTooltip('إخفاء لليوم'), findsNothing);
    expect(find.text('نجحت'), findsNothing);
  });

  testWidgets('«هلّ هلال رمضان»: the line, the name, one Ramadan chip', (
    tester,
  ) async {
    final container = await _pump(
      tester,
      const CompanionLine(
        key: 'ramadan-start:1448',
        kind: CompanionKind.ramadanStart,
        mood: CompanionMood.happy,
        name: 'سارة',
        actions: [CompanionAction.openRamadan],
        onceOnly: true,
      ),
    );
    expect(
      find.text(
        'هلّ هلال رمضان، مبارك عليكم الشهر! في كل يوم منه قنديل تضيئونه مع سارة.',
      ),
      findsOneWidget,
    );
    expect(find.text('برنامج رمضان'), findsOneWidget);
    expect(find.byTooltip('إخفاء لليوم'), findsOneWidget);
    // Once-only: held for this open, recorded for every open after it.
    await tester.pump();
    expect(
      container.read(heldOnceLinesProvider),
      contains('ramadan-start:1448'),
    );
    final prefs = await SharedPreferences.getInstance();
    expect(
      CompanionStore(prefs).read().seenKeys,
      contains('ramadan-start:1448'),
    );
  });

  testWidgets('the next-step sheet returns the slot the parent picked', (
    tester,
  ) async {
    PromiseSlot? picked;
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Builder(
          builder: (context) => TextButton(
            onPressed: () async => picked = await showNextStepSheet(
              context,
              tryThis: 'امدح صدقه',
              childName: 'سارة',
            ),
            child: const Text('open'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(find.text('متى ستجرّبها مع سارة؟'), findsOneWidget);
    await tester.tap(find.text('غدًا'));
    await tester.pumpAndSettle();
    expect(picked, PromiseSlot.tomorrow);
  });

  testWidgets('the slot labels are never cut — English, 360dp, 200% text', (
    tester,
  ) async {
    // The real font: the test font draws every glyph as a full square and
    // would cut labels no phone cuts.
    final cairo = FontLoader('Cairo');
    for (final w in ['Regular', 'Bold', 'ExtraBold']) {
      final f = File('assets/google_fonts/Cairo-$w.ttf');
      if (f.existsSync()) {
        cairo.addFont(Future.value(ByteData.sublistView(f.readAsBytesSync())));
      }
    }
    await cairo.load();
    tester.view.physicalSize = const Size(360, 800) * 3.0;
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(fontFamily: 'Cairo'),
        locale: const Locale('en'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: const TextScaler.linear(2.0)),
          child: child!,
        ),
        home: Builder(
          builder: (context) => TextButton(
            onPressed: () => showNextStepSheet(
              context,
              tryThis: 'Praise the truth first',
              childName: 'Sara',
            ),
            child: const Text('open'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    for (final label in ['Tonight', 'Tomorrow', 'This week']) {
      final f = find.text(label);
      expect(f, findsOneWidget, reason: label);
      final p = tester.renderObject<RenderParagraph>(
        find.descendant(of: f, matching: find.byType(RichText)).first,
      );
      expect(p.didExceedMaxLines, isFalse, reason: '$label is cut');
    }
    expect(tester.takeException(), isNull);
  });
}
