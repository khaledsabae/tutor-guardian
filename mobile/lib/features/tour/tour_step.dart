/// The first-run guided tour: what it points at, and whether it runs at all.
///
/// Hand-rolled on purpose. The packaged spotlight widgets (`showcaseview`,
/// `tutorial_coach_mark`) position their tooltips from raw `left`/`right`
/// offsets rather than from [Directionality], and this app forces
/// `TextDirection.rtl` in `MaterialApp.builder` — so the RTL path is the
/// *only* path we would ever run, and it is the broken one. Everything here
/// derives geometry from `RenderBox.localToGlobal`, which is already
/// direction-correct because the framework laid the target out.
library;

import 'dart:io';

import 'package:flutter/widgets.dart';

import '../../l10n/app_localizations.dart';

/// Bumped whenever the app's structure changes enough to be worth
/// re-introducing. Stored as an `int` (not a bool) so a future restructure can
/// ship a short "what moved" tour to people who already saw version 1 —
/// exactly how `lastSeenVersion` / `UpdateSplashScreen` work in `main.dart`.
const kTourVersion = 1;

/// Widget tests build the full app and tap the nav bar; a full-screen veil
/// would swallow every one of those taps. Same guard as the locale default in
/// `lib/main.dart`.
final kTourEnabled = !Platform.environment.containsKey('FLUTTER_TEST');

/// One spotlight: the widget to cut out of the veil, plus its copy.
class TourStep {
  const TourStep({required this.key, required this.caption, this.title});

  /// The target to highlight. Its rect is read from the live render tree.
  final GlobalKey key;
  final String Function(AppLocalizations) caption;
  final String Function(AppLocalizations)? title;
}

/// The five stops of the version-1 tour: the four nav destinations in visual
/// order, then the home screen's primary action.
///
/// [tabKeys] must be ordered by *logical* destination index (today, learn,
/// assistant, more) — not by screen position. The keys are attached to the
/// destinations themselves, so RTL mirroring is the framework's problem, not
/// ours.
List<TourStep> buildTourSteps({
  required List<GlobalKey> tabKeys,
  required GlobalKey focusKey,
}) {
  assert(tabKeys.length == 4, 'the nav bar has four destinations');
  return [
    TourStep(
      key: tabKeys[0],
      title: (l) => l.tourTodayTitle,
      caption: (l) => l.tourTodayBody,
    ),
    TourStep(
      key: tabKeys[1],
      title: (l) => l.tourLearnTitle,
      caption: (l) => l.tourLearnBody,
    ),
    TourStep(
      key: tabKeys[2],
      title: (l) => l.tourAssistantTitle,
      caption: (l) => l.tourAssistantBody,
    ),
    TourStep(
      key: tabKeys[3],
      title: (l) => l.tourMoreTitle,
      caption: (l) => l.tourMoreBody,
    ),
    TourStep(
      key: focusKey,
      title: (l) => l.tourFocusTitle,
      caption: (l) => l.tourFocusBody,
    ),
  ];
}
