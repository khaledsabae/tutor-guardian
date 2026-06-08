import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'config/app_config.dart';
import 'screens/chat_screen.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const ProviderScope(child: TutorGuardianApp()));
}

/// Root widget.
///
/// MaterialApp is configured for Arabic + RTL out of the box. The chat
/// surface lives in `screens/chat_screen.dart`; the notifier there
/// bootstraps the session on first frame (creating one if none exists).
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
      home: const ChatScreen(),
    );
  }
}
