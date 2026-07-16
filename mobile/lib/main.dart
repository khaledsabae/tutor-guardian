import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'l10n/app_localizations.dart';
import 'l10n/l10n_global.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import 'package:flutter_animate/flutter_animate.dart';

import 'core/analytics.dart';

import 'api/tg_client.dart';
import 'state/chat_notifier.dart';
import 'widgets/ui/bouncy_button.dart';
import 'features/identity/identity_service.dart';
import 'features/onboarding/providers/onboarding_providers.dart';
import 'features/onboarding/screens/onboarding_screen.dart';
import 'features/onboarding/screens/update_splash_screen.dart';
import 'features/program/providers/progress_providers.dart';
import 'features/program/screens/paths_screen.dart';
import 'features/deeplink/deep_link_handler.dart';
import 'features/push/push_service.dart';
import 'features/referral/referral_service.dart';
import 'firebase_options.dart';
import 'features/routine/providers/child_mode_providers.dart';
import 'features/routine/screens/daily_routine_screen.dart';
import 'features/routine/screens/habit_child_mode_screen.dart';
import 'features/adhkar/services/notification_service.dart';
import 'screens/home_screen.dart';
import 'screens/chat_screen.dart';
import 'features/quran/screens/quran_screen.dart';
import 'theme/app_theme.dart';
import 'theme/design_tokens.dart';

// FCM background handler lives in features/push/push_service.dart
// (registered there via FirebaseMessaging.onBackgroundMessage).

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    systemNavigationBarColor: Colors.transparent,
    systemNavigationBarIconBrightness: Brightness.dark,
    statusBarIconBrightness: Brightness.dark,
  ));

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
    NotificationService.instance.processPendingTap();
  });

  // Phase 0.2 + Phase 1 growth loops — fire-and-forget so it never blocks
  // cold start. Order: session → push token → referral → identity.
  unawaited(_postLaunchGrowthLoop());

  // Activation-funnel bookkeeping (first-open day → one-shot day2_return).
  unawaited(Analytics.appOpened());
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
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      // Arabic locale (no country code matches all Arab locales cleanly).
      locale: const Locale('ar'),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      builder: (context, child) {
        // Keep the global l10n handle (used by contextless services such as
        // TgClient and state notifiers) in sync with the app locale.
        AppL10n.current = AppLocalizations.of(context);
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

final appConfigProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.watch(tgClientProvider);
  return await client.fetchAppConfig();
});

final packageInfoProvider = FutureProvider<PackageInfo>((ref) async {
  return await PackageInfo.fromPlatform();
});

class ForceUpdateScreen extends ConsumerWidget {
  final String storeUrl;
  const ForceUpdateScreen({super.key, required this.storeUrl});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                '🚀',
                style: TextStyle(fontSize: 72),
              ).animate().scale(duration: 400.ms),
              const SizedBox(height: 24),
              Text(
                l10n.forceUpdateTitle,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w900,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                l10n.forceUpdateMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.textSecondary,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 32),
              BouncyButton(
                label: '${l10n.forceUpdateButton} 🔗',
                color: Dt.primary,
                onTap: () async {
                  final uri = Uri.parse(storeUrl);
                  if (await canLaunchUrl(uri)) {
                    await launchUrl(uri, mode: LaunchMode.externalApplication);
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Resolves the cold-boot async chain: prefs → onboarding flag →
/// active child re-hydration → push the right screen.
class _AppBootstrapper extends ConsumerWidget {
  const _AppBootstrapper();

  Widget _buildNormalApp(WidgetRef ref, dynamic childMode) {
    if (childMode.active) {
      return const HabitChildModeScreen();
    }
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
      Future(() {
        if (ref.read(activeChildIdProvider) != profile.id) {
          ref.read(activeChildIdProvider.notifier).state = profile.id;
        }
      });
    }
    // Also restore child mode from secure storage if a token exists.
    Future(() async {
      await ref.read(childModeProvider.notifier).restore();
    });
    // If the user just updated the app, show the what's-new splash
    // once before entering the main screen.
    ref.watch(updateSplashDismissedProvider);
    final seenVersion = ref.read(onboardingStorageProvider).lastSeenVersion;
    if (seenVersion != updateSplashVersion) {
      return const UpdateSplashScreen();
    }
    return const RootScaffold();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncPrefs = ref.watch(sharedPreferencesProvider);
    final childMode = ref.watch(childModeProvider);
    return asyncPrefs.when(
      data: (_) {
        final configAsync = ref.watch(appConfigProvider);
        return configAsync.when(
          data: (config) {
            final minBuild = config['minimum_build_number'] as int? ?? 0;
            final storeUrl = config['store_url'] as String? ??
                'https://play.google.com/store/apps/details?id=com.alsaba.almorabbi';

            final packageInfoAsync = ref.watch(packageInfoProvider);
            return packageInfoAsync.when(
              data: (packageInfo) {
                final currentBuild = int.tryParse(packageInfo.buildNumber) ?? 0;
                if (currentBuild < minBuild) {
                  return ForceUpdateScreen(storeUrl: storeUrl);
                }
                return _buildNormalApp(ref, childMode);
              },
              loading: () => const _SplashScreen(),
              error: (_, __) => _buildNormalApp(ref, childMode),
            );
          },
          loading: () => const _SplashScreen(),
          error: (_, __) => _buildNormalApp(ref, childMode),
        );
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
            Text(
              AppLocalizations.of(context).appTitle,
              style: const TextStyle(
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
    final l10n = AppLocalizations.of(context);
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
                '${l10n.bootError}\n$error',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The 5-tab bottom navigation shell: اليوم / مساراتي / الورد / حساب اليوم|ميزان العادات / المساعد.
///
/// Note: each tab keeps its own state via the [IndexedStack] so that
/// switching between tabs does not lose scroll position or in-flight
/// streaming tokens.
///
/// The label of the 4th tab changes based on the active child's age group:
///   * 0-6 years → «حِساب اليوم» (biological routine tracker)
///   * 7-18 years → «ميزان العادات» (habit/value tracker)
class RootScaffold extends ConsumerStatefulWidget {
  const RootScaffold({super.key});

  @override
  ConsumerState<RootScaffold> createState() => _RootScaffoldState();
}

class _RootScaffoldState extends ConsumerState<RootScaffold> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final profile = ref.watch(activeChildProfileProvider);
    final fourthLabel = habitTabLabel(profile?.ageGroup ?? '', l10n);

    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [
          HomeScreen(onGoToTab: (i) => setState(() => _index = i)),
          const PathsScreen(),
          const QuranScreen(),
          const DailyRoutineScreen(),
          const ChatScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) {
          if (i == 2) unawaited(Analytics.quranOpened());
          setState(() => _index = i);
        },
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.home_outlined),
            selectedIcon: const Icon(Icons.home_rounded),
            label: l10n.navToday,
          ),
          NavigationDestination(
            icon: const Icon(Icons.route_outlined),
            selectedIcon: const Icon(Icons.route),
            label: l10n.navMyPaths,
          ),
          NavigationDestination(
            icon: const Icon(Icons.menu_book_outlined),
            selectedIcon: const Icon(Icons.menu_book),
            label: l10n.navAdhkar,
          ),
          NavigationDestination(
            icon: const Icon(Icons.child_care_outlined),
            selectedIcon: const Icon(Icons.child_care),
            label: fourthLabel,
          ),
          NavigationDestination(
            icon: const Icon(Icons.chat_bubble_outline),
            selectedIcon: const Icon(Icons.chat_bubble),
            label: l10n.navAssistant,
          ),
        ],
      ),
    );
  }
}
