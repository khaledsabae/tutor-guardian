// E2: one app-wide line for offline and for "showing a saved copy".

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/curriculum_cache.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/connectivity_provider.dart';
import 'package:almorabbi/widgets/app_status_banner.dart';

Future<void> _pump(WidgetTester t, {required bool online}) async {
  await t.pumpWidget(ProviderScope(
    overrides: [
      connectivityProvider.overrideWith((ref) => Stream.value(online)),
    ],
    child: MaterialApp(
      locale: const Locale('en'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) => AppStatusBanner(child: child!),
      home: const Scaffold(body: Text('page')),
    ),
  ));
  await t.pump();
}

void main() {
  tearDown(() => CurriculumCache.servedStaleAt.value = null);

  testWidgets('online with live data: no banner', (t) async {
    await _pump(t, online: true);
    expect(find.text('page'), findsOneWidget);
    expect(find.byIcon(Icons.wifi_off), findsNothing);
    expect(find.byIcon(Icons.history), findsNothing);
  });

  testWidgets('offline: one banner above every route', (t) async {
    await _pump(t, online: false);
    expect(find.textContaining("You're offline"), findsOneWidget);
    expect(find.text('page'), findsOneWidget);
  });

  testWidgets('offline with a saved copy says so, with its time', (t) async {
    CurriculumCache.servedStaleAt.value = DateTime.now();
    await _pump(t, online: false);
    expect(find.textContaining('Offline — showing a saved copy'), findsOneWidget);
  });

  testWidgets('online but the server failed: the saved copy is named',
      (t) async {
    await _pump(t, online: true);
    CurriculumCache.servedStaleAt.value = DateTime.now();
    await t.pump();
    expect(find.textContaining("Couldn't refresh"), findsOneWidget);
    CurriculumCache.servedStaleAt.value = null;
    await t.pump();
    expect(find.textContaining("Couldn't refresh"), findsNothing);
  });
}
