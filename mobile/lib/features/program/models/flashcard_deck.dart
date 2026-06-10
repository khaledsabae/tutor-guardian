/// Flashcard deck content — served by `GET /api/program/asset-content/{id}`.
class Flashcard {
  final String front;
  final String back;

  const Flashcard({required this.front, required this.back});

  factory Flashcard.fromJson(Map<String, dynamic> json) {
    return Flashcard(
      front: (json['front'] as String?) ?? '',
      back: (json['back'] as String?) ?? '',
    );
  }

  /// Backend stores back-side bullet points separated by " | ".
  List<String> get backPoints => back
      .split('|')
      .map((s) => s.trim())
      .where((s) => s.isNotEmpty)
      .toList();
}

class FlashcardDeck {
  final String id;
  final String title;
  final List<Flashcard> cards;

  const FlashcardDeck({
    required this.id,
    required this.title,
    required this.cards,
  });

  factory FlashcardDeck.fromJson(Map<String, dynamic> json) {
    return FlashcardDeck(
      id: (json['id'] as String?) ?? '',
      title: (json['title'] as String?) ?? '',
      cards: ((json['cards'] as List?) ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(Flashcard.fromJson)
          .toList(),
    );
  }
}
