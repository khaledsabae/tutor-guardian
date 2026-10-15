/// Which child surfaces a band may be handed — the client's copy of the
/// server's age gate.
///
/// The server is the authority: `backend/guardrails/child_surface.v1.yaml`
/// decides, and `child_budget.open_session` refuses anything else with
/// `age_not_allowed` or `surface_not_allowed`. This copy exists so the app
/// never *offers* what the server will refuse. Before it, every entry point
/// carried its own hand-written band check — or none, when the profile had not
/// loaded — and a refusal reached the parent as «فشل الدخول لوضع الطفل» after
/// they had typed their PIN.
///
/// `test/child_surface_policy_test.dart` parses the YAML and fails when the two
/// disagree, so a policy change cannot ship with a stale client.
library;

/// `age_bands.<band>.allowed_surfaces`, band for band.
const Map<String, Set<String>> kChildSurfacePolicy = {
  'under-2': {},
  '2-3': {'screen_off'},
  '4-6': {'screen_off', 'agreement', 'mission', 'story'},
  '7-9': {'screen_off', 'agreement', 'mission', 'story', 'game', 'habit'},
  '10-12': {
    'screen_off', 'agreement', 'mission', 'story', 'game', 'habit', 'drill',
    'license',
  },
  '13-15': {
    'screen_off', 'agreement', 'mission', 'story', 'game', 'habit', 'drill',
    'license',
  },
  '16-18': {
    'screen_off', 'agreement', 'mission', 'story', 'game', 'habit', 'drill',
    'license',
  },
};

/// The band a child falls into when the profile cannot say.
///
/// Same direction as `FALLBACK_CHILD_SURFACE_BAND` on the server: the cost of
/// being wrong is a parent reading an explanation, versus an infant handed a
/// screen.
const String kFallbackChildSurfaceBand = 'under-2';

/// A profile's age group → its child-surface band.
///
/// Mirrors `core/taxonomy.map_profile_age_to_band`: `prenatal-1` and the
/// legacy `0-3` (which aliases onto it) both land on `under-2`, and anything
/// unrecognised fails closed to the same band.
String childSurfaceBand(String? profileAgeGroup) {
  final value = (profileAgeGroup ?? '').trim();
  if (value == 'prenatal-1' || value == '0-3') return 'under-2';
  return kChildSurfacePolicy.containsKey(value)
      ? value
      : kFallbackChildSurfaceBand;
}

/// Whether the policy lets this child open [surface].
bool childSurfaceAllowed(String? profileAgeGroup, String surface) =>
    kChildSurfacePolicy[childSurfaceBand(profileAgeGroup)]!.contains(surface);

/// The surfaces this build can hand to a child, in the order the gate lists
/// them.
///
/// Narrower than the policy on purpose. `agreement` is not chosen — it opens
/// on its own when a parent has signed and the child has not. `story`, `game`
/// and `drill` are in the policy but have no child-mode screen in the app yet,
/// so offering them would open nothing.
const List<String> kHandoverSurfaces = [
  'habit',
  'mission',
  'license',
  'screen_off',
];

/// Bands with an internet-licence scenario bank
/// (`knowledge_base/curriculum/license/scenarios_*_<band>.json`). 16-18 has the
/// surface in policy but no bank, so its tile stays hidden rather than opening
/// an empty screen.
const Set<String> kLicenseBankBands = {'10-12', '13-15'};

/// What the hand-over gate offers this child: allowed by the policy, and
/// something this build can actually open.
List<String> handoverSurfacesFor(String? profileAgeGroup) {
  final band = childSurfaceBand(profileAgeGroup);
  final allowed = kChildSurfacePolicy[band]!;
  return [
    for (final surface in kHandoverSurfaces)
      if (allowed.contains(surface) &&
          (surface != 'license' || kLicenseBankBands.contains(band)))
        surface,
  ];
}

/// «ركن الطفل» — what the child's corner may hold, in the order it shows them.
///
/// The corner is not a server surface. It is one paper scene that opens a
/// short story (`story`), a short game (`game`) and ends on the day's task
/// away from the screen (`mission`) — each billed on its own server surface
/// as the child moves between them. So it obeys the same policy, item by item:
/// whatever the band is not allowed is not in the corner at all, not shown
/// greyed or locked.
const List<String> kChildCornerActivities = ['story', 'game', 'mission'];

/// What the hand-over gate calls the corner. Never sent to the server.
const String kChildCornerSurface = 'corner';

/// Whether the corner offers its game. **Off for this launch** (decision of
/// 2026-10-16): the four games' questions are written for parents — 159 of
/// 200 say «طفلك/ابنك/بنتك», in Egyptian dialect, to a mother — so they are
/// not something to hand a child. The whole path (the quiet runner, the
/// card, the surface switch) stays in place; once child-facing questions
/// exist, flipping this is the only change. Off, every band's corner is the
/// day's story, then the task away from the screen.
const bool kChildCornerGameEnabled = false;

/// The corner's activities this child's band allows. [withGame] is the
/// switch above; tests pass it to keep the game's path covered.
List<String> childCornerActivitiesFor(
  String? profileAgeGroup, {
  bool withGame = kChildCornerGameEnabled,
}) {
  final allowed = kChildSurfacePolicy[childSurfaceBand(profileAgeGroup)]!;
  return [
    for (final activity in kChildCornerActivities)
      if (allowed.contains(activity) && (withGame || activity != 'game'))
        activity,
  ];
}

/// Whether the gate offers the corner: it always ends on the task away from
/// the screen, so `mission` is required, and there must be something to do
/// before it.
bool childCornerOffered(
  String? profileAgeGroup, {
  bool withGame = kChildCornerGameEnabled,
}) {
  final activities = childCornerActivitiesFor(
    profileAgeGroup,
    withGame: withGame,
  );
  return activities.contains('mission') &&
      (activities.contains('story') || activities.contains('game'));
}

/// The server surface the corner's session opens on — the first thing in it
/// the band allows. Null when the corner is not offered.
String? childCornerOpeningSurface(
  String? profileAgeGroup, {
  bool withGame = kChildCornerGameEnabled,
}) {
  if (!childCornerOffered(profileAgeGroup, withGame: withGame)) return null;
  return childCornerActivitiesFor(profileAgeGroup, withGame: withGame).first;
}
