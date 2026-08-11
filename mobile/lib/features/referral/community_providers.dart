/// Public aggregate community counts — «X أب وأمّ يربّون بثقة معنا».
///
/// A provider rather than a fetch inside the widget, because two surfaces show
/// this now (Home and the invite screen) and they must not each hit the network
/// for the same number. Riverpod keeps one in-flight request and one result.
///
/// No PII: the endpoint returns aggregates only.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/chat_notifier.dart';

/// How many families the community must hold before we say so out loud.
///
/// Weak social proof is worse than none — "٤ آباء يربّون معنا" tells a parent
/// they arrived somewhere empty.
const int kMinFamiliesForProof = 10;

/// Families on the app, or null when the count is unknown or too small to show.
///
/// Errors resolve to null rather than propagating: this is a reassurance line,
/// and no surface should show an error where a warm sentence was meant to be.
final communityFamiliesProvider = FutureProvider<int?>((ref) async {
  try {
    final stats = await ref.watch(tgClientProvider).getCommunityStats();
    final families = (stats['families'] as num?)?.toInt() ?? 0;
    return families >= kMinFamiliesForProof ? families : null;
  } catch (_) {
    return null;
  }
});
