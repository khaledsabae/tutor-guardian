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
/// So a batch is written to an outbox *before* it is sent, resent first on the
/// next open or send — the server answers a retry with the same `coins` for the
/// missions an earlier attempt confirmed (MOBILE_API §11.4.7) — and cleared
/// only once an answer has been paid out. Paying goes through
/// [CoinsService.creditConfirmedMissions], which pays each mission once.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../../api/tg_client.dart';
import '../coins/coins_service.dart';

/// What one round trip settled, and the coins it actually paid.
typedef MissionConfirmResult = ({int settled, int coins});

abstract final class MissionConfirmations {
  static const _outboxKey = 'missions.confirm_outbox';

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

  /// Sends [items] (`{mission_id, confirmed}`) with anything an earlier, lost
  /// answer left in the outbox, then pays the coins.
  ///
  /// Throws what the request threw; the outbox then keeps the batch for the
  /// next open or send. Needs no widget: safe to finish after the screen that
  /// started it is gone.
  static Future<MissionConfirmResult> send(
    TgClient client,
    List<Map<String, dynamic>> items, {
    CoinsService? coins,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final waiting = await outbox();
    final fresh = {for (final i in items) i['mission_id']};
    // A decision made now wins over an older one for the same card.
    final batch = [
      ...items,
      for (final w in waiting)
        if (!fresh.contains(w['mission_id'])) w,
    ];
    if (batch.isEmpty) return (settled: 0, coins: 0);
    await prefs.setString(_outboxKey, jsonEncode(batch)); // before sending
    final answer = await client.settleMissions(batch);
    final paid = await (coins ?? CoinsService.instance)
        .creditConfirmedMissions(answer.coins);
    await prefs.remove(_outboxKey);
    return (settled: answer.settled, coins: paid);
  }

  /// Resends what a lost answer left behind. Null when there was nothing.
  static Future<MissionConfirmResult?> flush(TgClient client, {CoinsService? coins}) async {
    if ((await outbox()).isEmpty) return null;
    return send(client, const [], coins: coins);
  }
}
