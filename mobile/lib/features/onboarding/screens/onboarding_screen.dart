/// Onboarding screen — first-launch flow.
///
/// Three swipeable pages (welcome → features → child form):
///   1. Welcome — big emoji + value proposition
///   2. What you'll find — feature highlights
///   3. Child setup, collects:
///      * Child's name (text)
///      * Age group (segmented chip selector)
///      * Avatar emoji (modal bottom sheet picker, optional)
///      * Gender (optional chip selector)
///
/// On submit:
///   * POST /api/children (via `createChildProvider`)
///   * Persist id + name + age_group to [OnboardingStorage]
///   * Set [onboardingCompletedProvider] = true
///   * Set [activeChildIdProvider] (in progress_providers) = new id
///   * Pop the route — the root scaffold takes over.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/enums.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../program/providers/progress_providers.dart';
import '../data/onboarding_storage.dart';
import '../providers/onboarding_providers.dart';
import 'avatar_picker_sheet.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _pageController = PageController();
  int _page = 0;
  String? _ageGroup;
  String? _gender;
  String? _avatarEmoji;

  static const _pageCount = 3;

  @override
  void dispose() {
    _nameController.dispose();
    _pageController.dispose();
    super.dispose();
  }

  void _goTo(int page) {
    _pageController.animateToPage(
      page,
      duration: Dt.base,
      curve: Curves.easeOutCubic,
    );
  }

  Future<void> _pickAvatar() async {
    final picked = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: AppTheme.surface,
      isScrollControlled: true,
      builder: (_) => AvatarPickerSheet(initial: _avatarEmoji),
    );
    if (picked != null) {
      setState(() => _avatarEmoji = picked);
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final ageGroup = _ageGroup;
    if (ageGroup == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('يرجى اختيار المرحلة العمرية.')),
      );
      return;
    }
    try {
      final child = await ref.read(createChildProvider.notifier).create(
            name: _nameController.text.trim(),
            ageGroup: ageGroup,
            gender: _gender,
            avatarEmoji: _avatarEmoji,
          );
      // Persist locally and flip the gate.
      final storage = ref.read(onboardingStorageProvider);
      await storage.setActiveChild(
        id: child.id,
        name: child.name,
        ageGroup: child.ageGroup,
      );
      await ref.read(onboardingStorageProvider).markOnboardingCompleted();
      await ref.read(onboardingCompletedProvider.notifier).markCompleted();
      if (mounted) {
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تعذّر إنشاء ملف الطفل: $e'),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final createState = ref.watch(createChildProvider);
    final busy = createState.isLoading;
    final isLastPage = _page == _pageCount - 1;

    return PopScope(
      canPop: false, // onboarding is mandatory
      child: Scaffold(
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: PageView(
                  controller: _pageController,
                  onPageChanged: (i) => setState(() => _page = i),
                  children: [
                    const _WelcomePage(),
                    const _FeaturesPage(),
                    _ChildFormPage(
                      formKey: _formKey,
                      nameController: _nameController,
                      ageGroup: _ageGroup,
                      gender: _gender,
                      avatarEmoji: _avatarEmoji,
                      onAgeGroup: (v) => setState(() => _ageGroup = v),
                      onGender: (v) => setState(() => _gender = v),
                      onPickAvatar: _pickAvatar,
                    ),
                  ],
                ),
              ),
              // ── Dots + CTA ──
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        for (var i = 0; i < _pageCount; i++)
                          AnimatedContainer(
                            duration: Dt.fast,
                            margin:
                                const EdgeInsets.symmetric(horizontal: 3),
                            width: _page == i ? 24 : 8,
                            height: 8,
                            decoration: BoxDecoration(
                              color: _page == i
                                  ? AppTheme.primary
                                  : Dt.track,
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    BouncyButton(
                      label: busy
                          ? 'جاري الحفظ...'
                          : (isLastPage ? 'ابدأ الرحلة' : 'التالي'),
                      icon: busy
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : null,
                      onTap: busy
                          ? null
                          : (isLastPage ? _submit : () => _goTo(_page + 1)),
                    ),
                    if (isLastPage) ...[
                      const SizedBox(height: 10),
                      Text(
                        'يمكنك تعديل هذه المعلومات لاحقاً من الإعدادات.',
                        textAlign: TextAlign.center,
                        style: Theme.of(context)
                            .textTheme
                            .bodySmall
                            ?.copyWith(color: AppTheme.textMuted),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _WelcomePage extends StatelessWidget {
  const _WelcomePage();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text('👨‍👩‍👧', style: TextStyle(fontSize: 96))
              .animate()
              .scale(
                begin: const Offset(.5, .5),
                duration: Dt.slow,
                curve: Curves.easeOutBack,
              ),
          const SizedBox(height: 24),
          Text(
            'أهلاً بك في المربّي الذكي',
            textAlign: TextAlign.center,
            style: Theme.of(context)
                .textTheme
                .headlineSmall
                ?.copyWith(fontWeight: FontWeight.w800),
          ).animate(delay: 150.ms).fadeIn(duration: Dt.base).slideY(begin: .2),
          const SizedBox(height: 12),
          Text(
            'رفيقك التربوي اليومي — مسارات تعليمية، نصائح مخصصة، '
            'ومساعد ذكي يجيب عن أسئلتك.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: AppTheme.textSecondary,
                  height: 1.7,
                ),
          ).animate(delay: 300.ms).fadeIn(duration: Dt.base).slideY(begin: .2),
        ],
      ),
    );
  }
}

class _FeaturesPage extends StatelessWidget {
  const _FeaturesPage();

  static const _features = [
    ('🛤️', 'مسارات تربوية', 'رحلات تعليمية قصيرة مصممة لعمر طفلك'),
    ('💬', 'مساعد ذكي', 'إجابات موثوقة عن تحدياتك التربوية اليومية'),
    ('🏅', 'إنجازات وتحفيز', 'تابع تقدمك واكسب شارات مع كل خطوة'),
  ];

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'ماذا ستجد؟',
            textAlign: TextAlign.center,
            style: Theme.of(context)
                .textTheme
                .headlineSmall
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 28),
          for (var i = 0; i < _features.length; i++) ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(20),
                boxShadow: Dt.cardShadow,
              ),
              child: Row(
                children: [
                  Text(_features[i].$1,
                      style: const TextStyle(fontSize: 36)),
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
                        const SizedBox(height: 2),
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
                .animate(delay: (120 * i).ms)
                .fadeIn(duration: Dt.base)
                .slideY(begin: .15, curve: Curves.easeOutCubic),
            if (i < _features.length - 1) const SizedBox(height: 14),
          ],
        ],
      ),
    );
  }
}

