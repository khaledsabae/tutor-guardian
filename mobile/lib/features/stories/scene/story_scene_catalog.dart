/// Which paper pieces make which page of which story.
///
/// One entry per page of the story, in order, read straight off the page's
/// text (who is there, where, holding what). A story the catalogue does not
/// know — a new one the server adds before the app catches up — gets a quiet
/// night-sky scene for every page rather than an empty frame or an emoji.
///
/// Placement is physical (x 0 = left), the same picture in Arabic and English.
/// People share one size (.8) so a child is always smaller than a parent.
library;

import 'story_scene.dart';

const _kid = .8;
const _adult = .8;

SceneLayer _p(
  String piece,
  double x, {
  double y = .97,
  double size = _kid,
  double depth = .5,
  SceneMotion motion = SceneMotion.still,
  bool flip = false,
  double phase = 0,
}) => SceneLayer(
  piece,
  x: x,
  y: y,
  size: size,
  depth: depth,
  motion: motion,
  flip: flip,
  phase: phase,
);

/// Something floating above the ground: a heart, a star, a bird in the air.
SceneLayer _air(
  String piece,
  double x,
  double y,
  double size, {
  SceneMotion motion = SceneMotion.bob,
  double phase = 0,
}) => _p(piece, x, y: y, size: size, depth: .9, motion: motion, phase: phase);

StoryScene _s(String backdrop, List<SceneLayer> layers) =>
    StoryScene(backdrop, layers);

/// The scene for page [index] (0-based) of [storyId].
StoryScene sceneFor(String storyId, int index) {
  final pages = _catalog[storyId];
  if (pages == null || pages.isEmpty) return fallbackScene;
  return pages[index.clamp(0, pages.length - 1)];
}

/// The scene a story's cover shows: its most telling page.
StoryScene coverSceneFor(String storyId) =>
    sceneFor(storyId, _coverPage[storyId] ?? 0);

/// Whether the catalogue knows this story (tests pin the bundled library).
bool hasScenesFor(String storyId) => _catalog.containsKey(storyId);

/// How many pages the catalogue drew for this story.
int scenePageCount(String storyId) => _catalog[storyId]?.length ?? 0;

final fallbackScene = _s('bg_night_sky', [
  _air('moon', .78, .62, .45, motion: SceneMotion.breathe),
  _air('star', .25, .38, .14, motion: SceneMotion.twinkle),
  _air('star', .5, .3, .1, motion: SceneMotion.twinkle, phase: .4),
]);

const _coverPage = <String, int>{
  'hope_sprout': 3,
  'kitten_kindness': 2,
  'layla_star': 5,
  'noor_clean': 4,
  'maryam_toys': 4,
  'omar_prayer': 3,
  'khadija_neighbor': 2,
  'abdullah_bismillah': 2,
  'aisha_permission': 2,
  'fatima_parents': 4,
  'bilal_forgiveness': 3,
  'hamza_truth': 2,
  'badr_broken_toy': 1,
  'sarah_basil_sprout': 3,
  'tamim_anger_volcano': 1,
  'noura_sharing_box': 3,
  'salman_secret_trust': 3,
};

