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
import '../onboarding/providers/onboarding_providers.dart';
import '../program/screens/paths_screen.dart';
import '../tour/tour_controller.dart';
import '../tour/tour_overlay.dart';
import '../tour/tour_step.dart';
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

class _RootScaffoldState extends ConsumerState<RootScaffold> with RouteAware {
  int _index = RootTab.today;

  /// Recent tab switches, for thrash detection.
  final List<(int tab, DateTime at)> _recent = [];

  static const _tabNames = [
    Screens.tabToday,
    Screens.tabLearn,
    Screens.tabAssistant,
    Screens.tabMore,
  ];

  /// Tour targets. The destination keys are attached to the destinations
  /// themselves (via [KeyedSubtree]) rather than derived by slicing the nav
  /// bar's width into quarters. Slicing would force us to flip the index by
  /// hand under RTL — precisely the direction-assuming arithmetic that makes
  /// the off-the-shelf tour packages misfire in this app. Letting the
  /// framework's own `Row` place each destination and then reading back its
  /// `localToGlobal` rect means mirroring is already correct, and it stays
  /// correct if the destination count or their padding ever changes.
  final List<GlobalKey> _tabKeys = List.generate(4, (_) => GlobalKey());
  final GlobalKey _focusCardKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    // Post-frame, not in `_AppBootstrapper`: the tour measures the laid-out
    // NavigationBar, which does not exist until this scaffold's first frame.
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeStartTour());
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!kTourEnabled) return;
    final route = ModalRoute.of(context);
    if (route is ModalRoute<void>) tourRouteObserver.subscribe(this, route);
  }

  @override
  void dispose() {
    if (kTourEnabled) tourRouteObserver.unsubscribe(this);
    super.dispose();
  }

  /// Back on top — e.g. settings just popped after rewinding the tour version.
  @override
  void didPopNext() => _maybeStartTour();

  void _maybeStartTour() {
    if (!kTourEnabled || !mounted) return;
    if (ref.read(tourControllerProvider).active) return;
    final onboarded = ref.read(onboardingCompletedProvider);
    if (!onboarded) return;
    if (ref.read(tourVersionProvider) >= kTourVersion) return;
    showTour(
      context,
      ref,
      buildTourSteps(tabKeys: _tabKeys, focusKey: _focusCardKey),
    );
  }

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
          HomeScreen(onGoToTab: _onSelect, focusCardKey: _focusCardKey),
          const PathsScreen(),
          const ChatScreen(),
          const HubScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: _onSelect,
        destinations: _destinations(l10n),
      ),
    );
  }

  /// Each destination is wrapped in a [KeyedSubtree]: inert layout-wise —
  /// NavigationBar still receives one widget per destination — but it gives
  /// the destination an element whose render object the tour can measure.
  List<Widget> _destinations(AppLocalizations l10n) {
    final specs = <(IconData, IconData, String)>[
      (Icons.home_outlined, Icons.home_rounded, l10n.navToday),
      (Icons.route_outlined, Icons.route, l10n.navLearn),
      (Icons.chat_bubble_outline, Icons.chat_bubble, l10n.navAssistant),
      (Icons.grid_view_outlined, Icons.grid_view_rounded, l10n.navMore),
    ];
    return [
      for (var i = 0; i < specs.length; i++)
        KeyedSubtree(
          key: _tabKeys[i],
          child: NavigationDestination(
            icon: Icon(specs[i].$1),
            selectedIcon: Icon(specs[i].$2),
            label: specs[i].$3,
          ),
        ),
    ];
  }
}
