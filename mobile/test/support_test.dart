/// «ادعم المربّي» — the two-sided gate, the app-wide purchase coordinator, the
/// record-then-consume order, and the screens.
///
/// The store is faked, but everything that flows through it is built with the
/// Android plugin's own types and factories: products are
/// `GooglePlayProductDetails.fromProductDetails`, purchases are
/// `GooglePlayPurchaseDetails.fromPurchase`, and a cancelled sheet or a billing
/// error is the bare `PurchaseDetails(productID: '', …)` the plugin emits when
/// Play answers with no purchases. A fake that invents friendlier shapes is
/// how the cancel-leaves-a-spinner bug got past the first version of this file.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_android/billing_client_wrappers.dart';
import 'package:in_app_purchase_android/in_app_purchase_android.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/screens/settings_screen.dart';
import 'package:almorabbi/features/support/support_providers.dart';
import 'package:almorabbi/features/support/support_screen.dart';
import 'package:almorabbi/features/support/support_store.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/main.dart' show appConfigProvider;
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/widgets/ui/directional_chevron.dart';

// ── Real plugin shapes ────────────────────────────────────────────────────

ProductDetails _product(String id, int priceMicros, {String currency = 'EGP'}) =>
    GooglePlayProductDetails.fromProductDetails(ProductDetailsWrapper(
      description: '',
      name: id,
      productId: id,
      productType: ProductType.inapp,
      title: '$id (Al-Murabbi)',
      oneTimePurchaseOfferDetails: OneTimePurchaseOfferDetailsWrapper(
        formattedPrice: '$currency ${(priceMicros / 1000000).toStringAsFixed(2)}',
        priceAmountMicros: priceMicros,
        priceCurrencyCode: currency,
      ),
    )).single;

GooglePlayPurchaseDetails _purchase(
  String id, {
  String? token,
  PurchaseStateWrapper state = PurchaseStateWrapper.purchased,
  bool restored = false,
}) {
  final details = GooglePlayPurchaseDetails.fromPurchase(PurchaseWrapper(
    orderId: 'GPA.0000-${id.hashCode.abs()}',
    packageName: 'com.alsaba.almorabbi',
    purchaseTime: DateTime.now().millisecondsSinceEpoch,
    purchaseToken: token ?? 'token-$id',
    signature: 'sig',
    products: [id],
    isAutoRenewing: false,
    originalJson: '{}',
    isAcknowledged: false,
    purchaseState: state,
  )).single;
  // restorePurchases() re-labels everything it finds this way, pending included.
  if (restored) details.status = PurchaseStatus.restored;
  return details;
}

/// What the plugin emits when Play answers a purchase flow with no purchases:
/// productID '' and no token — a cancelled sheet, a billing error, or (rarely)
/// an OK with nothing in it. Mirrors `_getPurchaseDetailsFromResult`.
PurchaseDetails _androidEmptyResult(BillingResponse code) {
  var status = PurchaseStatus.error;
  if (code == BillingResponse.userCanceled) {
    status = PurchaseStatus.canceled;
  } else if (code == BillingResponse.ok) {
    status = PurchaseStatus.purchased;
  }
  return PurchaseDetails(
    purchaseID: '',
    productID: '',
    status: status,
    transactionDate: null,
    verificationData: PurchaseVerificationData(
      localVerificationData: '',
      serverVerificationData: '',
      source: kIAPSource,
    ),
  )..error = code == BillingResponse.ok
      ? null
      : IAPError(
          source: kIAPSource,
          code: kPurchaseErrorCode,
          message: code.toString(),
          details: '',
        );
}

// ── Fakes ─────────────────────────────────────────────────────────────────

class _FakeStore implements SupportStore {
  bool available = true;
  Object? queryError;
  List<ProductDetails> products = [];
  int queries = 0;
  int restores = 0;

  /// Purchases Play still holds unconsumed — what restore() re-delivers.
  final owned = <GooglePlayPurchaseDetails>[];
  final consumed = <String>[];
  final bought = <String>[];
  final controller = StreamController<List<PurchaseDetails>>.broadcast();

  @override
  Future<bool> isAvailable() async => available;

  @override
  Future<List<ProductDetails>> queryProducts(Set<String> ids) async {
    queries++;
    final error = queryError;
    if (error != null) throw error;
    return products.where((p) => ids.contains(p.id)).toList();
  }

