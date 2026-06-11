/// Favorites screen — P1 launch item #1 (local-only).
///
/// Shows all favorited lessons and daily tips in a simple list.
/// Tapping a lesson navigates to the LessonScreen.
/// Tapping the delete icon removes from favorites.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../data/models.dart';
import '../providers/favorites_provider.dart';
import '../providers/program_providers.dart';
import 'lesson_screen.dart';

class FavoritesScreen extends ConsumerWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final favorites = ref.watch(favoritesProvider);
    final lessonIds = favorites['lessons'] ?? [];
    final tipIds = favorites['tips'] ?? [];

    if (lessonIds.isEmpty && tipIds.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: const Text('المفضلة')),
        body: const _EmptyState(),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('المفضلة'),
        actions: [
          if (lessonIds.isNotEmpty || tipIds.isNotEmpty)
            IconButton(
              tooltip: 'مسح الكل',
              icon: const Icon(Icons.delete_sweep_outlined),
              onPressed: () => _confirmClearAll(context, ref),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          if (lessonIds.isNotEmpty) ...[
            _SectionHeader(
              title: 'الدروس المحفوظة',
              count: lessonIds.length,
            ),
            const SizedBox(height: 8),
            for (final id in lessonIds)
              _FavoriteLessonCard(
                lessonId: id,
                onRemove: () => ref
                    .read(favoritesProvider.notifier)
                    .toggleLesson(id),
              ),
            const SizedBox(height: 24),
          ],
          if (tipIds.isNotEmpty) ...[
            _SectionHeader(
              title: 'النصائح المحفوظة',
              count: tipIds.length,
            ),
            const SizedBox(height: 8),
            for (final id in tipIds)
              _FavoriteTipCard(
                tipId: id,
                onRemove: () =>
                    ref.read(favoritesProvider.notifier).toggleTip(id),
              ),
          ],
        ],
      ),
    );
  }

  Future<void> _confirmClearAll(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('مسح جميع المفضلة؟'),
        content: const Text(
            'سيتم إزالة كل الدروس والنصائح المحفوظة. لا يمكن التراجع.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('إلغاء'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppTheme.dangerFg),
            child: const Text('مسح الكل'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(favoritesProvider.notifier).clearAll();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('تم مسح جميع المفضلة')),
        );
      }
    }
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.favorite_border,
              size: 64,
              color: AppTheme.textMuted.withValues(alpha: 0.5),
            ),
            const SizedBox(height: 16),
            Text(
              'لا توجد عناصر في المفضلة بعد',
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            Text(
              'اضغط أيقونة القلب ♡ على أي درس أو نصيحة\nلإضافتها هنا والوصول لها بسرعة.',
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: AppTheme.textMuted),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.count});

  final String title;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          title,
          style: Theme.of(context)
              .textTheme
              .titleMedium
              ?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(
            color: AppTheme.primary.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Text(
            '$count',
            style: const TextStyle(
              color: AppTheme.primary,
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
        ),
      ],
    );
  }
}

class _FavoriteLessonCard extends ConsumerWidget {
  const _FavoriteLessonCard({
    required this.lessonId,
    required this.onRemove,
  });

  final String lessonId;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncLesson = ref.watch(lessonProvider(lessonId));
    return asyncLesson.when(
      data: (lesson) => Card(
        margin: const EdgeInsets.only(bottom: 8),
        color: AppTheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: Color(0xFFE5E7EB)),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () {
            Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => LessonScreen(
                  lessonId: lesson.id,
                  ageGroup: lesson.ageGroup,
                  childId: null,
                ),
              ),
            );
          },
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.menu_book,
                      color: AppTheme.primary, size: 22),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        lesson.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${lesson.ageGroup} · ${lesson.domain}',
                        style: Theme.of(context)
                            .textTheme
                            .bodySmall
                            ?.copyWith(color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: onRemove,
                  icon: const Icon(Icons.favorite, color: Colors.redAccent),
                  tooltip: 'إزالة من المفضلة',
                ),
              ],
            ),
          ),
        ),
      ),
      loading: () => const _SkeletonCard(),
      error: (_, __) => const _ErrorCard(),
    );
  }
}

class _FavoriteTipCard extends ConsumerWidget {
  const _FavoriteTipCard({
    required this.tipId,
    required this.onRemove,
  });

  final String tipId;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Fallback: show just the ID with remove button
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      color: AppTheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: Color(0xFFE5E7EB)),
      ),
      child: ListTile(
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: const Color(0xFFFFE9C7),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(
            Icons.wb_sunny_outlined,
            color: Color(0xFF8A5A0F),
            size: 22,
          ),
        ),
        title: Text(
          tipId,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: const Text('نصيحة يومية محفوظة'),
        trailing: IconButton(
          onPressed: onRemove,
          icon: const Icon(Icons.favorite, color: Colors.redAccent),
          tooltip: 'إزالة من المفضلة',
        ),
      ),
    );
  }
}

class _SkeletonCard extends StatelessWidget {
  const _SkeletonCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: AppTheme.surfaceAlt,
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        title: Container(
          width: double.infinity,
          height: 16,
          color: AppTheme.surfaceAlt,
        ),
        subtitle: Container(
          width: 120,
          height: 12,
          color: AppTheme.surfaceAlt,
        ),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      color: AppTheme.dangerBg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: AppTheme.dangerFg),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            const Icon(Icons.error_outline, color: AppTheme.dangerFg),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'تعذّر تحميل هذا العنصر المحفوظ',
                style:
                    const TextStyle(color: AppTheme.dangerFg, fontSize: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
