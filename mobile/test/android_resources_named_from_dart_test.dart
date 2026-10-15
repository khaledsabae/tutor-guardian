// An Android resource that Dart names by string must survive resource
// shrinking.
//
// 2026-10-15, PR #121 (the paper-cut launcher icon): the manifest switched
// `android:icon` from `@mipmap/ic_launcher` to `@mipmap/ic_launcher_paper`.
// Nothing in the Java/Kotlin code or the manifest named `ic_launcher` after
// that, so release resource shrinking (`isShrinkResources = true`) dropped it
// from the APK — `aapt2 dump resources` on the PR's head APK has no
// `mipmap/ic_launcher` at all. But NotificationService still initialises
// flutter_local_notifications with `AndroidInitializationSettings(
// '@mipmap/ic_launcher')`; that string lives in the Dart snapshot, which the
// shrinker never reads. The plugin answered `invalid_icon`, init() failed on
// every launch (one Crashlytics non-fatal per process in the E2E logcat gate)
// and the daily reminders would never have been scheduled.
//
// The fix is `res/raw/keep.xml`. This test holds the two together: every
// `'@mipmap/…'`, `'@drawable/…'` or `'@raw/…'` string in lib/ must exist in
// res/ and be listed in keep.xml — whatever the manifest happens to point at.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const _res = 'android/app/src/main/res';

/// `@type/name` for every resource a Dart string names, with where it is.
Map<String, List<String>> _namedFromDart() {
  final pattern = RegExp(r'''['"]@(mipmap|drawable|raw)/([a-z0-9_]+)['"]''');
  final found = <String, List<String>>{};
  for (final entity in Directory('lib').listSync(recursive: true)) {
    if (entity is! File || !entity.path.endsWith('.dart')) continue;
    final lines = entity.readAsLinesSync();
    for (var i = 0; i < lines.length; i++) {
      for (final m in pattern.allMatches(lines[i])) {
        found
            .putIfAbsent('@${m[1]}/${m[2]}', () => [])
            .add('${entity.path}:${i + 1}');
      }
    }
  }
  return found;
}

void main() {
  test('the notification icon is still named from Dart (the scan works)', () {
    // If this goes, the scan below proves nothing — fix the pattern rather
    // than delete the test.
    expect(_namedFromDart().keys, contains('@mipmap/ic_launcher'));
  });

  test('every resource Dart names by string exists in res/', () {
    for (final entry in _namedFromDart().entries) {
      final parts = entry.key.substring(1).split('/');
      final type = parts[0], name = parts[1];
      final exists = Directory(_res)
          .listSync()
          .whereType<Directory>()
          .where((d) {
            final dir = d.uri.pathSegments.where((s) => s.isNotEmpty).last;
            return dir == type || dir.startsWith('$type-');
          })
          .expand((d) => d.listSync().whereType<File>())
          .any((f) => f.uri.pathSegments.last.split('.').first == name);
      expect(exists, isTrue,
          reason: '${entry.key} (named at ${entry.value.join(', ')}) '
              'has no file under $_res/$type*/');
    }
  });

  test('every resource Dart names by string is kept from shrinking', () {
    final keepFile = File('$_res/raw/keep.xml');
    expect(keepFile.existsSync(), isTrue,
        reason: 'res/raw/keep.xml is what stops the release shrinker from '
            'dropping resources only Dart refers to');
    final keepAttr = RegExp(r'tools:keep="([^"]*)"')
        .firstMatch(keepFile.readAsStringSync());
    expect(keepAttr, isNotNull, reason: 'keep.xml has no tools:keep');
    final kept = keepAttr![1]!.split(',').map((s) => s.trim()).toSet();
    for (final entry in _namedFromDart().entries) {
      expect(kept, contains(entry.key),
          reason: '${entry.key} is named from Dart at '
              '${entry.value.join(', ')} — the shrinker cannot see that, so '
              'list it in res/raw/keep.xml');
    }
  });
}
