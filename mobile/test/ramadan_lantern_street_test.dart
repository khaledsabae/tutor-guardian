// «شارع القناديل» — phase 5 of «نور والقناديل»: the month as thirty paper
// lanterns. A lantern is lit when the family marked anything that day; every
// other day is the same quiet paper, before today or after it (no missed
// state); today's hangs a little larger; the day keys and their screen-reader
// labels survive the chips they replaced. The day's marks are lantern toggles,
// and a day with every mark ticked glows a quiet «الحمد لله» — no confetti.

import 'dart:ui' show Tristate;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/programs/data/programs_models.dart';
import 'package:almorabbi/features/programs/screens/ramadan_day_screen.dart';
import 'package:almorabbi/features/programs/screens/ramadan_screen.dart';
import 'package:almorabbi/features/programs/widgets/ramadan_widgets.dart';
import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/widgets/ui/paper_lantern.dart';

import 'programs_support.dart';

const _tall = Size(400, 3200);

Finder _day(int d) => find.byKey(ValueKey('ramadan_day_$d'));
Finder _lanternOf(int d) =>
    find.descendant(of: _day(d), matching: find.byType(PaperLantern));
PaperLantern _lantern(WidgetTester t, int d) =>
    t.widget<PaperLantern>(_lanternOf(d));
PaperLanternPainter _painter(WidgetTester t, int d) =>
    t
            .widget<CustomPaint>(
              find.descendant(
                of: _lanternOf(d),
                matching: find.byType(CustomPaint),
              ),
            )
            .painter!
        as PaperLanternPainter;
TextStyle _number(WidgetTester t, int d) => t
    .widget<Text>(find.descendant(of: _day(d), matching: find.text('$d')))
    .style!;

final _missWords = RegExp(
  r'miss|fail|behind|late|فات|فائت|تأخّر|فشل',
  caseSensitive: false,
);

