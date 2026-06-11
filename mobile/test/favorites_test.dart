// Favorites tests (P1 #1) — storage round-trip + notifier state.
// Added in review (the original commit shipped without tests).

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/program/data/favorites_storage.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  Future<FavoritesStorage> makeStorage() async {
    final prefs = await SharedPreferences.getInstance();
    return FavoritesStorage(prefs);
  }

  group('FavoritesStorage', () {
    test('starts empty', () async {
      final s = await makeStorage();
      expect(s.loadAll()['lessons'], isEmpty);
      expect(s.loadAll()['tips'], isEmpty);
      expect(s.isLessonFavorite('l1'), isFalse);
    });

    test('toggle lesson adds then removes (round-trip)', () async {
      final s = await makeStorage();
      await s.toggleLesson('l1');
      expect(s.isLessonFavorite('l1'), isTrue);
      expect(s.loadAll()['lessons'], contains('l1'));

      await s.toggleLesson('l1');
      expect(s.isLessonFavorite('l1'), isFalse);
      expect(s.loadAll()['lessons'], isEmpty);
    });

    test('lessons and tips are independent', () async {
      final s = await makeStorage();
      await s.toggleLesson('l1');
      await s.toggleTip('t1');
      expect(s.isLessonFavorite('l1'), isTrue);
      expect(s.isTipFavorite('t1'), isTrue);
      expect(s.isTipFavorite('l1'), isFalse);
    });

    test('persists across new storage instances', () async {
      final s1 = await makeStorage();
      await s1.toggleLesson('l9');
      // a fresh storage over the same (mock) prefs sees it
      final s2 = await makeStorage();
      expect(s2.isLessonFavorite('l9'), isTrue);
    });

    test('clearAll wipes everything', () async {
      final s = await makeStorage();
      await s.toggleLesson('l1');
      await s.toggleTip('t1');
      await s.clearAll();
      expect(s.loadAll()['lessons'], isEmpty);
      expect(s.loadAll()['tips'], isEmpty);
    });

    test('corrupted entry degrades to empty, no crash', () async {
      SharedPreferences.setMockInitialValues({'tg.favorites.v1': 'not-json{'});
      final prefs = await SharedPreferences.getInstance();
      final s = FavoritesStorage(prefs);
      expect(s.loadAll()['lessons'], isEmpty);
      expect(s.isLessonFavorite('x'), isFalse);
    });
  });
}
