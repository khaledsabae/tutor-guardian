/// Children list — Phase 8-B multi-child switcher.
///
/// Reached from:
///   * the [ActiveChildChip] in the PathsScreen AppBar
///   * a "Switch child" row in the Settings screen (future)
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../journey/providers/journey_providers.dart';
import '../../journey/screens/child_journey_screen.dart';
import '../data/progress_models.dart';
import '../providers/progress_providers.dart';
import '../providers/settings_providers.dart';
import 'add_child_screen.dart';

class ChildrenListScreen extends ConsumerWidget {
  const ChildrenListScreen({super.key});

  /// Phase 8-B — capped to 5 to keep the UI manageable. The backend
  /// doesn't enforce this; it's a client-side affordance.
  static const int kMaxChildren = 5;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncList = ref.watch(childrenListProvider);
    final activeId = ref.watch(activeChildIdProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('إدارة الأطفال')),
      body: SafeArea(
        child: asyncList.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _ErrorView(
            error: '$e',
            onRetry: () => ref.invalidate(childrenListProvider),
          ),
          data: (envelope) {
            if (envelope.children.isEmpty) {
              return const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Text(
                    'لا يوجد أطفال على هذا الجهاز. ابدأ بإضافة أول طفل.',
                    textAlign: TextAlign.center,
                  ),
                ),
              );
            }
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
              children: [
                _ChildCount(count: envelope.children.length, max: kMaxChildren),
                const SizedBox(height: 8),
                ...envelope.children.map(
                  (c) => _ChildTile(
                    child: c,
                    isActive: c.id == activeId,
                    onSwitch: () => _switchTo(context, ref, c),
                    onDelete: () => _deleteChild(context, ref, c),
                    onJourney: () => _openJourney(context, c),
                  ),
                ),
                const SizedBox(height: 12),
                if (envelope.children.length < kMaxChildren)
                  OutlinedButton.icon(
                    onPressed: () => _addChild(context, ref),
                    icon: const Icon(Icons.add_circle_outline),
                    label: const Text('إضافة طفل جديد'),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(50),
                      side: BorderSide(
                        color: AppTheme.primary.withValues(alpha: 0.5),
                      ),
                      foregroundColor: AppTheme.primary,
                    ),
                  )
                else
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceAlt,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.info_outline,
                            size: 18, color: AppTheme.textMuted),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'وصلت للحد الأقصى ($kMaxChildren أطفال). احذف طفلاً لإضافة طفل جديد.',
                            style: TextStyle(
                              color: AppTheme.textSecondary,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }

  Future<void> _switchTo(
    BuildContext context,
    WidgetRef ref,
    ChildProfile child,
  ) async {
    final currentId = ref.read(activeChildIdProvider);
    if (currentId == child.id) {
      // No-op switch.
      Navigator.of(context).pop();
      return;
    }
    try {
      await ref.read(switchActiveChildProvider.notifier).call(child);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تم التبديل إلى ${child.name}.')),
        );
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تعذّر التبديل: $e'),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    }
  }

  void _openJourney(BuildContext context, ChildProfile child) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChildJourneyScreen(
          childId: child.id,
          childName: child.name,
          ageGroup: child.ageGroup,
        ),
      ),
    );
  }

  Future<void> _addChild(BuildContext context, WidgetRef ref) async {
    final added = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const AddChildScreen()),
    );
    if (added == true) {
      ref.invalidate(childrenListProvider);
    }
  }

  Future<void> _deleteChild(
    BuildContext context,
    WidgetRef ref,
    ChildProfile child,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('حذف الطفل'),
        content: Text(
          'هل أنت متأكد من حذف «${child.name}»؟ سيُحذف ملفه نهائيًا.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('إلغاء'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppTheme.dangerFg),
            child: const Text('حذف'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(deleteChildProvider.notifier).call(child.id);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تم حذف ${child.name}.')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تعذّر الحذف: $e'),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    }
  }
}

class _ChildCount extends StatelessWidget {
  const _ChildCount({required this.count, required this.max});
  final int count;
  final int max;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Text(
        'لديك $count من أصل $max أطفال',
        style: const TextStyle(
          color: AppTheme.textSecondary,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _ChildTile extends StatelessWidget {
  const _ChildTile({
    required this.child,
    required this.isActive,
    required this.onSwitch,
    required this.onDelete,
    required this.onJourney,
  });
  final ChildProfile child;
  final bool isActive;
  final VoidCallback onSwitch;
  final VoidCallback onDelete;
  final VoidCallback onJourney;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 8),
      color: isActive
          ? AppTheme.primary.withValues(alpha: 0.06)
          : AppTheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isActive ? AppTheme.primary : const Color(0xFFE4E7EC),
          width: isActive ? 1.5 : 1,
        ),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onSwitch,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AppTheme.surfaceAlt,
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Text(
                  child.avatarEmoji ?? '👶',
                  style: const TextStyle(fontSize: 24),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      child.name,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _ageLabel(child.ageGroup),
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              if (isActive) ...[
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppTheme.primary,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text(
                    'نشط',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: 4),
                const Icon(Icons.check_circle, color: AppTheme.primary, size: 20),
              ] else
                const Icon(Icons.chevron_left,
                    color: AppTheme.textMuted, size: 20),
              if (kJourneyEnabled)
                IconButton(
                  icon: const Icon(Icons.auto_stories_outlined,
                      color: AppTheme.primary, size: 20),
                  tooltip: 'رحلة الطفل',
                  visualDensity: VisualDensity.compact,
                  onPressed: onJourney,
                ),
              IconButton(
                icon: const Icon(Icons.delete_outline,
                    color: AppTheme.textMuted, size: 20),
                tooltip: 'حذف الطفل',
                visualDensity: VisualDensity.compact,
                onPressed: onDelete,
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _ageLabel(String wire) {
    switch (wire) {
      case 'prenatal-1':
        return 'فترة الحمل وحتى عام';
      case '2-3':
        return '2–3 سنوات';
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
            Text('تعذّر تحميل قائمة الأطفال.\n$error',
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
