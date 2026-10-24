/// Which story pages are told with their original painted picture, alive
/// (living_picture.dart) — and, on the sample pages, the regions the
/// narrator's words point the camera at.
///
/// Sample (2026-10-24, HOLD: dev freeze): maryam_toys only. Pages 2 and 5
/// have regions and cues; the other four drift and sparkle but have no
/// regions yet. Every other story keeps its paper-cut scene.
///
/// Regions are normalised to the 1024² painting; cue words are Arabic and
/// English in one list, matched by narration/word_cues.dart.
library;

import 'package:flutter/painting.dart';

import 'living_picture.dart';

String _art(String storyId, int page, [String suffix = '']) =>
    'assets/stories_art/${storyId}_$page$suffix.webp';

/// The living picture for page [index] (0-based) of [storyId], or null —
/// that page keeps its paper-cut scene.
LivingPicture? livingPictureFor(String storyId, int index) =>
    _catalog[storyId]?[index];

final Map<String, Map<int, LivingPicture>> _catalog = {
  'maryam_toys': {
    0: LivingPicture(image: _art('maryam_toys', 1)),
    // Fatimah looks at the new toys with longing; Maryam, afraid they will
    // break, hides her favourites behind her back.
    1: LivingPicture(
      image: _art('maryam_toys', 2),
      regions: const [
        PictureRegion(
          'fatimah',
          Rect.fromLTRB(.6, .2, .94, .95),
          cue: ['فاطم', 'fatimah'],
        ),
        PictureRegion(
          'the toys she longs for',
          Rect.fromLTRB(.48, .4, .7, .66),
          cue: ['العاب', 'toys'],
        ),
        PictureRegion(
          'maryam',
          Rect.fromLTRB(.14, .14, .5, .9),
          cue: ['مريم', 'maryam'],
        ),
        PictureRegion(
          'the toys she hides',
          Rect.fromLTRB(.12, .34, .5, .68),
          cue: ['اخفت', 'مفضل', 'hid', 'favourite'],
        ),
      ],
    ),
    2: LivingPicture(image: _art('maryam_toys', 3)),
    3: LivingPicture(image: _art('maryam_toys', 4)),
    // The box opens; a tall tower of coloured blocks, and laughter.
    4: LivingPicture(
      image: _art('maryam_toys', 5),
      ambient: PictureAmbient.sparkles,
      regions: const [
        PictureRegion(
          'maryam at ease',
          Rect.fromLTRB(.14, .26, .5, .82),
          cue: ['قلب', 'heart'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'maryam',
          Rect.fromLTRB(.14, .26, .5, .82),
          cue: ['مريم', 'maryam'],
        ),
        PictureRegion(
          'the box',
          Rect.fromLTRB(0, .72, .26, 1),
          cue: ['صندوق', 'box'],
        ),
        PictureRegion(
          'fatimah',
          Rect.fromLTRB(.56, .34, .9, .82),
          cue: ['فاطم', 'fatimah'],
        ),
        PictureRegion(
          'the tower of blocks',
          Rect.fromLTRB(.42, .06, .62, .84),
          cue: ['مكعب', 'برج', 'blocks', 'tower'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'laughing',
          Rect.fromLTRB(.16, .24, .86, .6),
          cue: ['=تضحكان', 'laughing'],
          burst: PictureBurst.hearts,
        ),
      ],
    ),
    5: LivingPicture(
      image: _art('maryam_toys', 6),
      ambient: PictureAmbient.sparkles,
    ),
  },
};
