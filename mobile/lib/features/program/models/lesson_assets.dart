class LessonAssets {
  final String? podcastMp3;
  final String? videoMp4;
  final String? infographic;
  final String? report;
  final String? dataTable;
  final List<dynamic> flashcards;
  final List<dynamic> quizzes;

  /// What the server actually served, per medium — `{requested, podcast,
  /// video, infographic, report, data_table}`, each a language code or null.
  ///
  /// The backend has returned this block since the media translations began,
  /// and the app threw it away. Asking for English and being handed Arabic
  /// audio is expected while English media is still being produced; the parent
  /// simply had no way to know that was the reason, so it read as a defect.
  final Map<String, String?> languages;

  const LessonAssets({
    this.podcastMp3,
    this.videoMp4,
    this.infographic,
    this.report,
    this.dataTable,
    this.flashcards = const [],
    this.quizzes = const [],
    this.languages = const {},
  });

  /// True when something arrived in a language other than the one asked for.
  ///
  /// Only counts media that actually arrived: a missing podcast is a missing
  /// podcast, not a translation gap, and saying otherwise would put a notice
  /// on lessons that have no media at all.
  bool get servedInAnotherLanguage {
    final want = languages['requested'];
    if (want == null || want.isEmpty) return false;
    const media = ['podcast', 'video', 'infographic', 'report', 'data_table'];
    for (final k in media) {
      final got = languages[k];
      if (got != null && got.isNotEmpty && got != want) return true;
    }
    return false;
  }

  factory LessonAssets.fromJson(Map<String, dynamic> json) {
    final langs = <String, String?>{};
    final raw = json['languages'];
    if (raw is Map) {
      raw.forEach((k, v) => langs['$k'] = v as String?);
    }
    return LessonAssets(
      podcastMp3: json['podcast_mp3'] as String?,
      videoMp4: json['video_mp4'] as String?,
      infographic: json['infographic'] as String?,
      report: json['report'] as String?,
      dataTable: json['data_table'] as String?,
      flashcards: (json['flashcards'] as List?) ?? const [],
      quizzes: (json['quizzes'] as List?) ?? const [],
      languages: langs,
    );
  }
}
