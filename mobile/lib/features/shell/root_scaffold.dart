/// The app shell: four bottom-navigation tabs.
///
/// It used to be five, and the fourth one **renamed itself based on the active
/// child's age** («حساب اليوم» for 0-6, «ميزان العادات» for 7-18). With
/// multi-child support, switching child silently relabelled a tab under the
/// user's thumb — destroying the spatial memory that bottom navigation exists
/// to build. That screen, and the Quran «الورد» tab beside it, are daily
/// rituals rather than peers of the curriculum; both now open from «اليوم» and
/// from the hub, and the nav bar is finally static.
///
/// The assistant moved from the far edge (index 4) to index 2 — it is the
/// app's most valuable surface and is now thumb-reachable in both RTL and LTR.
///
/// The [IndexedStack] is deliberately kept: each tab holds its own state, so
/// switching tabs never loses scroll position or an in-flight streaming reply.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/analytics.dart';
import '../../core/app_routes.dart';
import '../../l10n/app_localizations.dart';
import '../../screens/chat_screen.dart';
import '../../screens/home_screen.dart';
import '../hub/screens/hub_screen.dart';
import '../program/screens/paths_screen.dart';
import 'root_tab.dart';

/// How many switches inside [_thrashWindow] read as hunting rather than
/// deliberate navigation.
const _thrashThreshold = 4;
const _thrashWindow = Duration(seconds: 10);

class RootScaffold extends ConsumerStatefulWidget {
  const RootScaffold({super.key});

  @override
  ConsumerState<RootScaffold> createState() => _RootScaffoldState();
}

class _RootScaffoldState extends ConsumerState<RootScaffold> {
  int _index = RootTab.today;

  /// Recent tab switches, for thrash detection.
  final List<(int tab, DateTime at)> _recent = [];

  static const _tabNames = [
    Screens.tabToday,
    Screens.tabLearn,
    Screens.tabAssistant,
    Screens.tabMore,
  ];

  void _onSelect(int i) {
    if (i != _index) _recordSwitch(i);
    setState(() => _index = i);
  }

  void _recordSwitch(int i) {
    try {
      unawaited(Analytics.tabSelected(_tabNames[i]));

      final now = DateTime.now();
      _recent.add((i, now));
      _recent.removeWhere((e) => now.difference(e.$2) > _thrashWindow);
      if (_recent.length >= _thrashThreshold) {
        final pattern = _recent.map((e) => _tabNames[e.$1]).join('>');
        unawaited(Analytics.tabThrash(
          _recent.length,
          _thrashWindow.inMilliseconds,
          pattern,
        ));
        // Reset so one hunting episode reports once, not once per extra tap.
        _recent.clear();
      }
    } catch (_) {
      // instrumentation must never break navigation
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [
          HomeScreen(onGoToTab: _onSelect),
          const PathsScreen(),
          const ChatScreen(),
          const HubScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: _onSelect,
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.home_outlined),
            selectedIcon: const Icon(Icons.home_rounded),
            label: l10n.navToday,
          ),
          NavigationDestination(
            icon: const Icon(Icons.route_outlined),
            selectedIcon: const Icon(Icons.route),
            label: l10n.navLearn,
          ),
          NavigationDestination(
            icon: const Icon(Icons.chat_bubble_outline),
            selectedIcon: const Icon(Icons.chat_bubble),
            label: l10n.navAssistant,
          ),
          NavigationDestination(
            icon: const Icon(Icons.grid_view_outlined),
            selectedIcon: const Icon(Icons.grid_view_rounded),
            label: l10n.navMore,
          ),
        ],
      ),
    );
  }
}
