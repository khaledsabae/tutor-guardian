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
import '../home/widgets/today_focus_card.dart' show todayFocusOpenProvider;
import '../hub/screens/hub_screen.dart';
import '../onboarding/providers/onboarding_providers.dart';
import '../program/screens/paths_screen.dart';
import '../tour/tour_controller.dart';
import '../tour/tour_overlay.dart';
import '../tour/tour_step.dart';
import 'root_tab.dart'
    show RootTab, rootTabRequestProvider, pendingRootTabProvider, takePendingRootTab;
import 'package:almorabbi/core/haptics.dart';

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

  /// The tour's one target: Today's ① card. Attached to the card itself and
  /// read back through `localToGlobal`, so RTL mirroring is the framework's
  /// layout, never index arithmetic of ours.
  final GlobalKey _focusCardKey = GlobalKey();

  /// Today's own primary scroll controller, so the tour can bring ① back
  /// when Today is scrolled so far down that the card is not even built.
  /// (Without it Today's list would share the route's with every other tab.)
  final ScrollController _todayScroll = ScrollController();

  @override
  void initState() {
    super.initState();
    // Post-frame, not in `_AppBootstrapper`: the tour measures Today's laid-out
    // ① card, which does not exist until this scaffold's first frame.
    //
    // A tab armed before the shell existed — onboarding's deferred «ask the
    // mentor» — is consumed on the same frame, so the parent lands on the
    // assistant tab as the shell appears, not one tap later.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final pending = takePendingRootTab(ref);
      if (pending != null) _onSelect(pending);
      _maybeStartTour();
    });
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
    _todayScroll.dispose();
    super.dispose();
  }

  /// Back on top — e.g. settings just popped after rewinding the tour version.
  @override
  void didPopNext() => _maybeStartTour();

  void _maybeStartTour({bool retried = false}) {
    if (!kTourEnabled || !mounted) return;
    if (ref.read(tourControllerProvider).active) return;
    final onboarded = ref.read(onboardingCompletedProvider);
    if (!onboarded) return;
    if (!tourIsDue(ref.read(tourVersionProvider))) return;
    // The mark is on ①, which only Today shows. A parent the deferred ask
    // sent to the assistant is not pulled back: the tour waits for their
    // first visit to Today — which is also what the settings replay row
    // promises («ستظهر الجولة عند عودتك إلى الشاشة الرئيسية»).
    if (_index != RootTab.today) return;
    if (_focusCardKey.currentContext == null) {
      // Today is scrolled so far down that the list has not built ① (the
      // replay row can be used from anywhere). Bring the top back and look
      // once more next frame — never start a tour with nothing to point at:
      // it would wait invisibly and drop its veil whenever ① scrolls by.
      if (retried || !_todayScroll.hasClients) return;
      _todayScroll.jumpTo(0);
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => _maybeStartTour(retried: true),
      );
      return;
    }
    _revealFocusCard();
    showTour(
      context,
      ref,
      buildTourSteps(
        focusKey: _focusCardKey,
        // The card runs its own primary action — see todayFocusOpenProvider.
        onOpen: () => ref.read(todayFocusOpenProvider.notifier).state++,
      ),
    );
  }

  /// Brings ① wholly on screen before the veil measures it. Nothing moves on
  /// a first run at normal text size; at 200% the card's lower edge can sit
  /// under the fold, and after the replay row Today may be scrolled anywhere.
  void _revealFocusCard() {
    final ctx = _focusCardKey.currentContext;
    if (ctx == null) return;
    for (final policy in const [
      ScrollPositionAlignmentPolicy.keepVisibleAtEnd,
      ScrollPositionAlignmentPolicy.keepVisibleAtStart,
    ]) {
      unawaited(Scrollable.ensureVisible(ctx, alignmentPolicy: policy));
    }
  }

  void _onSelect(int i) {
    Haptics.selection();
    if (i != _index) _recordSwitch(i);
    setState(() => _index = i);
    // A tour that was waiting for Today (see _maybeStartTour) starts once
    // Today has laid out.
    if (i == RootTab.today && kTourEnabled) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _maybeStartTour());
    }
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
    // A tab switch requested from outside the shell (e.g. the follow-up
    // sheet handing the parent to the assistant). Served once, then the
    // request is cleared so a later rebuild cannot replay it.
    ref.listen<int?>(rootTabRequestProvider, (_, next) {
      if (next == null) return;
      if (next >= 0 && next < RootTab.count) _onSelect(next);
      ref.read(rootTabRequestProvider.notifier).state = null;
    });

    // Tabs armed while the shell is already alive. The mount-time read in
    // initState covers the value that predates this widget; this listener
    // covers everything armed after it.
    ref.listen<int?>(pendingRootTabProvider, (_, next) {
      final tab = takePendingRootTab(ref);
      if (tab != null) _onSelect(tab);
    });

    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [
          TickerMode(
            enabled: _index == RootTab.today,
            child: PrimaryScrollController(
              controller: _todayScroll,
              child: HomeScreen(
                onGoToTab: _onSelect,
                focusCardKey: _focusCardKey,
              ),
            ),
          ),
          TickerMode(
            enabled: _index == RootTab.learn,
            child: const PathsScreen(),
          ),
          TickerMode(
            enabled: _index == RootTab.assistant,
            child: const ChatScreen(),
          ),
          TickerMode(
            enabled: _index == RootTab.more,
            child: const HubScreen(),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: _onSelect,
        destinations: _destinations(l10n),
      ),
    );
  }

  List<Widget> _destinations(AppLocalizations l10n) {
    final specs = <(IconData, IconData, String)>[
      (Icons.home_outlined, Icons.home_rounded, l10n.navToday),
      (Icons.route_outlined, Icons.route, l10n.navLearn),
      (Icons.chat_bubble_outline, Icons.chat_bubble, l10n.navAssistant),
      (Icons.grid_view_outlined, Icons.grid_view_rounded, l10n.navMore),
    ];
    return [
      for (final (icon, selectedIcon, label) in specs)
        NavigationDestination(
          icon: Icon(icon),
          selectedIcon: Icon(selectedIcon),
          label: label,
        ),
    ];
  }
}
