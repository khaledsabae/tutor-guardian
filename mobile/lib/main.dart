import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'config/app_config.dart';
import 'features/program/screens/paths_screen.dart';
import 'screens/chat_screen.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const ProviderScope(child: TutorGuardianApp()));
}

/// Root widget.
///
/// MaterialApp is configured for Arabic + RTL out of the box. The
/// home surface lives behind a [RootScaffold] (a 2-tab NavigationBar)
/// that hosts:
///   * tab 0: [ChatScreen]    — the live assistant
///   * tab 1: [PathsScreen]   — the curriculum program layer (Phase 4)
///
/// The chat notifier bootstraps the session on first frame of tab 0
/// (creating one if none exists). The "مساراتي" tab is a *fresh* fetch
/// each time it's opened (Riverpod's `autoDispose` family providers).
class TutorGuardianApp extends StatelessWidget {
  const TutorGuardianApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppConfig.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      // Arabic locale (no country code matches all Arab locales cleanly).
      locale: const Locale('ar'),
      supportedLocales: const [Locale('ar'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      builder: (context, child) {
        // Force RTL at the framework level so every widget inherits it,
        // including platform-routed transitions.
        return Directionality(
          textDirection: TextDirection.rtl,
          child: child ?? const SizedBox.shrink(),
        );
      },
      home: const RootScaffold(),
    );
  }
}

/// The 2-tab bottom navigation shell.
///
/// Note: each tab keeps its own state via the [IndexedStack] so that
/// switching between the chat and the program lists does not lose
/// scroll position or in-flight streaming tokens.
class RootScaffold extends StatefulWidget {
  const RootScaffold({super.key});

  @override
  State<RootScaffold> createState() => _RootScaffoldState();
}

class _RootScaffoldState extends State<RootScaffold> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: const [
          ChatScreen(),
          PathsScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: 'المساعد',
          ),
          NavigationDestination(
            icon: Icon(Icons.route_outlined),
            selectedIcon: Icon(Icons.route),
            label: 'مساراتي',
          ),
        ],
      ),
    );
  }
}
