// Phase 1+3 smoke test — verifies the app boots into the chat screen with
// the Arabic title, and the chat notifier (Riverpod) builds without error
// when a mock client is injected.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/screens/chat_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';

void main() {
  testWidgets('App boots, chat screen shows Arabic title',
      (WidgetTester tester) async {
    // Provide a fake TgClient so bootstrap() doesn't try real network.
    final fake = _NullClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          tgClientProvider.overrideWithValue(fake),
        ],
        child: const MaterialApp(home: ChatScreen()),
      ),
    );
    // Allow bootstrap to run; the fake client throws TgApiError which the
    // notifier catches and surfaces in the errorBanner (not a crash).
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('🛡️  المربي الذكي'), findsOneWidget);
  });
}

/// Stub that fails every call. Sufficient for "app boots without crashing"
/// — the chat notifier catches the TgApiError and shows a banner.
class _NullClient extends TgClient {
  _NullClient() : super();
}
