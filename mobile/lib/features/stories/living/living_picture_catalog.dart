/// Which stories are told with their painted pictures, alive
/// (living_picture.dart) — and, page by page, the things in each picture the
/// narrator's words point the camera at.
///
/// A story is here only when every one of its pages has a real painting in
/// docs/stories/ (served by the backend, the same files the reader showed
/// before the paper-cut scenes). Five stories still have placeholder frames
/// instead of paintings there (aisha_permission, bilal_forgiveness,
/// fatima_parents, yaseen_creation, and hamza_truth pages 4–6): they keep
/// their paper-cut scenes, and so does any story the server adds before the
/// app knows it. The paper-cut scene is also the fallback when a painting
/// cannot be loaded (offline).
///
/// Regions are normalised to the 1024² painting. Cue words are Arabic and
/// English in one list (narration/word_cues.dart); every word here is one the
/// page's recording actually says in at least one language — pinned against
/// the real manifests in test/living_picture_test.dart.
library;

import 'package:flutter/painting.dart';

import 'living_picture.dart';

String _page(String storyId, int page) => 'docs/stories/${storyId}_$page.png';

/// The living picture for page [index] (0-based) of [storyId], or null —
/// that story keeps its paper-cut scenes.
LivingPicture? livingPictureFor(String storyId, int index) {
  final pages = _catalog[storyId];
  if (pages == null || index < 0 || index >= pages.length) return null;
  return pages[index];
}

/// The painted cover of a living story, or null.
String? livingCoverFor(String storyId) =>
    _catalog.containsKey(storyId) ? 'docs/stories/${storyId}_cover.png' : null;

/// The stories told with their paintings.
Iterable<String> get livingStories => _catalog.keys;

