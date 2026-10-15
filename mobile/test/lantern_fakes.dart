/// Test helpers for «قناديل الأسبوع» (MOBILE_API §12): the JSON the server
/// sends for a week, built around the phone's own clock.
library;

/// Monday of the local week [now] is in.
DateTime mondayOf(DateTime now) => DateTime(now.year, now.month, now.day)
    .subtract(Duration(days: now.weekday - DateTime.monday));

String dateWire(DateTime d) => '${d.year.toString().padLeft(4, '0')}-'
    '${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// One act: its kind, the local day of the week (0 = Monday) and hour, and
/// an optional title.
typedef FakeAct = ({String kind, int day, int hour, String? title});

FakeAct act(String kind, int day, {int hour = 10, String? title}) =>
    (kind: kind, day: day, hour: hour, title: title);

/// `GET /api/family/week` for the week of [now] (default: this week).
Map<String, dynamic> familyWeekJson({
  List<FakeAct> acts = const [],
  int litWeeksTotal = 3,
  DateTime? now,
}) {
  final monday = mondayOf(now ?? DateTime.now());
  return {
    'week_start': dateWire(monday),
    'acts': [
      for (final a in acts)
        {
          'kind': a.kind,
          'at': DateTime(monday.year, monday.month, monday.day + a.day, a.hour)
              .toUtc()
              .toIso8601String(),
          'child_id': a.kind == 'question' ? null : 12,
          'title': a.title,
        },
    ],
    'lit_this_week': acts.isNotEmpty,
    'lit_weeks_total': litWeeksTotal,
    'last_8': [
      for (var w = 7; w >= 0; w--)
        {
          'week_start': dateWire(monday.subtract(Duration(days: 7 * w))),
          'lit': w == 0 ? acts.isNotEmpty : w.isEven,
        },
    ],
  };
}
