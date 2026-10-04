/// Test doubles for «المربّي يعرف ابنك» (MOBILE_API §9–§10).
///
/// [FakeMemoryServer] is a TgClient whose memory, follow-up, plan, proof and
/// deletion endpoints answer from in-memory state with the server's own rules:
/// protected routes refuse an unproven session (`device_proof_required`) and
/// any session during a pause (`device_proof_cooldown`); switching memory off
/// and the weekly plan never need a proof; a server "without memory" answers
/// FastAPI's bare 404 everywhere.
///
/// The proof is a real round trip through [DeviceProofService]: `start` hands
/// the code to [deliverCode] (the test wires it to the service's inbox, the
/// way FCM would), and `complete` checks it.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/child_memory/device_proof/device_proof_service.dart';
import 'package:almorabbi/features/child_memory/providers/memory_providers.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/theme/app_palette.dart';
import 'package:almorabbi/theme/app_theme.dart';

TgApiError notFound() =>
    const TgApiError(404, 'Not Found'); // FastAPI's own: no code

TgApiError coded(int status, String code,
        {String message = 'msg', Map<String, dynamic> extra = const {}}) =>
    TgApiError(status, message,
        code: code, details: {'code': code, 'message': message, ...extra});

class FakeMemoryServer extends TgClient {
  FakeMemoryServer()
      : super.forTesting(
          baseUrl: 'http://fake.invalid',
          httpClient: MockClient((_) async => http.Response('{}', 500)),
        );

  /// Every call, in order: `'<METHOD> <path>'`.
  final List<String> calls = [];

  // ── server state ──────────────────────────────────────────────────────
  bool memorySupported = true;
  bool enabled = true;
  bool proven = false;
  bool pushRegistered = true;
  DateTime? cooldownUntil;
  DateTime? deletionPausedUntil;

  /// Facts by child id, newest first.
  final Map<int, List<Map<String, dynamic>>> facts = {};
  List<Map<String, dynamic>> due = [];
  final Map<int, Map<String, dynamic>> followups = {};
  final Map<int, Map<String, dynamic>> plans = {};
  List<Map<String, dynamic>> children = [];
  bool noteDropped = false;

  /// Where an account deletion stands on this phone, and what asking the
  /// server with the old token answers (TgClient's real logic is tested at
  /// the HTTP level in memory_api_test / pr36_review_fixes_test).
  String? deletionStateValue;
  bool? probeAnswer;
  int startOvers = 0;

  @override
  Future<String?> accountDeletionState() async => deletionStateValue;

  @override
  Future<void> clearAccountDeletionState() async => deletionStateValue = null;

  @override
  Future<void> startOverAfterAccountDeletion() async {
    startOvers++;
    deletionStateValue = kAccountDeletionConfirmed;
  }

  @override
  Future<bool?> probeAccountDeleted() async {
    calls.add('PROBE old token');
    return probeAnswer;
  }

  /// What the account deletion returns, or the error it throws.
  Map<String, dynamic> deletionResult = {
    'devices': 1,
    'signed_in': false,
    'deleted': {'child_profiles': 1},
    'deleted_at': '2026-10-04T18:40:00Z',
  };
  TgApiError? deletionError;

  // ── device proof ──────────────────────────────────────────────────────
  /// Hands a code to the app the way FCM would (wired by the test).
  void Function(String challengeId, String code)? deliverCode;

  /// When false, start succeeds but the code never arrives.
  bool deliverCodes = true;

  /// Errors `start` answers with, in order (then it succeeds).
  final List<TgApiError> startErrors = [];
  int starts = 0;
  int completes = 0;
  String? _liveChallenge;
  String? _liveCode;

  /// Deliver the code of the challenge in flight (when [deliverCodes] is off
  /// and the test wants to see the waiting state first).
  void sendPendingCode() {
    final id = _liveChallenge;
    final code = _liveCode;
    if (id != null && code != null) deliverCode?.call(id, code);
  }

  /// The error `POST …/memory` answers with, if any.
  TgApiError? addError;

