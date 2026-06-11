import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'config/app_config.dart';
import 'features/onboarding/providers/onboarding_providers.dart';
import 'features/onboarding/screens/onboarding_screen.dart';
import 'features/program/providers/progress_providers.dart';
import 'features/program/screens/paths_screen.dart';
import 'firebase_options.dart';
import 'screens/chat_screen.dart';
import 'theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

  // Crashlytics — funnel all Flutter errors to Firebase in release builds.
  FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterFatalError;
  PlatformDispatcher.instance.onError = (error, stack) {
    FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
    return true;
  };

  runApp(const ProviderScope(child: TutorGuardianApp()));
}

/// Root widget.
///
/// MaterialApp is configured for Arabic + RTL out of the box. The
/// home surface is decided at first frame:
///
///   * If `SharedPreferences` is not yet loaded (cold boot) → splash.
///   * If onboarding is not completed → [OnboardingScreen].
///   * Otherwise → [RootScaffold] (ChatScreen + PathsScreen).
///
/// Phase 6 wired up the onboarding gate. The active child id is
/// re-hydrated from [OnboardingStorage] in `bootProvider` so the
/// rest of the app can treat `activeChildIdProvider` as the truth.
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
      home: const _AppBootstrapper(),
    );
  }
}

/// Resolves the cold-boot async chain: prefs → onboarding flag →
/// active child re-hydration → push the right screen.
class _AppBootstrapper extends ConsumerWidget {
  const _AppBootstrapper();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncPrefs = ref.watch(sharedPreferencesProvider);
    return asyncPrefs.when(
      data: (_) {
        // First, sync the onboardingCompletedProvider from disk.
        final completed = ref.watch(onboardingCompletedProvider);
        if (!completed) {
          return const OnboardingScreen();
        }
        // Re-hydrate active child id from disk so all the existing
        // `ref.watch(activeChildIdProvider)` consumers pick it up.
        final profile = ref.watch(activeChildProfileProvider);
        if (profile != null) {
          // Push the id into the runtime provider used everywhere.
          // Deferred out of build(): Riverpod forbids modifying a provider
          // during the build phase. The guard prevents a rebuild loop.
          Future(() {
            if (ref.read(activeChildIdProvider) != profile.id) {
              ref.read(activeChildIdProvider.notifier).state = profile.id;
            }
          });
        }
        return const RootScaffold();
      },
      loading: () => const _SplashScreen(),
      error: (e, _) => _BootErrorScreen(error: '$e'),
    );
  }
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}

class _BootErrorScreen extends StatelessWidget {
  const _BootErrorScreen({required this.error});
  final String error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline,
                  size: 56, color: AppTheme.dangerFg),
              const SizedBox(height: 12),
              Text(
                'تعذّر تشغيل التطبيق.\n$error',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
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
