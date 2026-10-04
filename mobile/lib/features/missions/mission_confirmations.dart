/// The evening confirmation, independent of the screen that starts it.
///
/// Two ways a confirmed prayer card's coins used to be lost for good:
///  * the parent left the screen — back, or the 21:00 `/missions` push
///    unwinding to the root — while the request was in flight: the answer
///    came back to a disposed screen, after its missions were already marked
///    as paid;
///  * the answer never arrived although the server applied the batch: the
///    cards were no longer pending, so reopening the screen offered nothing to
///    retry with.
///
/// So a batch is written to an outbox *before* it is sent, resent on the next
/// open or send — the server answers a retry with the same `coins` for the
/// missions an earlier attempt confirmed (MOBILE_API §11.4.7) — and each
/// mission leaves the outbox only once its answer has been paid out. Paying
/// goes through [CoinsService.creditConfirmedMissions], which pays each
/// mission once.
///
/// Three rules keep the outbox from paying twice, losing a batch, or blocking
/// every later evening:
///  * **One delivery at a time.** A send and a flush (the screen reopened by
///    the 21:00 push while a send is in flight) are chained, never
///    interleaved; the second finds what the first left.
///  * **Only what was answered leaves the outbox.** Never the whole of it: a
///    batch whose answer was lost stays until it is delivered.
///  * **The waiting batch travels on its own,** in chunks the server accepts
///    (200 items), and a refusal that cannot change (400/404/409/422) drops it
///    — recorded — instead of resending it, merged into every new batch,
///    forever.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../api/tg_client.dart';
import '../coins/coins_service.dart';

/// What one delivery settled, and the coins it actually paid.
typedef MissionConfirmResult = ({int settled, int coins});

abstract final class MissionConfirmations {
  static const _outboxKey = 'missions.confirm_outbox';

  /// The server's limit per call (`MissionConfirmIn.items`, max_length 200).
  static const maxBatch = 200;

  /// Where a dropped batch is reported. Crashlytics in the app; a test can
  /// listen in.
  @visibleForTesting
  static void Function(Object error, StackTrace stack) reportDropped =
      _reportToCrashlytics;

  /// The end of the deliveries queued so far; null when none is running.
  /// Sends and flushes run one after another, each after the one before it.
  ///
  /// Null rather than a completed future when idle: a completed future keeps
  /// the zone it was made in, and chaining onto it later schedules there.
  static Future<void>? _tail;

  /// Tests only: forget a delivery a test left hanging.
  @visibleForTesting
  static void resetForTest() => _tail = null;

  static Future<T> _oneAtATime<T>(Future<T> Function() task) {
    final before = _tail;
    final run = before == null ? Future.sync(task) : before.then((_) => task());
    final tail = run.then<void>((_) {}, onError: (Object _) {});
    _tail = tail;
    unawaited(tail.then((_) {
      if (identical(_tail, tail)) _tail = null; // nothing queued behind it
    }));
    return run;
  }