  /// Answer like PR #39's server: `memory_enabled` on the follow-up routes,
  /// `remembered` on answers, `409 memory_off` on adding while off. False:
  /// like today's production, which sends none of it.
  bool memorySwitchFields = true;

  /// What the follow-up routes say about memory, when it should differ from
  /// the switch (the switch read is stale: turned off on another session).
  bool? followupMemoryEnabledOverride;

  bool get _followupMemoryEnabled => followupMemoryEnabledOverride ?? enabled;

  int _nextId = 100;

  void _guardMemory() {
    if (!memorySupported) throw notFound();
  }

  /// The proof rule of every protected route.
  void _requireProof() {
    _guardMemory();
    final until = cooldownUntil;
    if (until != null && until.isAfter(DateTime.now().toUtc())) {
      throw coded(403, 'device_proof_cooldown',
          message: 'paused', extra: {'available_at': until.toIso8601String()});
    }
    if (!proven) {
      throw coded(403, 'device_proof_required',
          message: 'prove first', extra: {'support_email': 'support@alsaba.cloud'});
    }
  }

  Map<String, dynamic> _settings() => {
        'enabled': enabled,
        'collecting': enabled && proven,
        'proven': proven && cooldownUntil == null,
        'cooldown_until': cooldownUntil?.toIso8601String(),
      };

  @override
  Future<Map<String, dynamic>> getDeviceProofStatus() async {
    calls.add('GET /api/device-proof');
    _guardMemory();
    return {
      'proven': proven,
      'proven_at': proven ? '2026-10-04T18:30:00Z' : null,
      'push_registered': pushRegistered,
      'cooldown_until': cooldownUntil?.toIso8601String(),
      'deletion_paused_until': deletionPausedUntil?.toIso8601String(),
    };
  }

  @override
  Future<Map<String, dynamic>> startDeviceProof() async {
    calls.add('POST /api/device-proof/start');
    _guardMemory();
    starts++;
    if (startErrors.isNotEmpty) throw startErrors.removeAt(0);
    if (!pushRegistered) {
      throw coded(409, 'no_push_token',
          extra: {'support_email': 'support@alsaba.cloud'});
    }
    final id = 'challenge${starts.toString().padLeft(4, '0')}';
    final code = 'code-$starts';
    _liveChallenge = id;
    _liveCode = code;
    if (deliverCodes) {
      // FCM delivers on its own schedule, after the 202.
      scheduleMicrotask(() => deliverCode?.call(id, code));
    }
    return {'challenge_id': id, 'expires_in': 300};
  }

  @override
  Future<Map<String, dynamic>> completeDeviceProof(
      String challengeId, String code) async {
    calls.add('POST /api/device-proof/complete');
    completes++;
    if (challengeId != _liveChallenge || code != _liveCode) {
      throw coded(409, 'proof_failed', extra: {'reason': 'wrong_code'});
    }
    proven = true;
    _liveChallenge = null;
    return {'proven': true, 'proven_at': '2026-10-04T18:30:00Z'};
  }

  @override
  Future<Map<String, dynamic>> getMemorySettings() async {
    calls.add('GET /api/children/memory/settings');
    _guardMemory();
    return _settings();
  }

  @override
  Future<Map<String, dynamic>> putMemorySettings({required bool enabled}) async {
    calls.add('PUT /api/children/memory/settings enabled=$enabled');
    _guardMemory();
    if (enabled) _requireProof(); // off: never
    this.enabled = enabled;
    return _settings();
  }

  @override
  Future<Map<String, dynamic>> getChildMemory(int childId,
      {String status = 'all'}) async {
    calls.add('GET /api/children/$childId/memory');
    _requireProof();
    return {
      'child_id': childId,
      'facts': facts[childId] ?? const [],
      'settings': _settings(),
      'limits': {'max_fact_chars': 160, 'max_facts': 40},
    };
  }

