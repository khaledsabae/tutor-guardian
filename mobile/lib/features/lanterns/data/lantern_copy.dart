/// The words for the week's acts — one place, so the acts sheet, the Friday
/// card and the shared image say the same thing.
library;

import '../../../l10n/app_localizations.dart';
import 'family_week.dart';

/// The act's kind as a short label («درس»، «سؤال»…).
String actKindLabel(AppLocalizations l10n, String kind) =>
    switch (ActKind.normalise(kind)) {
      ActKind.lesson => l10n.actKindLesson,
      ActKind.question => l10n.actKindQuestion,
      ActKind.followup => l10n.actKindFollowup,
      ActKind.mission => l10n.actKindMission,
      ActKind.planTick => l10n.actKindPlanTick,
      ActKind.habit => l10n.actKindHabit,
      ActKind.challenge => l10n.actKindChallenge,
      _ => l10n.actKindOther,
    };

String _countOf(AppLocalizations l10n, String kind, int n) => switch (kind) {
  ActKind.lesson => l10n.harvestLessons(n),
  ActKind.question => l10n.harvestQuestions(n),
  ActKind.followup => l10n.harvestFollowups(n),
  ActKind.mission => l10n.harvestMissions(n),
  ActKind.planTick => l10n.harvestPlanTicks(n),
  ActKind.habit => l10n.harvestHabits(n),
  ActKind.challenge => l10n.harvestChallenges(n),
  _ => l10n.harvestOthers(n),
};

/// «٣ دروس، سؤالان، مهمة واحدة» — the week by kind, in a fixed order, with
/// the Arabic plural each number takes. Empty for a week with no acts.
String harvestSummary(AppLocalizations l10n, FamilyWeek week) => [
  for (final MapEntry(key: kind, value: n) in week.countsByKind.entries)
    _countOf(l10n, kind, n),
].join(l10n.harvestListSeparator);
