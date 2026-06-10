// Phase 1+3 smoke test — verifies the app boots into the chat screen with
// the Arabic title, and the chat notifier (Riverpod) builds without error
// when a mock client is injected.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/screens/chat_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';

void main() {
  testWidgets('App boots, chat screen shows Arabic title',
      (WidgetTester tester) async {
    // Provide a fake TgClient so bootstrap() doesn't try real network.
    final fake = _NullClient();

    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final storage = OnboardingStorage(prefs);
    await storage.markOnboardingCompleted();

    final container = ProviderContainer(
      overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ],
    );
    await container.read(sharedPreferencesProvider.future);
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: ChatScreen()),
      ),
    );
    // Allow bootstrap to run; the fake client throws TgApiError which the
    // notifier catches and surfaces in the errorBanner (not a crash).
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('🛡️  المربي الذكي'), findsOneWidget);
  });
}

/// Stub that throws TgApiError on every call. Sufficient for "app boots without crashing"
/// — the chat notifier catches the TgApiError and shows a banner.
class _NullClient extends TgClient {
  _NullClient() : super.forTesting(baseUrl: 'http://test');

  @override
  Future<SessionResponse> createSession({Map<String, dynamic>? metadata}) async =>
      throw const TgApiError(500, 'fake-error');

  Future<void> deleteSession(String sessionId) async =>
      throw const TgApiError(500, 'fake-error');

  @override
  Future<String?> currentSessionId() async => throw const TgApiError(500, 'fake-error');

  @override
  Future<SessionHistory> getHistory(String sessionId) async =>
      throw const TgApiError(500, 'fake-error');

  @override
  Stream<TgStreamEvent> streamQuery(AssistantQuery q) async* {
    throw const TgApiError(500, 'fake-error');
    // never reached
  }
}
