/// «المزيد» — one predictable place for everything outside the daily loop.
///
/// The app had 40+ screens behind five tabs and two overloaded app bars, and
/// users reported getting lost. This tab is the answer to "where is that
/// thing I saw once": a single flat, grouped index, always one tap away.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../program/providers/program_providers.dart';
import '../data/hub_catalog.dart';
import '../widgets/help_sheet.dart';
import '../widgets/hub_group_card.dart';

class HubScreen extends ConsumerStatefulWidget {
  const HubScreen({super.key});

  @override
  ConsumerState<HubScreen> createState() => _HubScreenState();
}

class _HubScreenState extends ConsumerState<HubScreen> {
  // No initState analytics. The comment that used to live here claimed
  // IndexedStack builds this screen on first reveal; it does not — it mounts
  // every child immediately and only controls which one is painted. So
  // `hub_opened` fired once per cold start for every user, including the ones
  // who never tapped «المزيد», and its 2,678 users was a session count wearing
  // a discovery label. `tab_selected` with tab='tab_more'
  // (root_scaffold.dart) already measures the real thing.

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final ageGroup = ref.watch(selectedAgeGroupProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.hubTitle),
        actions: [
          // The hub is always one tap away, so help is always two — without
          // costing an action slot on the home screen.
          IconButton(
            tooltip: l10n.helpTooltip,
            icon: const Icon(Icons.help_outline),
            onPressed: () => showHelpSheet(context, Screens.hub),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          for (final group in kHubGroups)
            HubGroupCard(group: group, ageGroup: ageGroup),
        ],
      ),
    );
  }
}
