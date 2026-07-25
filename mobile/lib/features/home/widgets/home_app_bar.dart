/// Home tab AppBar, cut down to two actions.
///
/// The coin chip moved into the stats row, and feedback/settings now live
/// behind the «المزيد» tab — five competing actions left nothing legible.
library;

import 'package:flutter/material.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
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
      ],
    );
  }
}
