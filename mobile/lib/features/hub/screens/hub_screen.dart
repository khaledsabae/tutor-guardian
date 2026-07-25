/// «المزيد» — one predictable place for everything outside the daily loop.
///
/// The app had 40+ screens behind five tabs and two overloaded app bars, and
/// users reported getting lost. This tab is the answer to "where is that
/// thing I saw once": a single flat, grouped index, always one tap away.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../l10n/app_localizations.dart';
import '../../program/providers/program_providers.dart';
import '../data/hub_catalog.dart';
import '../widgets/hub_group_card.dart';

class HubScreen extends ConsumerStatefulWidget {
  const HubScreen({super.key});

  @override
  ConsumerState<HubScreen> createState() => _HubScreenState();
}

class _HubScreenState extends ConsumerState<HubScreen> {
  @override
  void initState() {
    super.initState();
    // The hub lives in an IndexedStack, so it is built once and `initState`
    // fires on first reveal rather than on every tab switch — which is the
    // number we want (did they ever find it at all?).
    unawaited(Analytics.hubOpened());
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final ageGroup = ref.watch(selectedAgeGroupProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.hubTitle)),
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
