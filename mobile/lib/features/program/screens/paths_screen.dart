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

/// Canonical display order for the domain filter chips. Any domain not
/// listed here is appended after these, in first-seen order.
const _domainChipOrder = <String>[
  'islamic_parenting',
  'aqeedah',
  'development',
  'medical',
  'cyber',
];

class PathsScreen extends ConsumerStatefulWidget {
  const PathsScreen({super.key});

  @override
  ConsumerState<PathsScreen> createState() => _PathsScreenState();
}

class _PathsScreenState extends ConsumerState<PathsScreen> {
  // Active domain filter; `null` means "show all paths".
  String? _filter;

  @override
  Widget build(BuildContext context) {
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
          final allPaths = envelope.paths;
          // Distinct domains present, in canonical-then-first-seen order.
          final present = <String>[];
          for (final p in allPaths) {
            if (!present.contains(p.domain)) present.add(p.domain);
          }
          present.sort((a, b) {
            final ia = _domainChipOrder.indexOf(a);
            final ib = _domainChipOrder.indexOf(b);
            return (ia == -1 ? 999 : ia).compareTo(ib == -1 ? 999 : ib);
          });

          // A filter that no longer matches any path falls back to "all".
          final activeFilter =
              (_filter != null && present.contains(_filter)) ? _filter : null;
          final visible = activeFilter == null
              ? allPaths
              : allPaths.where((p) => p.domain == activeFilter).toList();

          return Column(
            children: [
              if (present.length > 1)
                _DomainFilterBar(
                  domains: present,
                  selected: activeFilter,
                  onSelect: (d) => setState(() => _filter = d),
                ),
              Expanded(
                child: _buildPathsList(context, ref, visible, ageGroup, args),
              ),
            ],
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

  Widget _buildPathsList(
    BuildContext context,
    WidgetRef ref,
    List<CurriculumPath> paths,
    String ageGroup,
    PathsListArgs args,
  ) {
    if (paths.isEmpty) {
      return const EmptyState(
        emoji: '🧭',
        title: 'لا توجد مسارات بعد',
        subtitle: 'لا توجد مسارات لهذه المرحلة العمرية حالياً.',
      );
    }
    return RefreshIndicator(
      onRefresh: () => ref.read(pathsListProvider(args).notifier).refresh(),
      child: ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        itemCount: paths.length,
        separatorBuilder: (_, __) => const SizedBox(height: 16),
        itemBuilder: (context, i) {
          final card = _PathCard(path: paths[i], ageGroup: ageGroup);
          if (i >= Dt.maxStaggeredItems) return card;
          return card
              .animate(delay: Dt.stagger * i)
              .fadeIn(duration: Dt.base)
              .slideY(begin: .08, curve: Curves.easeOutCubic);
        },
      ),
    );
  }
}

/// Horizontal, scrollable row of domain filter chips. The first chip
/// ("الكل") clears the filter; each domain chip wears its own color so the
/// curriculum (تربية) and creed (عقيدة) tracks read as siblings you can hop
/// between freely — not locked, separate sections.
class _DomainFilterBar extends StatelessWidget {
  const _DomainFilterBar({
    required this.domains,
    required this.selected,
    required this.onSelect,
  });

  final List<String> domains;
  final String? selected;
  final ValueChanged<String?> onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 56,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
        children: [
          _Chip(
            label: 'الكل',
            emoji: '🗂️',
            color: Theme.of(context).colorScheme.primary,
            isSelected: selected == null,
            onTap: () => onSelect(null),
          ),
          const SizedBox(width: 8),
          for (final d in domains) ...[
            _Chip(
              label: CurriculumPath.labelForDomain(d),
              emoji: styleFor(d).emoji,
              color: styleFor(d).base,
              isSelected: selected == d,
              onTap: () => onSelect(d),
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({
    required this.label,
    required this.emoji,
    required this.color,
    required this.isSelected,
    required this.onTap,
  });

  final String label;
  final String emoji;
  final Color color;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: isSelected,
      label: 'تصفية: $label',
      excludeSemantics: true,
      child: Material(
        color: isSelected ? color : color.withValues(alpha: .10),
        borderRadius: BorderRadius.circular(Dt.rChip),
        child: InkWell(
          borderRadius: BorderRadius.circular(Dt.rChip),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(Dt.rChip),
              border: Border.all(
                color: isSelected ? color : color.withValues(alpha: .35),
                width: 1.5,
              ),
            ),
            child: Row(
              children: [
                Text(emoji, style: const TextStyle(fontSize: 15)),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: isSelected ? Colors.white : color,
                  ),
                ),
              ],
            ),
          ),
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
