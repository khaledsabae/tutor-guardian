/// Today's first-lesson card and «Continue your path» card follow the app
/// language after it is switched — store captures of 1.0.73.
///
/// The English store shots were taken the way a parent switches: the app
/// opens (Arabic), Settings → English, back to Today. Both cards kept their
/// Arabic titles — «الصدق: كيف تربّي طفلًا لا يكذب», «تزكية الأخلاق: …» —
/// while the lesson they opened read English. The titles are server-localised
/// (`?lang=`), and the providers behind the cards did not depend on the
/// language, so the Arabic answers stayed cached across the switch.
///
/// The fake server answers in whatever language the request carries, exactly
/// as the real one does, so these tests pin the refetch, not a client-side
/// title pick.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/home/widgets/today_focus_card.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/parent_day/child_day_card.dart';
import 'package:almorabbi/features/program/data/progress_models.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart'
    show activeChildIdProvider;
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart' show tgClientProvider;

const _pathAr = 'تزكية الأخلاق: الصدق والمسؤولية (7-9 سنوات)';
const _pathEn =
    'Tazkiyah of Akhlaq: Truthfulness and Responsibility (7-9 Years)';
const _lessonAr = 'الصدق: كيف تربّي طفلًا لا يكذب';
const _lessonEn = 'Truthfulness: How to Raise a Child Who Does Not Lie';

bool get _en => TgClient.uiLanguage == 'en';

class _FakeServer extends TgClient {
  @override
  Future<Map<String, dynamic>> getPathsList({
    String? ageGroup,
    String? domain,
  }) async => {
    'count': 1,
    'paths': [
      {
        'id': 'p1',
        'title': _en ? _pathEn : _pathAr,
        'age_group': '7-9',
        'domain': 'islamic_parenting',
        'lesson_ids': ['l1', 'l2', 'l3', 'l4'],
      },
    ],
  };

  @override
  Future<Map<String, dynamic>> getNextLesson(
    String ageGroup, {
    int? childId,
  }) async => {
    'lesson_id': 'l1',
    'path_id': 'p1',
    'path_title': _en ? _pathEn : _pathAr,
    'title': _en ? _lessonEn : _lessonAr,
    'order': 1,
    'resumed': false,
  };

  // The bank's English file keeps the `title_ar` key with English text —
  // the server's convention for every localised mission bank.
  @override
  Future<Map<String, dynamic>> fetchChildDay(int childId) async => {
    'screen': {'counted_seconds': 600, 'budget_seconds': 3600},
    'listening': {'counted_seconds': 0},
    'mission': {
      'status': 'assigned',
      'title_ar': _en ? 'Green Hunter' : 'صيّاد الأخضر',
    },
  };
}

/// The app as `main.dart` builds it: the locale comes from [appLocaleProvider].
Future<ProviderContainer> _pumpToday(
  WidgetTester tester,
  ChildProgressBundle? bundle, {
  Widget? body,
}) async {
  SharedPreferences.setMockInitialValues({'tg.ui_language': 'ar'});
  final prefs = await SharedPreferences.getInstance();
  final container = ProviderContainer(
    overrides: [
      tgClientProvider.overrideWithValue(_FakeServer()),
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ],
  );
  addTearDown(container.dispose);
  // Resolve the stored choice before the first frame, as the app does.
  await container.read(sharedPreferencesProvider.future);
  container.read(appLocaleProvider);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: Consumer(
        builder: (context, ref, _) => MaterialApp(
          locale: ref.watch(appLocaleProvider),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(
            body:
                body ??
                TodayFocusCard(
                  bundle: bundle,
                  ageGroup: '7-9',
                  onStartFirstPath: () {},
                ),
          ),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(seconds: 1));
  return container;
}

Future<void> _switchToEnglish(
  WidgetTester tester,
  ProviderContainer container,
) async {
  await container.read(appLocaleProvider.notifier).setLocale('en');
  await tester.pump();
  await tester.pump(const Duration(seconds: 1));
}

void main() {
  tearDown(() => TgClient.uiLanguage = null);

  testWidgets('first-lesson card: English title after switching to English', (
    tester,
  ) async {
    final container = await _pumpToday(tester, null);
    expect(find.text(_lessonAr), findsOneWidget);
    expect(find.text('ابدأ هذا الدرس'), findsOneWidget);

    await _switchToEnglish(tester, container);

    expect(find.text('Start This Lesson'), findsOneWidget);
    expect(find.text(_lessonEn), findsOneWidget);
    expect(find.text(_lessonAr), findsNothing);
  });

  testWidgets(
    '«Continue your path» card: English path title after the switch',
    (tester) async {
      const bundle = ChildProgressBundle(
        childId: 1,
        lessons: [
          LessonProgress(
            lessonId: 'l1',
            pathId: 'p1',
            status: ProgressStatus.completed,
          ),
          LessonProgress(
            lessonId: 'l2',
            pathId: 'p1',
            status: ProgressStatus.inProgress,
          ),
        ],
      );
      final container = await _pumpToday(tester, bundle);
      expect(find.text(_pathAr), findsOneWidget);

      await _switchToEnglish(tester, container);

      expect(find.text('Continue your path'), findsOneWidget);
      expect(find.text(_pathEn), findsOneWidget);
      expect(find.text(_pathAr), findsNothing);
    },
  );

  testWidgets("child's-day card: the mission title follows the switch too", (
    tester,
  ) async {
    final container = await _pumpToday(
      tester,
      null,
      body: const ChildDayCard(),
    );
    container.read(activeChildIdProvider.notifier).state = 1;
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(find.textContaining('صيّاد الأخضر'), findsOneWidget);

    await _switchToEnglish(tester, container);

    expect(find.textContaining('Green Hunter'), findsOneWidget);
    expect(find.textContaining('صيّاد الأخضر'), findsNothing);
  });
}