  @override
  Future<Map<String, dynamic>> addChildFact(int childId,
      {required String category, required String fact}) async {
    calls.add('POST /api/children/$childId/memory');
    _requireProof();
    final err = addError;
    if (err != null) throw err;
    if (memorySwitchFields && !enabled) {
      throw coded(409, 'memory_off', message: 'الذاكرة متوقفة');
    }
    final row = factJson(_nextId++, childId,
        category: category, fact: fact, source: 'parent_manual');
    (facts[childId] ??= []).insert(0, row);
    return row;
  }

  /// The last PATCH body, as sent.
  Map<String, Object?>? lastPatch;

  @override
  Future<Map<String, dynamic>> patchChildFact(int childId, int factId,
      {String? fact, String? category, String? status}) async {
    calls.add('PATCH /api/children/$childId/memory/$factId');
    _requireProof();
    lastPatch = {
      'fact': ?fact,
      'category': ?category,
      'status': ?status,
    };
    final row = (facts[childId] ?? const []).firstWhere((f) => f['id'] == factId);
    if (fact != null) row['fact'] = fact;
    if (category != null) row['category'] = category;
    if (status != null) row['status'] = status;
    return row;
  }

  @override
  Future<Map<String, dynamic>> deleteChildFact(int childId, int factId) async {
    calls.add('DELETE /api/children/$childId/memory/$factId');
    _requireProof();
    facts[childId]?.removeWhere((f) => f['id'] == factId);
    return {'deleted': true, 'fact_id': factId};
  }

  @override
  Future<Map<String, dynamic>> deleteChildMemory(int childId) async {
    calls.add('DELETE /api/children/$childId/memory');
    _requireProof();
    final n = facts.remove(childId)?.length ?? 0;
    return {
      'child_id': childId,
      'deleted': {'child_facts': n, 'followups': 0, 'weekly_plans': 0},
    };
  }

  @override
  Future<Map<String, dynamic>> getDueFollowups(
      {int limit = 10, int? tzOffsetMinutes}) async {
    calls.add('GET /api/children/followups/due tz=$tzOffsetMinutes');
    _requireProof();
    if (!memorySwitchFields) return {'followups': due};
    final on = _followupMemoryEnabled;
    return {'followups': on ? due : const [], 'memory_enabled': on};
  }

  @override
  Future<Map<String, dynamic>> getFollowup(int followupId) async {
    calls.add('GET /api/children/followups/$followupId');
    _requireProof();
    final f = followups[followupId];
    if (f == null) throw coded(404, 'followup_not_found');
    return {
      'followup': f,
      if (memorySwitchFields) 'memory_enabled': _followupMemoryEnabled,
    };
  }

  @override
  Future<Map<String, dynamic>> answerFollowup(int followupId,
      {required String outcome, String? note}) async {
    calls.add('POST /api/children/followups/$followupId/answer '
        'outcome=$outcome note=${note ?? '-'}');
    _requireProof();
    final f = followups[followupId] ??
        due.firstWhere((d) => d['id'] == followupId,
            orElse: () => throw coded(404, 'followup_not_found'));
    if (f['status'] != 'pending') {
      throw coded(409, 'followup_closed');
    }
    if (memorySwitchFields && !enabled) {
      // Nothing kept: the follow-up stays pending, no fact, no note.
      return {
        'followup': f,
        'fact': null,
        'note_dropped': false,
        'remembered': false,
      };
    }
    f['status'] = 'answered';
    f['outcome'] = outcome;
    f['note'] = noteDropped ? null : note;
    due.removeWhere((d) => d['id'] == followupId);
    return {
      'followup': f,
      'fact': factJson(_nextId++, f['child_id'] as int,
          category: 'outcome', fact: 'جُرِّب مع طفلي', source: 'followup'),
      'note_dropped': noteDropped,
      if (memorySwitchFields) 'remembered': true,
    };
  }

  @override
  Future<Map<String, dynamic>> dismissFollowup(int followupId) async {
    calls.add('POST /api/children/followups/$followupId/dismiss');
    _requireProof();
    final f = followups[followupId] ??
        due.firstWhere((d) => d['id'] == followupId);
    f['status'] = 'dismissed';
    due.removeWhere((d) => d['id'] == followupId);
    return {'followup': f};
  }

