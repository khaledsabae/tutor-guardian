/// Quiz content models — served by `GET /api/program/asset-content/{id}`
/// for assets whose `kind` is `quizzes` (per `lesson_assets_provider.dart`).
///
/// Wire shape (matches the JSON files in
/// `docs/lesson_assets/quizzes/*.json`):
/// ```
/// {
///   "title": "Parenting Quiz",
///   "questions": [
///     {
///       "question": "...",
///       "answerOptions": [
///         { "text": "...", "isCorrect": true, "rationale": "..." },
///         { "text": "...", "isCorrect": false, "rationale": "..." }
///       ],
///       "hint": "..."
///     }
///   ]
/// }
/// ```
class QuizQuestion {
  final String question;
  final List<QuizOption> options;
  final String? hint;
  final String? text; // optional extra context shown above the choices

  const QuizQuestion({
    required this.question,
    required this.options,
    this.hint,
    this.text,
  });

  factory QuizQuestion.fromJson(Map<String, dynamic> json) {
    final opts = ((json['answerOptions'] as List?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(QuizOption.fromJson)
        .toList();
    return QuizQuestion(
      question: (json['question'] as String?) ?? '',
      options: opts,
      hint: json['hint'] as String?,
      text: json['text'] as String?,
    );
  }
}

class QuizOption {
  final String text;
  final bool isCorrect;
  final String? rationale;

  const QuizOption({
    required this.text,
    required this.isCorrect,
    this.rationale,
  });

  factory QuizOption.fromJson(Map<String, dynamic> json) {
    return QuizOption(
      text: (json['text'] as String?) ?? '',
      isCorrect: json['isCorrect'] as bool? ?? false,
      rationale: json['rationale'] as String?,
    );
  }
}

class QuizDeck {
  final String id;
  final String title;
  final List<QuizQuestion> questions;

  const QuizDeck({
    required this.id,
    required this.title,
    required this.questions,
  });

  factory QuizDeck.fromJson(Map<String, dynamic> json) {
    return QuizDeck(
      id: (json['id'] as String?) ?? '',
      title: (json['title'] as String?) ?? 'اختبار',
      questions: ((json['questions'] as List?) ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(QuizQuestion.fromJson)
          .toList(),
    );
  }

  factory QuizDeck.fromAssetContent(Map<String, dynamic> json) =>
      QuizDeck.fromJson(json);
}
