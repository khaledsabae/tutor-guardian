/// Phase 1 «التطبيق يصحو» — first-run cheap touches (NOOR_WAL_QANADIL_PLAN).
///
/// Pins the onboarding half of the phase:
///   * the welcome hero is the bundled `onboarding_welcome.webp`, not 🌍;
///   * `TwinklingStars` sit behind the start page (still under reduceMotion,
///     which the sky itself enforces);
///   * picking an age band fires a selection haptic;
///   * the sample mentor question is a real button: tapping it arms a
///     deferred ask — after onboarding completes the question is seeded into
///     `pendingChatQuestionProvider` and the shell is pointed at the
///     assistant tab;
///   * the child-creation wait shows progressive status lines (and Noor),
///     not a bare spinner;
///   * ChatScreen consumes a question that was seeded before it mounted —
///     the exact ordering onboarding produces.
library;

import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/companion/widgets/noor_presence.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/onboarding/screens/onboarding_screen.dart';
import 'package:almorabbi/features/program/providers/program_providers.dart';
import 'package:almorabbi/features/shell/root_tab.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/screens/chat_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/widgets/ui/night_sky.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  /// A TgClient whose createChild blocks on a gate, so the waiting overlay
  /// can be observed mid-flight. Built inside each test on purpose: the
  /// Completer must belong to the test's fake-async zone, or completing it
  /// never resumes the awaiting `await` within that test.
  _GatedFakeTgClient newFake() => _GatedFakeTgClient()
    ..createChildJson = {
      'id': 1,
      'name': 'طفلي',
      'age_group': '4-6',
      'gender': null,
      'avatar_emoji': null,
      'created_at': '2026-06-08T12:00:00',
      'updated_at': '2026-06-08T12:00:00',
    };

  /// The stars arm their start on random delays of up to 3 s. Pump past
  /// them inside the body — the binding flags timers pending otherwise.
  Future<void> drainStars(WidgetTester tester) =>
      tester.pump(const Duration(seconds: 4));

  Future<ProviderContainer> pumpOnboarding(
    WidgetTester tester, {
    required _GatedFakeTgClient fake,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(overrides: [
      tgClientProvider.overrideWithValue(fake),
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ]);
    addTearDown(container.dispose);
    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        locale: const Locale('ar'),
        // Ambient loops (night sky, Noor's halo) never settle; hold them
        // still so pumpAndSettle works — same behaviour as a user with the
        // system's reduce-motion setting. The loops themselves are pinned
        // in noor_presence_test.dart.
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: child!,
        ),
        home: const OnboardingScreen(),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
      ),
    ));
    await tester.pumpAndSettle();
    // The stars arm their start on random delays of up to 3 s — fire them
    // now so no timer is left pending when a test ends early.
    await drainStars(tester);
    return container;
  }

  testWidgets('the start page shows the welcome hero, not the 🌍 emoji',
      (tester) async {
    await pumpOnboarding(tester, fake: newFake());

    final image = tester.widget<Image>(find.byType(Image).first);
    expect(
      (image.image as AssetImage).assetName,
      'assets/images/generated/onboarding_welcome.webp',
      reason: 'the bundled hero exists and must replace the emoji',
    );
    expect(find.text('🌍'), findsNothing);
    await drainStars(tester);
  });

  testWidgets('stars twinkle behind the start page', (tester) async {
    await pumpOnboarding(tester, fake: newFake());
    expect(
      find.descendant(
        of: find.byType(OnboardingScreen),
        matching: find.byType(TwinklingStars),
      ),
      findsOneWidget,
    );
    await drainStars(tester);
  });

  testWidgets('picking an age band fires a selection haptic',
      (tester) async {
    final platformCalls = <Object?>[];
    // SystemChannels.platform speaks JSONMethodCodec — a plain MethodChannel
    // mock would decode its messages as "corrupted".
    const platform = MethodChannel('flutter/platform', JSONMethodCodec());
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(platform, (call) async {
      platformCalls.add(call.arguments ?? call.method);
      return null;
    });
    addTearDown(() {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(platform, null);
    });

    await pumpOnboarding(tester, fake: newFake());
    await tester.tap(find.text('العربية'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('4–6 سنوات'));
    await tester.pumpAndSettle();

    expect(
      platformCalls,
      contains('HapticFeedbackType.selectionClick'),
      reason: 'Haptics.selection must fire on the age choice',
    );
    await drainStars(tester);
  });

  testWidgets('tapping the sample question arms a deferred ask',
      (tester) async {
    final fake = newFake();
    final container = await pumpOnboarding(tester, fake: fake);
    await tester.tap(find.text('العربية'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('4–6 سنوات'));
    await tester.pumpAndSettle();

    // The sample question is now a button — tapping it shows the armed hint.
    // It sits below the fold on the 800x600 test surface; bring it in first.
    final questionFinder =
        find.textContaining('ابني في الخامسة يرفض الصلاة');
    await tester.scrollUntilVisible(questionFinder, 200,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(questionFinder);
    await tester.pumpAndSettle();
    expect(find.byType(ChoiceChip), findsNothing); // sanity: still value page
    expect(
      find.textContaining('المربّي'),
      findsWidgets,
    );

    // Finish onboarding: the question is seeded for the chat and the shell
    // is pointed at the assistant tab.
    fake.gate.complete();
    await tester.tap(find.text('ابدأ الرحلة'));
    await tester.pumpAndSettle();

    expect(
      container.read(pendingChatQuestionProvider),
      'ابني في الخامسة يرفض الصلاة، ماذا أفعل؟',
    );
    expect(container.read(pendingRootTabProvider), RootTab.assistant);
    await drainStars(tester);
  });

  testWidgets(
      'the waiting overlay shows Noor and progressive lines, not a bare spinner',
      (tester) async {
    final fake = newFake();
    await pumpOnboarding(tester, fake: fake);
    await tester.tap(find.text('العربية'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('4–6 سنوات'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('ابدأ الرحلة'));
    await tester.pump(); // overlay appears, first status line

    // Noor inside the overlay itself (the value page behind it has one too).
    final overlay = find
        .ancestor(
          of: find.text('أجهّز ملف طفلك…'),
          matching: find.byType(Column),
        )
        .first;
    expect(
      find.descendant(of: overlay, matching: find.byType(NoorPresence)),
      findsOneWidget,
    );
    // No bare spinner as the wait's centerpiece — the CTA keeps its own
    // inline one, which is not what this assertion is about.
    expect(
      find.descendant(
        of: overlay,
        matching: find.byType(CircularProgressIndicator),
      ),
      findsNothing,
    );
    expect(find.text('أجهّز ملف طفلك…'), findsOneWidget);
    expect(find.text('أختار لك أول درس…'), findsNothing);

    // The second line arrives on the timer while the create is in flight.
    await tester.pump(const Duration(seconds: 4));
    expect(find.text('أختار لك أول درس…'), findsOneWidget);
    expect(find.text('أجهّز ملف طفلك…'), findsOneWidget,
        reason: 'progressive lines stack, they do not replace each other');

    // Release the create — the overlay leaves with it.
    fake.gate.complete();
    await tester.pumpAndSettle();
    expect(find.text('أجهّز ملف طفلك…'), findsNothing);
    await drainStars(tester);
  });

  // ── Chat bootstrap: the seeded question survives mount ordering ──────

  testWidgets('ChatScreen consumes a question seeded before it mounted',
      (tester) async {
    final prefs = await SharedPreferences.getInstance();
    final tg = TgClient.forTesting(
      baseUrl: 'http://x',
      httpClient: _IdleHttpClient(),
      storage: _MemStorage(),
    );
    final chat = _RecordingChatNotifier(tg);
    final container = ProviderContainer(overrides: [
      tgClientProvider.overrideWithValue(tg),
      chatNotifierProvider.overrideWith((ref) => chat),
      sharedPreferencesProvider.overrideWith((_) async => prefs),
    ]);
    await container.read(sharedPreferencesProvider.future);
    addTearDown(container.dispose);

    // Onboarding's ordering: seed FIRST, the shell (and ChatScreen) mounts
    // after. ref.listen alone would never see this value.
    container.read(pendingChatQuestionProvider.notifier).state =
        'ابني في الخامسة يرفض الصلاة، ماذا أفعل؟';

    await tester.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        locale: Locale('ar'),
        home: ChatScreen(),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
      ),
    ));
    await tester.pump();
    await tester.pump();

    expect(chat.sent, contains('ابني في الخامسة يرفض الصلاة، ماذا أفعل؟'));
    expect(container.read(pendingChatQuestionProvider), isNull,
        reason: 'consumed exactly once, never re-fired');
  });

  // ── Source pins (same shape as notification_permission_test) ──────────

  test('the tour card frames Noor through NoorPresence', () {
    final source = File('lib/features/tour/tour_overlay.dart').readAsStringSync();
    expect(source, contains('NoorPresence('));
    expect(source, isNot(contains('NoorMascot(')),
        reason: 'the moon window replaces the bare tile in the tour card');
  });

  test('the root shell consumes a pending tab on mount and on change', () {
    final source =
        File('lib/features/shell/root_scaffold.dart').readAsStringSync();
    expect(source, contains('takePendingRootTab'),
        reason: 'onboarding arms the assistant tab before the shell mounts');
  });

  test('pendingRootTabProvider starts unset', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    expect(container.read(pendingRootTabProvider), isNull);
  });
}

