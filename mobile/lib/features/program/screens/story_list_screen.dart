import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/skeleton.dart';
import '../data/story_models.dart';
import 'story_reader_screen.dart';

class StoryListScreen extends ConsumerWidget {
  const StoryListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final storiesAsync = ref.watch(storiesProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('حكايات قبل النوم 🌙'),
      ),
      body: storiesAsync.when(
        loading: () => const SingleChildScrollView(
          physics: NeverScrollableScrollPhysics(),
          child: SkeletonList(count: 3, itemHeight: 120),
        ),
        error: (e, __) => EmptyState(
          emoji: '⚠️',
          title: 'تعذر تحميل القصص',
          subtitle: e.toString(),
        ),
        data: (stories) {
          if (stories.isEmpty) {
            return const EmptyState(
              emoji: '📚',
              title: 'لا توجد قصص حالياً',
              subtitle: 'انتظرونا، سنضيف قصصاً جديدة قريباً!',
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: stories.length,
            itemBuilder: (context, index) {
              final story = stories[index];
              final themeColor = Color(
                int.tryParse(story.themeColor) ?? 0xFF0D9488,
              );

              return Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: GestureDetector(
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => StoryReaderScreen(story: story),
                      ),
                    );
                  },
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(Dt.rCard),
                      boxShadow: Dt.cardShadow,
                      border: Border.all(
                        color: themeColor.withValues(alpha: .2),
                        width: 1.5,
                      ),
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(Dt.rCard),
                      child: IntrinsicHeight(
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            // Cover Image Placeholder
                            Container(
                              width: 100,
                              color: themeColor.withValues(alpha: .1),
                              child: Center(
                                child: Text(
                                  story.id == 'hope_sprout' ? '🌱' : '🐱',
                                  style: const TextStyle(fontSize: 40),
                                ),
                              ),
                            ),
                            Expanded(
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      story.title,
                                      style: const TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.w800,
                                        color: AppTheme.textPrimary,
                                      ),
                                    ),
                                    const SizedBox(height: 6),
                                    Text(
                                      story.description,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        color: AppTheme.textSecondary,
                                        height: 1.4,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.all(12),
                              child: Center(
                                child: Icon(
                                  Icons.chevron_left,
                                  color: themeColor,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                )
                    .animate(delay: (100 * (index % Dt.maxStaggeredItems)).ms)
                    .fadeIn(duration: Dt.base)
                    .slideY(begin: .05),
              );
            },
          );
        },
      ),
    );
  }
}
