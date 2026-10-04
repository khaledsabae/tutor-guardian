/// One titled section of the hub, rendered as a grid of tiles.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/analytics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/two_column_rows.dart';
import '../data/hub_catalog.dart';

class HubGroupCard extends StatelessWidget {
  const HubGroupCard({
    super.key,
    required this.group,
    required this.ageGroup,
    this.available = const {},
  });

  final HubGroup group;

  /// The active child's age group — only the routine/habit tile reads it.
  final String ageGroup;

  /// Server capabilities seen so far; a tile that needs one not in here is
  /// left out (see [HubRequirement]).
  final Set<HubRequirement> available;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final items = [
      for (final item in group.items)
        if (item.requires == null || available.contains(item.requires)) item,
    ];
    if (items.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 0, 4, 10),
          child: Text(
            group.title(l10n),
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textSecondary,
                ),
          ),
        ),
        // Fixed tile height keeps rows aligned across groups; two columns keeps
        // Arabic labels readable without truncating.
        // Not GridView.count: a fixed childAspectRatio fixes every tile's
        // height, so at 200% text a two-line label was clipped. Rows grow
        // with their tallest tile — see TwoColumnRows.
        TwoColumnRows(
          spacing: 10,
          children: [
            for (final item in items)
              _HubTile(item: item, groupId: group.id, ageGroup: ageGroup),
          ],
        ),
        const SizedBox(height: 22),
      ],
    );
  }
}

class _HubTile extends StatelessWidget {
  const _HubTile({
    required this.item,
    required this.groupId,
    required this.ageGroup,
  });

  final HubItem item;
  final String groupId;
  final String ageGroup;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Material(
      color: Dt.surface,
      borderRadius: BorderRadius.circular(Dt.rCard),
      child: InkWell(
        borderRadius: BorderRadius.circular(Dt.rCard),
        onTap: () {
          unawaited(Analytics.hubItemTapped(groupId, item.id));
          Navigator.of(context).push(item.route());
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Text(item.emoji, style: const TextStyle(fontSize: 20)),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  item.label(l10n, ageGroup),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
