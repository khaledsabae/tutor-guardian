/// Home tab AppBar, cut down to two actions.
///
/// The coin chip moved into the stats row, and feedback/settings now live
/// behind the «المزيد» tab — five competing actions left nothing legible.
library;

import 'package:flutter/material.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../hub/widgets/help_sheet.dart';
import '../../program/widgets/active_child_chip.dart';

class HomeAppBar extends StatelessWidget implements PreferredSizeWidget {
  const HomeAppBar({super.key});

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AppBar(
      title: Text(l10n.todaySun),
      actions: [
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 10, horizontal: 4),
          child: Center(child: ActiveChildChip()),
        ),
        IconButton(
          tooltip: l10n.searchTooltip,
          icon: const Icon(Icons.search),
          onPressed: () => Navigator.of(context).push(AppRoutes.search()),
        ),
        // Help used to be reachable only from the «المزيد» tab: an unlabelled
        // icon inside a destination named "more stuff" — two taps and a guess.
        // The sheet exists to answer «من أين أبدأ؟» and was hidden from
        // everyone who needed to ask it. One tap from the screen the parent
        // actually lands on.
        IconButton(
          tooltip: l10n.helpTooltip,
          icon: const Icon(Icons.help_outline),
          onPressed: () => showHelpSheet(context, Screens.tabToday),
        ),
      ],
    );
  }
}
