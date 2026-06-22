import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_animate/flutter_animate.dart';

import 'api/tg_client.dart';
import 'config/app_config.dart';
import 'features/identity/identity_service.dart';
import 'features/onboarding/providers/onboarding_providers.dart';
import 'features/onboarding/screens/onboarding_screen.dart';
import 'features/program/providers/progress_providers.dart';
import 'features/program/screens/paths_screen.dart';
import 'features/deeplink/deep_link_handler.dart';
import 'features/push/push_service.dart';
import 'features/referral/referral_service.dart';
import 'firebase_options.dart';
import 'screens/chat_screen.dart';
import 'features/adhkar/services/notification_service.dart';
import 'screens/home_screen.dart';
import 'features/quran/screens/quran_screen.dart';
import 'theme/app_theme.dart';
import 'theme/design_tokens.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

  // Crashlytics — funnel all Flutter errors to Firebase in release builds.
  FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterFatalError;
  PlatformDispatcher.instance.onError = (error, stack) {
    FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
    return true;
  };

  // Initialize daily Adhkar local notifications
  await NotificationService.instance.init();

  runApp(const ProviderScope(child: TutorGuardianApp()));

  // Phase 0/1 deep links.
  WidgetsBinding.instance.addPostFrameCallback((_) {
    DeepLinkHandler.instance.init(appNavigatorKey);
  });

  // Phase 0.2 + Phase 1 growth loops — fire-and-forget so it never blocks
  // cold start. Order: session → push token → referral → identity.
  unawaited(_postLaunchGrowthLoop());
}

Future<void> _postLaunchGrowthLoop() async {
  try {
    await TgClient().ensureSession();
  } catch (_) {
    return;
  }
  await PushService.instance.registerToken();
  await PushService.instance.listenForeground();
  await ReferralService.instance.captureAndClaimOnFirstRun();
  await ReferralService.instance.refresh();
  await IdentityService.instance.silentRestore();
}

// Global navigator key for deep links/pushes that fire before a context exists.
final GlobalKey<NavigatorState> appNavigatorKey = GlobalKey<NavigatorState>();

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
      navigatorKey: appNavigatorKey,
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
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('🛡️', style: TextStyle(fontSize: 64))
                .animate()
                .scale(
                  begin: const Offset(.6, .6),
                  duration: Dt.slow,
                  curve: Curves.easeOutBack,
                ),
            const SizedBox(height: 12),
            const Text(
              AppConfig.appName,
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: AppTheme.primary,
              ),
            ).animate(delay: 150.ms).fadeIn(duration: Dt.base),
          ],
        ),
      ),
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

/// The 3-tab bottom navigation shell: اليوم / مساراتي / المساعد.
///
/// Note: each tab keeps its own state via the [IndexedStack] so that
/// switching between tabs does not lose scroll position or in-flight
/// streaming tokens.
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
        children: [
          HomeScreen(onGoToTab: (i) => setState(() => _index = i)),
          const PathsScreen(),
          const QuranScreen(),
          const ChatScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home_rounded),
            label: 'اليوم',
          ),
          NavigationDestination(
            icon: Icon(Icons.route_outlined),
            selectedIcon: Icon(Icons.route),
            label: 'مساراتي',
          ),
          NavigationDestination(
            icon: Icon(Icons.menu_book_outlined),
            selectedIcon: Icon(Icons.menu_book),
            label: 'الورد',
          ),
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: 'المساعد',
          ),
        ],
      ),
    );
  }
}
