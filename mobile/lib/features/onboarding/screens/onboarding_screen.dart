/// Onboarding screen — first-launch flow.
///
/// Collects:
///   1. Child's name (text)
///   2. Age group (segmented chip selector)
///   3. Avatar emoji (modal bottom sheet picker, optional)
///   4. Gender (optional chip selector)
///
/// On submit:
///   * POST /api/children (via `createChildProvider`)
///   * Persist id + name + age_group to [OnboardingStorage]
///   * Set [onboardingCompletedProvider] = true
///   * Set [activeChildIdProvider] (in progress_providers) = new id
///   * Pop the route — the root scaffold (ChatScreen + PathsScreen)
///     takes over.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/enums.dart';
import '../../../theme/app_theme.dart';
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
  String? _ageGroup;
  String? _gender;
  String? _avatarEmoji;

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
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

    return PopScope(
      canPop: false, // onboarding is mandatory
      child: Scaffold(
        body: SafeArea(
          child: Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
              children: [
                const SizedBox(height: 16),
                Row(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        color: AppTheme.primary.withValues(alpha: 0.10),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: const Icon(
                        Icons.family_restroom,
                        color: AppTheme.primary,
                        size: 32,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'أهلاً بك في المربّي الذكي',
                            style: Theme.of(context)
                                .textTheme
                                .titleLarge
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'حدّثنا عن طفلك لنخصّص له تجربة تربوية مناسبة.',
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
                const SizedBox(height: 32),
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
                  controller: _nameController,
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
                            selected: _ageGroup == a.wire,
                            onTap: () => setState(() => _ageGroup = a.wire),
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
                  borderRadius: BorderRadius.circular(12),
                  onTap: _pickAvatar,
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFD0D5DD)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 48,
                          height: 48,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: AppTheme.surfaceAlt,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            _avatarEmoji ?? '👶',
                            style: const TextStyle(fontSize: 24),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            _avatarEmoji == null
                                ? 'اضغط لاختيار إيموجي'
                                : 'اضغط لتغيير الإيموجي',
                            style: TextStyle(
                              color: _avatarEmoji == null
                                  ? AppTheme.textMuted
                                  : AppTheme.textPrimary,
                            ),
                          ),
                        ),
                        const Icon(Icons.chevron_left,
                            color: AppTheme.textMuted),
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
                      selected: _gender == 'male',
                      onTap: () => setState(() => _gender = 'male'),
                    ),
                    _Pill(
                      label: 'بنت',
                      icon: Icons.girl,
                      selected: _gender == 'female',
                      onTap: () => setState(() => _gender = 'female'),
                    ),

                    if (_gender != null)
                      _Pill(
                        label: 'مسح',
                        icon: Icons.close,
                        selected: false,
                        onTap: () => setState(() => _gender = null),
                      ),
                  ],
                ),
                const SizedBox(height: 32),
                ElevatedButton.icon(
                  onPressed: busy ? null : _submit,
                  icon: busy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.check),
                  label: Text(busy ? 'جاري الحفظ...' : 'ابدأ الرحلة'),
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size.fromHeight(54),
                    textStyle: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'يمكنك تعديل هذه المعلومات لاحقاً من الإعدادات.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(color: AppTheme.textMuted),
                ),
              ],
            ),
          ),
        ),
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
