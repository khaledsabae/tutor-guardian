class LessonAssets {
  final String? podcastMp3;
  final String? videoMp4;
  final String? infographic;
  final String? report;
  final String? dataTable;
  final List<dynamic> flashcards;
  final List<dynamic> quizzes;

  const LessonAssets({
    this.podcastMp3,
    this.videoMp4,
    this.infographic,
    this.report,
    this.dataTable,
    this.flashcards = const [],
    this.quizzes = const [],
  });

  factory LessonAssets.fromJson(Map<String, dynamic> json) {
    return LessonAssets(
      podcastMp3: json['podcast_mp3'] as String?,
      videoMp4: json['video_mp4'] as String?,
      infographic: json['infographic'] as String?,
      report: json['report'] as String?,
      dataTable: json['data_table'] as String?,
      flashcards: (json['flashcards'] as List?) ?? const [],
      quizzes: (json['quizzes'] as List?) ?? const [],
    );
  }
}