void main() {
  group('the street', () {
    testWidgets('a lantern lights for any mark; the rest stay paper; today is larger', (tester) async {
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(day: 5, daysMarked: [1, 3]);
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client, phone: _tall);
      await settle(tester);
      await scrollTo(tester, _day(30));
      for (var d = 1; d <= 30; d++) {
        expect(_day(d), findsOneWidget, reason: 'day $d keeps ramadan_day_$d');
      }
      expect(_day(31), findsNothing);
      expect(find.byType(ActionChip), findsNothing);
      expect(_lantern(tester, 1).lit, isTrue);
      expect(_lantern(tester, 3).lit, isTrue);
      for (final d in [2, 4, 5, 6, 30]) {
        expect(_lantern(tester, d).lit, isFalse, reason: 'day $d');
      }
      // Today hangs a little larger; every other day, lit or not, is one size.
      final today = tester.getSize(_lanternOf(5));
      final other = tester.getSize(_lanternOf(4));
      expect(today.height, greaterThan(other.height));
      expect(today.height, lessThan(other.height * 1.5));
      expect(tester.getSize(_lanternOf(1)), other);
      expect(_number(tester, 5).color, AppPalette.light.primary);
    });

    testWidgets('a past unmarked day looks exactly like a day still to come — nothing greyed, crossed or called missed', (tester) async {
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(day: 12, content: dayContentJson(day: 12), daysMarked: [1]);
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client, phone: _tall);
      await settle(tester);
      await scrollTo(tester, _day(30));
      const past = 4, future = 20;
      for (final d in [past, future]) {
        expect(_lantern(tester, d).lit, isFalse);
        final p = _painter(tester, d);
        expect(p.glow, 0, reason: 'day $d has no flame and no halo');
        expect(p.paper, AppPalette.light.paperIvory, reason: 'day $d is plain ivory paper');
        expect(p.frame, AppPalette.light.paperEmerald);
      }
      expect(tester.getSize(_lanternOf(past)), tester.getSize(_lanternOf(future)));
      final a = _number(tester, past), b = _number(tester, future);
      expect(a.color, b.color);
      expect(a.color, AppPalette.light.ink, reason: 'the number is ink, not a faded grey');
      expect(a.fontWeight, b.fontWeight);
      expect(a.decoration, isNull, reason: 'never struck through');
      final street = find.byType(RamadanLanternStreet);
      expect(find.descendant(of: street, matching: find.byType(Opacity)), findsNothing);
      expect(find.descendant(of: street, matching: find.byType(ColorFiltered)), findsNothing);
      expect(find.descendant(of: street, matching: find.byType(Icon)), findsNothing);
      for (final t in tester.widgetList<Text>(find.descendant(of: street, matching: find.byType(Text)))) {
        final text = t.data ?? '';
        expect(_missWords.hasMatch(text), isFalse, reason: 'shame wording: "$text"');
        expect(RegExp(r'\d+\s*(/|of|من)\s*\d+').hasMatch(text), isFalse, reason: 'a count: "$text"');
      }
    });

    testWidgets('each day is a button that says which day; a lit one says so, an unlit one says nothing more', (tester) async {
      final handle = tester.ensureSemantics();
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(day: 5, daysMarked: [1]);
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client, phone: _tall);
      await settle(tester);
      await scrollTo(tester, _day(30));
      final lit = tester.getSemantics(_day(1)).getSemanticsData();
      expect(lit.label, 'Day 1');
      expect(lit.value, 'lantern lit');
      expect(lit.flagsCollection.isButton, isTrue);
      final plain = tester.getSemantics(_day(2)).getSemanticsData();
      expect(plain.label, 'Day 2');
      expect(plain.value, isEmpty);
      expect(tester.getSemantics(_day(5)).getSemanticsData().label, 'Day 5, today');
      handle.dispose();
    });

    for (final state in ['eid', 'after']) {
      testWidgets('$state: the street stays, lit by the season, with no today', (tester) async {
        final client = FakeProgramsClient()
          ..ramadanToday = ramadanTodayJson(state: state, recap: true, daysMarked: [1, 29]);
        await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client, phone: _tall);
        await settle(tester);
        await scrollTo(tester, _day(30));
        expect(_lantern(tester, 1).lit, isTrue);
        expect(_lantern(tester, 29).lit, isTrue);
        expect(_lantern(tester, 2).lit, isFalse);
        final sizes = {for (var d = 1; d <= 30; d++) tester.getSize(_lanternOf(d))};
        expect(sizes, hasLength(1), reason: 'no day is today');
      });
    }

    testWidgets('tapping a lantern opens its day', (tester) async {
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: FakeProgramsClient());
      await settle(tester);
      await scrollTo(tester, _day(7));
      await tester.tap(_day(7));
      await settle(tester);
      expect(find.byType(RamadanDayScreen), findsOneWidget);
      expect(find.text('Day 7'), findsWidgets);
    });
  });

  group('layout', () {
    testWidgets('360dp, 200% text: six lanterns a string, five strings, every day a 48dp target', (tester) async {
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId),
          client: FakeProgramsClient(), phone: const Size(360, 740), textScale: 2.0);
      await settle(tester);
      await scrollTo(tester, _day(30));
      expect(tester.takeException(), isNull);
      final rows = <int, List<int>>{};
      for (var d = 1; d <= 30; d++) {
        rows.putIfAbsent(tester.getTopLeft(_day(d)).dy.round(), () => []).add(d);
        final size = tester.getSize(_day(d));
        expect(size.width, greaterThanOrEqualTo(48), reason: 'day $d width');
        expect(size.height, greaterThanOrEqualTo(48), reason: 'day $d height');
      }
      expect(rows.values.toList(), [
        for (var r = 0; r < 5; r++) [for (var d = r * 6 + 1; d <= r * 6 + 6; d++) d],
      ]);
      // Left to right in English.
      expect(tester.getCenter(_day(1)).dx, lessThan(tester.getCenter(_day(2)).dx));
    });

    testWidgets('320dp Arabic, 200% text: five a string, right to left, a 29-day month ends short', (tester) async {
      final client = FakeProgramsClient()
        ..ramadanToday = {...ramadanTodayJson(), 'season': seasonJson(days: 29)};
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId),
          client: client, locale: const Locale('ar'), phone: const Size(320, 640), textScale: 2.0);
      await settle(tester);
      await scrollTo(tester, _day(29));
      expect(tester.takeException(), isNull);
      expect(_day(30), findsNothing);
      final rows = <int>{for (var d = 1; d <= 29; d++) tester.getTopLeft(_day(d)).dy.round()};
      expect(rows, hasLength(6));
      expect(tester.getCenter(_day(1)).dx, greaterThan(tester.getCenter(_day(2)).dx));
      expect(tester.getTopLeft(_day(5)).dy, tester.getTopLeft(_day(1)).dy);
      expect(tester.getTopLeft(_day(6)).dy, greaterThan(tester.getTopLeft(_day(5)).dy));
    });

    test('columns: ten on a wide screen, six on a phone, five on a small one', () {
      expect(RamadanLanternStreet.columnsFor(600), 10);
      expect(RamadanLanternStreet.columnsFor(296), 6);
      expect(RamadanLanternStreet.columnsFor(256), 5);
      expect(RamadanLanternStreet.columnsFor(200), 4);
    });
  });

  group('the day\'s marks are lanterns', () {
    testWidgets('a tick lights today on the street at once, with a selection click; unticking puts it out', (tester) async {
      final haptics = <Object?>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
        if (call.method == 'HapticFeedback.vibrate') haptics.add(call.arguments);
        return null;
      });
      addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
      final client = FakeProgramsClient();
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client, phone: _tall);
      await settle(tester);
      await scrollTo(tester, _day(30));
      expect(_lantern(tester, 3).lit, isFalse);
      final wird = find.byKey(const ValueKey('ramadan_mark_wird_done'));
      expect(tester.widget<RamadanLanternToggle>(wird).lit, isFalse);
      await tester.tap(wird);
      await tester.pump();
      expect(_lantern(tester, 3).lit, isTrue, reason: 'lit on the tap, not after the refetch');
      expect(haptics, contains('HapticFeedbackType.selectionClick'));
      await settle(tester);
      expect(client.bodies.last, {'mark': 'wird_done', 'day': 3, 'done': true, 'choice_index': null});
      expect(_lantern(tester, 3).lit, isTrue);
      expect(tester.widget<RamadanLanternToggle>(wird).lit, isTrue);
      await tester.tap(wird);
      await settle(tester);
      expect(tester.widget<RamadanLanternToggle>(wird).lit, isFalse);
      expect(_lantern(tester, 3).lit, isFalse);
      expect(_lantern(tester, 2).lit, isTrue, reason: "another day's lantern is untouched");
    });

    testWidgets('a toggle is a button with a toggled state, named after its mark', (tester) async {
      final handle = tester.ensureSemantics();
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(
          marks: {'challenge_done': true, 'wird_done': false, 'story_heard': false, 'juz_read': false},
        );
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client, phone: _tall);
      await settle(tester);
      final on = tester.getSemantics(find.byKey(const ValueKey('ramadan_mark_challenge_done'))).getSemanticsData();
      expect(on.label, 'The challenge');
      expect(on.flagsCollection.isButton, isTrue);
      expect(on.flagsCollection.isToggled, Tristate.isTrue);
      final off = tester.getSemantics(find.byKey(const ValueKey('ramadan_mark_wird_done'))).getSemanticsData();
      expect(off.flagsCollection.isToggled, Tristate.isFalse);
      handle.dispose();
    });

    testWidgets('every mark of the day ticked → a quiet «الحمد لله» glow, no confetti', (tester) async {
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(
          marks: {'challenge_done': true, 'wird_done': true, 'story_heard': true, 'juz_read': false},
        );
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client, phone: _tall);
      await settle(tester);
      const glow = ValueKey('ramadan_day_complete');
      expect(find.byKey(glow), findsNothing);
      final juz = find.byKey(const ValueKey('ramadan_mark_juz_read'));
      await tester.tap(juz);
      await tester.pump(const Duration(seconds: 1));
      expect(find.byKey(glow), findsOneWidget);
      expect(find.text('Alhamdulillah'), findsOneWidget);
      expect(
        find.byWidgetPredicate((w) => w.runtimeType.toString().toLowerCase().contains('confetti')),
        findsNothing,
      );
      expect(tester.takeException(), isNull);
      await tester.tap(juz);
      // The answer, the refetch, then the fade out (600ms) and the frame that
      // drops the faded line.
      for (var i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(find.byKey(glow), findsNothing);
      expect(tester.widget<RamadanLanternToggle>(juz).lit, isFalse);
    });

    testWidgets('the family word counts on day 28: no glow until it is chosen', (tester) async {
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(
          day: 28,
          content: dayContentJson(day: 28, tracks: ['challenge_done', 'family_word'], word: true),
          marks: {'challenge_done': true, 'family_word': null},
        );
      await pumpPrograms(tester, const RamadanScreen(childId: kChildId), client: client, phone: _tall);
      await settle(tester);
      const glow = ValueKey('ramadan_day_complete');
      expect(find.byKey(glow), findsNothing);
      await tester.tap(find.text('Joy'));
      await tester.pump(const Duration(seconds: 1));
      expect(find.byKey(glow), findsOneWidget);
    });

    testWidgets('under reduced motion the lantern lights and the glow shows without animating', (tester) async {
      final client = FakeProgramsClient()
        ..ramadanToday = ramadanTodayJson(
          marks: {'challenge_done': true, 'wird_done': true, 'story_heard': true, 'juz_read': false},
        );
      await pumpPrograms(
        tester,
        Builder(
          builder: (context) => MediaQuery(
            data: MediaQuery.of(context).copyWith(disableAnimations: true),
            child: const RamadanScreen(childId: kChildId),
          ),
        ),
        client: client,
        phone: _tall,
      );
      await settle(tester);
      await tester.tap(find.byKey(const ValueKey('ramadan_mark_juz_read')));
      await tester.pump();
      final toggle = find.descendant(
        of: find.byKey(const ValueKey('ramadan_mark_juz_read')),
        matching: find.byType(CustomPaint),
      );
      final painter = tester.widgetList<CustomPaint>(toggle).map((c) => c.painter).whereType<PaperLanternPainter>().single;
      expect(painter.glow, 1, reason: 'no tween under reduced motion');
      expect(find.byKey(const ValueKey('ramadan_day_complete')), findsOneWidget);
      expect(_painter(tester, 3).glow, 1);
    });
  });

  group('the model', () {
    test('days_marked is a set of days; missing or junk is just empty', () {
      final t = RamadanToday.fromJson({...ramadanTodayJson(), 'days_marked': [1, '3', null, 'x', 3]});
      expect(t.daysMarked, {1, 3});
      final old = Map<String, dynamic>.of(ramadanTodayJson())..remove('days_marked');
      expect(RamadanToday.fromJson(old).daysMarked, isEmpty);
      expect(RamadanToday.fromJson({...ramadanTodayJson(), 'days_marked': 'no'}).daysMarked, isEmpty);
    });

    test('anyDone: a tick or a chosen word', () {
      expect(const RamadanMarks().anyDone, isFalse);
      expect(const RamadanMarks(ticks: {'wird_done': false}).anyDone, isFalse);
      expect(const RamadanMarks(ticks: {'wird_done': true}).anyDone, isTrue);
      expect(const RamadanMarks(familyWordIndex: 2).anyDone, isTrue);
    });
  });
}
