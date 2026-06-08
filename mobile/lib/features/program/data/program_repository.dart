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
  /// The backend returns `{ "path": {...}, "lessons": [...] }` when
  /// `?include=lessons` is set, and `{ "path": {...} }` otherwise.
  Future<PathDetail> getPathDetail(
    String pathId, {
    bool includeLessons = true,
  }) async {
    final json = await _client.getPathDetail(
      pathId,
      includeLessons: includeLessons,
    );
    final path = CurriculumPath.fromJson(json['path'] as Map<String, dynamic>);
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
}