  @override
  Stream<List<PurchaseDetails>> get purchaseStream => controller.stream;

  @override
  Future<bool> buy(ProductDetails product) async {
    bought.add(product.id);
    return true;
  }

  @override
  Future<void> restore() async {
    restores++;
    if (owned.isEmpty) return;
    controller.add([
      for (final p in owned)
        _purchase(p.productID,
            token: p.verificationData.serverVerificationData,
            state: p.billingClientPurchase.purchaseState,
            restored: true),
    ]);
  }

  @override
  Future<void> consume(PurchaseDetails purchase) async {
    consumed.add(purchase.productID);
    owned.removeWhere((p) =>
        p.verificationData.serverVerificationData ==
        purchase.verificationData.serverVerificationData);
  }
}

class _FakeClient extends TgClient {
  Map<String, dynamic>? transparency;
  Object? verifyError;
  Map<String, dynamic> verifyResult = {
    'ok': true, 'consumed': true, 'already_recorded': false, 'pending': false,
  };

  /// Per-token answers, over [verifyResult] — the server's view of each
  /// purchase can differ (one still pending at Play, one recorded).
  final verifyByToken = <String, Map<String, dynamic>>{};
  final verified = <String>[];

  @override
  Future<Map<String, dynamic>> listChildren() async => {
        'count': 1,
        'children': [
          {
            'id': 5, 'name': 'سارة', 'age_group': '4-6', 'gender': null,
            'avatar_emoji': null, 'created_at': '2026-10-01T10:00:00',
            'updated_at': '2026-10-01T10:00:00',
          }
        ],
      };

  @override
  Future<Map<String, dynamic>> fetchSupportTransparency() async {
    final t = transparency;
    if (t == null) throw const TgApiError(404, 'Not Found'); // older server
    return t;
  }

  @override
  Future<Map<String, dynamic>> verifySupportPurchase({
    required String productId,
    required String purchaseToken,
    int? priceMicros,
    String? currency,
  }) async {
    verified.add('$productId:$purchaseToken:$priceMicros:$currency');
    final e = verifyError;
    if (e != null) throw e;
    return verifyByToken[purchaseToken] ?? verifyResult;
  }
}

class _MemoryStorage implements FlutterSecureStorage {
  final _values = <String, String>{};

