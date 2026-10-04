/// The store side of «ادعم المربّي» — a thin seam over `in_app_purchase`.
///
/// Why Play Billing at all, for a free app: Google Play's Payments policy
/// requires its billing system for payments made inside an app, and keeps it
/// *out* only for "tax exempt donations" — which needs a registered tax-exempt
/// organisation. The developer is an individual, so support is sold as
/// consumable in-app products that unlock nothing. Citation and the server
/// half: `backend/app/services/donations.py`.
///
/// Consumables are consumed by the server after it verifies them, so the same
/// family can support again. If the server could not consume, [consume] does
/// it here; if the server could not even verify (offline, Play down), the
/// purchase is left untouched — Play re-delivers it through [restore] on the
/// next visit, and refunds it automatically after three days if it is never
/// acknowledged. Nothing is ever consumed without being recorded first.
library;

import 'dart:async';

import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_android/in_app_purchase_android.dart';

abstract class SupportStore {
  Future<bool> isAvailable();
  Future<List<ProductDetails>> queryProducts(Set<String> ids);
  Stream<List<PurchaseDetails>> get purchaseStream;
  Future<bool> buy(ProductDetails product);

  /// Re-delivers owned, unconsumed purchases on [purchaseStream] — how a
  /// purchase the server could not verify last time gets another try.
  Future<void> restore();

  /// Consume locally, for when the server recorded but could not consume.
  Future<void> consume(PurchaseDetails purchase);
}

class PlaySupportStore implements SupportStore {
  InAppPurchase get _iap => InAppPurchase.instance;

  @override
  Future<bool> isAvailable() => _iap.isAvailable();

  @override
  Future<List<ProductDetails>> queryProducts(Set<String> ids) async {
    final res = await _iap.queryProductDetails(ids);
    return res.productDetails;
  }

  @override
  Stream<List<PurchaseDetails>> get purchaseStream => _iap.purchaseStream;

  @override
  Future<bool> buy(ProductDetails product) => _iap.buyConsumable(
        purchaseParam: PurchaseParam(productDetails: product),
        // The server consumes after verifying. Auto-consume would spend the
        // purchase before anyone recorded it.
        autoConsume: false,
      );

  @override
  Future<void> restore() => _iap.restorePurchases();

  @override
  Future<void> consume(PurchaseDetails purchase) async {
    final android =
        _iap.getPlatformAddition<InAppPurchaseAndroidPlatformAddition>();
    await android.consumePurchase(purchase);
  }
}
