/// Update splash screen — «إيه الجديد؟» shown once after each version bump.
///
/// Plays the welcome video and lists what's new. The user taps «ابدأ»
/// to proceed. The version is recorded so this screen doesn't show again
/// until the next update.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:video_player/video_player.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../data/onboarding_storage.dart';

/// The app version tag displayed in the what's-new list.
/// Bump this whenever a new update-splash is warranted.
const updateSplashVersion = '1.0.26';

/// Simple state — when set to true, [_AppBootstrapper] knows the update
/// splash has been dismissed and will render [RootScaffold] instead.
final updateSplashDismissedProvider = StateProvider<bool>((ref) => false);

class UpdateSplashScreen extends ConsumerStatefulWidget {
  const UpdateSplashScreen({super.key});

  @override
  ConsumerState<UpdateSplashScreen> createState() => _UpdateSplashScreenState();
}

class _UpdateSplashScreenState extends ConsumerState<UpdateSplashScreen> {
  late final VideoPlayerController _controller;
  bool _videoReady = false;

  static const _features = [
    ('📖', 'قصص قبل النوم الجديدة',
        'أضفنا 4 قصص تربوية مصورة وهادئة جديدة (ليلى، صالح، نور، ومريم) لمساعدة طفلك على الاسترخاء والنوم بسلام.'),
    ('📱', 'QR ويب شير للمراهقين 13-18',
        'شارك "ميزان العادات" مع ابنك المراهق عبر رابط ويب — يدخل من متصفحه بدون تثبيت.'),
    ('👦', 'وضع الطفل 7-12 سنة',
        'خلّي طفلك يسجّل عاداته اليومية بنفسه تحت إشرافك — تقييم ذاتي بدون ضغط.'),
    ('🔗', 'ثبات وسرعة',
        'التطبيق بقى يتعامل مع انقطاع الشبكة بسلاسة — بياناتك في أمان.'),
  ];

  @override
  void initState() {
    super.initState();
    _controller = VideoPlayerController.asset(
      'assets/images/generated/onboarding_welcome.mp4',
    );
    WidgetsBinding.instance.addPostFrameCallback((_) => _initVideo());
  }

  Future<void> _initVideo() async {
    try {
      await _controller.initialize();
      if (!mounted) return;
      _controller.setLooping(true);
      _controller.setVolume(0);
      _controller.play();
      setState(() => _videoReady = true);
    } catch (_) {
      // Video unavailable — proceed without it.
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _dismiss() async {
    // Record this version in SharedPreferences.
    final prefs = await SharedPreferences.getInstance();
    final storage = OnboardingStorage(prefs);
    await storage.markUpdateSeen(updateSplashVersion);

    // Flip the provider — [_AppBootstrapper] watches it and will
    // rebuild showing [RootScaffold] instead of this screen.
    if (!mounted) return;
    ref.read(updateSplashDismissedProvider.notifier).state = true;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
          child: Column(
            children: [
              // ── Video ──
              ClipRRect(
                borderRadius: BorderRadius.circular(18),
                child: _videoReady
                    ? AspectRatio(
                        aspectRatio: _controller.value.aspectRatio,
                        child: VideoPlayer(_controller),
                      )
                    : AspectRatio(
                        aspectRatio: 1280 / 720,
                        child: Container(
                          color: Colors.black12,
                          child: const Center(
                            child: Icon(Icons.play_circle_outline,
                                size: 48, color: Colors.white24),
                          ),
                        ),
                      ),
              )
                  .animate()
                  .scale(
                    begin: const Offset(.85, .85),
                    duration: Dt.slow,
                    curve: Curves.easeOutBack,
                  )
                  .fadeIn(duration: Dt.base),
              const SizedBox(height: 24),

              // ── Title ──
              Text(
                'تحديث رئيسي 🎉',
                textAlign: TextAlign.center,
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              )
                  .animate(delay: 150.ms)
                  .fadeIn(duration: Dt.base)
                  .slideY(begin: .2),
              const SizedBox(height: 8),
              Text(
                'إصدار $updateSplashVersion — إيه الجديد؟',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppTheme.primary,
                      fontWeight: FontWeight.w600,
                    ),
              )
                  .animate(delay: 250.ms)
                  .fadeIn(duration: Dt.base),
              const SizedBox(height: 24),

              // ── Feature list ──
              for (var i = 0; i < _features.length; i++) ...[
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: Dt.cardShadow,
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(_features[i].$1,
                          style: const TextStyle(fontSize: 32)),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _features[i].$2,
                              style: const TextStyle(
                                fontWeight: FontWeight.w800,
                                fontSize: 16,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              _features[i].$3,
                              style: const TextStyle(
                                color: AppTheme.textSecondary,
                                fontSize: 13,
                                height: 1.5,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                )
                    .animate(delay: (300 + 100 * i).ms)
                    .fadeIn(duration: Dt.base)
                    .slideY(begin: .15, curve: Curves.easeOutCubic),
                if (i < _features.length - 1) const SizedBox(height: 12),
              ],

              const SizedBox(height: 32),

              // ── CTA ──
              BouncyButton(
                label: 'ابدأ',
                icon: const Icon(Icons.arrow_forward, color: Colors.white),
                onTap: _dismiss,
              )
                  .animate(delay: 800.ms)
                  .fadeIn(duration: Dt.base),
              const SizedBox(height: 12),
              Text(
                'مرّة واحدة فقط — لن تظهر هذه الشاشة مجدداً.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textMuted,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