  /// The decisions whose answer has not been processed yet.
  static Future<List<Map<String, dynamic>>> outbox() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_outboxKey);
    if (raw == null || raw.isEmpty) return const [];
    try {
      return (jsonDecode(raw) as List<dynamic>)
          .whereType<Map<dynamic, dynamic>>()
          .map((e) => Map<String, dynamic>.from(e))
          .where((e) => e['mission_id'] is int)
          .toList();
    } catch (_) {
      await prefs.remove(_outboxKey); // unreadable: nothing to resend
      return const [];
    }
  }

  /// Sends [items] (`{mission_id, confirmed}`): first, on its own, anything an
  /// earlier lost answer left in the outbox; then these. Pays the coins.
  ///
  /// Throws what a request threw on a failure that may pass (the network, the
  /// server); the outbox then keeps what was not answered for the next open or
  /// send. Needs no widget: safe to finish after the screen that started it
  /// is gone.
  static Future<MissionConfirmResult> send(
    TgClient client,
    List<Map<String, dynamic>> items, {
    CoinsService? coins,
  }) => _oneAtATime(() => _send(client, items, coins ?? CoinsService.instance));

  /// Resends what a lost answer left behind. Null when there was nothing.
  static Future<MissionConfirmResult?> flush(TgClient client, {CoinsService? coins}) =>
      _oneAtATime(() async {
        final waiting = await outbox();
        if (waiting.isEmpty) return null;
        return _deliver(client, waiting, coins ?? CoinsService.instance, waiting: true);
      });

  static Future<MissionConfirmResult> _send(
    TgClient client,
    List<Map<String, dynamic>> items,
    CoinsService coins,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    final fresh = {for (final i in items) i['mission_id']};
    // A decision made now replaces an older one for the same card.
    final waiting = [
      for (final w in await outbox())
        if (!fresh.contains(w['mission_id'])) w,
    ];
    await _save(prefs, [...waiting, ...items]); // before anything is sent

    var settled = 0;
    var paid = 0;
    if (waiting.isNotEmpty) {
      final r = await _deliver(client, waiting, coins, waiting: true);
      settled += r.settled;
      paid += r.coins;
    }
    if (items.isNotEmpty) {
      final r = await _deliver(client, items, coins, waiting: false);
      settled += r.settled;
      paid += r.coins;
    }
    return (settled: settled, coins: paid);
  }

  /// Sends [entries] in chunks the server accepts, pays each answer, and lets
  /// each answered chunk leave the outbox.
  ///
  /// A failure that may pass stops here and is rethrown, the rest staying in
  /// the outbox. A refusal that cannot change drops its chunk and is recorded;
  /// for tonight's own decisions ([waiting] false) it is also rethrown, so
  /// the parent sees it. (A stale id is not such a refusal: the server answers
  /// 200 and simply settles nothing for it.)
  static Future<MissionConfirmResult> _deliver(
    TgClient client,
    List<Map<String, dynamic>> entries,
    CoinsService coins, {
    required bool waiting,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    var settled = 0;
    var paid = 0;
    TgApiError? refused;
    StackTrace? refusedAt;
    for (var i = 0; i < entries.length; i += maxBatch) {
      final chunk = entries.sublist(i, math.min(i + maxBatch, entries.length));
      final ids = {for (final e in chunk) e['mission_id']};
      try {
        final answer = await client.settleMissions(chunk);
        paid += await coins.creditConfirmedMissions(answer.coins);
        settled += answer.settled;
        await _forget(prefs, ids);
      } on TgApiError catch (e, stack) {
        if (!_permanent(e)) rethrow;
        await _forget(prefs, ids);
        reportDropped(e, stack);
        refused ??= e;
        refusedAt ??= stack;
      }
    }
    if (refused != null && !waiting) {
      Error.throwWithStackTrace(refused, refusedAt!);
    }
    return (settled: settled, coins: paid);
  }

  /// A refusal that resending cannot change.
  static bool _permanent(TgApiError e) =>
      const {400, 404, 409, 422}.contains(e.statusCode);

  /// Removes [ids] from the outbox — only those.
  static Future<void> _forget(SharedPreferences prefs, Set<Object?> ids) async {
    await _save(prefs, [
      for (final e in await outbox())
        if (!ids.contains(e['mission_id'])) e,
    ]);
  }

  static Future<void> _save(SharedPreferences prefs, List<Map<String, dynamic>> entries) async {
    if (entries.isEmpty) {
      await prefs.remove(_outboxKey);
    } else {
      await prefs.setString(_outboxKey, jsonEncode(entries));
    }
  }

  static void _reportToCrashlytics(Object error, StackTrace stack) {
    try {
      unawaited(FirebaseCrashlytics.instance
          .recordError(error, stack,
              reason: 'mission confirmations dropped after a permanent refusal',
              fatal: false)
          .catchError((Object _) {}));
    } catch (_) {
      // No Firebase (tests, a broken install): the drop itself still happens.
    }
  }
}
