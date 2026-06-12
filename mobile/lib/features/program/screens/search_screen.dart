import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/skeleton.dart';
import '../models/search_result.dart';
import '../providers/program_providers.dart';
import '../providers/progress_providers.dart';
import 'lesson_screen.dart';
import 'path_detail_screen.dart';

/// Curriculum-wide search results for a query (≥2 chars). Empty for shorter.
final searchResultsProvider = FutureProvider.autoDispose
    .family<List<SearchResult>, String>((ref, query) async {
  if (query.trim().length < 2) return const [];
  final repo = ref.watch(programRepositoryProvider);
  return repo.search(query.trim());
});

/// Full-screen search over lessons, paths, and daily tips.
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _controller = TextEditingController();
  Timer? _debounce;
  String _query = '';

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (mounted) setState(() => _query = value);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        // Pill search field — readable on the light app bar.
        title: Container(
          height: 44,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(Dt.rChip),
            boxShadow: Dt.cardShadow,
          ),
          child: TextField(
            controller: _controller,
            autofocus: true,
            textInputAction: TextInputAction.search,
            onChanged: _onChanged,
            style:
                const TextStyle(color: AppTheme.textPrimary, fontSize: 15),
            decoration: const InputDecoration(
              hintText: 'ابحث في الدروس والنصائح…',
              hintStyle: TextStyle(color: AppTheme.textMuted),
              prefixIcon:
                  Icon(Icons.search, color: AppTheme.textMuted, size: 20),
              filled: false,
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              isDense: true,
              contentPadding: EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        ),
        actions: [
          if (_controller.text.isNotEmpty)
            IconButton(
              tooltip: 'مسح',
              icon: const Icon(Icons.close),
              onPressed: () {
                _controller.clear();
                setState(() => _query = '');
              },
            ),
        ],
      ),
      body: _Body(query: _query),
    );
  }
}

class _Body extends ConsumerWidget {
  final String query;
  const _Body({required this.query});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (query.trim().length < 2) {
      return const EmptyState(
        emoji: '🔎',
        title: 'ابحث في كل المنهج',
        subtitle: 'اكتب حرفين على الأقل للبحث في الدروس والمسارات والنصائح.',
      );
    }
    final async = ref.watch(searchResultsProvider(query));
    return async.when(
      loading: () => const SingleChildScrollView(
        physics: NeverScrollableScrollPhysics(),
        child: SkeletonList(count: 5, itemHeight: 80),
      ),
      error: (e, _) => EmptyState(
        emoji: '📡',
        title: 'تعذّر البحث',
        subtitle: '$e',
      ),
      data: (results) {
        if (results.isEmpty) {
          return EmptyState(
            emoji: '🤷',
            title: 'لا نتائج لـ «$query»',
            subtitle: 'جرّب كلمات أخرى أو أبسط.',
          );
        }
        return ListView.separated(
          padding: const EdgeInsets.all(12),
          itemCount: results.length,
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (_, i) => _ResultTile(result: results[i]),
        );
      },
    );
  }
}

class _ResultTile extends ConsumerWidget {
  final SearchResult result;
  const _ResultTile({required this.result});

  static const _typeLabel = {
    SearchResultType.lesson: 'درس',
    SearchResultType.path: 'مسار',
    SearchResultType.tip: 'نصيحة',
    SearchResultType.unknown: '',
  };

  String get _emoji {
    switch (result.type) {
      case SearchResultType.lesson:
        return '📖';
      case SearchResultType.path:
        return '🛤️';
      case SearchResultType.tip:
        return '💡';
      case SearchResultType.unknown:
        return '📄';
    }
  }

  void _open(BuildContext context, WidgetRef ref) {
    final age = result.ageGroup ?? '';
    if (result.type == SearchResultType.lesson) {
      final childId = ref.read(activeChildIdProvider);
      Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => LessonScreen(
          lessonId: result.id,
          ageGroup: age,
          childId: childId,
        ),
      ));
    } else if (result.type == SearchResultType.path) {
      Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => PathDetailScreen(pathId: result.id, ageGroup: age),
      ));
    }
    // tips are informational — no destination screen.
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tappable = result.type == SearchResultType.lesson ||
        result.type == SearchResultType.path;
    final label = _typeLabel[result.type] ?? '';
    // Shadow on the outer box; color on a Material so the ListTile's
    // ink renders correctly (framework assertion in debug/tests).
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        boxShadow: Dt.cardShadow,
      ),
      child: Material(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        clipBehavior: Clip.antiAlias,
        child: ListTile(
        leading: Container(
          width: 44,
          height: 44,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: AppTheme.primary.withValues(alpha: .08),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Text(_emoji, style: const TextStyle(fontSize: 20)),
        ),
        title: Text(
          result.title,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        subtitle: result.snippet.isEmpty
            ? null
            : Text(result.snippet,
                maxLines: 2, overflow: TextOverflow.ellipsis),
        trailing: Wrap(
          spacing: 6,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            if (label.isNotEmpty)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: .1),
                  borderRadius: BorderRadius.circular(Dt.rChip),
                ),
                child: Text(
                  label,
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppTheme.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            if (result.ageGroup != null)
              Text(result.ageGroup!,
                  style: const TextStyle(
                      fontSize: 11, color: AppTheme.textMuted)),
          ],
        ),
        onTap: tappable ? () => _open(context, ref) : null,
        ),
      ),
    );
  }
}

