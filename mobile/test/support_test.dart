/// «ادعم المربّي» — the two-sided gate, the record-then-consume order, and the
/// transparency card.
///
/// The store is faked: what is under test is what the app does with each
/// answer it can get (no billing, no products, a purchase the server could or
/// could not record) — and that nothing is ever consumed before it is recorded.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
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

ProductDetails _product(String id, double price) => ProductDetails(
      id: id,
      title: '$id (Al-Murabbi)',
      description: '',
      price: 'EGP ${price.toStringAsFixed(2)}',
      rawPrice: price,
      currencyCode: 'EGP',
    );

PurchaseDetails _purchase(String id,
        {PurchaseStatus status = PurchaseStatus.purchased}) =>
    PurchaseDetails(
      productID: id,
      verificationData: PurchaseVerificationData(
        localVerificationData: '',
        serverVerificationData: 'token-$id',
        source: 'google_play',
      ),
      transactionDate: '0',
      status: status,
    );

class _FakeStore implements SupportStore {
  bool available = true;
  List<ProductDetails> products = [];
  int queries = 0;
  final consumed = <String>[];
  final bought = <String>[];
  final controller = StreamController<List<PurchaseDetails>>.broadcast();

  @override
  Future<bool> isAvailable() async => available;

  @override
  Future<List<ProductDetails>> queryProducts(Set<String> ids) async {
    queries++;
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
  Future<void> restore() async {}

  @override
  Future<void> consume(PurchaseDetails purchase) async =>
      consumed.add(purchase.productID);
}

class _FakeClient extends TgClient {
  Map<String, dynamic>? transparency;
  Object? verifyError;
  Map<String, dynamic> verifyResult = {
    'ok': true, 'consumed': true, 'already_recorded': false, 'status': 200,
  };
  final verified = <String>[];

  // The settings screen lists the children before it renders its rows.
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
    return verifyResult;
  }
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

  group('the gate', () {
    test('server flag off: hidden, and the store is never asked', () async {
      store.products = [_product('support_small', 10)];
      final c = container(flag: false);
      await c.read(appConfigProvider.future);
      expect(await c.read(supportProductsProvider.future), isEmpty);
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
        ..products = [_product('support_small', 10)];
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      expect(await c.read(supportProductsProvider.future), isEmpty);
      expect(c.read(supportVisibleProvider), isFalse);
    });

    test('flag on but the products were never created: hidden', () async {
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      expect(await c.read(supportProductsProvider.future), isEmpty);
      expect(c.read(supportVisibleProvider), isFalse);
    });

    test('flag on and products returned: shown, cheapest first', () async {
      store.products = [
        _product('support_large', 200),
        _product('support_small', 20),
        _product('support_medium', 60),
      ];
      final c = container(flag: true);
      await c.read(appConfigProvider.future);
      final products = await c.read(supportProductsProvider.future);
      expect(products.map((p) => p.id),
          ['support_small', 'support_medium', 'support_large']);
      expect(c.read(supportVisibleProvider), isTrue);
    });
  });

  group('record, then consume', () {
    SupportPurchaseHandler handler() => SupportPurchaseHandler(
          client: client,
          store: store,
          productIds: kDefaultSupportProductIds,
          productById: (id) => id == 'support_small'
              ? _product('support_small', 20)
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
        'ok': true, 'consumed': false, 'already_recorded': false, 'status': 200,
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
          await handler().handle(
              _purchase('support_small', status: PurchaseStatus.pending)),
          SupportOutcome.pending);
      expect(client.verified, isEmpty);
      client.verifyResult = {'ok': false, 'pending': true, 'status': 202};
      expect(await handler().handle(_purchase('support_small')),
          SupportOutcome.pending);
      expect(store.consumed, isEmpty);
    });

    test('a re-delivered purchase already thanked for stays quiet', () async {
      client.verifyResult = {
        'ok': true, 'consumed': true, 'already_recorded': true, 'status': 200,
      };
      expect(
          await handler().handle(
              _purchase('support_small', status: PurchaseStatus.restored)),
          isNull);
    });

    test("someone else's product is ignored", () async {
      expect(await handler().handle(_purchase('premium_unlock')), isNull);
      expect(client.verified, isEmpty);
    });
  });

  group('screens', () {
    Future<void> pump(WidgetTester tester, Widget home,
        {required bool flag, Locale locale = const Locale('ar')}) async {
      final c = container(flag: flag);
      await tester.pumpWidget(UncontrolledProviderScope(
        container: c,
        child: MaterialApp(
          locale: locale,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(body: home),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
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
      store.products = [_product('support_small', 20)];
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
      store.products = [_product('support_small', 20)];
      await pumpSettings(tester, flag: true);
      expect(find.text('ادعم المربّي'), findsOneWidget);
      await tester.tap(find.text('ادعم المربّي'));
      await tester.pumpAndSettle();
      expect(find.byType(SupportScreen), findsOneWidget);
      expect(find.text('دعم صغير'), findsOneWidget);
    });

    testWidgets('transparency with a declared cost shows the share',
        (tester) async {
      store.products = [
        _product('support_small', 20),
        _product('support_large', 200),
      ];
      client.transparency = {
        'enabled': true, 'month': '2026-10', 'cost_usd': 40.0,
        'covered_usd': 34.0, 'covered_pct': 85, 'supports': 4,
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

    testWidgets('no declared cost: says what was given, no percentage (EN)',
        (tester) async {
      store.products = [_product('support_small', 20)];
      client.transparency = {
        'enabled': true, 'month': '2026-10', 'cost_usd': null,
        'covered_usd': 1.7, 'covered_pct': null, 'supports': 1,
        'breakdown': [],
      };
      await pump(tester, const SupportScreen(),
          flag: true, locale: const Locale('en'));
      expect(find.text('Supporters gave \$1.70 this month'), findsOneWidget);
      expect(find.textContaining('covered'), findsNothing);
    });

    testWidgets('older server: no transparency card, the screen still works',
        (tester) async {
      store.products = [_product('support_small', 20)];
      await pump(tester, const SupportScreen(), flag: true);
      expect(find.textContaining('تكلفة المربّي'), findsNothing);
      expect(find.text('دعم صغير'), findsOneWidget);
    });
  });
}
