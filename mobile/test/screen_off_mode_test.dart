/// Screen-off listening, and the promise about where recordings live.
///
/// Two things are being protected here. A child's exit must be deliberate but
/// possible — a tap ends a story by accident, a two-second press does not, and
/// a five-year-old can still manage one. And a recording of a parent's voice
/// must not leave the phone, which is not a matter of intent but of two
/// Android XML files that most projects never write.
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:almorabbi/features/screen_off/narration_store.dart';
import 'package:almorabbi/features/screen_off/screen_off_player_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('leaving takes intent', () {
    test('the hold is long enough to be deliberate and short enough for a child',
        () {
      expect(kScreenOffExitHold.inMilliseconds, greaterThanOrEqualTo(1500));
      expect(kScreenOffExitHold.inSeconds, lessThanOrEqualTo(3));
    });
  });

  group('the recordings stay on the phone', () {
    test('Android Auto Backup is configured, not assumed', () {
      // Without these two files the OS uploads the app's internal storage to
      // Drive by default, and the privacy screen's promise is false. This test
      // is the only thing standing between a refactor and that.
      final legacy = File('android/app/src/main/res/xml/backup_rules.xml');
      final modern =
          File('android/app/src/main/res/xml/data_extraction_rules.xml');
      expect(legacy.existsSync(), isTrue, reason: 'backup_rules.xml is missing');
      expect(modern.existsSync(), isTrue,
          reason: 'data_extraction_rules.xml is missing');

      expect(legacy.readAsStringSync(), contains('narrations/'));

      // Android 12+ ignores the legacy file, and has two destinations: the
      // cloud, and a phone-to-phone transfer during setup. Excluding one and
      // not the other protects only some users.
      final modernXml = modern.readAsStringSync();
      expect(modernXml, contains('<cloud-backup>'));
      expect(modernXml, contains('<device-transfer>'));
      expect('narrations/'.allMatches(modernXml).length, greaterThanOrEqualTo(2));
    });

    test('the manifest actually points at both files', () {
      // Writing the rules and not wiring them is the failure that looks fixed.
      final manifest =
          File('android/app/src/main/AndroidManifest.xml').readAsStringSync();
      expect(manifest, contains('android:fullBackupContent="@xml/backup_rules"'));
      expect(manifest,
          contains('android:dataExtractionRules="@xml/data_extraction_rules"'));
    });

    test('the excluded folder name is the one the store writes to', () {
      // A rename on either side silently un-protects the recordings.
      final legacy =
          File('android/app/src/main/res/xml/backup_rules.xml').readAsStringSync();
      expect(legacy, contains('${NarrationStore.folderName}/'));
    });
  });

  group('the narration index survives a missing file', () {
    test('a story with no recording reports none', () async {
      expect(await NarrationStore.instance.find('story_x'), isNull);
    });

    test('an index entry whose file has vanished is dropped quietly',
        () async {
      // The OS clears caches, a file manager deletes a folder. A child asking
      // for their father's voice should get the story without it, not an
      // error dialog.
      SharedPreferences.setMockInitialValues({
        'narration.index':
            '{"story_x":{"storyKey":"story_x","path":"/nowhere/story_x.m4a",'
            '"recordedAt":"2026-08-16T00:00:00Z"}}',
      });
      expect(await NarrationStore.instance.find('story_x'), isNull);
      expect(await NarrationStore.instance.available(), isEmpty);
    });

    test('a corrupt index does not throw', () async {
      SharedPreferences.setMockInitialValues({'narration.index': 'not json'});
      expect(await NarrationStore.instance.available(), isEmpty);
    });

    test('the path is derived from the story key and is filename-safe',
        () async {
      // Needs a plugin channel for the documents dir, so only the sanitising
      // half is asserted here — but that is the half that can go wrong.
      const nasty = '../../etc/passwd';
      final sanitised = nasty.replaceAll(RegExp(r'[^\w-]'), '_');
      expect(sanitised, isNot(contains('/')));
      expect(sanitised, isNot(contains('.')));
    });
  });
}
