/// «ادعم المربّي» — the two-sided gate, the transparency read, the purchase
/// handler, and the app-wide coordinator that owns the purchase stream.
///
/// The surface is shown only when BOTH are true:
///  1. the server says so — `donations_enabled` in `/api/app-config`, which is
///     false unless `DONATIONS_ENABLED=true` and the Play service account
///     loads;
///  2. the store returned at least one of the products. No Play Store (an
///     emulator, a de-Googled phone), no products created yet, billing down —
///     all mean the same thing: nothing to sell, so nothing is shown.
/// An older server has no such field, so it reads as off.
library;

import 'dart:async';
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../api/tg_client.dart';
import '../../core/analytics.dart';
import '../../main.dart' show appConfigProvider;
import '../../state/chat_notifier.dart' show tgClientProvider;
import 'support_store.dart';

const Set<String> kDefaultSupportProductIds = {
  'support_small',
  'support_medium',
  'support_large',
};

/// Verification aid, never shipped: a debug build started with
/// `--dart-define=SUPPORT_PREVIEW=true` shows the support row when the server
/// flag is on even though the store has no products (an emulator has no Play
/// Store), so the transparency half can be walked on a device. The
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
///
/// autoDispose, so one failed query is not the answer for the rest of the
/// process: billing that was briefly unavailable — no network at launch, Play
/// services updating — is asked again the next time Settings opens, and on
/// every resume (see [SupportPurchaseCoordinator.onResume]).
final AutoDisposeFutureProvider<List<ProductDetails>> supportProductsProvider =
    FutureProvider.autoDispose<List<ProductDetails>>((ref) async {
  if (!ref.watch(donationsEnabledProvider)) return const [];
  final ids = ref.watch(donationProductIdsProvider);
  final store = ref.watch(supportStoreProvider);
  try {
    if (!await store.isAvailable()) return const [];
    final products = [...await store.queryProducts(ids)]
      ..sort((a, b) => a.rawPrice.compareTo(b.rawPrice));
    ref.read(supportCoordinatorProvider).rememberProducts(products);
    return products;
  } catch (_) {
    return const [];
  }
});

