// The community line is reassurance, so silence is the only acceptable failure.
//
// It reads a network count. If that call is slow, fails, or the community is
// still small, Home must show nothing at all — never a spinner, an error, or
// "٤ أب وأمّ يربّون معنا", which tells a parent they arrived somewhere empty.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/home/widgets/home_community_note.dart';
import 'package:almorabbi/features/referral/community_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

/// The line fades in after a delay, and flutter_animate's delay is a Timer that
/// pumpAndSettle leaves pending. Pump past delay + duration instead.
Future<void> _settle(WidgetTester t) async {
  await t.pump();
  await t.pump(const Duration(seconds: 2));
}

Widget _host(AsyncValue<int?> stats) => ProviderScope(
      overrides: [
        communityFamiliesProvider.overrideWith((ref) async => stats.valueOrNull),
      ],
      child: MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const Scaffold(body: HomeCommunityNote()),
      ),
    );

void main() {
  testWidgets('shows the count once the community is big enough', (t) async {
    await t.pumpWidget(_host(const AsyncValue.data(3102)));
    await _settle(t);
    expect(find.textContaining('3102'), findsOneWidget);
    expect(find.textContaining('لست وحدك'), findsOneWidget);
  });

  testWidgets('shows nothing at all while the count is unknown', (t) async {
    await t.pumpWidget(_host(const AsyncValue.data(null)));
    await _settle(t);
    expect(find.byType(Text), findsNothing);
    expect(find.byType(Icon), findsNothing);
  });

  testWidgets('renders no box or divider — type only', (t) async {
    await t.pumpWidget(_host(const AsyncValue.data(3102)));
    await _settle(t);
    // A filled, bordered block on Home is what got this removed last time.
    expect(find.byType(Card), findsNothing);
    expect(find.byType(Divider), findsNothing);
    final boxes = t
        .widgetList<Container>(find.byType(Container))
        .where((c) => c.decoration != null);
    expect(boxes, isEmpty);
  });

  test('the threshold is stated, not implied', () {
    // Referenced by the provider; a change here is a product decision.
    expect(kMinFamiliesForProof, 10);
  });
}
