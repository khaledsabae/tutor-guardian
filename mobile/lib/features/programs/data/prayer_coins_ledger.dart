/// Credits Prayer Journey coins exactly once per mission (MOBILE_API §11.4.7).
///
/// There is no server coin ledger: the evening confirm answers with the coins
/// each confirmed prayer card is worth, and the device credits them. That list
/// is idempotent on the server — a retried batch (the first answer was lost on
/// a flaky connection) lists the same missions again — so the device keeps the
/// ids it has already paid and skips them. Without this, one dropped response
/// paid a child twice for the same prayer.
library;

import 'package:shared_preferences/shared_preferences.dart';

abstract final class PrayerCoinsLedger {
  static const _key = 'programs.credited_prayer_missions';

  /// Recent ids kept. A card expires after 48 h, so a retry older than a few
  /// hundred missions back cannot happen; the cap keeps the list small.
  static const keep = 500;

  /// The coins in [entries] not credited before, recorded as credited.
  ///
  /// Recorded before the caller credits them: if the app dies in between, a
  /// coin is lost rather than paid twice — the safer of the two for a reward
  /// a parent has to honour.
  static Future<int> takeNew(List<Map<String, dynamic>> entries) async {
    final prefs = await SharedPreferences.getInstance();
    final seen = [...?prefs.getStringList(_key)];
    final known = seen.toSet();
    var total = 0;
    for (final entry in entries) {
      final id = entry['mission_id'];
      final coins = (entry['coins'] as num?)?.toInt() ?? 0;
      if (id == null || coins <= 0) continue;
      if (!known.add('$id')) continue; // paid before, or twice in this batch
      seen.add('$id');
      total += coins;
    }
    if (seen.length > keep) seen.removeRange(0, seen.length - keep);
    await prefs.setStringList(_key, seen);
    return total;
  }
}
