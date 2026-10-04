/// «ادعم المربّي» — the two-sided gate, the transparency read, and the
/// purchase handler.
///
/// The surface is shown only when BOTH are true:
///  1. the server says so — `donations_enabled` in `/api/app-config`, which is
///     false unless `DONATIONS_ENABLED=true` and the Play verifier is set up;
///  2. the store returned at least one of the products. No Play Store (an
///     emulator, a de-Googled phone), no products created yet, billing down —
///     all mean the same thing: nothing to sell, so nothing is shown.
/// An older server has no such field, so it reads as off.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import '../../api/tg_client.dart';
import '../../main.dart' show appConfigProvider;
import '../../state/chat_notifier.dart' show tgClientProvider;
import 'support_store.dart';

const Set<String> kDefaultSupportProductIds = {
  'support_small',
  'support_medium',
  'support_large',
};

/// Verification aid, never shipped: a debug build started with
/// `--dart-define=SUPPORT_PREVIEW=true` shows the support screen when the
/// server flag is on even though the store has no products (an emulator has
/// no Play Store), so the transparency half can be walked on a device. The
/// `kDebugMode` term makes it a compile-time false in every release build.
const bool kSupportPreview =
    kDebugMode && bool.fromEnvironment('SUPPORT_PREVIEW');

/// Server half of the gate.
final donationsEnabledProvider = Provider<bool>((ref) {
  final cfg = ref.watch(appConfigProvider).valueOrNull;
  return cfg?['donations_enabled'] == true;
});

final donationProductIdsProvider = Provider<Set<String>>((ref) {
  final raw = ref.watch(appConfigProvider).valueOrNull?['donation_product_ids'];
  if (raw is List) {
    final ids = raw.whereType<String>().where((s) => s.isNotEmpty).toSet();
    if (ids.isNotEmpty) return ids;
  }
  return kDefaultSupportProductIds;
});

final supportStoreProvider = Provider<SupportStore>((ref) => PlaySupportStore());

/// Store half of the gate: the products Play actually returned, cheapest
/// first. The store is not even asked while the server flag is off.
final supportProductsProvider =
    FutureProvider<List<ProductDetails>>((ref) async {
  if (!ref.watch(donationsEnabledProvider)) return const [];
  final ids = ref.watch(donationProductIdsProvider);
  final store = ref.watch(supportStoreProvider);
  try {
    if (!await store.isAvailable()) return const [];
    final products = [...await store.queryProducts(ids)]
      ..sort((a, b) => a.rawPrice.compareTo(b.rawPrice));
    return products;
  } catch (_) {
    return const [];
  }
});

final supportVisibleProvider = Provider<bool>((ref) {
  if (kSupportPreview && ref.watch(donationsEnabledProvider)) return true;
  final products = ref.watch(supportProductsProvider).valueOrNull;
  return products != null && products.isNotEmpty;
});

/// This month's cost and coverage. Null on any failure — an older server
/// has no such endpoint, and the screen simply omits the card.
final supportTransparencyProvider =
    FutureProvider.autoDispose<Map<String, dynamic>?>((ref) async {
  try {
    return await ref.watch(tgClientProvider).fetchSupportTransparency();
  } catch (_) {
    return null;
  }
});

enum SupportOutcome { thanked, pending, retryLater, cancelled, error }

/// Turns one store update into a server call and an outcome to show.
///
/// The order is the whole point: verify and record on the server first, then
/// consume. A purchase is never consumed here unless the server said it was
/// recorded, and is left untouched when the server could not be reached, so
/// Play re-delivers it next time (or refunds it after three days).
class SupportPurchaseHandler {
  SupportPurchaseHandler({
    required this.client,
    required this.store,
    required this.productIds,
    required this.productById,
  });

  final TgClient client;
  final SupportStore store;
  final Set<String> productIds;
  final ProductDetails? Function(String id) productById;

  /// Null when there is nothing to tell the parent (someone else's product, or
  /// a re-delivered purchase that had already been thanked for).
  Future<SupportOutcome?> handle(PurchaseDetails p) async {
    if (!productIds.contains(p.productID)) return null;
    switch (p.status) {
      case PurchaseStatus.pending:
        return SupportOutcome.pending;
      case PurchaseStatus.canceled:
        return SupportOutcome.cancelled;
      case PurchaseStatus.error:
        return SupportOutcome.error;
      case PurchaseStatus.purchased:
      case PurchaseStatus.restored:
        final product = productById(p.productID);
        final Map<String, dynamic> res;
        try {
          res = await client.verifySupportPurchase(
            productId: p.productID,
            purchaseToken: p.verificationData.serverVerificationData,
            priceMicros:
                product == null ? null : (product.rawPrice * 1000000).round(),
            currency: product?.currencyCode,
          );
        } on TgApiError catch (e) {
          // 400: Play says this is not a purchase. Anything else (503, no
          // network, an older server without the endpoint) is retryable.
          return e.statusCode == 400
              ? SupportOutcome.error
              : SupportOutcome.retryLater;
        } catch (_) {
          return SupportOutcome.retryLater;
        }
        if (res['status'] == 202 || res['pending'] == true) {
          return SupportOutcome.pending;
        }
        if (res['ok'] != true) return SupportOutcome.error;
        if (res['consumed'] != true) {
          try {
            await store.consume(p);
          } catch (_) {
            // Recorded already; the next visit's restore retries the consume.
          }
        }
        final reDelivered =
            p.status == PurchaseStatus.restored && res['already_recorded'] == true;
        return reDelivered ? null : SupportOutcome.thanked;
    }
  }
}
