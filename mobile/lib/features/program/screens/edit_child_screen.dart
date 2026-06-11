/// Edit child screen — same fields as onboarding, but PATCHes the
/// existing child instead of creating a new one.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/enums.dart';
import '../../../theme/app_theme.dart';
import '../../onboarding/screens/avatar_picker_sheet.dart';
import '../data/progress_models.dart';
import '../providers/settings_providers.dart';

class EditChildScreen extends ConsumerStatefulWidget {
  const EditChildScreen({super.key, required this.child});
  final ChildProfile child;

  @override
  ConsumerState<EditChildScreen> createState() => _EditChildScreenState();
}

class _EditChildScreenState extends ConsumerState<EditChildScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController =
      TextEditingController(text: widget.child.name);
  late String _ageGroup = widget.child.ageGroup;
  late String? _gender = widget.child.gender;
  late String? _avatarEmoji = widget.child.avatarEmoji;

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
    try {
      await ref.read(updateChildProvider.notifier).call(
            childId: widget.child.id,
            name: _nameController.text.trim(),
            ageGroup: _ageGroup,
            gender: _gender,
            avatarEmoji: _avatarEmoji,
          );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('تم حفظ التغييرات.')),
        );
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تعذّر الحفظ: $e'),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final updateState = ref.watch(updateChildProvider);
    final busy = updateState.isLoading;

    return Scaffold(
      appBar: AppBar(
        title: const Text('تعديل ملف الطفل'),
        actions: [
          TextButton(
            onPressed: busy ? null : _submit,
            child: const Text(
              'حفظ',
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
              // ── Name ──
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

              // ── Avatar ──
              Text(
                'صورة الطفل',
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

              // ── Gender ──
              Text(
                'الجنس',
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
                  _GenderPill(
                    label: 'ولد',
                    selected: _gender == 'male',
                    onTap: () => setState(() => _gender = 'male'),
                  ),
                  _GenderPill(
                    label: 'بنت',
                    selected: _gender == 'female',
                    onTap: () => setState(() => _gender = 'female'),
                  ),

                  if (_gender != null)
                    _GenderPill(
                      label: 'مسح',
                      selected: false,
                      onTap: () => setState(() => _gender = null),
                    ),
                ],
              ),
              const SizedBox(height: 32),
              if (busy)
                const Center(child: CircularProgressIndicator()),
            ],
          ),
        ),
      ),
    );
  }
}

class _GenderPill extends StatelessWidget {
  const _GenderPill({
    required this.label,
    required this.selected,
    required this.onTap,
  });
  final String label;
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
        child: Text(
          label,
          style: TextStyle(
            color: selected ? Colors.white : AppTheme.textPrimary,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}