class _GatedFakeTgClient extends TgClient {
  Map<String, dynamic>? createChildJson;
  final gate = Completer<void>();

  _GatedFakeTgClient()
      : super.forTesting(
          baseUrl: 'http://x',
          // A never-sending client: every request in these tests is
          // intercepted by the override, and flutter_test forbids real
          // sockets anyway.
          httpClient: _IdleHttpClient(),
          storage: _MemStorage(),
        );

  @override
  Future<Map<String, dynamic>> createChild({
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
    String? birthMonth,
  }) async {
    await gate.future;
    return createChildJson ?? {};
  }
}

/// An http client that never connects — every call these tests make is
/// intercepted before reaching it.
class _IdleHttpClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    throw StateError('unexpected network in test: \${request.url}');
  }
}

class _RecordingChatNotifier extends ChatNotifier {
  _RecordingChatNotifier(super.client);

  final sent = <String>[];

  @override
  Future<void> bootstrap() async {}

  @override
  Future<void> sendMessage(String text) async => sent.add(text);
}

class _MemStorage implements FlutterSecureStorage {
  final Map<String, String> _store = {};

  @override
  Future<String?> read({
    required String key,
    Object? aOptions,
    Object? iOptions,
    Object? lOptions,
    Object? webOptions,
    Object? mOptions,
    Object? wOptions,
  }) async =>
      _store[key];

  @override
  Future<void> write({
    required String key,
    required String? value,
    Object? aOptions,
    Object? iOptions,
    Object? lOptions,
    Object? webOptions,
    Object? mOptions,
    Object? wOptions,
  }) async {
    if (value == null) {
      _store.remove(key);
    } else {
      _store[key] = value;
    }
  }

  @override
  Future<void> delete({
    required String key,
    Object? aOptions,
    Object? iOptions,
    Object? lOptions,
    Object? webOptions,
    Object? mOptions,
    Object? wOptions,
  }) async =>
      _store.remove(key);

  @override
  dynamic noSuchMethod(Invocation i) => super.noSuchMethod(i);
}
