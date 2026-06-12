/// Settings screen — Phase 7. Pushed onto the navigator from an
/// IconButton in the PathsScreen AppBar. The NavigationBar stays 2
/// tabs (المساعد / مساراتي); settings is a modal stack only.
///
/// Layout:
///   * Header — emoji + name + age_group of the active child
///   * Edit row — "تعديل المعلومات" → EditChildScreen
///   * Reset row — "إعادة تعيين التقدّم" → confirm dialog
///   * About row — privacy policy link (reuses /privacy-policy)
///   * Version footer
library;

import 'dart:io';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart'
    show launchUrl, canLaunchUrl, LaunchMode;
import 'package:file_picker/file_picker.dart';
import 'package:share_plus/share_plus.dart';

import '../../../config/app_config.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../data/progress_models.dart';
import '../providers/settings_providers.dart';
import '../providers/backup_provider.dart';
import 'children_list_screen.dart';
import 'edit_child_screen.dart';
import 'badges_screen.dart';
import 'favorites_screen.dart';
import '../providers/lesson_assets_provider.dart';
import '../../adhkar/services/notification_service.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  void _toggleLanguage(BuildContext context, WidgetRef ref, String current) {
    final newLang = current == 'ar' ? 'en' : 'ar';
    ref.read(contentLanguageProvider.notifier).setLanguage(newLang);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          newLang == 'ar'
              ? 'تم تغيير لغة الوسائط إلى العربية'
              : 'Media language changed to English',
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncList = ref.watch(childrenListProvider);
    final profile = ref.watch(activeChildProfileProvider);
    final currentLanguage = ref.watch(contentLanguageProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('الإعدادات')),
      body: SafeArea(
        child: asyncList.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _ErrorView(
            error: '$e',
            onRetry: () => ref.invalidate(childrenListProvider),
          ),
          data: (envelope) {
            final activeChild = profile != null
                ? envelope.children
                    .where((c) => c.id == profile.id)
                    .firstOrNull
                : envelope.children.firstOrNull;
            if (activeChild == null) {
              return const Center(
                child: Text('لا يوجد ملف طفل نشط.'),
              );
            }
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
              children: [
                _ChildHeader(child: activeChild),
                const SizedBox(height: 24),
                _SettingsRow(
                  icon: Icons.swap_horiz,
                  title: 'تبديل الطفل النشط',
                  subtitle: 'لديك ${envelope.count} من أصل ${ChildrenListScreen.kMaxChildren} أطفال',
                  onTap: () async {
                    await Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const ChildrenListScreen(),
                      ),
                    );
                    if (context.mounted) {
                      ref.invalidate(childrenListProvider);
                    }
                  },
                ),
                _SettingsRow(
                  icon: Icons.edit_outlined,
                  title: 'تعديل معلومات الطفل',
                  subtitle: 'الاسم، المرحلة العمرية، الصورة، الجنس',
                  onTap: () async {
                    final changed = await Navigator.of(context).push<bool>(
                      MaterialPageRoute(
                        builder: (_) => EditChildScreen(child: activeChild),
                      ),
                    );
                    if (changed == true) {
                      ref.invalidate(childrenListProvider);
                    }
                  },
                ),
                _SettingsRow(
                  icon: Icons.restart_alt,
                  title: 'إعادة تعيين التقدّم',
                  subtitle: 'سيتم مسح كل الدروس المكمّلة وإعادة السلسلة إلى 0',
                  iconColor: AppTheme.dangerFg,
                  onTap: () => _confirmReset(context, ref, activeChild),
                ),
                const SizedBox(height: 24),
                _SettingsRow(
                  icon: Icons.language,
                  title: 'لغة الوسائط التعليمية',
                  subtitle: currentLanguage == 'ar'
                      ? 'العربية (بودكاست وفيديو عربي)'
                      : 'English (English audio/video)',
                  onTap: () => _toggleLanguage(context, ref, currentLanguage),
                ),
                const SizedBox(height: 24),
                const _AdhkarSettingsRow(),
                const SizedBox(height: 24),
                _SettingsRow(
                  icon: Icons.shield_outlined,
                  title: 'سياسة الخصوصية',
                  subtitle: 'كيف نتعامل مع بياناتك',
                  onTap: () async {
                    final uri = Uri.parse(
                        '${AppConfig.apiBaseUrl}/privacy-policy');
                    if (await canLaunchUrl(uri)) {
                      await launchUrl(uri,
                          mode: LaunchMode.externalApplication);
                    }
                  },
                ),
                _SettingsRow(
                  icon: Icons.favorite_outline,
                  title: 'المفضلة',
                  subtitle: 'الدروس والنصائح التي حفظتها',
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const FavoritesScreen(),
                      ),
                    );
                  },
                ),
                _SettingsRow(
                  icon: Icons.emoji_events_outlined,
                  title: 'إنجازاتي',
                  subtitle: 'الشارات التي حصلت عليها',
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const BadgesScreen(),
                      ),
                    );
                  },
                ),
                _SettingsRow(
                  icon: Icons.file_download_outlined,
                  title: 'تصدير بياناتي',
                  subtitle: 'تصدير المفضلة والملاحظات كملف JSON',
                  onTap: () => _exportData(context, ref),
                ),
                _SettingsRow(
                  icon: Icons.file_upload_outlined,
                  title: 'استيراد بياناتي',
                  subtitle: 'استيراد النسخة الاحتياطية من ملف JSON',
                  onTap: () => _importData(context, ref),
                ),
                const SizedBox(height: 24),
                const Center(
                  child: Text(
                    'الإصدار ${AppConfig.appVersion}',
                    style: TextStyle(
                      color: AppTheme.textMuted,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  /// Export user data to JSON file and share it.
  Future<void> _exportData(BuildContext context, WidgetRef ref) async {
    final backupService = ref.read(backupServiceProvider);
    
    // Show loading indicator
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    scaffoldMessenger.showSnackBar(
      const SnackBar(content: Text('جاري تجهيز النسخة الاحتياطية...')),
    );

    try {
      final jsonString = await backupService.exportToJson();
      final filename = backupService.generateBackupFilename();
      
      // Save to temporary file
      final tempDir = await Directory.systemTemp.createTemp('tg_backup_');
      final file = File('${tempDir.path}/$filename');
      await file.writeAsString(jsonString);
      
      // Share the file
      await Share.shareXFiles(
        [XFile(file.path)],
        text: 'نسخة احتياطية من بيانات المربي الذكي',
        subject: 'نسخة احتياطية - المربي الذكي',
      );
      
      if (context.mounted) {
        scaffoldMessenger.showSnackBar(
          const SnackBar(content: Text('تم تصدير البيانات بنجاح')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        scaffoldMessenger.showSnackBar(
          SnackBar(
            content: Text('تعذّر التصدير: $e'),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    }
  }

  /// Import user data from JSON file.
  Future<void> _importData(BuildContext context, WidgetRef ref) async {
    final backupService = ref.read(backupServiceProvider);
    
    try {
      // Pick a file
      final pickerResult = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['json'],
        dialogTitle: 'اختر ملف النسخة الاحتياطية',
      );

      if (pickerResult == null || pickerResult.files.isEmpty) return;

      final file = pickerResult.files.first;
      final bytes = file.bytes ?? await File(file.path!).readAsBytes();
      final jsonString = utf8.decode(bytes);

      if (!context.mounted) return;

      // Show confirmation dialog
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('استيراد البيانات؟'),
          content: const Text(
            'سيتم دمج البيانات المستوردة مع بياناتك الحالية. '
            'هذا الإجراء لا يمكن التراجع عنه بسهولة.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('إلغاء'),
            ),
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              style: TextButton.styleFrom(foregroundColor: AppTheme.primary),
              child: const Text('استيراد'),
            ),
          ],
        ),
      );

      if (confirmed != true) return;

      // Perform import
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('جاري استيراد البيانات...')),
        );
      }

      final importResult = await backupService.importFromJson(jsonString);

      if (context.mounted) {
        if (importResult.success) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                'تم الاستيراد بنجاح: ${importResult.importedReflectionsCount} ملاحظة، ${importResult.importedFavoritesCount} مفضلة',
              ),
              backgroundColor: AppTheme.success,
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('تعذّر الاستيراد: ${importResult.errorMessage}'),
              backgroundColor: AppTheme.dangerFg,
            ),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تعذّر الاستيراد: $e'),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    }
  }

  Future<void> _confirmReset(
    BuildContext context,
    WidgetRef ref,
    ChildProfile child,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('إعادة تعيين التقدّم؟'),
        content: Text(
          'سيتم مسح كل الدروس المكمّلة لـ ${child.name} وستُعاد السلسلة إلى الصفر. '
          'هذا الإجراء لا يمكن التراجع عنه.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('إلغاء'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppTheme.dangerFg),
            child: const Text('إعادة التعيين'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    if (!context.mounted) return;
    try {
      final deleted = await ref
          .read(resetProgressProvider.notifier)
          .call(child.id);
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            deleted == 0
                ? 'لا يوجد تقدّم لإعادة تعيينه.'
                : 'تم مسح $deleted درس. السلسلة الآن 0.',
          ),
        ),
      );
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('تعذّر إعادة التعيين: $e'),
          backgroundColor: AppTheme.dangerFg,
        ),
      );
    }
  }
}

