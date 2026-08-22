/// Working out which timezone "6 AM" means.
///
/// `tz.initializeTimeZones()` loads the database. It does **not** set
/// `tz.local`, which stays UTC until something calls `setLocalLocation`.
/// Nothing did, so `TZDateTime(tz.local, y, m, d, 6)` meant six in the morning
/// UTC for every user on earth, and the daily reminder landed wherever that
/// fell: 9am in Riyadh, 1pm in Jakarta, 2am on the US east coast, and 11pm the
/// previous evening in California. The count was right — fourteen days queued,
/// every time — which is why it read as working.
///
/// The resolution is split out here, away from the plugin and the platform
/// channel, so the part that can be wrong can also be tested.
library;

import 'package:timezone/timezone.dart' as tz;

/// The location whose local time the reminder should be scheduled in.
///
/// [ianaName] is the device's zone id (`Asia/Riyadh`) when the platform gave
/// one. [deviceOffset] is `DateTime.now().timeZoneOffset`, used as the fallback
/// signal.
///
/// Resolution order, and why:
///
///  1. **The name**, when the database knows it. It carries DST rules, so a
///     reminder set in January is still correct in July.
///  2. **A zone with the same current offset**, when the name is missing or
///     unknown. Loses future DST transitions — the next reschedule fixes that,
///     and the app reschedules on every launch — but it puts the notification
///     in the right part of the user's day today, which is the whole point.
///  3. **UTC**, only when even the offset matches nothing. Same behaviour as
///     the bug, reached only when there is genuinely no information.
///
/// Step 2 is not paranoia about typos. `getLocalTimezone` can return an id the
/// bundled database has not got — a zone added or renamed since this build's
/// `timezone` package was published — and without the fallback that returns
/// silently to UTC, which is exactly the failure this file exists to end.
tz.Location resolveLocalLocation(String? ianaName, Duration deviceOffset) {
  if (ianaName != null && ianaName.trim().isNotEmpty) {
    try {
      return tz.getLocation(ianaName.trim());
    } catch (_) {
      // Unknown to this build's database. Fall through to the offset.
    }
  }

  final wanted = deviceOffset.inMilliseconds;
  if (wanted == 0) return tz.UTC;

  tz.Location? match;
  for (final location in tz.timeZoneDatabase.locations.values) {
    if (location.currentTimeZone.offset != wanted) continue;
    // Prefer a region/city id over the legacy aliases (`Etc/GMT-3`, `EST`)
    // that share an offset — the named zone is likelier to carry sane DST
    // rules if this location ends up being used for more than today.
    if (location.name.contains('/') && !location.name.startsWith('Etc/')) {
      return location;
    }
    match ??= location;
  }
  return match ?? tz.UTC;
}
