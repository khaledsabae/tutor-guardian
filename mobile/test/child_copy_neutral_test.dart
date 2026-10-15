// Child-facing mission copy names the family, never one parent, and carries
// no emoji — the glyph next to it is drawn by the screen (BrandGlyph).
//
// Many of the people confirming missions are mothers; «بابا سيراها» told every
// child their father was the one watching. The English copy was already
// neutral («A parent will see it tonight»); this pins both.
import 'package:almorabbi/l10n/app_localizations_ar.dart';
import 'package:almorabbi/l10n/app_localizations_en.dart';
import 'package:flutter_test/flutter_test.dart';

final _onlyOneParent = RegExp(r'بابا|ماما|أبوك|أمك|\b(dad|mum|mom)\b',
    caseSensitive: false);
final _emoji = RegExp(r'[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}]',
    unicode: true);

void main() {
  final ar = AppLocalizationsAr();
  final en = AppLocalizationsEn();

  final childMissionCopy = <String, String>{
    'ar.missionClaimedNote': ar.missionClaimedNote,
    'ar.missionAlreadyDone': ar.missionAlreadyDone,
    'ar.missionDone': ar.missionDone,
    'ar.praiseFromFamily': ar.praiseFromFamily,
    'en.missionClaimedNote': en.missionClaimedNote,
    'en.missionAlreadyDone': en.missionAlreadyDone,
    'en.missionDone': en.missionDone,
    'en.praiseFromFamily': en.praiseFromFamily,
  };

  childMissionCopy.forEach((key, text) {
    test('$key names the family, not one parent', () {
      expect(_onlyOneParent.hasMatch(text), isFalse, reason: text);
    });
    test('$key has no emoji', () {
      expect(_emoji.hasMatch(text), isFalse, reason: text);
    });
  });
}
