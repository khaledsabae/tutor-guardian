/// Path list screen — "مساراتي" tab.
///
/// Reads [pathsListProvider] (filtered by the current
/// [selectedAgeGroupProvider]). Renders a scrollable list of cards,
/// one per [CurriculumPath]. Tapping a card navigates to
/// [PathDetailScreen] with `?include=lessons` (the detail screen
/// makes a second, more focused fetch — so we don't pull lessons
/// for paths the user never opens).
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/emoji_hero.dart';
import '../../../widgets/ui/skeleton.dart';
import '../data/models.dart';
import '../providers/program_providers.dart';
import '../widgets/active_child_chip.dart';
import 'path_detail_screen.dart';
import 'search_screen.dart';
import 'settings_screen.dart';

class PathsScreen extends ConsumerWidget {
  const PathsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ageGroup = ref.watch(selectedAgeGroupProvider);
    final args = PathsListArgs(ageGroup: ageGroup);
    final asyncPaths = ref.watch(pathsListProvider(args));

    return Scaffold(
      appBar: AppBar(
        title: const Text('مساراتي 🛤️'),
        actions: [
          // Phase 8-B — active child chip (tap to switch).
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 10, horizontal: 4),
            child: Center(child: ActiveChildChip()),
          ),
          IconButton(
            tooltip: 'بحث',
            icon: const Icon(Icons.search),
            onPressed: () {
              Navigator.of(
                context,
              ).push(MaterialPageRoute(builder: (_) => const SearchScreen()));
            },
          ),
          // Phase 7 — settings is a push route, not a tab.
          IconButton(
            tooltip: 'الإعدادات',
            icon: const Icon(Icons.settings_outlined),
            onPressed: () {
              Navigator.of(
                context,
              ).push(MaterialPageRoute(builder: (_) => const SettingsScreen()));
            },
          ),
          IconButton(
            tooltip: 'تحديث',
            onPressed: () =>
                ref.read(pathsListProvider(args).notifier).refresh(),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: asyncPaths.when(
        data: (envelope) {
          if (envelope.paths.isEmpty) {
            return const EmptyState(
              emoji: '🧭',
              title: 'لا توجد مسارات بعد',
              subtitle: 'لا توجد مسارات لهذه المرحلة العمرية حالياً.',
            );
          }
          return RefreshIndicator(
            onRefresh: () =>
                ref.read(pathsListProvider(args).notifier).refresh(),
            child: ListView.separated(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
              itemCount: envelope.paths.length,
              separatorBuilder: (_, __) => const SizedBox(height: 16),
              itemBuilder: (context, i) {
                final card =
                    _PathCard(path: envelope.paths[i], ageGroup: ageGroup);
                // Stagger only the first screenful; later items appear
                // instantly (they're below the fold anyway).
                if (i >= Dt.maxStaggeredItems) return card;
                return card
                    .animate(delay: Dt.stagger * i)
                    .fadeIn(duration: Dt.base)
                    .slideY(begin: .08, curve: Curves.easeOutCubic);
              },
            ),
          );
        },
        loading: () => const SingleChildScrollView(
          physics: NeverScrollableScrollPhysics(),
          child: SkeletonList(count: 4, itemHeight: 170),
        ),
        error: (err, _) => EmptyState(
          emoji: '📡',
          title: 'تعذّر تحميل المسارات',
          subtitle: '$err',
          actionLabel: 'إعادة المحاولة',
          onAction: () => ref.read(pathsListProvider(args).notifier).refresh(),
        ),
      ),
    );
  }
}

class _PathCard extends StatelessWidget {
  const _PathCard({required this.path, required this.ageGroup});
  final CurriculumPath path;
  final String ageGroup;

  void _open(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PathDetailScreen(pathId: path.id, ageGroup: ageGroup),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final style = styleFor(path.domain);
    // One coherent button node for screen readers (title + description),
    // with the inner visual tree's own semantics excluded to avoid
    // fragmented announcements.
    return Semantics(
      button: true,
      label: 'مسار: ${path.title}. ${path.description}',
      onTap: () => _open(context),
      excludeSemantics: true,
      child: BouncyTap(
        onTap: () => _open(context),
        child: Hero(
          tag: 'path-${path.id}',
          child: Container(
            decoration: BoxDecoration(
              gradient: style.gradient,
              borderRadius: BorderRadius.circular(Dt.rCard),
              boxShadow: Dt.softShadow(style.base),
            ),
            padding: const EdgeInsets.all(20),
            child: DefaultTextStyle(
              style: const TextStyle(color: Colors.white),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      EmojiHero(emoji: style.emoji, size: 56),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              path.title,
                              style: const TextStyle(
                                fontSize: 19,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                                height: 1.3,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${path.ageLabel} · ${path.domainLabel}',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.white.withValues(alpha: .85),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    path.description,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 13,
                      height: 1.5,
                      color: Colors.white.withValues(alpha: .92),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _Pill(label: '⏱️ ${path.estimatedDays} يوم'),
                      _Pill(label: '📚 ${path.lessonIds.length} دروس'),
                      if (path.pedagogicalFramework != null)
                        _Pill(
                          label:
                              '🧠 ${_frameworkLabel(path.pedagogicalFramework!)}',
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  static String _frameworkLabel(String wire) {
    switch (wire) {
      case 'prophetic_7_7_7':
        return 'المنهج النبوي 7-7-7';
      case 'ghazali_tazkiyah':
        return 'تزكية الغزالي';
      case 'attachment_rahma':
        return 'الرابطة والرحمة';
      case 'zpd_scaffolded':
        return 'منطقة النمو القريبة';
      default:
        return wire;
    }
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: .18),
        borderRadius: BorderRadius.circular(Dt.rChip),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
    );
  }
}
