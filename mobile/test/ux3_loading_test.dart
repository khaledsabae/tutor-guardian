// E3/E4: skeleton loading with a slow-network hint at 8 s and Retry at 20 s.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/widgets/ui/loading_view.dart';
import 'package:almorabbi/widgets/ui/skeleton.dart';

Widget _host(Widget home) => MaterialApp(
      locale: const Locale('en'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: home,
    );

void main() {
  testWidgets('skeleton first; slow line at 8 s; Retry at 20 s', (t) async {
    var retried = 0;
    await t.pumpWidget(_host(Scaffold(
      body: LoadingView(onRetry: () => retried++),
    )));
    expect(find.byType(SkeletonList), findsOneWidget);
    expect(find.textContaining('connection is slow'), findsNothing);

    await t.pump(SlowNetworkHint.slowAfter);
    expect(find.textContaining('connection is slow'), findsOneWidget);
    expect(find.text('Try again'), findsNothing);

    await t.pump(SlowNetworkHint.retryAfter - SlowNetworkHint.slowAfter);
    await t.tap(find.text('Try again'));
    expect(retried, 1);
  });

  testWidgets('Back is offered only where the route can be left', (t) async {
    await t.pumpWidget(_host(const Scaffold(body: LoadingView.spinner())));
    await t.pump(SlowNetworkHint.slowAfter);
    expect(find.text('Go back'), findsNothing);

    final nav = t.state<NavigatorState>(find.byType(Navigator));
    nav.push(MaterialPageRoute<void>(
        builder: (_) => const Scaffold(body: LoadingView.spinner())));
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    await t.pump(SlowNetworkHint.slowAfter);
    await t.tap(find.text('Go back').last);
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    expect(nav.canPop(), isFalse);
  });

  testWidgets('no retry without a callback', (t) async {
    await t.pumpWidget(_host(const Scaffold(body: LoadingView())));
    await t.pump(SlowNetworkHint.retryAfter);
    expect(find.text('Try again'), findsNothing);
  });
}