class _ChildHeader extends StatelessWidget {
  const _ChildHeader({required this.child});
  final ChildProfile child;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(24),
        boxShadow: Dt.cardShadow,
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 64,
              height: 64,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppTheme.primary.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(32),
              ),
              child: Text(
                child.avatarEmoji ?? '👶',
                style: const TextStyle(fontSize: 32),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    child.name,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: [
                      _Tag(
                        icon: Icons.cake_outlined,
                        text: _ageLabel(child.ageGroup),
                      ),
                      if (child.gender != null)
                        _Tag(
                          icon: Icons.person_outline,
                          text: _genderLabel(child.gender!),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _ageLabel(String wire) {
    switch (wire) {
      case '0-3':
        return '0–3 سنوات';
      case '4-6':
        return '4–6 سنوات';
      case '7-9':
        return '7–9 سنوات';
      case '10-12':
        return '10–12 سنة';
      case '13-15':
        return '13–15 سنة';
      case '16-18':
        return '16–18 سنة';
      default:
        return wire;
    }
  }

  String _genderLabel(String wire) {
    switch (wire) {
      case 'male':
        return 'ولد';
      case 'female':
        return 'بنت';
      case 'other':
        return 'أخرى';
      default:
        return wire;
    }
  }
}

class _Tag extends StatelessWidget {
  const _Tag({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: AppTheme.textSecondary),
          const SizedBox(width: 3),
          Text(
            text,
            style: const TextStyle(
              fontSize: 11,
              color: AppTheme.textSecondary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsRow extends StatelessWidget {
  const _SettingsRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.iconColor,
  });
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Color? iconColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        boxShadow: Dt.cardShadow,
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: (iconColor ?? AppTheme.primary).withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  icon,
                  size: 18,
                  color: iconColor ?? AppTheme.primary,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_left,
                  size: 18, color: AppTheme.textMuted),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.error, required this.onRetry});
  final String error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline,
                size: 48, color: AppTheme.dangerFg),
            const SizedBox(height: 12),
            Text('تعذّر تحميل الإعدادات.\n$error',
                textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('إعادة المحاولة'),
            ),
          ],
        ),
      ),
    );
  }
}

