/// «أعطال اتلقت في الطريق» — the milestone badge asset builder.
///
/// The keys already start with `first_` (`first_prayer`), and the builder
/// prepended another one, producing `milestone_first_first_prayer.webp` — a
/// path that matches no file, so every one of the three illustrations fell
/// back to a bare emoji. And the fallback directory (`assets/images/
/// milestones/`) does not exist at all. Pinned here: every asset the builder
/// can name exists in the bundle, and nothing points at the dead directory.
library;

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/journey/data/journey_milestones.dart';

const _brandedKeys = [
  'first_prayer',
  'first_surah',
  'first_fast',
  'keeps_prayer',
  'quran_khatma',
  'shahada',
  'first_dua',
  'good_manner',
  'helped_others',
];

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('the three "first" milestones build the asset names that exist',
      () async {
    expect(milestoneBadgeAsset('first_prayer'),
        'assets/images/generated/milestone_first_prayer.webp');
    expect(milestoneBadgeAsset('first_surah'),
        'assets/images/generated/milestone_first_surah.webp');
    expect(milestoneBadgeAsset('first_fast'),
        'assets/images/generated/milestone_first_fast.webp');
  });

  test('every branded milestone asset the builder names is in the bundle',
      () async {
    for (final key in _brandedKeys) {
      final asset = milestoneBadgeAsset(key);
      expect(asset, isNotNull, reason: '$key is a badge milestone key');
      expect(asset!.startsWith('assets/images/generated/'), isTrue,
          reason: '$key must resolve into the generated set');
      await rootBundle.load(asset); // throws if the file is not shipped
    }
  });

  test('a key outside the badge set has no illustration (emoji shows)',
      () async {
    expect(milestoneBadgeAsset('dev_sits_alone'), isNull);
  });
}