final Map<String, List<StoryScene>> _catalog = {
  // يوسف وغرسة الأمل
  'hope_sprout': [
    _s('bg_garden_day', [
      _p('tree', .12, size: .95, depth: .2, motion: SceneMotion.sway),
      _p('father_out', .4, size: _adult),
      _p('boy_hold', .64),
    ]),
    _s('bg_garden_day', [
      _p('boy', .35),
      _p('seed', .6, y: 1, size: .45, depth: .8),
      _p('watering_can', .84, size: .38, depth: .7),
    ]),
    _s('bg_garden_evening', [
      _p('boy', .36),
      _p('father', .64, size: _adult, flip: true),
      _p('seed', .86, y: 1, size: .35, depth: .8),
    ]),
    _s('bg_garden_day', [
      _p('boy_up', .3, motion: SceneMotion.bob),
      _p('plant', .6, y: 1, size: .65, depth: .7, motion: SceneMotion.sway),
      _air('bird', .84, .5, .26),
    ]),
  ],
  // أنس والهر الصغير
  'kitten_kindness': [
    _s('bg_street', [
      _p('tree', .14, size: .95, depth: .2, motion: SceneMotion.sway),
      _p('boy', .45),
      _p('kitten', .76, size: .42, depth: .85, motion: SceneMotion.breathe),
    ]),
    _s('bg_street', [
      _p('boy', .4),
      _air('heart', .55, .45, .2),
      _p('kitten', .7, size: .42, depth: .85, motion: SceneMotion.breathe),
    ]),
    _s('bg_street', [
      _p('boy_hold', .38),
      _p('water_bowl', .58, size: .34, depth: .85),
      _p('kitten', .78, size: .42, depth: .85, motion: SceneMotion.breathe),
    ]),
    _s('bg_garden_evening', [
      _p('boy', .36),
      _air('heart', .5, .42, .2),
      _p('kitten', .64, size: .46, depth: .85, motion: SceneMotion.breathe),
    ]),
  ],
  // ليلى ونجمتها الصغيرة
  'layla_star': [
    _s('bg_room_night', [
      _p('girl', .3),
      _air('star', .73, .42, .12, motion: SceneMotion.twinkle),
    ]),
    _s('bg_room_night', [
      _p('bed_girl', .4, size: .78),
      _air('star', .73, .42, .14, motion: SceneMotion.twinkle),
    ]),
    _s('bg_night_sky', [
      _air('star', .5, .38, .2, motion: SceneMotion.twinkle),
      _air('moon', .84, .5, .32, motion: SceneMotion.breathe),
      _air('cloud', .28, .82, .5, motion: SceneMotion.drift),
      _air('cloud', .66, .74, .42, motion: SceneMotion.drift, phase: .5),
    ]),
    _s('bg_night_sky', [
      _air('moon', .2, .55, .4, motion: SceneMotion.breathe),
      _air('star', .58, .32, .14, motion: SceneMotion.twinkle),
      _air('star', .78, .52, .1, motion: SceneMotion.twinkle, phase: .3),
      _p('tree', .9, size: .62, depth: .3, motion: SceneMotion.sway),
    ]),
    _s('bg_room_night', [
      _p('kitten', .14, size: .38, depth: .8, motion: SceneMotion.breathe),
      _p('girl', .38),
      _p('soup_bowl', .6, size: .28, depth: .8),
      _p('flower', .82, size: .45, depth: .7, motion: SceneMotion.sway),
    ]),
    _s('bg_room_night', [
      _p('bed_girl', .42, size: .82, motion: SceneMotion.breathe),
      _air('star', .73, .42, .12, motion: SceneMotion.twinkle),
    ]),
  ],
  // صالح وعصفور الأمانة
  'saleh_bird': [
    _s('bg_garden_day', [
      _p('tree_nest', .28, size: 1, depth: .2, motion: SceneMotion.sway),
      _air('bird', .42, .36, .18),
      _p('boy', .6),
      _p('man', .86, size: _adult, flip: true),
    ]),
    _s('bg_garden_day', [
      _p('tree_olive', .18, size: .95, depth: .2, motion: SceneMotion.sway),
      _p('boy', .48),
      _p('wallet', .72, y: 1, size: .26, depth: .9),
    ]),
    _s('bg_garden_day', [
      _p('boy_hold', .32),
      _p('man', .58, size: _adult, flip: true),
      _p('father', .82, size: _adult, flip: true),
    ]),
    _s('bg_garden_evening', [
      _p('bush', .28, size: .6, depth: .3),
      _p('man', .66, size: _adult, flip: true),
    ]),
    _s('bg_garden_day', [
      _p('boy_hold', .38),
      _air('wallet', .46, .8, .18, motion: SceneMotion.still),
      _p('man', .66, size: _adult, flip: true),
    ]),
    _s('bg_garden_evening', [
      _p('boy_wave', .46),
      _air('heart', .46, .4, .18),
      _air('bird', .8, .42, .2, phase: .5),
    ]),
  ],
  // نور والحديقة النظيفة
  'noor_clean': [
    _s('bg_garden_day', [
      _p('girl', .28),
      _p('litter', .62, y: 1, size: .45, depth: .85),
      _p('bench', .86, size: .5, depth: .3),
    ]),
    _s('bg_garden_day', [
      _p('girl_hold', .3),
      _p('trash_bag', .52, size: .36, depth: .8),
      _p('litter', .78, y: 1, size: .42, depth: .85),
    ]),
    _s('bg_garden_day', [
      _p('girl', .3),
      _p('sign', .64, size: .58, depth: .4),
    ]),
    _s('bg_playground', [
      _p('girl', .22),
      _p('boy_friend', .48),
      _p('girl_friend', .74),
      _p('trash_bag', .92, size: .3, depth: .8),
    ]),
    _s('bg_garden_day', [
      _p('girl', .22),
      _p('flower', .5, size: .48, depth: .7, motion: SceneMotion.sway),
      _p('watering_can', .64, size: .26, depth: .8),
      _p('boy_friend', .8, flip: true),
    ]),
    _s('bg_garden_evening', [
      _p('bench', .5, size: .7, depth: .3),
      _p('girl', .38),
      _p('boy_friend', .6),
      _p('flower', .86, size: .42, depth: .7, motion: SceneMotion.sway),
    ]),
  ],
  // مريم وصندوق الألعاب
  'maryam_toys': [
    _s('bg_room_day', [
      _p('girl_hold', .36),
      _p('toy_chest_open', .64, size: .45, depth: .8),
      _p('gift', .86, size: .3, depth: .8),
    ]),
    _s('bg_room_day', [
      _p('girl', .32),
      _p('toy_chest', .52, size: .36, depth: .8),
      _p('girl_friend', .74, flip: true),
    ]),
    _s('bg_room_day', [
      _p('girl', .28),
      _p('toy_chest', .5, size: .36, depth: .8),
      _p('girl_friend', .76),
    ]),
    _s('bg_room_day', [
      _p('girl', .34),
      _p('mother', .64, size: _adult, flip: true),
    ]),
    _s('bg_room_day', [
      _p('girl', .24),
      _p('blocks', .5, size: .48, depth: .8, motion: SceneMotion.breathe),
      _p('girl_friend', .76, flip: true),
    ]),
    _s('bg_room_day', [
      _p('girl_wave', .3),
      _air('heart', .5, .4, .18),
      _p('girl_friend_hold', .7),
    ]),
  ],
  // عمر ونور الصلاة
  'omar_prayer': [
    _s('bg_garden_day', [
      _p('minaret', .9, size: .95, depth: .15),
      _p('boy_friend', .2),
      _p('boy', .45),
      _p('boy_friend2', .68),
    ]),
    _s('bg_garden_day', [
      _p('minaret', .92, size: .95, depth: .15),
      _p('boy_friend', .24),
      _p('boy_wave', .48),
      _p('boy_friend2', .72, flip: true),
    ]),
    _s('bg_mosque', [
      _p('boy', .26),
      _p('water_tap', .56, size: .72, depth: .4),
    ]),
    _s('bg_mosque', [
      _p('prayer_rug', .5, y: 1.04, size: .8, depth: .3),
      _p('boy', .38),
      _p('father', .62, size: _adult),
    ]),
    _s('bg_mosque', [_p('sujood', .5, y: 1.02, size: .78, depth: .4)]),
    _s('bg_garden_evening', [
      _p('minaret', .92, size: .95, depth: .15),
      _p('boy_friend', .24),
      _p('boy_wave', .5),
      _p('boy_friend2', .74, flip: true),
    ]),
  ],
  // خديجة وحق الجار
  'khadija_neighbor': [
    _s('bg_kitchen', [
      _p('girl', .32),
      _p('soup_pot', .52, y: .66, size: .3, depth: .6),
      _p('mother', .72, size: _adult, flip: true),
    ]),
    _s('bg_kitchen', [
      _p('girl', .32),
      _p('soup_bowl', .52, y: .66, size: .26, depth: .6),
      _p('mother', .72, size: _adult, flip: true),
    ]),
    _s('bg_street', [
      _p('door', .8, size: .92, depth: .3),
      _p('girl_hold', .44),
      _air('soup_bowl', .44, .78, .16, motion: SceneMotion.still),
    ]),
    _s('bg_street', [
      _p('door_open', .8, size: .92, depth: .3),
      _p('grandma', .64, size: _adult, flip: true),
      _p('girl', .34),
    ]),
    _s('bg_street', [
      _p('tree', .12, size: .85, depth: .2, motion: SceneMotion.sway),
      _p('girl_wave', .42),
      _air('heart', .58, .4, .18),
    ]),
    _s('bg_room_day', [
      _p('girl', .34),
      _p('fruit_plate', .62, size: .36, depth: .85),
      _air('heart', .82, .42, .15),
    ]),
  ],
  // عبد الله وباسم الله
  'abdullah_bismillah': [
    _s('bg_room_day', [
      _p('boy', .3),
      _p('table_food', .56, size: .9, depth: .6),
    ]),
    _s('bg_room_day', [
      _p('boy', .28),
      _p('father', .8, size: _adult, flip: true),
      _p('table_food', .55, size: .9, depth: .6),
    ]),
    _s('bg_room_day', [
      _p('boy', .3),
      _p('father', .8, size: _adult, flip: true),
      _p('table_food', .55, size: .9, depth: .6),
    ]),
    _s('bg_room_day', [
      _p('boy', .3),
      _p('fruit_plate', .52, size: .3, depth: .85),
      _p('father', .74, size: _adult, flip: true),
    ]),
    _s('bg_room_day', [
      _p('boy_up', .42, motion: SceneMotion.bob),
      _p('fruit_plate', .7, size: .3, depth: .85),
    ]),
    _s('bg_room_day', [
      _p('mother', .18, size: _adult),
      _p('boy', .4),
      _p('father', .8, size: _adult, flip: true),
      _p('table_food', .52, size: .9, depth: .6),
    ]),
  ],
  // عائشة وأدب الاستئذان
  'aisha_permission': [
    _s('bg_room_day', [_p('door', .7, size: .92, depth: .3), _p('girl', .34)]),
    _s('bg_room_day', [
      _p('door', .7, size: .92, depth: .3),
      _p('girl', .38),
      _air('star', .38, .3, .12, motion: SceneMotion.twinkle),
    ]),
    _s('bg_room_day', [
      _p('door', .66, size: .92, depth: .3),
      _p('girl_wave', .36),
    ]),
    _s('bg_room_day', [
      _p('door_open', .7, size: .92, depth: .3),
      _p('mother', .71, size: .74),
      _p('girl', .32),
    ]),
    _s('bg_room_day', [
      _p('girl', .34),
      _air('heart', .5, .4, .15),
      _p('mother', .66, size: _adult, flip: true),
    ]),
    _s('bg_hallway', [_p('girl', .3), _p('girl_friend', .58)]),
  ],
  // ياسين وعجائب الخالق
  'yaseen_creation': [
    _s('bg_garden_day', [
      _p('father', .3, size: _adult),
      _p('boy', .54),
      _p('ant', .8, y: 1, size: .3, depth: .9, motion: SceneMotion.drift),
    ]),
    _s('bg_garden_day', [
      _p('boy', .38),
      _p('ant', .64, y: 1, size: .36, depth: .9, motion: SceneMotion.drift),
    ]),
    _s('bg_garden_day', [
      _p('boy', .34),
      _p('father', .6, size: _adult, flip: true),
      _p('tree', .88, size: .92, depth: .2, motion: SceneMotion.sway),
    ]),
    _s('bg_night_sky', [
      _p('tree', .14, size: .8, depth: .2, motion: SceneMotion.sway),
      _p('boy', .4),
      _p('flower', .62, size: .4, depth: .8, motion: SceneMotion.sway),
      _air('moon', .82, .48, .3, motion: SceneMotion.breathe),
    ]),
    _s('bg_garden_evening', [
      _p('flower', .18, size: .42, depth: .8, motion: SceneMotion.sway),
      _p('boy_up', .45),
      _air('bird', .76, .42, .2),
    ]),
    _s('bg_garden_day', [
      _p('flower', .22, size: .42, depth: .8, motion: SceneMotion.sway),
      _p('boy', .48),
      _p('tree', .82, size: .92, depth: .2, motion: SceneMotion.sway),
      _air('bird', .84, .34, .15, phase: .5),
    ]),
  ],
  // فاطمة وزهرة البر
  'fatima_parents': [
    _s('bg_room_day', [
      _p('mother', .6, size: _adult),
      _p('sofa', .6, size: .8, depth: .5),
    ]),
    _s('bg_room_day', [
      _p('girl', .24),
      _p('mother', .66, size: _adult),
      _p('sofa', .66, size: .8, depth: .5),
    ]),
    _s('bg_room_day', [
      _p('girl_hold', .3),
      _air('water_glass', .3, .8, .14, motion: SceneMotion.still),
      _p('toy_chest', .7, size: .36, depth: .8),
    ]),
    _s('bg_room_day', [
      _p('girl', .4),
      _air('heart', .5, .32, .15),
      _p('mother_out', .62, size: _adult),
    ]),
    _s('bg_room_day', [
      _p('girl', .34),
      _air('rose', .5, .85, .3, motion: SceneMotion.sway),
      _p('father', .7, size: _adult, flip: true),
    ]),
    _s('bg_room_day', [
      _p('mother', .2, size: _adult),
      _p('girl_wave', .5),
      _p('father', .8, size: _adult, flip: true),
    ]),
  ],
  // بلال وقلب التسامح
  'bilal_forgiveness': [
    _s('bg_classroom', [
      _p('boy', .2),
      _p('canvas', .45, size: .62, depth: .5),
      _p('boy_friend', .74, flip: true),
    ]),
    _s('bg_classroom', [
      _p('boy', .2),
      _p('canvas_spilled', .46, size: .62, depth: .5),
      _p('juice_tipped', .66, y: 1, size: .26, depth: .9),
      _p('boy_friend', .8, flip: true),
    ]),
    _s('bg_classroom', [_p('boy', .44), _air('heart', .44, .32, .15)]),
    _s('bg_classroom', [
      _p('boy_wave', .34),
      _p('boy_friend', .64, flip: true),
    ]),
    _s('bg_classroom', [
      _p('boy', .3),
      _p('boy_friend', .7, flip: true),
      _p('table', .5, size: .9, depth: .6),
      _p('pencils', .5, y: .62, size: .26, depth: .7),
    ]),
    _s('bg_classroom', [
      _p('boy', .32),
      _p('boy_friend', .56),
      _p('canvas', .82, size: .56, depth: .3),
    ]),
  ],
  // حمزة وأمانة الكلمة
  'hamza_truth': [
    _s('bg_playground', [
      _p('boy', .2),
      _p('boy_friend2', .5),
      _p('boy_friend', .78, flip: true),
    ]),
    _s('bg_playground', [
      _p('boy', .4),
      _air('star', .4, .3, .12, motion: SceneMotion.twinkle),
    ]),
    _s('bg_playground', [
      _p('boy_hold', .38),
      _p('boy_friend2', .6, flip: true),
    ]),
    _s('bg_playground', [
      _p('boy', .2),
      _p('boy_friend', .45),
      _p('boy_friend2', .7),
      _air('heart', .58, .34, .15),
    ]),
    _s('bg_room_day', [
      _p('boy_up', .42, motion: SceneMotion.bob),
      _p('mother', .74, size: _adult, flip: true),
    ]),
    _s('bg_classroom', [
      _p('boy', .3),
      _p('boy_friend', .55),
      _p('boy_friend2', .8, flip: true),
    ]),
  ],
  // بدر واللعبة المكسورة
  'badr_broken_toy': [
    _s('bg_room_day', [
      _p('boy', .3),
      _p(
        'toy_car',
        .64,
        y: 1,
        size: .36,
        depth: .85,
        motion: SceneMotion.drift,
      ),
    ]),
    _s('bg_room_day', [
      _p('boy', .24),
      _p('toy_car_broken', .5, y: 1, size: .36, depth: .85),
      _p('sofa', .82, size: .7, depth: .3),
    ]),
    _s('bg_room_day', [_p('boy', .44), _air('heart', .44, .34, .14)]),
    _s('bg_room_day', [
      _p('boy_hold', .36),
      _air('toy_car_broken', .36, .8, .2, motion: SceneMotion.still),
      _p('boy_friend2', .68, size: .9, flip: true),
    ]),
  ],
  // سارة ونبتة الريحان
  'sarah_basil_sprout': [
    _s('bg_playground', [
      _p('girl', .28),
      _p('basil_wilted', .66, size: .45, depth: .8),
      _p('litter', .86, y: 1, size: .32, depth: .9),
    ]),
    _s('bg_playground', [
      _p('girl', .28),
      _p('girl_friend', .52),
      _p('basil_wilted', .8, size: .45, depth: .8),
    ]),
    _s('bg_playground', [
      _p('girl_hold', .3),
      _p('watering_can', .52, size: .28, depth: .85),
      _p('basil_wilted', .74, size: .45, depth: .8),
    ]),
    _s('bg_playground', [
      _p('girl_up', .34, motion: SceneMotion.bob),
      _p('basil', .6, size: .5, depth: .8, motion: SceneMotion.sway),
      _p('teacher', .86, size: _adult, flip: true),
    ]),
  ],
  // تميم وبركان الغضب
  'tamim_anger_volcano': [
    _s('bg_classroom', [
      _p('boy', .3),
      _p('blocks', .56, size: .62, depth: .8),
    ]),
    _s('bg_classroom', [
      _p('boy', .3),
      _air('volcano', .3, .44, .24),
      _p('blocks_fallen', .58, y: 1, size: .5, depth: .85),
    ]),
    _s('bg_room_day', [
      _p('boy', .34),
      _air('volcano', .34, .44, .18, motion: SceneMotion.breathe),
      _p('mother', .66, size: _adult, flip: true),
    ]),
    _s('bg_room_day', [
      _p('boy_up', .38, motion: SceneMotion.bob),
      _p('blocks', .66, size: .52, depth: .8, motion: SceneMotion.breathe),
    ]),
  ],
  // نورة وصندوق المشاركة
  'noura_sharing_box': [
    _s('bg_classroom', [
      _p('girl_hold', .34),
      _air('pencils', .34, .8, .2, motion: SceneMotion.still),
      _p('canvas', .74, size: .56, depth: .3),
    ]),
    _s('bg_classroom', [_p('girl', .3), _p('girl_friend', .66, flip: true)]),
    _s('bg_classroom', [
      _p('girl', .38),
      _p('pencils', .62, size: .3, depth: .85),
    ]),
    _s('bg_classroom', [
      _p('girl_wave', .28),
      _air('heart', .46, .36, .15),
      _p('girl_friend_hold', .62),
      _p('canvas', .86, size: .5, depth: .3),
    ]),
  ],
  // سلمان وسر الأمانة
  'salman_secret_trust': [
    _s('bg_hallway', [
      _p('boy', .34),
      _p('wallet_rocket', .62, y: 1, size: .24, depth: .9),
    ]),
    _s('bg_hallway', [
      _p('boy_hold', .44),
      _air('wallet_rocket', .44, .8, .16, motion: SceneMotion.still),
    ]),
    _s('bg_classroom', [
      _p('boy_hold', .34),
      _p('man', .68, size: _adult, flip: true),
    ]),
    _s('bg_classroom', [
      _p('boy', .34),
      _air('shield', .5, .42, .22),
      _p('boy_friend', .66, flip: true),
    ]),
  ],
};
