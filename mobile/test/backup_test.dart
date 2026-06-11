// Backup export/import tests (P1 #3) — round-trip + validation.
// Added in review (the original commit shipped without tests).

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/program/data/backup_service.dart';
import 'package:almorabbi/features/program/data/favorites_storage.dart';
import 'package:almorabbi/features/reflections/data/reflection_storage.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  Future<SharedPreferences> prefs() => SharedPreferences.getInstance();

  test('export → clear → import restores reflections + favorites', () async {
    final p = await prefs();
    final favs = FavoritesStorage(p);
    final refs = ReflectionStorage(p);
    final backup = BackupService(p);

    // seed
    await favs.toggleLesson('lesson_A');
    await favs.toggleTip('tip_B');
    final now = DateTime.utc(2026, 6, 11);
    await refs.upsert(ReflectionEntry(
      lessonId: 'lesson_A',
      text: 'ملاحظتي على الدرس',
      createdAt: now,
      updatedAt: now,
    ));

    final json = backup.exportData();

    // wipe everything
    await favs.clearAll();
    await refs.clearAll();
    expect(favs.isLessonFavorite('lesson_A'), isFalse);
    expect(refs.loadAll(), isEmpty);

    // import back
    final result = await backup.importFromJson(json);
    expect(result.success, isTrue);
    expect(result.importedFavoritesCount, 2);
    expect(result.importedReflectionsCount, 1);

    expect(favs.isLessonFavorite('lesson_A'), isTrue);
    expect(favs.isTipFavorite('tip_B'), isTrue);
    expect(refs.loadAll()['lesson_A']?.text, 'ملاحظتي على الدرس');
  });

  test('malformed JSON fails gracefully (no throw)', () async {
    final backup = BackupService(await prefs());
    final result = await backup.importFromJson('not json {');
    expect(result.success, isFalse);
    expect(result.errorMessage, isNotNull);
  });

  test('missing version is rejected', () async {
    final backup = BackupService(await prefs());
    final result = await backup.importFromJson('{"reflections":{},"favorites":{}}');
    expect(result.success, isFalse);
  });

  test('future version is rejected', () async {
    final backup = BackupService(await prefs());
    final result =
        await backup.importFromJson('{"version":999,"reflections":{},"favorites":{}}');
    expect(result.success, isFalse);
    expect(result.errorMessage, contains('999'));
  });

  test('import merges without clobbering existing (default)', () async {
    final p = await prefs();
    final favs = FavoritesStorage(p);
    final backup = BackupService(p);
    await favs.toggleLesson('existing');
    await backup.importFromJson(
        '{"version":1,"favorites":{"lessons":["imported"],"tips":[]}}');
    expect(favs.isLessonFavorite('existing'), isTrue);
    expect(favs.isLessonFavorite('imported'), isTrue);
  });
}
