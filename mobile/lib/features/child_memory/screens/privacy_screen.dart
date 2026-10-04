/// Settings → «الخصوصية وبياناتك»: every control over the family's data in
/// one place (MOBILE_API §9.2, §9.6, §10).
///
///   * the memory switch, and «ما يعرفه المربّي عن …» for each child;
///   * erase the memory of every child at once (the switch keeps its setting);
///   * delete the account — or ask for it without the app;
///   * the privacy policy.
///
/// The memory rows appear only when the server has memory; deletion is always
/// offered (on a server without in-app deletion its screen gives the e-mail
/// path and the public page).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../config/app_config.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/directional_chevron.dart';
import '../../program/providers/settings_providers.dart';
import '../device_proof/device_proof_service.dart' show kSupportEmail;
import '../providers/memory_providers.dart';
import '../widgets/memory_errors.dart';
import '../widgets/memory_switch_tile.dart';
import 'account_deletion_screen.dart' show deleteAccountPageUri;

class PrivacyScreen extends ConsumerStatefulWidget {
  const PrivacyScreen({super.key});

  @override
  ConsumerState<PrivacyScreen> createState() => _PrivacyScreenState();
}

class _PrivacyScreenState extends ConsumerState<PrivacyScreen> {
  bool _busy = false;

  Future<void> _eraseAll() async {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.privacyEraseMemory),
        content: Text(l10n.privacyEraseMemoryBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.cancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: colors.dangerFg),
            child: Text(l10n.delete),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    final container = ProviderScope.containerOf(context, listen: false);
    try {
      await container.read(memoryRepositoryProvider).eraseAll();
      container
        ..invalidate(childMemoryProvider)
        ..invalidate(dueFollowupsProvider)
        ..invalidate(weeklyPlanProvider);
      messenger.showSnackBar(SnackBar(content: Text(l10n.privacyMemoryErased)));
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(describeActionFailure(context, e))));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _open(Uri uri) async {
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      // No browser: nothing sensible to add here.
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final memory = ref.watch(memorySettingsProvider).valueOrNull;
    final children =
        ref.watch(childrenListProvider).valueOrNull?.children ?? const [];

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.privacyDataTitle),
        bottom: _busy
            ? const PreferredSize(
                preferredSize: Size.fromHeight(2),
                child: LinearProgressIndicator(minHeight: 2),
              )
            : null,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          children: [
            if (memory != null) ...[
              _Heading(text: l10n.privacyMemorySection),
              MemorySwitchTile(fallback: memory),
              const SizedBox(height: 8),
              for (final c in children)
                _Row(
                  icon: Icons.psychology_alt_outlined,
                  title: l10n.memoryTitle(c.name),
                  onTap: () => Navigator.of(context).push(
                      AppRoutes.childMemory(childId: c.id, childName: c.name)),
                ),
              _Row(
                icon: Icons.delete_sweep_outlined,
                iconColor: colors.dangerFg,
                title: l10n.privacyEraseMemory,
                subtitle: l10n.privacyEraseMemoryDesc,
                onTap: _busy ? null : _eraseAll,
              ),
              const SizedBox(height: 20),
            ],
            _Heading(text: l10n.privacyAccountSection),
            _Row(
              icon: Icons.person_remove_outlined,
              iconColor: colors.dangerFg,
              title: l10n.deleteAccount,
              subtitle: l10n.privacyDeleteAccountDesc,
              onTap: () =>
                  Navigator.of(context).push(AppRoutes.accountDeletion()),
            ),
            _Row(
              icon: Icons.open_in_new_rounded,
              title: l10n.privacyDeleteWithoutApp,
              subtitle: l10n.privacyDeleteWithoutAppDesc(kSupportEmail),
              onTap: () => _open(deleteAccountPageUri),
            ),
            const SizedBox(height: 20),
            _Row(
              icon: Icons.shield_outlined,
              title: l10n.settingsPrivacy,
              subtitle: l10n.settingsPrivacyDesc,
              onTap: () =>
                  _open(Uri.parse('${AppConfig.apiBaseUrl}/privacy-policy')),
            ),
          ],
        ),
      ),
    );
  }
}

class _Heading extends StatelessWidget {
  const _Heading({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.fromSTEB(4, 0, 4, 8),
      child: Semantics(
        header: true,
        child: Text(
          text,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: context.colors.textSecondary,
                fontWeight: FontWeight.w800,
              ),
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({
    required this.icon,
    required this.title,
    required this.onTap,
    this.subtitle,
    this.iconColor,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final Color? iconColor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: colors.surface,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(
              children: [
                Icon(icon, color: iconColor ?? colors.primary, size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title,
                          style: TextStyle(
                              color: colors.ink,
                              fontWeight: FontWeight.w700,
                              fontSize: 14.5,
                              height: 1.4)),
                      if (subtitle != null) ...[
                        const SizedBox(height: 2),
                        Text(subtitle!,
                            style: TextStyle(
                                color: colors.textSecondary,
                                fontSize: 12.5,
                                height: 1.4)),
                      ],
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                DirectionalChevron(color: colors.inkSoft),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
