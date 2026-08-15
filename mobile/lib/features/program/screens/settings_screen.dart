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
import '../../../l10n/app_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart'
    show launchUrl, canLaunchUrl, LaunchMode;
import 'package:file_picker/file_picker.dart';
import 'package:share_plus/share_plus.dart';

import '../../../config/app_config.dart';
import '../../../core/app_routes.dart';
import 'package:package_info_plus/package_info_plus.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../data/progress_models.dart';
import '../providers/settings_providers.dart';
import '../providers/backup_provider.dart';
import 'children_list_screen.dart';
import '../../adhkar/services/notification_service.dart';
import '../widgets/follow_us_row.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  /// Re-arms the first-run tour by rewinding the stored version to 0. It can't
  /// play here — it points at the root scaffold's nav bar, which this modal
  /// route covers — so we say where it will show up instead.
  Future<void> _replayTour(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    await ref.read(onboardingStorageProvider).markTourSeen(0);
    ref.invalidate(tourVersionProvider);
    messenger.showSnackBar(
      SnackBar(
        content: Text(l10n.tourReplayQueued),
        duration: const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final asyncList = ref.watch(childrenListProvider);
    final profile = ref.watch(activeChildProfileProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.settingsTitle)),
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
              // A bare sentence used to be the whole branch. It is the same
              // shape of mistake as the empty children list that shipped with
              // no add button: a state the user can reach, that names the
              // problem and offers nothing to do about it.
              return Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(l10n.settingsNoChild),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: () =>
                          Navigator.of(context).push(AppRoutes.childrenList()),
                      icon: const Icon(Icons.add_circle_outline),
                      label: Text(l10n.childrenAddNew),
                    ),
                  ],
                ),
              );
            }
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
              children: [
                _ChildHeader(child: activeChild),
                const SizedBox(height: 24),
                _SettingsRow(
                  icon: Icons.swap_horiz,
                  title: l10n.settingsSwitchChild,
                  subtitle: l10n.settingsChildCount(
                      envelope.count, ChildrenListScreen.kMaxChildren),
                  onTap: () async {
                    await Navigator.of(context).push(AppRoutes.childrenList());
                    if (context.mounted) {
                      ref.invalidate(childrenListProvider);
                    }
                  },
                ),
                _SettingsRow(
                  icon: Icons.edit_outlined,
                  title: l10n.settingsEditChild,
                  subtitle: l10n.settingsEditChildDesc,
                  onTap: () async {
                    final changed = await Navigator.of(context).push(
                      AppRoutes.editChild(activeChild),
                    );
                    if (changed == true) {
                      ref.invalidate(childrenListProvider);
                    }
                  },
                ),
                // «ادعُ صديقًا» now lives in the hub under الإعدادات والمساعدة.
                // Settings is for settings; content and rewards belong in the
                // index, not buried behind a gear icon.
                _SettingsRow(
                  icon: Icons.cloud_sync_outlined,
                  title: l10n.settingsBackup,
                  subtitle: l10n.settingsBackupDesc,
                  iconColor: AppTheme.primary,
                  onTap: () => Navigator.of(context).push(AppRoutes.identity()),
                ),
                _SettingsRow(
                  icon: Icons.feedback_outlined,
                  title: l10n.settingsShareFeedback,
                  subtitle: l10n.settingsShareFeedbackDesc,
                  onTap: () => Navigator.of(context).push(AppRoutes.feedback()),
                ),
                _SettingsRow(
                  icon: Icons.explore_outlined,
                  title: l10n.tourReplay,
                  subtitle: l10n.tourReplayDesc,
                  onTap: () => _replayTour(context, ref),
                ),
                _SettingsRow(
                  icon: Icons.restart_alt,
                  title: l10n.settingsResetProgress,
                  subtitle: l10n.settingsResetDesc,
                  iconColor: AppTheme.dangerFg,
                  onTap: () => _confirmReset(context, ref, activeChild),
                ),
                const SizedBox(height: 24),
                // The single language control. It sets the interface, the
                // curriculum text and the media language together — there used
                // to be a second switch here just for media, and two switches
                // meant they could disagree.
                _SettingsRow(
                  icon: Icons.translate,
                  title: l10n.language,
                  subtitle: Localizations.localeOf(context).languageCode == 'ar'
                      ? l10n.arabic
                      : l10n.english,
                  onTap: () {
                    final currentLocale = ref.read(appLocaleProvider);
                    final currentCode = currentLocale?.languageCode ?? Localizations.localeOf(context).languageCode;
                    final nextCode = currentCode == 'ar' ? 'en' : 'ar';
                    ref.read(appLocaleProvider.notifier).setLocale(nextCode);
                  },
                ),
                const SizedBox(height: 24),
                const _AdhkarSettingsRow(),
                const SizedBox(height: 24),
                _SettingsRow(
                  icon: Icons.star_outline,
                  title: l10n.settingsRate,
                  subtitle: l10n.settingsRateDesc,
                  onTap: () async {
                    final market = Uri.parse(
                        'market://details?id=com.alsaba.almorabbi');
                    final web = Uri.parse(
                        'https://play.google.com/store/apps/details?id=com.alsaba.almorabbi');
                    if (await canLaunchUrl(market)) {
                      await launchUrl(market,
                          mode: LaunchMode.externalApplication);
                    } else {
                      await launchUrl(web,
                          mode: LaunchMode.externalApplication);
                    }
                  },
                ),
                _SettingsRow(
                  icon: Icons.shield_outlined,
                  title: l10n.settingsPrivacy,
                  subtitle: l10n.settingsPrivacyDesc,
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
                  icon: Icons.menu_book_outlined,
                  title: l10n.settingsMethodologyLink,
                  subtitle: l10n.settingsMethodologyDesc,
                  onTap: () async {
                    final uri =
                        Uri.parse('https://alsaba.cloud/methodology');
                    if (await canLaunchUrl(uri)) {
                      await launchUrl(uri,
                          mode: LaunchMode.externalApplication);
                    }
                  },
                ),
                const SizedBox(height: 20),
                const FollowUsRow(),
                const SizedBox(height: 20),
                // المفضلة and إنجازاتي moved to the hub (المكتبة / الإنجازات).
                // Content people go looking for should be in the index, not
                // findable only by someone who thought to open settings.
                _SettingsRow(
                  icon: Icons.file_download_outlined,
                  title: l10n.settingsExport,
                  subtitle: l10n.settingsExportDesc,
                  onTap: () => _exportData(context, ref),
                ),
                _SettingsRow(
                  icon: Icons.file_upload_outlined,
                  title: l10n.settingsImport,
                  subtitle: l10n.settingsImportDesc,
                  onTap: () => _importData(context, ref),
                ),
                const SizedBox(height: 24),
                Center(
                  child: FutureBuilder<PackageInfo>(
                    future: PackageInfo.fromPlatform(),
                    builder: (context, snap) {
                      final version = snap.hasData
                          ? '${snap.data!.version}+${snap.data!.buildNumber}'
                          : '—';
                      return Text(
                        l10n.settingsVersion(version),
                        style: const TextStyle(
                          color: AppTheme.textMuted,
                          fontSize: 12,
                        ),
                      );
                    },
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
    final l10n = AppLocalizations.of(context);
    final backupService = ref.read(backupServiceProvider);

    // Show loading indicator
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    scaffoldMessenger.showSnackBar(
      SnackBar(content: Text(l10n.settingsPreparingBackup)),
    );

    try {
      final jsonString = await backupService.exportToJson();
      final filename = backupService.generateBackupFilename();
      
      // Save to temporary file
      final tempDir = await Directory.systemTemp.createTemp('tg_backup_');
      final file = File('${tempDir.path}/$filename');
      await file.writeAsString(jsonString);
      
      // Share the file
      await SharePlus.instance.share(ShareParams(
        files: [XFile(file.path)],
        text: l10n.settingsBackupTitle,
        subject: l10n.settingsBackupName,
      ));

      if (context.mounted) {
        scaffoldMessenger.showSnackBar(
          SnackBar(content: Text(l10n.settingsExportSuccess)),
        );
      }
    } catch (e) {
      if (context.mounted) {
        scaffoldMessenger.showSnackBar(
          SnackBar(
            content: Text(l10n.settingsExportFailed(e)),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    }
  }

  /// Import user data from JSON file.
  Future<void> _importData(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final backupService = ref.read(backupServiceProvider);

    try {
      // Pick a file
      final pickerResult = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['json'],
        dialogTitle: l10n.settingsImportFile,
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
          title: Text(l10n.settingsImportConfirm),
          content: Text(
            '${l10n.settingsImportDesc1} ${l10n.settingsImportDesc2}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: Text(l10n.cancel),
            ),
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              style: TextButton.styleFrom(foregroundColor: AppTheme.primary),
              child: Text(l10n.settingsImportBtn),
            ),
          ],
        ),
      );

      if (confirmed != true) return;

      // Perform import
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.settingsImporting)),
        );
      }

      final importResult = await backupService.importFromJson(jsonString);

      if (context.mounted) {
        if (importResult.success) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                l10n.settingsImportSuccess(
                  importResult.importedFavoritesCount,
                  importResult.importedReflectionsCount,
                ),
              ),
              backgroundColor: AppTheme.success,
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                  l10n.settingsImportFailed('${importResult.errorMessage}')),
              backgroundColor: AppTheme.dangerFg,
            ),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(l10n.settingsImportFailed(e)),
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
    final l10n = AppLocalizations.of(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.settingsResetConfirm),
        content: Text(
          '${l10n.settingsResetDesc1(child.name)} ${l10n.settingsResetDesc2}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.cancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppTheme.dangerFg),
            child: Text(l10n.settingsResetBtn),
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
                ? l10n.settingsNoProgress
                : l10n.settingsResetDone(deleted),
          ),
        ),
      );
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.settingsResetFailed(e)),
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
    final l10n = AppLocalizations.of(context);
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
                        text: _ageLabel(l10n, child.ageGroup),
                      ),
                      if (child.gender != null)
                        _Tag(
                          icon: Icons.person_outline,
                          text: _genderLabel(l10n, child.gender!),
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

  String _ageLabel(AppLocalizations l10n, String wire) {
    switch (wire) {
      case 'prenatal-1':
        return l10n.ageGroupPrenatal;
      case '2-3':
        return l10n.ageGroup2to3;
      case '4-6':
        return l10n.ageGroup4to6;
      case '7-9':
        return l10n.ageGroup7to9;
      case '10-12':
        return l10n.ageGroup10to12;
      case '13-15':
        return l10n.ageGroup13to15;
      case '16-18':
        return l10n.ageGroup16to18;
      default:
        return wire;
    }
  }

  String _genderLabel(AppLocalizations l10n, String wire) {
    switch (wire) {
      case 'male':
        return l10n.onbBoy;
      case 'female':
        return l10n.onbGirl;
      case 'other':
        return l10n.genderOther;
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
            Text(AppLocalizations.of(context).settingsLoadFailed(error),
                textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: Text(AppLocalizations.of(context).retry),
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
        title: Text(
          AppLocalizations.of(context).settingsFamilyAdhkar,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
        ),
        subtitle: Text(
          AppLocalizations.of(context).settingsFamilyAdhkarDesc,
          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
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
