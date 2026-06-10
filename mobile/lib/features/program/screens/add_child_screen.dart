/// Add a new child to the device's roster.
///
/// Re-uses [AvatarPickerSheet] and the [AgeGroup] enum, but unlike
/// [OnboardingScreen] it does NOT flip the `onboardingCompleted` flag
/// (the user already finished onboarding — they're just adding a
/// sibling). The new child becomes the active child on success.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/enums.dart';
import '../../../theme/app_theme.dart';
import '../../onboarding/screens/avatar_picker_sheet.dart';
import '../providers/progress_providers.dart';

class AddChildScreen extends ConsumerStatefulWidget {
  const AddChildScreen({super.key});

  @override
  ConsumerState<AddChildScreen> createState() => _AddChildScreenState();
}

class _AddChildScreenState extends ConsumerState<AddChildScreen> {
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تمّت إضافة ${child.name}.')),
        );
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تعذّر إضافة الطفل: $e'),
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

    return Scaffold(
      appBar: AppBar(
        title: const Text('إضافة طفل'),
        actions: [
          TextButton(
            onPressed: busy ? null : _submit,
            child: const Text(
              'إضافة',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 16,
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
            children: [
              Text(
                'اسم الطفل',
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(
                  hintText: 'مثلاً: يوسف، مريم، زياد',
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
                    .map((a) => ChoiceChip(
                          label: Text(a.label),
                          selected: _ageGroup == a.wire,
                          selectedColor: AppTheme.primary,
                          labelStyle: TextStyle(
                            color: _ageGroup == a.wire
                                ? Colors.white
                                : AppTheme.textPrimary,
                            fontWeight: _ageGroup == a.wire
                                ? FontWeight.w700
                                : FontWeight.w500,
                          ),
                          onSelected: (_) =>
                              setState(() => _ageGroup = a.wire),
                        ))
                    .toList(),
              ),
              const SizedBox(height: 24),
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
              if (busy) const Center(child: CircularProgressIndicator()),
            ],
          ),
        ),
      ),
    );
  }
}
