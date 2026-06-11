/// One curriculum search hit — served by `GET /api/program/search`.
enum SearchResultType { lesson, path, tip, unknown }

class SearchResult {
  final SearchResultType type;
  final String id;
  final String title;
  final String snippet;
  final String? ageGroup;
  final String? domain;
  final String? pathId;

  const SearchResult({
    required this.type,
    required this.id,
    required this.title,
    required this.snippet,
    this.ageGroup,
    this.domain,
    this.pathId,
  });

  factory SearchResult.fromJson(Map<String, dynamic> json) {
    return SearchResult(
      type: _parseType(json['type'] as String?),
      id: (json['id'] as String?) ?? '',
      title: (json['title'] as String?) ?? '',
      snippet: (json['snippet'] as String?) ?? '',
      ageGroup: json['age_group'] as String?,
      domain: json['domain'] as String?,
      pathId: json['path_id'] as String?,
    );
  }

  static SearchResultType _parseType(String? v) {
    switch (v) {
      case 'lesson':
        return SearchResultType.lesson;
      case 'path':
        return SearchResultType.path;
      case 'tip':
        return SearchResultType.tip;
      default:
        return SearchResultType.unknown;
    }
  }
}
