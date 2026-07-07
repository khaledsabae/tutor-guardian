import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/providers/habit_providers.dart';
import 'package:almorabbi/features/routine/screens/daily_routine_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets(
      'DailyRoutineScreen shows QR share dialog for teen age group 13-15',
      (tester) async {
    final fake = _FakeTgClient(claimUrl: 'https://tg.example.com/?claim=abc123');
    final todayHabits = StreamProvider.autoDispose.family<HabitDay, int>(
      (ref, childId) async* {
        yield HabitDay(
          childId: childId,
          date: '2026-07-07',
          habits: [],
          events: [],
          points: 0,
        );
      },
    );

    final container = ProviderContainer(
      overrides: [
        tgClientProvider.overrideWithValue(fake),
        activeChildIdProvider.overrideWith((ref) => 7),
        activeChildProfileProvider.overrideWith(
          (ref) => const ActiveChildProfile(
            id: 7,
            name: 'يوسف',
            ageGroup: '13-15',
          ),
        ),
        todayHabitsProvider.overrideWithProvider(todayHabits),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: DailyRoutineScreen(),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('مشاركة الميزان عبر الويب 🔗'), findsOneWidget);

    await tester.tap(find.text('مشاركة الميزان عبر الويب 🔗'));
    await tester.pump();
    // Progress dialog visible thanks to 10ms delay in fake
    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    await tester.pumpAndSettle();

    expect(find.text('شارك الميزان مع المراهق'), findsOneWidget);
    expect(find.text('https://tg.example.com/?claim=abc123'), findsOneWidget);
    expect(find.byType(QrImageView), findsOneWidget);

    await tester.tap(find.text('نسخ الرابط'));
    await tester.pump(const Duration(milliseconds: 200));

    expect(fake.createWebClaimCalled, isTrue);
    expect(fake.childIdUsed, 7);
  });
}

class _FakeTgClient extends TgClient {
  final String claimUrl;
  bool createWebClaimCalled = false;
  int? childIdUsed;

  _FakeTgClient({required this.claimUrl});

  @override
  Future<Map<String, dynamic>> createChildWebClaim(int childId) async {
    await Future.delayed(const Duration(milliseconds: 10));
    createWebClaimCalled = true;
    childIdUsed = childId;
    return {'claim_url': claimUrl};
  }
}