class _ChildFormPage extends StatelessWidget {
  const _ChildFormPage({
    required this.formKey,
    required this.nameController,
    required this.ageGroup,
    required this.gender,
    required this.avatarEmoji,
    required this.onAgeGroup,
    required this.onGender,
    required this.onPickAvatar,
  });

  final GlobalKey<FormState> formKey;
  final TextEditingController nameController;
  final String? ageGroup;
  final String? gender;
  final String? avatarEmoji;
  final ValueChanged<String> onAgeGroup;
  final ValueChanged<String?> onGender;
  final VoidCallback onPickAvatar;

  @override
  Widget build(BuildContext context) {
    return Form(
      key: formKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
        children: [
          Row(
            children: [
              Container(
                width: 56,
                height: 56,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Text('🧒', style: TextStyle(fontSize: 30)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'حدّثنا عن طفلك',
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'لنخصّص له تجربة تربوية مناسبة.',
                      style: Theme.of(context)
                          .textTheme
                          .bodyMedium
                          ?.copyWith(color: AppTheme.textSecondary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 28),
          // ── Name ──
          Text(
            'اسم طفلك',
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          TextFormField(
            controller: nameController,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              hintText: 'مثلاً: سارة، أحمد، ليلى',
              prefixIcon: Icon(Icons.person_outline),
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) {
                return 'الاسم مطلوب';
              }
              if (v.trim().length > 80) {
                return 'الاسم طويل جداً (الحد الأقصى 80 حرفاً)';
              }
              return null;
            },
          ),
          const SizedBox(height: 24),

          // ── Age group ──
          Text(
            'المرحلة العمرية',
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: AgeGroup.values
                .where((a) => a != AgeGroup.unspecified)
                .map((a) => _AgeChip(
                      label: a.label,
                      selected: ageGroup == a.wire,
                      onTap: () => onAgeGroup(a.wire),
                    ))
                .toList(),
          ),
          const SizedBox(height: 24),

          // ── Avatar ──
          Text(
            'صورة الطفل (اختياري)',
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          InkWell(
            borderRadius: BorderRadius.circular(Dt.rButton),
            onTap: onPickAvatar,
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(Dt.rButton),
                boxShadow: Dt.cardShadow,
              ),
              child: Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceAlt,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      avatarEmoji ?? '👶',
                      style: const TextStyle(fontSize: 24),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      avatarEmoji == null
                          ? 'اضغط لاختيار إيموجي'
                          : 'اضغط لتغيير الإيموجي',
                      style: TextStyle(
                        color: avatarEmoji == null
                            ? AppTheme.textMuted
                            : AppTheme.textPrimary,
                      ),
                    ),
                  ),
                  const Icon(Icons.chevron_left, color: AppTheme.textMuted),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // ── Gender (optional) ──
          Text(
            'الجنس (اختياري)',
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _Pill(
                label: 'ولد',
                icon: Icons.boy,
                selected: gender == 'male',
                onTap: () => onGender('male'),
              ),
              _Pill(
                label: 'بنت',
                icon: Icons.girl,
                selected: gender == 'female',
                onTap: () => onGender('female'),
              ),
              if (gender != null)
                _Pill(
                  label: 'مسح',
                  icon: Icons.close,
                  selected: false,
                  onTap: () => onGender(null),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _AgeChip extends StatelessWidget {
  const _AgeChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: AppTheme.primary,
      labelStyle: TextStyle(
        color: selected ? Colors.white : AppTheme.textPrimary,
        fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
      ),
      side: BorderSide(
        color: selected ? AppTheme.primary : const Color(0xFFD0D5DD),
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? AppTheme.primary : AppTheme.surfaceAlt,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 16,
              color: selected ? Colors.white : AppTheme.textSecondary,
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                color: selected ? Colors.white : AppTheme.textPrimary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// Note: we don't import `progress_providers.dart` from the form code
// — the create call is the only side effect. The exports come
// through [progress_providers.dart] when the user lands on
// PathsScreen, so the existing `activeChildIdProvider` picks up the
// new id transparently.
