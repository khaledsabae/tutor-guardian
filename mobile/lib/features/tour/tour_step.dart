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
///
/// Bumped to 2 on 2026-08-17. Version 1's five captions were locative
/// tautologies — «خطوتك التالية دائمًا هنا» under a spotlight already pointing
/// at the next step. They named the furniture and never said what the house
/// was: who the lessons are for, or what to do in the first ten minutes. The
/// people who already saw version 1 are exactly the ones who wrote «مش عارفين
/// نتعامل مع البرنامج», so they get the rewrite rather than only new installs.
///
/// Bumped to 3 for «نور والقناديل» phase 2: five stops became one. The tour
/// stood between a new parent and the card that took lesson_opened/child_added
/// from 39% to 54% — four nav-bar captions to read before the one thing worth
/// doing. Version 3 is a single mark on Today's ① card, and tapping it opens
/// the lesson. Unlike version 2 it is NOT re-shown to people who finished an
/// earlier rewrite — see [tourIsDue].
const kTourVersion = 3;

/// The oldest finished version that already covers what version 3 says.
///
/// Version 3 only points at ① — a parent who walked version 2 was shown that
/// card as its last stop, has had Today in front of them since, and would
/// meet the same spotlight again for nothing. Version 1 ended on ① too, but
/// with the tautology version 2 was written to replace, and anyone still at 1
/// has not opened the app since that rewrite shipped: they get the mark. So
/// does 0 — never toured, or the settings replay row's rewind.
const kTourCoveredFrom = 2;

/// Whether the first-run tour should run for someone whose stored
/// `OnboardingStorage.tourVersion` is [seenVersion].
bool tourIsDue(int seenVersion) => seenVersion < kTourCoveredFrom;

/// Widget tests build the full app and tap the nav bar; a full-screen veil
/// would swallow every one of those taps. Same guard as the locale default in
/// `lib/main.dart`.
final kTourEnabled = !Platform.environment.containsKey('FLUTTER_TEST');

/// One spotlight: the widget to cut out of the veil, plus its copy.
class TourStep {
  const TourStep({
    required this.key,
    required this.caption,
    this.title,
    this.onTargetTap,
    this.actionLabel,
  });

  /// The target to highlight. Its rect is read from the live render tree.
  final GlobalKey key;
  final String Function(AppLocalizations) caption;
  final String Function(AppLocalizations)? title;

  /// When set, the spotlight is a stand-in for the target: tapping the cut-out
  /// (or the card's primary button) ends the tour and runs this — it does what
  /// the target itself would do, instead of only moving the tour on.
  final VoidCallback? onTargetTap;

  /// The primary button's label. Defaults to the usual «التالي» / «تم».
  final String Function(AppLocalizations)? actionLabel;
}

/// Version 3: one mark, on Today's ① card ([focusKey]).
///
/// [onOpen] must do what the card's own primary button does — open the lesson
/// it offers (or, while that is still loading, whatever the card offers
/// instead). The mark says «ابدأ من هنا»; tapping it has to *start*, not
/// merely dismiss a caption about starting.
List<TourStep> buildTourSteps({
  required GlobalKey focusKey,
  required VoidCallback onOpen,
}) {
  return [
    TourStep(
      key: focusKey,
      title: (l) => l.tourStartHereTitle,
      caption: (l) => l.tourStartHereBody,
      actionLabel: (l) => l.tourStartHereGo,
      onTargetTap: onOpen,
    ),
  ];
}