class _AdhkarSettingsRow extends StatefulWidget {
  const _AdhkarSettingsRow();

  @override
  State<_AdhkarSettingsRow> createState() => _AdhkarSettingsRowState();
}

class _AdhkarSettingsRowState extends State<_AdhkarSettingsRow> {
  bool _enabled = true;

  @override
  void initState() {
    super.initState();
    _loadState();
  }

  Future<void> _loadState() async {
    final enabled = await NotificationService.instance.isEnabled();
    if (mounted) {
      setState(() => _enabled = enabled);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Shadow on the outer box; color on a Material so the
    // SwitchListTile's ink renders correctly (framework assertion).
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        boxShadow: Dt.cardShadow,
      ),
      child: Material(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        clipBehavior: Clip.antiAlias,
        child: SwitchListTile(
        title: const Text(
          'إشعارات أذكار الأسرة',
          style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
        ),
        subtitle: const Text(
          'أحاديث نبوية وأدعية يومية (صباحاً ومساءً)',
          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
        ),
        value: _enabled,
        onChanged: (val) async {
          setState(() => _enabled = val);
          await NotificationService.instance.setEnabled(val);
        },
        secondary: Container(
          width: 36,
          height: 36,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: const Color(0xFFE65100).withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(
            Icons.notifications_active_outlined,
            size: 18,
            color: Color(0xFFE65100),
          ),
        ),
        ),
      ),
    );
  }
}
