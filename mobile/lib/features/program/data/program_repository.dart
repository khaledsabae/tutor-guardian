/// Repository for the curriculum program layer (Phase 4).
///
/// This is the only layer that knows about the [TgClient] and the
/// `routers/program.py` wire format. Screens and providers consume
/// [CurriculumPath] / [CurriculumLesson] / [DailyTip] typed objects.
///
/// The repository is intentionally thin — it does no caching (Riverpod's
/// `AsyncNotifier` + `keepAlive` handles that) and no aggregation (the
/// detail screen fans out via [getPathDetail] which returns a
/// [PathDetail] bundle when the caller asks for `?include=lessons`).
library;

import '../../../api/tg_client.dart';
import '../models/flashcard_deck.dart';
import '../models/lesson_assets.dart';
import '../models/quiz_deck.dart';
import '../models/search_result.dart';
import 'models.dart';

class ProgramRepository {
  ProgramRepository(this._client);

  final TgClient _client;

  /// `GET /api/program/paths?age_group=&domain=`
  ///
  /// Returns the typed [PathListEnvelope]. Pass `null` for a given
  /// filter to omit the query parameter.
  Future<PathListEnvelope> listPaths({
    String? ageGroup,
    String? domain,
  }) async {
    final json = await _client.getPathsList(ageGroup: ageGroup, domain: domain);
    return PathListEnvelope.fromJson(json);
  }

  /// `GET /api/program/paths/{id}` (no lessons) or
  /// `GET /api/program/paths/{id}?include=lessons` (bundled).
  ///
  /// The backend returns the path fields at the root level (flat), with an
  /// optional `lessons` array when `?include=lessons` is set.
  Future<PathDetail> getPathDetail(
    String pathId, {
    bool includeLessons = true,
  }) async {
    final json = await _client.getPathDetail(
      pathId,
      includeLessons: includeLessons,
    );
    // API returns path fields at root level — no "path" wrapper key.
    final path = CurriculumPath.fromJson(json);
    final lessons = includeLessons
        ? ((json['lessons'] as List?) ?? const [])
            .map(
              (e) => CurriculumLesson.fromJson(e as Map<String, dynamic>),
            )
            .toList()
        : const <CurriculumLesson>[];
    return PathDetail(path: path, lessons: lessons);
  }

  /// `GET /api/program/lessons/{id}`
  Future<CurriculumLesson> getLesson(String lessonId) async {
    final json = await _client.getLesson(lessonId);
    return CurriculumLesson.fromJson(json);
  }

  /// `GET /api/program/lesson-assets/{id}`
  Future<LessonAssets?> getLessonAssets(String lessonId, {String? lang}) async {
    try {
      final json = await _client.getLessonAssets(lessonId, lang: lang);
      return LessonAssets.fromJson(json);
    } catch (_) {
      return null;
    }
  }

  /// `GET /api/program/asset-content/{id}` — full flashcard deck content.
  Future<FlashcardDeck?> getFlashcardDeck(String assetId) async {
    try {
      final json = await _client.getAssetContent(assetId);
      return FlashcardDeck.fromJson(json);
    } catch (_) {
      return null;
    }
  }

  /// `GET /api/program/asset-content/{id}` — full quiz deck content.
  ///
  /// The backend serves both flashcards and quizzes through the same
  /// endpoint, differentiated by the `kind` field that comes via
  /// `getLessonAssets`. We just parse the response as a [QuizDeck] here.
  Future<QuizDeck?> getQuizDeck(String assetId) async {
    try {
      final json = await _client.getAssetContent(assetId);
      return QuizDeck.fromAssetContent(json);
    } catch (_) {
      return null;
    }
  }

  /// `GET /api/program/search?q=` — curriculum-wide text search.
  Future<List<SearchResult>> search(String query, {int limit = 20}) async {
    final json = await _client.searchCurriculum(query, limit: limit);
    final raw = (json['results'] as List?) ?? const [];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(SearchResult.fromJson)
        .toList();
  }

  /// `GET /api/program/daily-tip?age_group=&time_of_day=`
  ///
  /// `timeOfDay` ∈ {`morning`, `evening`, `bedtime`, `anytime`} — pass
  /// `null` to let the backend pick deterministically from `today`.
  Future<DailyTip> getDailyTip({
    required String ageGroup,
    String? timeOfDay,
  }) async {
    final json = await _client.getDailyTip(
      ageGroup: ageGroup,
      timeOfDay: timeOfDay,
    );
    return DailyTip.fromJson(json);
  }

  /// `GET /api/program/coach-tip?child_id=` — proactive personalized tip
  /// (gracefully degrades to a plain daily tip server-side).
  Future<CoachTip> getCoachTip(int childId) async {
    final json = await _client.getCoachTip(childId);
    return CoachTip.fromJson(json);
  }

  /// `POST /api/program/coach-tip/{id}/tap` — light engagement signal.
  Future<void> recordCoachTipTap(int tipId) =>
      _client.recordCoachTipTap(tipId);
}
