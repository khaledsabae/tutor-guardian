import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
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
        title: TextField(
          controller: _controller,
          autofocus: true,
          textInputAction: TextInputAction.search,
          onChanged: _onChanged,
          style: const TextStyle(color: Colors.white, fontSize: 16),
          cursorColor: Colors.white,
          decoration: const InputDecoration(
            hintText: 'ابحث في الدروس والنصائح…',
            hintStyle: TextStyle(color: Colors.white70),
            border: InputBorder.none,
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
      return const _Hint(text: 'اكتب حرفين على الأقل للبحث في كل المنهج.');
    }
    final async = ref.watch(searchResultsProvider(query));
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => _Hint(text: 'تعذّر البحث.\n$e'),
      data: (results) {
        if (results.isEmpty) {
          return _Hint(text: 'لا نتائج لـ «$query».');
        }
        return ListView.separated(
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: results.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
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

  IconData get _icon {
    switch (result.type) {
      case SearchResultType.lesson:
        return Icons.menu_book_outlined;
      case SearchResultType.path:
        return Icons.route_outlined;
      case SearchResultType.tip:
        return Icons.lightbulb_outline;
      case SearchResultType.unknown:
        return Icons.article_outlined;
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
    return ListTile(
      leading: Icon(_icon, color: AppTheme.primary),
      title: Text(
        result.title,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(fontWeight: FontWeight.w600),
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
            Chip(
              label: Text(label, style: const TextStyle(fontSize: 11)),
              visualDensity: VisualDensity.compact,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              padding: EdgeInsets.zero,
            ),
          if (result.ageGroup != null)
            Text(result.ageGroup!,
                style: const TextStyle(
                    fontSize: 11, color: AppTheme.textMuted)),
        ],
      ),
      onTap: tappable ? () => _open(context, ref) : null,
    );
  }
}

class _Hint extends StatelessWidget {
  final String text;
  const _Hint({required this.text});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Text(
          text,
          textAlign: TextAlign.center,
          style: const TextStyle(color: AppTheme.textMuted),
        ),
      ),
    );
  }
}