  @override
  Future<Map<String, dynamic>> getWeeklyPlan(int childId,
      {String? lang, int? tzOffsetMinutes}) async {
    calls.add('GET /api/children/$childId/weekly-plan lang=$lang '
        'tz=$tzOffsetMinutes');
    _guardMemory(); // no proof needed
    final p = plans[childId];
    if (p == null) throw const TgApiError(404, 'الطفل غير موجود.');
    return p;
  }

  @override
  Future<Map<String, dynamic>> deleteAllMemory() async {
    calls.add('DELETE /api/privacy/memory');
    _requireProof();
    facts.clear();
    return {
      'deleted': {'child_facts': 0, 'followups': 0, 'weekly_plans': 0},
      'deleted_at': '2026-10-04T18:30:00Z',
    };
  }

  @override
  Future<Map<String, dynamic>> deleteAccount() async {
    calls.add('DELETE /api/privacy/account?confirm=true');
    _guardMemory();
    final paused = deletionPausedUntil;
    if (paused != null && paused.isAfter(DateTime.now().toUtc())) {
      throw coded(403, 'device_proof_cooldown',
          extra: {'available_at': paused.toIso8601String()});
    }
    _requireProof();
    final err = deletionError;
    if (err != null) {
      if (err.code == 'account_deletion_unconfirmed') {
        deletionStateValue = kAccountDeletionRequested;
      }
      throw err;
    }
    deletionStateValue = kAccountDeletionConfirmed;
    return deletionResult;
  }

  @override
  Future<Map<String, dynamic>> listChildren() async {
    calls.add('GET /api/children');
    return {'count': children.length, 'children': children};
  }

  // Nothing else on these screens may reach a network.
  @override
  Future<SessionResponse> ensureSession() async =>
      const SessionResponse(sessionId: 's1', token: 't1');
}

Map<String, dynamic> factJson(
  int id,
  int childId, {
  String category = 'temperament',
  String fact = 'طفلي يخاف من الظلام',
  String source = 'chat',
  String status = 'active',
  String lang = 'ar',
}) =>
    {
      'id': id,
      'child_id': childId,
      'category': category,
      'fact': fact,
      'source': source,
      'confidence': 0.9,
      'status': status,
      'lang': lang,
      'created_at': '2026-10-04T18:20:11Z',
      'updated_at': '2026-10-04T18:20:11Z',
    };

Map<String, dynamic> childJson(int id, String name, {String age = '7-9'}) => {
      'id': id,
      'name': name,
      'age_group': age,
      'gender': null,
      'avatar_emoji': '🧒',
      'created_at': '2026-06-08T10:00:00',
      'updated_at': '2026-06-08T10:00:00',
    };

Map<String, dynamic> followupJson(
  int id,
  int childId, {
  String strategy = 'روتين نوم ثابت مع قصة قبل النوم لطفلي',
  String status = 'pending',
  String? outcome,
  String lang = 'ar',
}) =>
    {
      'id': id,
      'child_id': childId,
      'strategy': strategy,
      'topic': 'sleep',
      'lang': lang,
      'due_at': '2026-10-08T18:20:11Z',
      'status': status,
      'outcome': outcome,
      'note': null,
      'created_at': '2026-10-04T18:20:11Z',
      'answered_at': null,
    };