  @override
  Future<String?> read({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async =>
      _values[key];

  @override
  Future<void> write({
    required String key,
    required String? value,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    if (value == null) {
      _values.remove(key);
    } else {
      _values[key] = value;
    }
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => Future<void>.value();
}

void main() {
  late _FakeStore store;
  late _FakeClient client;

  setUp(() {
    store = _FakeStore();
    client = _FakeClient();
    SharedPreferences.setMockInitialValues({});
  });

  ProviderContainer container({required bool flag}) {
    final c = ProviderContainer(overrides: [
      appConfigProvider.overrideWith((ref) async => {
            'minimum_build_number': 0,
            if (flag) 'donations_enabled': true,
          }),
      supportStoreProvider.overrideWithValue(store),
      tgClientProvider.overrideWithValue(client),
    ]);
    addTearDown(c.dispose);
    return c;
  }

  Future<List<ProductDetails>> productsOf(ProviderContainer c) async {
    final sub = c.listen(supportProductsProvider, (_, _) {});
    try {
      return await c.read(supportProductsProvider.future);
    } finally {
      sub.close();
    }
  }

  group('the gate', () {
    test('server flag off: hidden, and the store is never asked', () async {
      store.products = [_product('support_small', 10000000)];
      final c = container(flag: false);
      await c.read(appConfigProvider.future);
      expect(await productsOf(c), isEmpty);
      expect(c.read(supportVisibleProvider), isFalse);
      expect(store.queries, 0);
    });

    test('an older server (no field at all) reads as off', () async {
      final c = container(flag: false);
      await c.read(appConfigProvider.future);
      expect(c.read(donationsEnabledProvider), isFalse);
      expect(c.read(donationProductIdsProvider), kDefaultSupportProductIds);
    });

    test('flag on but no Play billing (emulator): hidden', () async {
      store
        ..available = false
        ..products = [_product('support_small', 10000000)];
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      expect(await productsOf(c), isEmpty);
    });

    test('flag on but the products were never created: hidden', () async {
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      expect(await productsOf(c), isEmpty);
    });

    test('flag on and products returned: shown, cheapest first', () async {
      store.products = [
        _product('support_large', 200000000),
        _product('support_small', 20000000),
        _product('support_medium', 60000000),
      ];
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      final visible = c.listen(supportVisibleProvider, (_, _) {});
      final products = await c.read(supportProductsProvider.future);
      expect(products.map((p) => p.id),
          ['support_small', 'support_medium', 'support_large']);
      expect(visible.read(), isTrue);
      visible.close();
    });

    test('a transient billing failure is asked again on the next visit',
        () async {
      // Item 11: the products used to be cached for the whole process, so a
      // single failed query — no network at launch — hid the row until the
      // app was killed.
      store
        ..products = [_product('support_small', 20000000)]
        ..queryError = Exception('BillingResponse.serviceUnavailable');
      final c = container(flag: true);
      await c.read(appConfigProvider.future);

      final first = c.listen(supportVisibleProvider, (_, _) {});
      await c.read(supportProductsProvider.future);
      expect(first.read(), isFalse);
      first.close(); // Settings closed
      await Future<void>.delayed(Duration.zero);

      store.queryError = null;
      final second = c.listen(supportVisibleProvider, (_, _) {}); // reopened
      await c.read(supportProductsProvider.future);
      expect(second.read(), isTrue);
      expect(store.queries, 2);
      second.close();
    });

    test('a resume asks the store again while Settings stays open', () async {
      store
        ..products = [_product('support_small', 20000000)]
        ..queryError = Exception('BillingResponse.serviceDisconnected');
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      final visible = c.listen(supportVisibleProvider, (_, _) {});
      await c.read(supportProductsProvider.future);
      expect(visible.read(), isFalse);

      store.queryError = null;
      final coordinator = c.read(supportCoordinatorProvider)..start();
      coordinator.didChangeAppLifecycleState(AppLifecycleState.resumed);
      await c.read(supportProductsProvider.future);
      expect(visible.read(), isTrue);
      visible.close();
    });
  });

  group('the app-wide coordinator', () {
    // TestWidgetsFlutterBinding, because the coordinator observes the app's
    // lifecycle through WidgetsBinding.
    TestWidgetsFlutterBinding.ensureInitialized();

    test('never touches billing while the server flag is off', () async {
      final c = container(flag: false);
      await c.read(appConfigProvider.future);
      c.read(supportBootProvider);
      expect(c.read(supportCoordinatorProvider).started, isFalse);
      expect(store.controller.hasListener, isFalse);
      expect(store.restores, 0);
    });

    test('starts once at launch when on: one subscription, one restore',
        () async {
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      c.read(supportBootProvider);
      c.read(supportBootProvider);
      c.read(supportCoordinatorProvider).start();
      expect(c.read(supportCoordinatorProvider).started, isTrue);
      expect(store.controller.hasListener, isTrue);
      expect(store.restores, 1);
    });

    test('a purchase finishing with no support screen open is still recorded',
        () async {
      // Item 1: the screen used to own the only listener. Close it before
      // Play answers — a slow card, a parent who backs out — and the
      // purchase reached no one, stayed unacknowledged, and was refunded.
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      c.read(supportBootProvider);
      store.controller.add([_purchase('support_small')]);
      await pumpEventQueue();
      expect(client.verified, ['support_small:token-support_small:null:null']);
    });

    test('a pending cash payment is verified when Play completes it later',
        () async {
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      c.read(supportBootProvider);
      final outcomes = <SupportOutcome?>[];
      c.read(supportCoordinatorProvider).events.listen((e) => outcomes.add(e.outcome));

      store.controller.add(
          [_purchase('support_medium', state: PurchaseStateWrapper.pending)]);
      await pumpEventQueue();
      expect(outcomes, [SupportOutcome.pending]);
      expect(client.verified, isEmpty);

      // Hours later, with the app in the background and no screen open.
      store.controller.add([_purchase('support_medium')]);
      await pumpEventQueue();
      expect(client.verified, hasLength(1));
      expect(outcomes.last, SupportOutcome.thanked);
    });

    testWidgets('every resume re-asks Play for unfinished purchases',
        (tester) async {
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      c.read(supportBootProvider);
      await tester.pump();
      expect(store.restores, 1);

      // A purchase the server could not reach last time is still owned.
      client.verifyError = const TgApiError(503, 'verification_unavailable');
      store.owned.add(_purchase('support_small'));
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      // Duration.zero, not pump(): only an elapse runs the zero-length timer
      // the products provider's invalidation schedules.
      await tester.pump(Duration.zero);
      expect(store.restores, 2);
      expect(client.verified, hasLength(1));
      expect(store.consumed, isEmpty); // not recorded → never consumed

      client.verifyError = null;
      client.verifyResult = {
        'ok': true, 'consumed': false, 'already_recorded': false, 'pending': false,
      };
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      // Duration.zero, not pump(): only an elapse runs the zero-length timer
      // the products provider's invalidation schedules.
      await tester.pump(Duration.zero);
      expect(store.restores, 3);
      expect(store.consumed, ['support_small']); // recorded → consumed here
    });

    test('re-delivered outcomes are logged once, cancels every time', () async {
      // Item 19: a pending payment is re-delivered on every launch and
      // resume; logging each would count one parent dozens of times.
      final logged = <SupportOutcome>[];
      final coordinator = SupportPurchaseCoordinator(
        store: store,
        clientOf: () => client,
        logOutcome: (o) async => logged.add(o),
      );
      addTearDown(coordinator.dispose);
      coordinator.start();

      final pending = _purchase('support_small',
          state: PurchaseStateWrapper.pending, restored: false);
      store.controller.add([pending]);
      store.controller.add([pending]);
      client.verifyError = const TgApiError(503, 'verification_unavailable');
      store.controller.add([_purchase('support_large', restored: true)]);
      store.controller.add([_purchase('support_large', restored: true)]);
      store.controller.add([_androidEmptyResult(BillingResponse.userCanceled)]);
      store.controller.add([_androidEmptyResult(BillingResponse.userCanceled)]);
      await pumpEventQueue();

      expect(logged, [
        SupportOutcome.pending,
        SupportOutcome.retryLater,
        SupportOutcome.cancelled,
        SupportOutcome.cancelled,
      ]);
    });
  });

  group('record, then consume', () {
    SupportPurchaseHandler handler() => SupportPurchaseHandler(
          client: client,
          store: store,
          productById: (id) => id == 'support_small'
              ? _product('support_small', 20000000)
              : null,
        );

    test('server recorded and consumed: thanked, nothing consumed here',
        () async {
      expect(await handler().handle(_purchase('support_small')),
          SupportOutcome.thanked);
      expect(client.verified,
          ['support_small:token-support_small:20000000:EGP']);
      expect(store.consumed, isEmpty);
    });

    test('server recorded but could not consume: consumed here', () async {
      client.verifyResult = {
        'ok': true, 'consumed': false, 'already_recorded': false, 'pending': false,
      };
      expect(await handler().handle(_purchase('support_small')),
          SupportOutcome.thanked);
      expect(store.consumed, ['support_small']);
    });

    test('server unreachable: left untouched for the next visit', () async {
      client.verifyError = const TgApiError(503, 'verification_unavailable');
      expect(await handler().handle(_purchase('support_small')),
          SupportOutcome.retryLater);
      expect(store.consumed, isEmpty);
    });

    test('older server without the endpoint: also retried, never consumed',
        () async {
      client.verifyError = const TgApiError(404, 'Not Found');
      expect(await handler().handle(_purchase('support_small')),
          SupportOutcome.retryLater);
      expect(store.consumed, isEmpty);
    });

    test('Play says it is not a purchase: error, not consumed', () async {
      client.verifyError = const TgApiError(400, 'invalid_purchase');
      expect(await handler().handle(_purchase('support_small')),
          SupportOutcome.error);
      expect(store.consumed, isEmpty);
    });

    test('pending at Play: nothing recorded or consumed yet', () async {
      expect(
          await handler().handle(_purchase('support_small',
              state: PurchaseStateWrapper.pending)),
          SupportOutcome.pending);
      expect(client.verified, isEmpty);
      client.verifyResult = {
        'ok': false, 'consumed': false, 'already_recorded': false, 'pending': true,
      };
      expect(await handler().handle(_purchase('support_small')),
          SupportOutcome.pending);
      expect(store.consumed, isEmpty);
    });

    test('a re-delivered purchase already thanked for stays quiet', () async {
      client.verifyResult = {
        'ok': true, 'consumed': true, 'already_recorded': true, 'pending': false,
      };
      expect(
          await handler()
              .handle(_purchase('support_small', restored: true)),
          isNull);
    });

    test('a product since dropped from the server list still reaches it',
        () async {
      // Item 17: the server recognises it by its token; the app must not
      // drop it on the way.
      client.verifyResult = {
        'ok': true, 'consumed': true, 'already_recorded': true, 'pending': false,
      };
      expect(
          await handler()
              .handle(_purchase('support_retired', restored: true)),
          isNull);
      expect(client.verified, ['support_retired:token-support_retired:null:null']);
    });

    test("Android's cancel and error shapes (productID '') are answered",
        () async {
      // Item 4: they carry no product id and no token, and used to be
      // dropped as "someone else's product" — leaving the spinner up.
      expect(await handler().handle(
              _androidEmptyResult(BillingResponse.userCanceled)),
          SupportOutcome.cancelled);
      expect(await handler().handle(
              _androidEmptyResult(BillingResponse.serviceUnavailable)),
          SupportOutcome.error);
      expect(await handler().handle(_androidEmptyResult(BillingResponse.ok)),
          isNull);
      expect(client.verified, isEmpty);
    });
  });

  test('the client hands back the body the server sent, nothing added',
      () async {
    // Item 23: `pending` is the server's word for it; the client used to add
    // its own `status` beside it, two encodings of one fact.
    final http.Client mock = MockClient((req) async {
      if (req.url.path == '/api/chat/sessions') {
        return http.Response(jsonEncode({'session_id': 's1', 'token': 'tg_tok'}),
            201, headers: {'content-type': 'application/json'});
      }
      expect(req.url.path, '/api/support/verify');
      return http.Response(
          jsonEncode({'ok': false, 'consumed': false,
                      'already_recorded': false, 'pending': true}),
          202, headers: {'content-type': 'application/json'});
    });
    final api = TgClient.forTesting(
        baseUrl: 'http://api.test', httpClient: mock, storage: _MemoryStorage());
    final res = await api.verifySupportPurchase(
        productId: 'support_small', purchaseToken: 'token-1234');
    expect(res, {'ok': false, 'consumed': false,
                 'already_recorded': false, 'pending': true});
  });

  group('screens', () {
    Future<ProviderContainer> pump(WidgetTester tester, Widget home,
        {required bool flag, Locale locale = const Locale('ar')}) async {
      final c = container(flag: flag);
      await tester.pumpWidget(UncontrolledProviderScope(
        container: c,
        child: MaterialApp(
          locale: locale,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: home,
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      return c;
    }

    // The ask lives in Settings, beside «قيّم التطبيق», and nowhere else in
    // the app's chrome — and not even there unless both halves of the gate
    // are open.
    Future<void> pumpSettings(WidgetTester tester, {required bool flag}) async {
      final prefs = await SharedPreferences.getInstance();
      await OnboardingStorage(prefs)
          .setActiveChild(id: 5, name: 'سارة', ageGroup: '4-6');
      final c = ProviderContainer(overrides: [
        appConfigProvider.overrideWith((ref) async => {
              'minimum_build_number': 0,
              if (flag) 'donations_enabled': true,
            }),
        supportStoreProvider.overrideWithValue(store),
        tgClientProvider.overrideWithValue(client),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
      ]);
      addTearDown(c.dispose);
      await c.read(sharedPreferencesProvider.future);
      await tester.pumpWidget(UncontrolledProviderScope(
        container: c,
        child: const MaterialApp(
          locale: Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: SettingsScreen(),
        ),
      ));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('قيّم التطبيق'), 300,
          scrollable: find.byType(Scrollable).first);
    }

    testWidgets('settings: no support row while the flag is off',
        (tester) async {
      store.products = [_product('support_small', 20000000)];
      await pumpSettings(tester, flag: false);
      expect(find.text('ادعم المربّي'), findsNothing);
    });

    testWidgets('settings: no support row when the store has no products',
        (tester) async {
      await pumpSettings(tester, flag: true);
      expect(find.text('ادعم المربّي'), findsNothing);
    });

    testWidgets('settings: the row opens the support screen when both are on',
        (tester) async {
      store.products = [_product('support_small', 20000000)];
      await pumpSettings(tester, flag: true);
      expect(find.text('ادعم المربّي'), findsOneWidget);
      await tester.tap(find.text('ادعم المربّي'));
      await tester.pumpAndSettle();
      expect(find.byType(SupportScreen), findsOneWidget);
      expect(find.text('دعم صغير'), findsOneWidget);
    });

    testWidgets('settings: every chevron points forward in Arabic',
        (tester) async {
      // Item 15: Icons.chevron_left mirrors itself under RTL, so the rows'
      // "open" chevron pointed back at the screen edge.
      store.products = [_product('support_small', 20000000)];
      await pumpSettings(tester, flag: true);
      final chevrons = find.byWidgetPredicate((w) =>
          w is Icon &&
          (w.icon == Icons.chevron_left || w.icon == Icons.chevron_right));
      final directional = find.descendant(
          of: find.byType(DirectionalChevron), matching: chevrons);
      expect(chevrons, findsWidgets);
      expect(directional.evaluate().length, chevrons.evaluate().length);
    });

    testWidgets('transparency with a declared cost shows the share',
        (tester) async {
      store.products = [
        _product('support_small', 20000000),
        _product('support_large', 200000000),
      ];
      client.transparency = {
        'month': '2026-10', 'cost_usd': 40.0, 'covered_usd': 34.0,
        'covered_pct': 85, 'supports': 4, 'unpriced': 0,
        'breakdown': [
          {'key': 'server', 'usd': 12.0},
          {'key': 'ai', 'usd': 25.0},
        ],
      };
      await pump(tester, const SupportScreen(), flag: true);
      expect(find.text('تكلفة المربّي هذا الشهر: \$40'), findsOneWidget);
      expect(find.text('غطّى الداعمون 85٪'), findsOneWidget);
      expect(find.text('الخوادم'), findsOneWidget);
      expect(find.text('دعم صغير'), findsOneWidget);
      expect(find.text('دعم كبير'), findsOneWidget);
      expect(find.text('EGP 20.00'), findsOneWidget);
      expect(find.textContaining('لا يفتح الدعم أي ميزة'), findsOneWidget);
      expect(find.textContaining('ليس قناة زكاة'), findsOneWidget);

      await tester.tap(find.text('دعم صغير'));
      await tester.pump();
      expect(store.bought, ['support_small']);

      // Play reports the purchase; the server records it; the parent is thanked.
      store.controller.add([_purchase('support_small')]);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('نسأل الله أن يتقبّل منك 🤍 وصل دعمك.'), findsOneWidget);
      expect(client.verified, hasLength(1));
      expect(store.consumed, isEmpty); // the server consumed it
    });

    testWidgets("a cancelled sheet (Android's real shape) gives the buttons back",
        (tester) async {
      store.products = [_product('support_small', 20000000)];
      await pump(tester, const SupportScreen(), flag: true);
      await tester.tap(find.text('دعم صغير'));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      store.controller.add([_androidEmptyResult(BillingResponse.userCanceled)]);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.text('تعذّر إتمام الدفع. حاول مرة أخرى.'), findsNothing);
      await tester.tap(find.text('دعم صغير'));
      expect(store.bought, ['support_small', 'support_small']);
    });

    testWidgets("a billing error (Android's real shape) says so",
        (tester) async {
      store.products = [_product('support_small', 20000000)];
      await pump(tester, const SupportScreen(), flag: true);
      await tester.tap(find.text('دعم صغير'));
      await tester.pump();

      store.controller
          .add([_androidEmptyResult(BillingResponse.serviceUnavailable)]);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.text('تعذّر إتمام الدفع. حاول مرة أخرى.'), findsOneWidget);
    });

    testWidgets("an older purchase's restore never speaks for the live one",
        (tester) async {
      // Item 3 (delta), from the review's probe: a cash payment started days
      // ago and still pending is re-delivered by the resume-time restore — and
      // its "pending" used to replace the thanks for the card payment the
      // parent had just made.
      store.products = [_product('support_small', 20000000)];
      store.owned.add(_purchase('support_medium',
          token: 'old-cash', state: PurchaseStateWrapper.pending));
      // The server's view, as in production: the old cash payment is still
      // pending at Play; the new card payment is recorded.
      client.verifyByToken['old-cash'] = {
        'ok': false, 'consumed': false, 'already_recorded': false, 'pending': true,
      };
      final c = await pump(tester, const SupportScreen(), flag: true);
      c.read(supportBootProvider); // the app root started it at launch
      await tester.pump(Duration.zero);

      await tester.tap(find.text('دعم صغير'));
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      store.controller.add([_purchase('support_small', token: 'new-card')]);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump(Duration.zero);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(client.verified.map((v) => v.split(':')[1]),
          containsAll(['old-cash', 'new-card']));
      expect(find.text('نسأل الله أن يتقبّل منك 🤍 وصل دعمك.'), findsOneWidget);
      expect(find.text('الدفع قيد المعالجة، وسنؤكّده حين يكتمل.'), findsNothing);
    });

    testWidgets("an older purchase's update never clears the live spinner",
        (tester) async {
      store.products = [
        _product('support_small', 20000000),
        _product('support_medium', 60000000),
      ];
      final c = await pump(tester, const SupportScreen(), flag: true);
      // At launch, Play re-delivered last week's pending cash payment.
      c.read(supportCoordinatorProvider).start();
      store.controller.add([_purchase('support_small',
          token: 'cash-from-last-week',
          state: PurchaseStateWrapper.pending, restored: true)]);
      await tester.pump(Duration.zero);
      await tester.tap(find.text('دعم صغير'));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Re-delivered, another product, or a week-old purchase of the same
      // product — seen at launch, and now completing while this sheet is
      // open: none of them is this sheet's answer.
      store.controller.add([
        _purchase('support_medium', token: 'last-week', restored: true),
        _purchase('support_small', token: 'also-old', restored: true),
        _purchase('support_small', token: 'cash-from-last-week'),
      ]);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('نسأل الله أن يتقبّل منك 🤍 وصل دعمك.'), findsNothing);

      // The live answer.
      store.controller.add([_purchase('support_small', token: 'the-live-one')]);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.text('نسأل الله أن يتقبّل منك 🤍 وصل دعمك.'), findsOneWidget);
    });

    testWidgets('a pending payment started here is followed to its end',
        (tester) async {
      store.products = [_product('support_small', 20000000)];
      await pump(tester, const SupportScreen(), flag: true);
      await tester.tap(find.text('دعم صغير'));
      await tester.pump();
      store.controller.add([_purchase('support_small',
          token: 'fawry-1', state: PurchaseStateWrapper.pending)]);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('الدفع قيد المعالجة، وسنؤكّده حين يكتمل.'), findsOneWidget);

      // Paid at the kiosk; Play completes the same purchase.
      store.controller.add([_purchase('support_small', token: 'fawry-1')]);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('نسأل الله أن يتقبّل منك 🤍 وصل دعمك.'), findsOneWidget);
    });

    testWidgets('unpriced support makes the figure "about", and says why',
        (tester) async {
      // Item 4 (delta): rows Play has not priced yet are in no sum.
      store.products = [_product('support_small', 20000000)];
      client.transparency = {
        'month': '2026-10', 'cost_usd': 40.0, 'covered_usd': 34.0,
        'covered_pct': 85, 'supports': 6, 'unpriced': 2, 'breakdown': [],
      };
      await pump(tester, const SupportScreen(), flag: true);
      expect(find.text('غطّى الداعمون نحو 85٪'), findsOneWidget);
      expect(find.text('غطّى الداعمون 85٪'), findsNothing);
      expect(find.textContaining('بعض الدعم (2)'), findsOneWidget);
    });

    testWidgets('no declared cost: says what was given, no percentage (EN)',
        (tester) async {
      store.products = [_product('support_small', 20000000)];
      client.transparency = {
        'month': '2026-10', 'cost_usd': null, 'covered_usd': 1.7,
        'covered_pct': null, 'supports': 1, 'unpriced': 0, 'breakdown': [],
      };
      await pump(tester, const SupportScreen(),
          flag: true, locale: const Locale('en'));
      expect(find.text('Supporters gave \$1.70 this month'), findsOneWidget);
      expect(find.textContaining('covered'), findsNothing);
    });

    testWidgets('older server: no transparency card, the screen still works',
        (tester) async {
      store.products = [_product('support_small', 20000000)];
      await pump(tester, const SupportScreen(), flag: true);
      expect(find.textContaining('تكلفة المربّي'), findsNothing);
      expect(find.text('دعم صغير'), findsOneWidget);
    });
  });
}
