/// `horizon_to_action_48h` — did a tap on the horizon lead to a parenting
/// act within two days? (عالم الأسرة, the «على الأفق» experiment's second
/// half: ≥15% of those who see the strip tap it, *and then act*.)
///
/// Counted on the phone because GA4 cannot join two events of one device
/// across days on its own. The last tap — a gate on «درب {الاسم}» or the
/// strip on Today — is kept (kind + time); the first parenting act logged
/// within 48 hours of it fires the event once and clears it. Worship is not
/// an act here, the same as for the lanterns.
library;

import 'package:shared_preferences/shared_preferences.dart';

import 'analytics.dart';

abstract final class HorizonAttribution {
  static const window = Duration(hours: 48);

  static const _kGate = 'tg.horizon.tap_gate';
  static const _kAt = 'tg.horizon.tap_at';

  /// The events that are parenting acts — the lanterns' own list, as the
  /// app logs them: a lesson finished, a question asked, a follow-up or a
  /// promise answered, a next step kept, praise sent.
  static const acts = {
    'lesson_completed',
    'chat_message_sent',
    'followup_answered',
    'promise_checked',
    'next_step_committed',
    'praise_sent',
  };

  /// Remember a tap on [gate] (a `GateKind.wire`, or `strip`).
  static Future<void> recordTap(String gate, {DateTime? now}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kGate, gate);
      await prefs.setInt(_kAt, (now ?? DateTime.now()).millisecondsSinceEpoch);
    } catch (_) {
      // analytics must never affect UX
    }
  }

  /// Called for every logged event; acts on [acts] only.
  static Future<void> onEvent(String name, {DateTime? now}) async {
    if (!acts.contains(name)) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final gate = prefs.getString(_kGate);
      final at = prefs.getInt(_kAt);
      if (gate == null || at == null) return;
      final since = (now ?? DateTime.now()).difference(
        DateTime.fromMillisecondsSinceEpoch(at),
      );
      await prefs.remove(_kGate);
      await prefs.remove(_kAt);
      if (since.isNegative || since > window) return;
      await Analytics.horizonToAction48h(gate, name, since.inHours);
    } catch (_) {
      // analytics must never affect UX
    }
  }
}
