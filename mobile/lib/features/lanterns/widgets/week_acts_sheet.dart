/// The week's acts behind the lanterns — opened from the lantern string.
///
/// Grouped by local day, oldest first: one lit lantern per act, its kind
/// («درس»، «سؤال»، «مهمة»…) and its title when the server sends one (a
/// lesson's, a mission's, a plan step's — never a question, a fact or a
/// child's name). Only what was done is listed; there are no empty days.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' as intl;

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../core/clock.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/paper_lantern.dart';
import '../data/family_week.dart';
import '../data/lantern_copy.dart';
import 'friday_harvest.dart';

/// Opens the sheet; its harvest button closes it and opens the Friday card
/// from [context], which outlives the sheet.
Future<void> showWeekActsSheet(BuildContext context, FamilyWeek week) async {
  final next = await showModalBottomSheet<String>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    routeSettings: const RouteSettings(name: Screens.weekLanterns),
    builder: (_) => WeekActsSheet(week: week),
  );
  if (next == _openHarvest && context.mounted) {
    await Analytics.harvestOpened('sheet');
    if (context.mounted) await showFridayHarvest(context, week);
  }
}

const _openHarvest = 'harvest';

class WeekActsSheet extends ConsumerWidget {
  const WeekActsSheet({super.key, required this.week});

  final FamilyWeek week;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final locale = Localizations.localeOf(context).toLanguageTag();
    final appDir = Directionality.of(context);
    // The harvest stays one tap away from Friday to the week's end, for a
    // parent who closed Noor's Friday line or opened the app later.
    final weekday = ref.watch(clockProvider)().weekday;
    final harvest = week.acts.isNotEmpty && weekday >= DateTime.friday;

    return ConstrainedBox(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * .8,
      ),
      child: ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        children: [
          Text(
            l10n.weekActsTitle,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w800,
              color: colors.ink,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            week.acts.isEmpty ? l10n.weekLanternsHint : l10n.weekActsSubtitle,
            style: TextStyle(color: colors.textSecondary, height: 1.5),
          ),
          for (final (day, acts) in week.byDay) ...[
            const SizedBox(height: 16),
            Text(
              '${intl.DateFormat.EEEE(locale).format(day)} · '
              '${MaterialLocalizations.of(context).formatShortMonthDay(day)}',
              style: TextStyle(
                color: colors.accentDeep,
                fontWeight: FontWeight.w800,
                fontSize: 13,
              ),
            ),
            const SizedBox(height: 6),
            for (final act in acts)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const PaperLantern(lit: true, height: 22),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            actKindLabel(l10n, act.kind),
                            style: TextStyle(
                              color: colors.ink,
                              fontWeight: FontWeight.w700,
                              fontSize: 14,
                            ),
                          ),
                          if (act.title != null)
                            Text(
                              act.title!,
                              textDirection: ContentDirectionality.resolve(
                                text: act.title!,
                                fallback: appDir,
                              ),
                              style: TextStyle(
                                color: colors.textSecondary,
                                fontSize: 13,
                                height: 1.45,
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
          if (week.litWeeksTotal > 0) ...[
            const SizedBox(height: 14),
            Text(
              l10n.litWeeksCount(week.litWeeksTotal),
              style: TextStyle(
                color: colors.textSecondary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          if (harvest) ...[
            const SizedBox(height: 14),
            OutlinedButton(
              onPressed: () => Navigator.of(context).pop(_openHarvest),
              child: Text(l10n.harvestTitle),
            ),
          ],
        ],
      ),
    );
  }
}
