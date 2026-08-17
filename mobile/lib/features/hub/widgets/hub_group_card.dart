/// One titled section of the hub, rendered as a grid of tiles.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/analytics.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../data/hub_catalog.dart';

class HubGroupCard extends StatelessWidget {
  const HubGroupCard({super.key, required this.group, required this.ageGroup});

  final HubGroup group;

  /// The active child's age group — only the routine/habit tile reads it.
  final String ageGroup;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
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
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 2.9,
          children: [
            for (final item in group.items)
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
