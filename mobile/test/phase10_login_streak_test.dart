// Phase 10 widget test — HomeScreen "days in a row" streak uses the
// new backend field `daily_login_streak`, not the lesson streak.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/screens/home_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/widgets/ui/stat_chip.dart';

void main() {
  testWidgets('HomeScreen stats row shows daily_login_streak from backend',
      (tester) async {
    final fake = _FakeTgClient();
    fake.childProgressJson = {
      'child_id': 1,
      'lessons': [],
      'streak_days': 2, // lesson streak
      'daily_login_streak': 5, // login streak
      'last_completed_at': null,
    };

    SharedPreferences.setMockInitialValues({
      OnboardingStorage.keyActiveChildId: 1,
      OnboardingStorage.keyActiveChildName: 'سارة',
      OnboardingStorage.keyActiveChildAgeGroup: '4-6',
      OnboardingStorage.keyOnboardingCompleted: true,
    });
    final prefs = await SharedPreferences.getInstance();

    final container = ProviderContainer(
      overrides: [
        tgClientProvider.overrideWithValue(fake),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ],
    );
    addTearDown(container.dispose);
    await container.read(sharedPreferencesProvider.future);
    container.read(activeChildIdProvider.notifier).state = 1;

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: HomeScreen(onGoToTab: (_) {}),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    // The "أيام متتالية" chip must reflect dailyLoginStreak (5), not streakDays (2).
    expect(find.text('أيام متتالية'), findsOneWidget);
    expect(
      find.descendant(
        of: find.ancestor(of: find.text('أيام متتالية'), matching: find.byType(StatChip)),
        matching: find.text('5'),
      ),
      findsOneWidget,
    );
  });
}

class _FakeTgClient extends TgClient {
  Map<String, dynamic>? childProgressJson;

  @override
  Future<Map<String, dynamic>> getChildProgress(
    int childId, {
    String? pathId,
  }) async =>
      childProgressJson ?? {'child_id': childId, 'lessons': []};
}