final Map<String, List<LivingPicture>> _catalog = {
  // يوسف وغرسة الأمل — Yusuf and the Seed of Hope
  'hope_sprout': [
    LivingPicture(
      image: _page('hope_sprout', 1),
      regions: [
        PictureRegion(
          'father',
          Rect.fromLTRB(0.5, 0.15, 0.9, 0.9),
          cue: ['والده', 'والدي', 'father'],
        ),
        PictureRegion(
          'yusuf',
          Rect.fromLTRB(0.22, 0.28, 0.48, 0.85),
          cue: ['يوسف', 'yusuf'],
        ),
        PictureRegion(
          'the golden seed',
          Rect.fromLTRB(0.38, 0.48, 0.6, 0.65),
          cue: ['بذر', 'seed'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the garden',
          Rect.fromLTRB(0, 0.55, 1, 1),
          cue: ['طبيع', 'nature'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('hope_sprout', 2),
      regions: [
        PictureRegion(
          'yusuf',
          Rect.fromLTRB(0.25, 0.15, 0.7, 0.8),
          cue: ['يوسف', 'yusuf'],
        ),
        PictureRegion(
          'the pot of earth',
          Rect.fromLTRB(0.48, 0.62, 0.72, 0.9),
          cue: ['تراب', 'بذر', 'soil', 'seed'],
        ),
        PictureRegion(
          'the watering can',
          Rect.fromLTRB(0.62, 0.48, 0.86, 0.7),
          cue: ['سقا', 'watered'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the trowel',
          Rect.fromLTRB(0.3, 0.78, 0.5, 0.95),
          cue: ['حفر', 'dug'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('hope_sprout', 3),
      regions: [
        PictureRegion(
          'yusuf, sad',
          Rect.fromLTRB(0.25, 0.35, 0.62, 0.95),
          cue: ['يوسف', 'yusuf', 'حزين', 'sad'],
        ),
        PictureRegion(
          'his father',
          Rect.fromLTRB(0.5, 0.05, 0.98, 0.95),
          cue: ['والده', 'father', 'ضاحك', 'laughed'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('hope_sprout', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'yusuf',
          Rect.fromLTRB(0.05, 0.3, 0.6, 0.95),
          cue: ['يوسف', 'yusuf'],
        ),
        PictureRegion(
          'the green shoot',
          Rect.fromLTRB(0.5, 0.4, 0.82, 0.98),
          cue: ['برعم', 'shoot'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the morning sun',
          Rect.fromLTRB(0.4, 0, 0.9, 0.32),
          cue: ['شمس', 'sun'],
        ),
        PictureRegion(
          'yusuf happy',
          Rect.fromLTRB(0.2, 0.3, 0.55, 0.65),
          cue: ['فرح', 'happy'],
          burst: PictureBurst.hearts,
        ),
      ],
    ),
  ],
  // أنس والهر الصغير — Anas and the Little Cat
  'kitten_kindness': [
    LivingPicture(
      image: _page('kitten_kindness', 1),
      regions: [
        PictureRegion(
          'anas',
          Rect.fromLTRB(0.58, 0.33, 0.84, 0.85),
          cue: ['انس', 'anas', 'مدرس', 'school'],
        ),
        PictureRegion(
          'the old tree',
          Rect.fromLTRB(0, 0, 0.55, 0.85),
          cue: ['شجر', 'tree'],
        ),
        PictureRegion(
          'the kitten',
          Rect.fromLTRB(0.28, 0.48, 0.5, 0.72),
          cue: ['صوت', 'هر', 'sound', 'cat'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('kitten_kindness', 2),
      regions: [
        PictureRegion(
          'the kitten',
          Rect.fromLTRB(0.33, 0.52, 0.62, 0.87),
          cue: ['مخلوق', 'creature', 'animals'],
        ),
        PictureRegion(
          'anas',
          Rect.fromLTRB(0.5, 0.15, 0.95, 0.85),
          cue: ['انس', 'anas'],
        ),
        PictureRegion(
          'anas feels for it',
          Rect.fromLTRB(0.55, 0.15, 0.9, 0.5),
          cue: ['شفق', 'رحم', 'pity', 'mercy'],
          burst: PictureBurst.hearts,
        ),
      ],
    ),
    LivingPicture(
      image: _page('kitten_kindness', 3),
      regions: [
        PictureRegion(
          'anas',
          Rect.fromLTRB(0.4, 0.05, 0.95, 0.85),
          cue: ['انس', 'anas'],
        ),
        PictureRegion(
          'the bowl of water',
          Rect.fromLTRB(0.16, 0.7, 0.38, 0.9),
          cue: ['وعاء', 'bowl'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the cloth',
          Rect.fromLTRB(0.4, 0.55, 0.66, 0.85),
          cue: ['منديل', 'مسح', 'cloth', 'wiped'],
        ),
        PictureRegion(
          'the kitten',
          Rect.fromLTRB(0.2, 0.55, 0.56, 0.85),
          cue: ['هر', 'cat'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('kitten_kindness', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the kitten',
          Rect.fromLTRB(0.08, 0.45, 0.52, 0.95),
          cue: ['هر', 'cat', 'صوت', 'purr'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'anas',
          Rect.fromLTRB(0.42, 0.1, 0.85, 0.95),
          cue: ['انس', 'anas'],
        ),
        PictureRegion(
          'his happy heart',
          Rect.fromLTRB(0.42, 0.1, 0.8, 0.5),
          cue: ['قلب', 'سرور', 'heart', 'joy'],
          burst: PictureBurst.hearts,
        ),
      ],
    ),
  ],
  // ليلى ونجمتها الصغيرة — Layla and Her Little Star
  'layla_star': [
    LivingPicture(
      image: _page('layla_star', 1),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'layla',
          Rect.fromLTRB(0.2, 0.2, 0.65, 0.9),
          cue: ['ليلي', 'layla'],
        ),
        PictureRegion(
          'the starry sky',
          Rect.fromLTRB(0.4, 0.05, 0.95, 0.75),
          cue: ['سماء', 'نجوم', 'sky', 'stars'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
    LivingPicture(
      image: _page('layla_star', 2),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the little star',
          Rect.fromLTRB(0.62, 0, 0.98, 0.42),
          cue: ['نجم', 'star'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'layla',
          Rect.fromLTRB(0.3, 0.25, 0.56, 0.72),
          cue: ['ليلي', 'layla'],
        ),
        PictureRegion(
          'her bed',
          Rect.fromLTRB(0.22, 0.5, 0.82, 0.92),
          cue: ['سرير', 'bed'],
        ),
        PictureRegion(
          'her mother',
          Rect.fromLTRB(0.5, 0.15, 0.86, 0.95),
          cue: ['والدت', 'mother'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('layla_star', 3),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the dream cloud',
          Rect.fromLTRB(0.12, 0.05, 0.95, 0.55),
          cue: ['سحاب', 'نجم', 'clouds', 'star'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'layla',
          Rect.fromLTRB(0.35, 0.45, 0.82, 0.92),
          cue: ['ليلي', 'layla'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('layla_star', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the stars in the window',
          Rect.fromLTRB(0, 0.05, 0.45, 0.62),
          cue: ['نجوم', 'كون', 'stars', 'universe'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'layla',
          Rect.fromLTRB(0.45, 0.38, 0.9, 0.75),
          cue: ['ليلي', 'layla'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('layla_star', 5),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'her kitten',
          Rect.fromLTRB(0.08, 0.22, 0.42, 0.5),
          cue: ['قط', 'kitten'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'mother\'s food',
          Rect.fromLTRB(0.32, 0.18, 0.66, 0.52),
          cue: ['طعام', 'امي', 'food', 'mother'],
        ),
        PictureRegion(
          'grandfather\'s garden',
          Rect.fromLTRB(0.6, 0.18, 0.92, 0.56),
          cue: ['جدي', 'حديق', 'grandfather', 'garden'],
        ),
        PictureRegion(
          'layla',
          Rect.fromLTRB(0.3, 0.58, 0.82, 0.96),
          cue: ['ليلي', 'layla'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('layla_star', 6),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'her little star',
          Rect.fromLTRB(0.08, 0.12, 0.5, 0.46),
          cue: ['نجم', 'star'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'layla',
          Rect.fromLTRB(0.45, 0.4, 0.9, 0.72),
          cue: ['ليلي', 'layla'],
        ),
        PictureRegion(
          'the warm blanket',
          Rect.fromLTRB(0.08, 0.55, 0.82, 0.95),
          cue: ['لحاف', 'blanket'],
        ),
      ],
    ),
  ],
  // صالح وعصفور الأمانة — Saleh and the Little Bird of Amanah
  'saleh_bird': [
    LivingPicture(
      image: _page('saleh_bird', 1),
      regions: [
        PictureRegion(
          'saleh',
          Rect.fromLTRB(0.2, 0.45, 0.5, 0.92),
          cue: ['صالح', 'saleh'],
        ),
        PictureRegion(
          'his ball',
          Rect.fromLTRB(0.4, 0.82, 0.56, 0.97),
          cue: ['كرت', 'ball'],
        ),
        PictureRegion(
          'the bird and its nest',
          Rect.fromLTRB(0.6, 0.15, 0.9, 0.38),
          cue: ['عصفور', 'عش', 'bird', 'nest'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the olive tree',
          Rect.fromLTRB(0.5, 0, 1, 0.9),
          cue: ['زيتون', 'شجر', 'tree'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('saleh_bird', 2),
      regions: [
        PictureRegion(
          'saleh',
          Rect.fromLTRB(0.25, 0.4, 0.7, 0.9),
          cue: ['صالح', 'saleh'],
        ),
        PictureRegion(
          'the wallet',
          Rect.fromLTRB(0.46, 0.66, 0.72, 0.86),
          cue: ['محفظ', 'نقود', 'wallet', 'money'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the tree',
          Rect.fromLTRB(0.4, 0, 1, 0.75),
          cue: ['شجر', 'tree'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('saleh_bird', 3),
      regions: [
        PictureRegion(
          'saleh',
          Rect.fromLTRB(0.2, 0.3, 0.46, 0.92),
          cue: ['صالح', 'saleh'],
        ),
        PictureRegion(
          'the kind man',
          Rect.fromLTRB(0.55, 0.28, 0.95, 0.92),
          cue: ['حارس', 'جار', 'احمد', 'guard', 'neighbor', 'ahmad'],
        ),
        PictureRegion(
          'the wallet',
          Rect.fromLTRB(0.38, 0.4, 0.56, 0.56),
          cue: ['محفظ', 'wallet'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('saleh_bird', 4),
      regions: [
        PictureRegion(
          'the man',
          Rect.fromLTRB(0.5, 0.32, 0.92, 0.97),
          cue: ['رجل', 'man'],
        ),
        PictureRegion(
          'saleh',
          Rect.fromLTRB(0.2, 0.4, 0.46, 0.92),
          cue: ['صالح', 'saleh'],
        ),
        PictureRegion(
          'the grass',
          Rect.fromLTRB(0, 0.65, 1, 1),
          cue: ['اعشاب', 'grass'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('saleh_bird', 5),
      regions: [
        PictureRegion(
          'saleh',
          Rect.fromLTRB(0.28, 0.32, 0.52, 0.95),
          cue: ['صالح', 'saleh'],
        ),
        PictureRegion(
          'the man',
          Rect.fromLTRB(0.48, 0.25, 0.9, 0.97),
          cue: ['رجل', 'man'],
        ),
        PictureRegion(
          'the wallet',
          Rect.fromLTRB(0.4, 0.52, 0.6, 0.7),
          cue: ['محفظ', 'wallet'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'saleh\'s smile',
          Rect.fromLTRB(0.3, 0.32, 0.5, 0.55),
          cue: ['ابتسام', 'smile'],
          burst: PictureBurst.hearts,
        ),
      ],
    ),
    LivingPicture(
      image: _page('saleh_bird', 6),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the man, joyful',
          Rect.fromLTRB(0.55, 0.25, 0.95, 0.95),
          cue: ['رجل', 'فرح', 'man', 'joy'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'saleh',
          Rect.fromLTRB(0.25, 0.35, 0.56, 0.95),
          cue: ['صالح', 'saleh'],
        ),
        PictureRegion(
          'the singing bird',
          Rect.fromLTRB(0.3, 0.12, 0.58, 0.34),
          cue: ['سعيد', 'happy'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
  ],
  // نور والحديقة النظيفة — Noor and the Clean Garden
  'noor_clean': [
    LivingPicture(
      image: _page('noor_clean', 1),
      regions: [
        PictureRegion(
          'noor',
          Rect.fromLTRB(0.2, 0.15, 0.6, 0.75),
          cue: ['نور', 'noor'],
        ),
        PictureRegion(
          'the litter',
          Rect.fromLTRB(0.45, 0.55, 0.95, 0.95),
          cue: ['مخلفات', 'اوراق', 'trash', 'leaves'],
        ),
        PictureRegion(
          'the garden',
          Rect.fromLTRB(0, 0, 1, 0.5),
          cue: ['حديق', 'garden'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('noor_clean', 2),
      regions: [
        PictureRegion(
          'noor',
          Rect.fromLTRB(0.3, 0.12, 0.66, 0.86),
          cue: ['نور', 'noor'],
        ),
        PictureRegion(
          'the big bag',
          Rect.fromLTRB(0.58, 0.45, 0.96, 0.9),
          cue: ['اكياس', 'bags'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the bottles and papers',
          Rect.fromLTRB(0.05, 0.65, 0.62, 0.98),
          cue: ['علب', 'اوراق', 'bottles', 'leaves'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('noor_clean', 3),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the sign',
          Rect.fromLTRB(0.8, 0.16, 1, 0.36),
          cue: ['لافت', 'sign'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'noor',
          Rect.fromLTRB(0.3, 0.18, 0.56, 0.75),
          cue: ['نور', 'noor'],
        ),
        PictureRegion(
          'the garden',
          Rect.fromLTRB(0, 0.3, 1, 1),
          cue: ['حديق', 'garden'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('noor_clean', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the friends',
          Rect.fromLTRB(0.08, 0.4, 0.92, 0.86),
          cue: ['اصدقاء', 'friends', 'فريق', 'team'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the garden',
          Rect.fromLTRB(0, 0, 1, 0.45),
          cue: ['garden'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('noor_clean', 5),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the little flower',
          Rect.fromLTRB(0.42, 0.66, 0.72, 0.9),
          cue: ['ورد', 'flower'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the watering can',
          Rect.fromLTRB(0.36, 0.5, 0.62, 0.7),
          cue: ['سقو', 'watered'],
        ),
        PictureRegion(
          'the children',
          Rect.fromLTRB(0.14, 0.35, 0.92, 0.9),
          cue: ['اطفال', 'children'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('noor_clean', 6),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the wooden bench',
          Rect.fromLTRB(0.2, 0.5, 0.86, 0.86),
          cue: ['مقعد', 'bench'],
        ),
        PictureRegion(
          'the happy children',
          Rect.fromLTRB(0.2, 0.35, 0.86, 0.8),
          cue: ['نور', 'noor', 'سعاد', 'happy'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the trees in the breeze',
          Rect.fromLTRB(0, 0, 1, 0.42),
          cue: ['نسيم', 'breeze'],
        ),
      ],
    ),
  ],
  // مريم وصندوق الألعاب — Maryam and the Toy Box
  'maryam_toys': [
    LivingPicture(
      image: _page('maryam_toys', 1),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'maryam',
          Rect.fromLTRB(0.46, 0.18, 0.84, 0.76),
          cue: ['مريم', 'maryam', 'سعيد', 'happy'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the new toy box',
          Rect.fromLTRB(0.2, 0.6, 0.64, 0.94),
          cue: ['صندوق', 'box'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the dolls',
          Rect.fromLTRB(0.38, 0.48, 0.62, 0.72),
          cue: ['دمي', 'dolls'],
        ),
        PictureRegion(
          'the little cars',
          Rect.fromLTRB(0.52, 0.76, 0.84, 0.96),
          cue: ['سيار', 'cars'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('maryam_toys', 2),
      regions: [
        PictureRegion(
          'fatimah',
          Rect.fromLTRB(0.6, 0.2, 0.94, 0.95),
          cue: ['فاطم', 'fatimah'],
        ),
        PictureRegion(
          'the toys she longs for',
          Rect.fromLTRB(0.48, 0.4, 0.7, 0.66),
          cue: ['العاب', 'toys'],
        ),
        PictureRegion(
          'maryam',
          Rect.fromLTRB(0.14, 0.14, 0.5, 0.9),
          cue: ['مريم', 'maryam'],
        ),
        PictureRegion(
          'the toys she hides',
          Rect.fromLTRB(0.12, 0.34, 0.5, 0.68),
          cue: ['اخفت', 'مفضل', 'hid', 'favourite'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('maryam_toys', 3),
      regions: [
        PictureRegion(
          'maryam',
          Rect.fromLTRB(0.2, 0.36, 0.56, 0.96),
          cue: ['مريم', 'maryam'],
        ),
        PictureRegion(
          'the room',
          Rect.fromLTRB(0, 0, 1, 0.5),
          cue: ['تصرف', 'right'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('maryam_toys', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'maryam',
          Rect.fromLTRB(0.04, 0.24, 0.56, 0.9),
          cue: ['مريم', 'maryam'],
        ),
        PictureRegion(
          'maryam\'s toys',
          Rect.fromLTRB(0.24, 0.62, 0.64, 0.96),
          cue: ['العاب', 'toys'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'her friend',
          Rect.fromLTRB(0.54, 0.3, 0.96, 0.96),
          cue: ['معا', 'together'],
        ),
        PictureRegion(
          'happy hearts',
          Rect.fromLTRB(0.1, 0.2, 0.9, 0.7),
          cue: ['قلوب', 'hearts'],
          burst: PictureBurst.hearts,
        ),
      ],
    ),
    LivingPicture(
      image: _page('maryam_toys', 5),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'maryam at ease',
          Rect.fromLTRB(0.14, 0.26, 0.5, 0.82),
          cue: ['قلب', 'heart'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'maryam',
          Rect.fromLTRB(0.14, 0.26, 0.5, 0.82),
          cue: ['مريم', 'maryam'],
        ),
        PictureRegion(
          'the box',
          Rect.fromLTRB(0, 0.72, 0.26, 1),
          cue: ['صندوق', 'box'],
        ),
        PictureRegion(
          'fatimah',
          Rect.fromLTRB(0.56, 0.34, 0.9, 0.82),
          cue: ['فاطم', 'fatimah'],
        ),
        PictureRegion(
          'the tower of blocks',
          Rect.fromLTRB(0.42, 0.06, 0.62, 0.84),
          cue: ['مكعب', 'برج', 'blocks', 'tower'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'laughing',
          Rect.fromLTRB(0.16, 0.24, 0.86, 0.6),
          cue: ['=تضحكان', 'laughing'],
          burst: PictureBurst.hearts,
        ),
      ],
    ),
    LivingPicture(
      image: _page('maryam_toys', 6),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the two friends hugging',
          Rect.fromLTRB(0.18, 0.18, 0.76, 0.92),
          cue: ['فاطم', 'ابتسام', 'fatimah', 'smile'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the shared toy box',
          Rect.fromLTRB(0.6, 0.54, 0.96, 0.94),
          cue: ['مشارك', 'sharing'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
  ],
  // عمر ونور الصلاة — Umar and the Light of Salah
  'omar_prayer': [
    LivingPicture(
      image: _page('omar_prayer', 1),
      regions: [
        PictureRegion(
          'umar',
          Rect.fromLTRB(0.38, 0.44, 0.64, 0.86),
          cue: ['عمر', 'umar'],
        ),
        PictureRegion(
          'his friends',
          Rect.fromLTRB(0.1, 0.48, 0.9, 0.86),
          cue: ['friends'],
        ),
        PictureRegion(
          'the minaret',
          Rect.fromLTRB(0.56, 0.06, 0.74, 0.44),
          cue: ['اذان', 'adhan'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
    LivingPicture(
      image: _page('omar_prayer', 2),
      regions: [
        PictureRegion(
          'umar',
          Rect.fromLTRB(0.44, 0.36, 0.72, 0.86),
          cue: ['عمر', 'umar'],
        ),
        PictureRegion(
          'his friends',
          Rect.fromLTRB(0.16, 0.42, 0.92, 0.88),
          cue: ['friends'],
        ),
        PictureRegion(
          'the masjid',
          Rect.fromLTRB(0.52, 0.14, 0.96, 0.44),
          cue: ['مسجد', 'masjid'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
    LivingPicture(
      image: _page('omar_prayer', 3),
      regions: [
        PictureRegion(
          'umar',
          Rect.fromLTRB(0.2, 0.22, 0.6, 0.92),
          cue: ['عمر', 'umar'],
        ),
        PictureRegion(
          'the water of wudu',
          Rect.fromLTRB(0.55, 0.38, 0.96, 0.76),
          cue: ['وضوء', 'متوضا', 'wudu'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'his face',
          Rect.fromLTRB(0.24, 0.2, 0.52, 0.46),
          cue: ['وجه', 'face'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('omar_prayer', 4),
      regions: [
        PictureRegion(
          'umar',
          Rect.fromLTRB(0.32, 0.48, 0.54, 0.96),
          cue: ['عمر', 'umar'],
        ),
        PictureRegion(
          'his father',
          Rect.fromLTRB(0.5, 0.28, 0.76, 0.96),
          cue: ['والده', 'father'],
        ),
        PictureRegion(
          'the masjid',
          Rect.fromLTRB(0, 0, 1, 0.6),
          cue: ['مسجد', 'masjid'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('omar_prayer', 5),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'umar',
          Rect.fromLTRB(0.36, 0.42, 0.7, 0.97),
          cue: ['عمر', 'umar', 'صدر', 'chest'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the light',
          Rect.fromLTRB(0.28, 0.04, 0.96, 0.62),
          cue: ['نور', 'light'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
    LivingPicture(
      image: _page('omar_prayer', 6),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'umar',
          Rect.fromLTRB(0.2, 0.3, 0.56, 0.9),
          cue: ['عمر', 'umar'],
        ),
        PictureRegion(
          'his friends',
          Rect.fromLTRB(0.5, 0.36, 0.96, 0.9),
          cue: ['اصدقاء', 'friends'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the masjid',
          Rect.fromLTRB(0.6, 0.18, 0.96, 0.44),
          cue: ['اذان', 'adhan'],
        ),
      ],
    ),
  ],
  // خديجة وحق الجار — Khadijah and the Right of the Neighbor
  'khadija_neighbor': [
    LivingPicture(
      image: _page('khadija_neighbor', 1),
      regions: [
        PictureRegion(
          'khadijah',
          Rect.fromLTRB(0.24, 0.2, 0.58, 0.86),
          cue: ['خديج', 'khadijah'],
        ),
        PictureRegion(
          'her mother',
          Rect.fromLTRB(0.5, 0.14, 0.9, 0.76),
          cue: ['والدت', 'ام', 'mother'],
        ),
        PictureRegion(
          'the warm soup',
          Rect.fromLTRB(0.42, 0.54, 0.8, 0.86),
          cue: ['حساء', 'soup'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
    LivingPicture(
      image: _page('khadija_neighbor', 2),
      regions: [
        PictureRegion(
          'her mother',
          Rect.fromLTRB(0.14, 0.14, 0.62, 0.96),
          cue: ['ام', 'mother', 'smiled'],
        ),
        PictureRegion(
          'khadijah',
          Rect.fromLTRB(0.54, 0.24, 0.86, 0.98),
          cue: ['خديج', 'khadijah'],
        ),
        PictureRegion(
          'the dish',
          Rect.fromLTRB(0.44, 0.46, 0.72, 0.7),
          cue: ['طعام', 'food'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('khadija_neighbor', 3),
      regions: [
        PictureRegion(
          'khadijah',
          Rect.fromLTRB(0.54, 0.38, 0.82, 0.9),
          cue: ['خديج', 'khadijah'],
        ),
        PictureRegion(
          'the warm plate',
          Rect.fromLTRB(0.54, 0.48, 0.72, 0.64),
          cue: ['طبق', 'plate'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the door',
          Rect.fromLTRB(0.14, 0.28, 0.46, 0.82),
          cue: ['باب', 'door'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('khadija_neighbor', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'grandma aisha',
          Rect.fromLTRB(0.44, 0.24, 0.9, 0.96),
          cue: ['جدة', 'grandma'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'khadijah',
          Rect.fromLTRB(0.2, 0.54, 0.48, 0.96),
          cue: ['خديج', 'khadijah'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('khadija_neighbor', 5),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'khadijah, happy',
          Rect.fromLTRB(0.36, 0.34, 0.7, 0.96),
          cue: ['خديج', 'khadijah', 'قلب', 'heart'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the night sky',
          Rect.fromLTRB(0.45, 0, 0.9, 0.32),
          cue: ['سعاد', 'happiness'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
    LivingPicture(
      image: _page('khadija_neighbor', 6),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the basket of fruit',
          Rect.fromLTRB(0.36, 0.4, 0.68, 0.66),
          cue: ['فواك', 'fruits'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'grandma aisha',
          Rect.fromLTRB(0.58, 0.24, 0.96, 0.96),
          cue: ['جدة', 'grandma'],
        ),
        PictureRegion(
          'khadijah',
          Rect.fromLTRB(0.24, 0.28, 0.6, 0.96),
          cue: ['خديج', 'khadijah'],
          burst: PictureBurst.hearts,
        ),
      ],
    ),
  ],
  // عبد الله وباسم الله — Abdullah and 'Bismillah'
  'abdullah_bismillah': [
    LivingPicture(
      image: _page('abdullah_bismillah', 1),
      regions: [
        PictureRegion(
          'abdullah',
          Rect.fromLTRB(0.1, 0.18, 0.52, 0.96),
          cue: ['عبد', 'abdullah'],
        ),
        PictureRegion(
          'the table',
          Rect.fromLTRB(0.34, 0.48, 0.98, 0.92),
          cue: ['مائد', 'table'],
        ),
        PictureRegion(
          'the fruit',
          Rect.fromLTRB(0.66, 0.48, 0.96, 0.72),
          cue: ['فاكه', 'fruit'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'his school bag',
          Rect.fromLTRB(0, 0.68, 0.22, 0.96),
          cue: ['مدرس', 'school'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('abdullah_bismillah', 2),
      regions: [
        PictureRegion(
          'his father',
          Rect.fromLTRB(0.04, 0.14, 0.62, 0.86),
          cue: ['والده', 'father'],
        ),
        PictureRegion(
          'abdullah',
          Rect.fromLTRB(0.54, 0.28, 0.86, 0.82),
          cue: ['عبد', 'abdullah'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('abdullah_bismillah', 3),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'abdullah smiling',
          Rect.fromLTRB(0.28, 0.04, 0.76, 0.76),
          cue: ['عبد', 'abdullah', 'ابتسم', 'smiled'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the food in front of him',
          Rect.fromLTRB(0.18, 0.68, 0.86, 1),
          cue: ['امام', 'front'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
    LivingPicture(
      image: _page('abdullah_bismillah', 4),
      regions: [
        PictureRegion(
          'abdullah',
          Rect.fromLTRB(0.18, 0.18, 0.62, 0.96),
          cue: ['عبد'],
        ),
        PictureRegion(
          'his food',
          Rect.fromLTRB(0.34, 0.58, 0.64, 0.74),
          cue: ['طعام', 'food'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
    LivingPicture(
      image: _page('abdullah_bismillah', 5),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'abdullah',
          Rect.fromLTRB(0.28, 0.22, 0.74, 0.76),
          cue: ['عبد', 'abdullah', 'حمد', 'alhamdulillah'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'his hands',
          Rect.fromLTRB(0.4, 0.52, 0.64, 0.76),
          cue: ['مسح', 'wiped'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('abdullah_bismillah', 6),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the family',
          Rect.fromLTRB(0.08, 0.28, 0.96, 0.96),
          cue: ['عائل', 'family'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'abdullah',
          Rect.fromLTRB(0.4, 0.3, 0.62, 0.62),
          cue: ['عبد', 'abdullah'],
        ),
        PictureRegion(
          'the table',
          Rect.fromLTRB(0.18, 0.58, 0.96, 0.96),
          cue: ['مائد', 'table'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
  ],
  // بدر واللعبة المكسورة — Badr and the Broken Toy
  'badr_broken_toy': [
    LivingPicture(
      image: _page('badr_broken_toy', 1),
      regions: [
        PictureRegion(
          'badr',
          Rect.fromLTRB(0.38, 0.24, 0.76, 0.86),
          cue: ['بدر', 'badr'],
        ),
        PictureRegion(
          'the blue racing car',
          Rect.fromLTRB(0.2, 0.7, 0.56, 0.93),
          cue: ['سيار', 'car'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the carpet',
          Rect.fromLTRB(0, 0.66, 1, 1),
          cue: ['سجاد', 'carpet'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('badr_broken_toy', 2),
      regions: [
        PictureRegion(
          'the broken wheel',
          Rect.fromLTRB(0.2, 0.7, 0.6, 0.93),
          cue: ['عجلات', 'wheels'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the table',
          Rect.fromLTRB(0, 0.46, 0.34, 0.72),
          cue: ['طاول', 'table'],
        ),
        PictureRegion(
          'badr, scared',
          Rect.fromLTRB(0.44, 0.26, 0.8, 0.84),
          cue: ['بدر', 'badr', 'خوف', 'scared'],
        ),
        PictureRegion(
          'the sofa',
          Rect.fromLTRB(0, 0.18, 0.46, 0.52),
          cue: ['اريك', 'sofa'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('badr_broken_toy', 3),
      regions: [
        PictureRegion(
          'badr',
          Rect.fromLTRB(0.36, 0.24, 0.72, 0.92),
          cue: ['بدر', 'badr'],
        ),
        PictureRegion(
          'his father\'s photo',
          Rect.fromLTRB(0.66, 0.18, 0.82, 0.34),
          cue: ['والده', 'father'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the broken car',
          Rect.fromLTRB(0.34, 0.52, 0.62, 0.74),
          cue: ['حقيق', 'truth'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('badr_broken_toy', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'badr',
          Rect.fromLTRB(0.28, 0.3, 0.64, 0.92),
          cue: ['بدر', 'badr'],
        ),
        PictureRegion(
          'his brother omar',
          Rect.fromLTRB(0.54, 0.28, 0.86, 0.92),
          cue: ['عمر', 'omar', 'احتضن', 'hugged'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'dad with the toolbox',
          Rect.fromLTRB(0.16, 0.1, 0.4, 0.64),
          cue: ['ابي', 'dad'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the car',
          Rect.fromLTRB(0.4, 0.58, 0.66, 0.74),
          cue: ['سيار', 'car'],
        ),
      ],
    ),
  ],
  // سارة ونبتة الريحان — Sarah and the Basil Plant
  'sarah_basil_sprout': [
    LivingPicture(
      image: _page('sarah_basil_sprout', 1),
      regions: [
        PictureRegion(
          'sarah',
          Rect.fromLTRB(0.44, 0.16, 0.86, 0.84),
          cue: ['سار', 'sarah'],
        ),
        PictureRegion(
          'the plant pot',
          Rect.fromLTRB(0.14, 0.38, 0.44, 0.86),
          cue: ['حوض', 'pot'],
        ),
        PictureRegion(
          'the dry leaves and tissues',
          Rect.fromLTRB(0, 0.72, 0.52, 0.96),
          cue: ['مناديل', 'اوراق', 'tissues', 'leaves'],
        ),
        PictureRegion(
          'the yard',
          Rect.fromLTRB(0.18, 0.12, 0.62, 0.42),
          cue: ['فسح', 'break'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('sarah_basil_sprout', 2),
      regions: [
        PictureRegion(
          'sarah',
          Rect.fromLTRB(0.4, 0.16, 0.76, 0.82),
          cue: ['سار', 'sarah'],
        ),
        PictureRegion(
          'hind',
          Rect.fromLTRB(0.64, 0.36, 0.96, 0.86),
          cue: ['هند', 'hind'],
        ),
        PictureRegion(
          'the drooping plant',
          Rect.fromLTRB(0.14, 0.38, 0.44, 0.86),
          cue: ['نبت', 'نبات', 'plant'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('sarah_basil_sprout', 3),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'sarah',
          Rect.fromLTRB(0.46, 0.16, 0.84, 0.86),
          cue: ['سار', 'sarah'],
        ),
        PictureRegion(
          'the watering can',
          Rect.fromLTRB(0.44, 0.46, 0.72, 0.66),
          cue: ['رشاش', 'watering'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the bin',
          Rect.fromLTRB(0.64, 0.58, 0.92, 0.76),
          cue: ['=سلة', 'bin'],
        ),
        PictureRegion(
          'the dry soil',
          Rect.fromLTRB(0.18, 0.58, 0.44, 0.74),
          cue: ['ترب', 'soil'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('sarah_basil_sprout', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the basil',
          Rect.fromLTRB(0.14, 0.58, 0.44, 0.96),
          cue: ['ريحان', 'basil'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'sarah',
          Rect.fromLTRB(0.28, 0.28, 0.56, 0.84),
          cue: ['سار', 'sarah', 'happy'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the teacher',
          Rect.fromLTRB(0.5, 0.18, 0.84, 0.92),
          cue: ['معلم', 'teacher'],
        ),
        PictureRegion(
          'the yard',
          Rect.fromLTRB(0, 0, 1, 0.28),
          cue: ['رائح', 'smell'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
  ],
  // تميم وبركان الغضب — Tamim and the Volcano of Anger
  'tamim_anger_volcano': [
    LivingPicture(
      image: _page('tamim_anger_volcano', 1),
      regions: [
        PictureRegion(
          'the falling tower',
          Rect.fromLTRB(0.28, 0.26, 0.64, 0.72),
          cue: ['برج', 'مكعب', 'tower', 'blocks'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'tamim',
          Rect.fromLTRB(0.58, 0.18, 0.9, 0.86),
          cue: ['تميم', 'tamim'],
        ),
        PictureRegion(
          'the table',
          Rect.fromLTRB(0.24, 0.58, 0.76, 0.92),
          cue: ['طاول', 'table'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('tamim_anger_volcano', 2),
      regions: [
        PictureRegion(
          'tamim',
          Rect.fromLTRB(0.54, 0.16, 0.86, 0.84),
          cue: ['تميم', 'tamim'],
        ),
        PictureRegion(
          'the red heat',
          Rect.fromLTRB(0.24, 0.08, 0.56, 0.56),
          cue: ['بركان', 'volcano'],
        ),
        PictureRegion(
          'the blocks',
          Rect.fromLTRB(0.24, 0.58, 0.82, 0.96),
          cue: ['مكعب', 'blocks'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('tamim_anger_volcano', 3),
      regions: [
        PictureRegion(
          'his mother',
          Rect.fromLTRB(0.54, 0.24, 0.98, 0.9),
          cue: ['والدت', 'mother'],
        ),
        PictureRegion(
          'tamim',
          Rect.fromLTRB(0.3, 0.36, 0.64, 0.9),
          cue: ['تميم', 'tamim'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('tamim_anger_volcano', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'washing his face',
          Rect.fromLTRB(0.04, 0.24, 0.46, 0.96),
          cue: ['غسل', 'washed'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'tamim and his tower',
          Rect.fromLTRB(0.48, 0.24, 0.86, 0.92),
          cue: ['تميم', 'برج', 'tamim', 'tower'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'his mother',
          Rect.fromLTRB(0.78, 0.28, 1, 0.96),
          cue: ['ام', 'mother'],
        ),
      ],
    ),
  ],
  // نورة وصندوق المشاركة — Noura and the Sharing Box
  'noura_sharing_box': [
    LivingPicture(
      image: _page('noura_sharing_box', 1),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'noura',
          Rect.fromLTRB(0.28, 0.34, 0.66, 0.86),
          cue: ['نور', 'noura'],
        ),
        PictureRegion(
          'the box of colours',
          Rect.fromLTRB(0.54, 0.46, 0.76, 0.66),
          cue: ['الوان', 'pencils'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the drawing paper',
          Rect.fromLTRB(0.24, 0.64, 0.82, 0.9),
          cue: ['رسم', 'draw'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('noura_sharing_box', 2),
      regions: [
        PictureRegion(
          'layla',
          Rect.fromLTRB(0.24, 0.34, 0.52, 0.86),
          cue: ['ليلي', 'layla'],
        ),
        PictureRegion(
          'noura',
          Rect.fromLTRB(0.54, 0.34, 0.86, 0.86),
          cue: ['نور', 'noura'],
        ),
        PictureRegion(
          'the pencil box',
          Rect.fromLTRB(0.46, 0.58, 0.72, 0.74),
          cue: ['الوان'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('noura_sharing_box', 3),
      regions: [
        PictureRegion(
          'noura, thinking',
          Rect.fromLTRB(0.6, 0.18, 0.92, 0.86),
          cue: ['نور', 'noura'],
        ),
        PictureRegion(
          'the pencils',
          Rect.fromLTRB(0.48, 0.52, 0.76, 0.74),
          cue: ['الوان', 'pencils'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'her classmate',
          Rect.fromLTRB(0.18, 0.34, 0.52, 0.86),
          cue: ['قلوب', 'heart'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('noura_sharing_box', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the rainbow picture',
          Rect.fromLTRB(0.28, 0.62, 0.66, 0.86),
          cue: ['لوح', 'picture'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'layla laughing',
          Rect.fromLTRB(0.24, 0.34, 0.52, 0.76),
          cue: ['ليلي', 'layla'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'noura',
          Rect.fromLTRB(0.54, 0.3, 0.86, 0.86),
          cue: ['نور', 'noura'],
        ),
        PictureRegion(
          'the shared pencils',
          Rect.fromLTRB(0.48, 0.58, 0.8, 0.76),
          cue: ['الوان', 'pencils'],
        ),
      ],
    ),
  ],
  // سلمان وسر الأمانة — Salman and the Secret of Trust
  'salman_secret_trust': [
    LivingPicture(
      image: _page('salman_secret_trust', 1),
      regions: [
        PictureRegion(
          'salman',
          Rect.fromLTRB(0.14, 0.34, 0.52, 0.96),
          cue: ['سلمان', 'salman'],
        ),
        PictureRegion(
          'the shiny wallet',
          Rect.fromLTRB(0.4, 0.74, 0.62, 0.9),
          cue: ['محفظ', 'wallet'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'the corridor',
          Rect.fromLTRB(0, 0, 1, 0.6),
          cue: ['ممر', 'corridor'],
        ),
      ],
    ),
    LivingPicture(
      image: _page('salman_secret_trust', 2),
      regions: [
        PictureRegion(
          'salman',
          Rect.fromLTRB(0.14, 0.34, 0.56, 0.96),
          cue: ['سلمان', 'salman'],
        ),
        PictureRegion(
          'the wallet',
          Rect.fromLTRB(0.46, 0.54, 0.68, 0.74),
          cue: ['محفظ', 'wallet'],
          burst: PictureBurst.sparkles,
        ),
        PictureRegion(
          'his heart',
          Rect.fromLTRB(0.24, 0.48, 0.46, 0.7),
          cue: ['قلب', 'heart'],
          burst: PictureBurst.hearts,
        ),
      ],
    ),
    LivingPicture(
      image: _page('salman_secret_trust', 3),
      regions: [
        PictureRegion(
          'the teacher',
          Rect.fromLTRB(0.54, 0.16, 0.86, 0.6),
          cue: ['معلم', 'teacher'],
        ),
        PictureRegion(
          'salman',
          Rect.fromLTRB(0.18, 0.34, 0.52, 0.96),
          cue: ['سلمان', 'salman'],
        ),
        PictureRegion(
          'the wallet',
          Rect.fromLTRB(0.46, 0.54, 0.66, 0.7),
          cue: ['محفظ', 'wallet'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
    LivingPicture(
      image: _page('salman_secret_trust', 4),
      ambient: PictureAmbient.sparkles,
      regions: [
        PictureRegion(
          'the head teacher',
          Rect.fromLTRB(0.24, 0.22, 0.5, 0.86),
          cue: ['مدير', 'head'],
        ),
        PictureRegion(
          'salman',
          Rect.fromLTRB(0.46, 0.3, 0.72, 0.86),
          cue: ['سلمان', 'salman'],
        ),
        PictureRegion(
          'ziyad with his wallet',
          Rect.fromLTRB(0.64, 0.58, 0.96, 1),
          cue: ['زياد', 'ziyad'],
          burst: PictureBurst.hearts,
        ),
        PictureRegion(
          'the award',
          Rect.fromLTRB(0.34, 0.44, 0.56, 0.62),
          cue: ['درع', 'award'],
          burst: PictureBurst.sparkles,
        ),
      ],
    ),
  ],
};