Map<String, dynamic> planJson(int childId,
        {String lang = 'ar', bool withLesson = true}) =>
    {
      'child_id': childId,
      'week': '2026-W41',
      'week_start': '2026-10-05',
      'lang': lang,
      'band': '7-9',
      'focus': {
        'topic': 'sleep',
        'title': lang == 'en' ? 'Enough sleep, better focus' : 'نوم كافٍ لتركيز أفضل',
        'reason': 'memory',
        'reason_text': lang == 'en'
            ? 'Based on what you told us about your child.'
            : 'بناءً على ما أخبرتنا به عن طفلك.',
      },
      'actions': [
        {'key': 'a1', 'text': lang == 'en' ? 'Fix a bedtime on school days.' : 'ثبّت موعد النوم في أيام الدراسة.'},
        {'key': 'a2', 'text': lang == 'en' ? 'Screens off an hour before bed.' : 'أوقف الشاشات قبل النوم بساعة.'},
        {'key': 'a3', 'text': lang == 'en' ? 'Less sugar in the evening.' : 'خفّف السكريات في المساء.'},
      ],
      'adapted_from_outcomes': true,
      'worship': {
        'key': 'w1',
        'text': lang == 'en' ? 'Choose a small charity together.' : 'اختاروا معًا عملًا خيريًا صغيرًا.'
      },
      'lesson': withLesson
          ? {
              'id': 'lesson_7-9_medical_emotional_health_02',
              'title': lang == 'en' ? 'Sleep and focus' : 'النوم والتركيز',
              'path_id': 'path_7-9_medical_emotional_health',
              'estimated_minutes': 7,
              'completed': false,
            }
          : null,
      'source': 'bank',
      'generated_at': '2026-10-05T06:12:40Z',
    };

/// A proof service over [server] whose codes arrive the way FCM would, wired
/// as the client's proof hook — without ports (no isolate plumbing in a
/// widget test).
DeviceProofService proofFor(FakeMemoryServer server,
    {Duration messageTimeout = const Duration(seconds: 20)}) {
  final proof = DeviceProofService(server, messageTimeout: messageTimeout);
  server.deliverCode = (id, code) => proof.deliver(
      {'type': kDeviceProofMessageType, 'challenge_id': id, 'code': code});
  server.onDeviceProofRequired = () => proof.prove();
  return proof;
}

/// Pump [home] the way the app shows it: the fake server, the proof service,
/// the active child «أحمد» (id 12, 7-9) on disk, and the given locale, theme
/// and text scale.
Future<ProviderContainer> pumpMemoryApp(
  WidgetTester tester,
  Widget home, {
  required FakeMemoryServer server,
  DeviceProofService? proof,
  Locale locale = const Locale('ar'),
  bool dark = false,
  double textScale = 1.0,
  Size phone = const Size(360, 800),
  bool withActiveChild = true,
  List<NavigatorObserver> observers = const [],
  List<Override> overrides = const [],
  GlobalKey<NavigatorState>? navigatorKey,
}) async {
  tester.view.physicalSize = phone * 3.0;
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({
    OnboardingStorage.keyOnboardingCompleted: true,
    if (withActiveChild) ...{
      OnboardingStorage.keyActiveChildId: 12,
      OnboardingStorage.keyActiveChildName: 'أحمد',
      OnboardingStorage.keyActiveChildAgeGroup: '7-9',
    },
  });
  final prefs = await SharedPreferences.getInstance();
  final service = proof ?? proofFor(server);
  final container = ProviderContainer(overrides: [
    tgClientProvider.overrideWithValue(server),
    deviceProofServiceProvider.overrideWithValue(service),
    sharedPreferencesProvider.overrideWith((_) async => prefs),
    ...overrides,
  ]);
  addTearDown(container.dispose);
  await container.read(sharedPreferencesProvider.future);
  if (withActiveChild) container.read(activeChildIdProvider.notifier).state = 12;
  if (dark) AppPalette.current = AppPalette.dark;
  addTearDown(() => AppPalette.current = AppPalette.light);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        navigatorKey: navigatorKey,
        locale: locale,
        theme: dark ? AppTheme.dark() : AppTheme.light(),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        navigatorObservers: observers,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!,
        ),
        home: home,
      ),
    ),
  );
  await tester.pump();
  return container;
}

/// Lets futures, microtasks and one frame run (no pumpAndSettle: the proof
/// view's spinner never settles).
Future<void> settle(WidgetTester tester, [int frames = 6]) async {
  for (var i = 0; i < frames; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}
