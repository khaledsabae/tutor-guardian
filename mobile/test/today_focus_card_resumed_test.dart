/// TodayFocusCard reads `NextLesson.resumed` — «أعطال اتلقت في الطريق».
///
/// The endpoint says `resumed: true` only when the starter path is entirely
/// done (and hands back its *last* lesson). The card used to offer that
/// lesson under «ابدأ هذا الدرس», telling a parent who had finished the
/// path that they were at its beginning. Pinned: resumed says the path is
/// done and points at browsing; not-resumed keeps the start card.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/home/widgets/today_focus_card.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/state/chat_notifier.dart' show tgClientProvider;

const _path = {
  'id': 'p1',
  'title': 'مسار الصلاة',
  'age_group': '7-9',
  'domain': 'worship',
  'lesson_ids': ['l1', 'l2', 'l3'],
};

class _FakeClient extends TgClient {
  _FakeClient(this.next);

  final Map<String, dynamic> next;

  @override
  Future<Map<String, dynamic>> getChildProgress(int childId,
          {String? pathId}) async =>
      {'child_id': childId, 'lessons': []};

  @override
  Future<Map<String, dynamic>> getPathsList(
      {String? ageGroup, String? domain}) async {
    return {'paths': [_path], 'count': 1};
  }

  @override
  Future<Map<String, dynamic>> getNextLesson(String ageGroup,
      {int? childId}) async {
    return next;
  }
}

Future<void> pumpCard(WidgetTester tester, Map<String, dynamic> next,
    List<String> started) async {
  SharedPreferences.setMockInitialValues({});
  final prefs = await SharedPreferences.getInstance();
  final container = ProviderContainer(overrides: [
    tgClientProvider.overrideWithValue(_FakeClient(next)),
    sharedPreferencesProvider.overrideWith((_) async => prefs),
  ]);
  addTearDown(container.dispose);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: const Locale('ar'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: TodayFocusCard(
            bundle: null,
            ageGroup: '7-9',
            onStartFirstPath: () => started.add('browse'),
          ),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(seconds: 1));
}

void main() {
  testWidgets('a finished starter path is said to be finished, and browses',
      (tester) async {
    final started = <String>[];
    await pumpCard(
      tester,
      {
        'lesson_id': 'l3',
        'path_id': 'p1',
        'path_title': 'مسار الصلاة',
        'title': 'أسماء الصلاة',
        'order': 3,
        'resumed': true,
      },
      started,
    );

    expect(find.text('ما شاء الله، أتممتَ هذا المسار'), findsOneWidget);
    // Not the lesson the endpoint echoed back — that one is already done.
    expect(find.text('ابدأ هذا الدرس'), findsNothing);
    final browse = find.text('استعرض المسارات');
    expect(browse, findsOneWidget);
    await tester.tap(browse);
    expect(started, ['browse']);
  });

  testWidgets('a truly first lesson keeps the start card', (tester) async {
    final started = <String>[];
    await pumpCard(
      tester,
      {
        'lesson_id': 'l1',
        'path_id': 'p1',
        'path_title': 'مسار الصلاة',
        'title': 'أسماء الصلاة',
        'order': 1,
        'resumed': false,
      },
      started,
    );

    expect(find.text('ابدأ هذا الدرس'), findsOneWidget);
    expect(find.text('ما شاء الله، أتممتَ هذا المسار'), findsNothing);
  });
}