final supportVisibleProvider = Provider.autoDispose<bool>((ref) {
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
///
/// Every purchase on the stream is this app's, and this app sells nothing
/// else — so the product id is not filtered here. A product since dropped
/// from the server's list still has to reach the server, which recognises it
/// by its token.
class SupportPurchaseHandler {
  SupportPurchaseHandler({
    required this.client,
    required this.store,
    required this.productById,
  });

  final TgClient client;
  final SupportStore store;
  final ProductDetails? Function(String id) productById;

  /// Null when there is nothing to tell the parent: a re-delivered purchase
  /// that had already been thanked for, or a billing update with nothing in it.
  Future<SupportOutcome?> handle(PurchaseDetails p) async {
    // On Android a cancelled sheet and a billing error arrive as a bare
    // PurchaseDetails with productID '' and no token — still answers to the
    // tap that opened the sheet, so they are handled before anything that
    // needs a product or a token.
    switch (p.status) {
      case PurchaseStatus.canceled:
        return SupportOutcome.cancelled;
      case PurchaseStatus.error:
        return SupportOutcome.error;
      case PurchaseStatus.pending:
        return SupportOutcome.pending;
      case PurchaseStatus.purchased:
      case PurchaseStatus.restored:
        break;
    }
    final token = p.verificationData.serverVerificationData;
    if (token.isEmpty) return null; // an OK update that carried no purchase

    final product = productById(p.productID);
    final Map<String, dynamic> res;
    try {
      res = await client.verifySupportPurchase(
        productId: p.productID,
        purchaseToken: token,
        priceMicros:
            product == null ? null : (product.rawPrice * 1000000).round(),
        currency: product?.currencyCode,
      );
    } on TgApiError catch (e) {
      // 400: Play says this is not a purchase, or a product never sold. Any
      // other failure (503, no network, an older server without the
      // endpoint) is retryable — the purchase stays unconsumed for next time.
      return e.statusCode == 400
          ? SupportOutcome.error
          : SupportOutcome.retryLater;
    } catch (_) {
      return SupportOutcome.retryLater;
    }
    if (res['pending'] == true) return SupportOutcome.pending;
    if (res['ok'] != true) return SupportOutcome.error;
    if (res['consumed'] != true) {
      try {
        await store.consume(p);
      } catch (_) {
        // Recorded already; the next restore retries the consume.
      }
    }
    final reDelivered =
        p.status == PurchaseStatus.restored && res['already_recorded'] == true;
    return reDelivered ? null : SupportOutcome.thanked;
  }
}

/// The one listener on the store's purchase stream, for the life of the app.
///
/// A purchase does not end while the support screen is open. Cash and Fawry
/// payments complete hours later; a purchase the server could not verify must
/// be re-sent on a later launch. If only the screen listened, every one of
/// those arrived to no one — and Play refunds an unacknowledged purchase after
/// three days. So, as the in_app_purchase README asks, the stream is
/// subscribed from launch, once, and unfinished purchases are re-requested
/// ([SupportStore.restore]) at launch and on every resume.
///
/// Started only when the server has donations on (see [supportBootProvider]):
/// for everyone else the billing client is never touched. The support screen
/// only displays what arrives on [outcomes].
class SupportPurchaseCoordinator with WidgetsBindingObserver {
  SupportPurchaseCoordinator({
    required this.store,
    required this.clientOf,
    this.onResume,
    Future<void> Function(SupportOutcome outcome)? logOutcome,
    Future<SharedPreferences> Function()? prefs,
  })  : _logOutcome = logOutcome ?? _logToAnalytics,
        _prefs = prefs ?? SharedPreferences.getInstance;

  final SupportStore store;
  final TgClient Function() clientOf;

  /// Called on every resume before the restore — the products provider is
  /// invalidated here, so a transient billing failure is retried.
  final VoidCallback? onResume;

  final Future<void> Function(SupportOutcome outcome) _logOutcome;
  final Future<SharedPreferences> Function() _prefs;

  static const _kLogged = 'support.logged_outcomes';
  static const _kLoggedMax = 50;

  final _outcomes = StreamController<SupportOutcome?>.broadcast();
  final Map<String, ProductDetails> _products = {};
  StreamSubscription<List<PurchaseDetails>>? _sub;
  bool _started = false;
  bool _disposed = false;

  /// Updates are handled one at a time, in arrival order. A restore can land
  /// while a live purchase is still at the server; handled concurrently, the
  /// same token went out twice and the analytics dedupe raced itself.
  Future<void> _queue = Future<void>.value();

  /// One event per settled store update: an outcome to show, or null for
  /// "settled, nothing to say" — either way, any busy state can clear.
  Stream<SupportOutcome?> get outcomes => _outcomes.stream;

  bool get started => _started;

  /// Idempotent. The first call subscribes and asks Play for anything left
  /// unfinished; later calls do nothing.
  void start() {
    if (_started || _disposed) return;
    _started = true;
    try {
      _sub = store.purchaseStream.listen(
        (purchases) => _queue = _queue
            .then((_) => _onPurchases(purchases))
            .catchError((Object _) {}),
        onError: (_) {},
      );
    } catch (_) {
      // No billing on this device; nothing will ever arrive.
    }
    WidgetsBinding.instance.addObserver(this);
    unawaited(_restore());
  }

  void rememberProducts(List<ProductDetails> products) {
    for (final p in products) {
      _products[p.id] = p;
    }
  }

  Future<bool> buy(ProductDetails product) => store.buy(product);

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed || !_started || _disposed) return;
    onResume?.call();
    unawaited(_restore());
  }

  Future<void> _restore() async {
    try {
      await store.restore();
    } catch (_) {
      // Billing unavailable right now; the next resume asks again.
    }
  }

  Future<void> _onPurchases(List<PurchaseDetails> purchases) async {
    if (_disposed) return;
    final handler = SupportPurchaseHandler(
      client: clientOf(),
      store: store,
      productById: (id) => _products[id],
    );
    for (final p in purchases) {
      SupportOutcome? outcome;
      try {
        outcome = await handler.handle(p);
      } catch (_) {
        outcome = SupportOutcome.retryLater;
      }
      if (outcome != null) await _log(p, outcome);
      if (!_disposed) _outcomes.add(outcome);
    }
  }

  /// One `support_outcome` per purchase and outcome — not one per resume.
  ///
  /// A pending cash payment or a purchase the server cannot reach yet is
  /// re-delivered on every launch and every resume; logging each of those
  /// would count one parent as dozens. Keyed by a digest of the token, never
  /// the token itself. A cancel or a billing error carries no token, and each
  /// is a separate tap by the parent, so those are always logged.
  Future<void> _log(PurchaseDetails p, SupportOutcome outcome) async {
    final token = p.verificationData.serverVerificationData;
    if (token.isEmpty) {
      await _logOutcome(outcome);
      return;
    }
    final key =
        '${sha256.convert(utf8.encode(token)).toString().substring(0, 16)}:${outcome.name}';
    try {
      final prefs = await _prefs();
      final seen = prefs.getStringList(_kLogged) ?? const <String>[];
      if (seen.contains(key)) return;
      await _logOutcome(outcome);
      final next = [...seen, key];
      await prefs.setStringList(
          _kLogged,
          next.length > _kLoggedMax
              ? next.sublist(next.length - _kLoggedMax)
              : next);
    } catch (_) {
      await _logOutcome(outcome);
    }
  }

  static Future<void> _logToAnalytics(SupportOutcome outcome) =>
      Analytics.supportOutcome(switch (outcome) {
        SupportOutcome.thanked => 'thanked',
        SupportOutcome.pending => 'pending',
        SupportOutcome.retryLater => 'retry_later',
        SupportOutcome.cancelled => 'cancelled',
        SupportOutcome.error => 'error',
      });

  void dispose() {
    _disposed = true;
    _sub?.cancel();
    if (_started) WidgetsBinding.instance.removeObserver(this);
    _outcomes.close();
  }
}

/// Kept alive for the whole process — one subscription, ever.
final Provider<SupportPurchaseCoordinator> supportCoordinatorProvider =
    Provider<SupportPurchaseCoordinator>((ref) {
  final coordinator = SupportPurchaseCoordinator(
    store: ref.watch(supportStoreProvider),
    clientOf: () => ref.read(tgClientProvider),
    onResume: () => ref.invalidate(supportProductsProvider),
  );
  ref.onDispose(coordinator.dispose);
  return coordinator;
});

/// Watched from the app root. Starts the coordinator the first time the
/// server says donations are on — and never touches billing otherwise.
final supportBootProvider = Provider<void>((ref) {
  if (ref.watch(donationsEnabledProvider)) {
    ref.read(supportCoordinatorProvider).start();
  }
});
