/// The wird reminder is back. These tests pin the three faults that killed it,
/// so bringing it back does not bring them back with it.
///
/// From the v1.0.39+84 commit that retired it: it could not be switched off
/// (its `setWirdEnabled` had no caller), it was scheduled as an unbounded daily
/// repeat, and it was one fixed string 365 times a year.
library;

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/features/adhkar/services/notification_service.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    // wirdLine reads AppL10n.current, which the app fills from the widget tree.
    AppL10n.current = await AppLocalizations.delegate.load(const Locale('ar'));
  });

  final service = NotificationService.instance;

  test('every rotation index maps to a distinct line', () {
    // Fault 3: one fixed string, every day. The whole point of the rotation is
    // that two days running never read the same, so duplicates defeat it.
    final lines = <String>{
      for (var i = 0; i < NotificationService.wirdLineCount; i++)
        service.wirdLine(i),
    };
    expect(lines, hasLength(NotificationService.wirdLineCount));
    for (final line in lines) {
      expect(line.trim(), isNotEmpty);
    }
  });

  test('the count matches the switch — no unreachable lines', () {
    // A count smaller than the switch makes the last lines undeliverable. That
    // exact bug left 96% of the adhkar pack unreachable for months, and it is
    // invisible at runtime: everything still fires, just never those items.
    final last = service.wirdLine(NotificationService.wirdLineCount - 1);
    final wrapped = service.wirdLine(NotificationService.wirdLineCount);
    // Index `count` wraps to the default branch, which is the last line. If
    // the switch had more arms than the count admits, this would differ.
    expect(wrapped, last);
  });

  test('consecutive days never repeat', () {
    // How the scheduler indexes: (epochDay + dayOffset) % count.
    for (var epochDay = 0; epochDay < 40; epochDay++) {
      final today =
          service.wirdLine(epochDay % NotificationService.wirdLineCount);
      final tomorrow =
          service.wirdLine((epochDay + 1) % NotificationService.wirdLineCount);
      expect(today, isNot(tomorrow), reason: 'repeat at epochDay $epochDay');
    }
  });

  test('a full cycle visits every line', () {
    final seen = <String>{};
    for (var d = 0; d < NotificationService.wirdLineCount; d++) {
      seen.add(service.wirdLine(d % NotificationService.wirdLineCount));
    }
    expect(seen, hasLength(NotificationService.wirdLineCount));
  });

  group('the off switch that never existed', () {
    test('defaults to on', () async {
      SharedPreferences.setMockInitialValues({});
      expect(await service.isWirdEnabled(), isTrue);
    });

    test('reads the pref it is stored under', () async {
      SharedPreferences.setMockInitialValues(
          {'tg.wird_notifications_enabled': false});
      expect(await service.isWirdEnabled(), isFalse);
    });

    test('is independent of the adhkar switch', () async {
      // Fault 1: the old wird was gated by a pref nothing wrote, and
      // setEnabled(false) never touched its ids — so it could not be silenced.
      // These two must not share a key.
      SharedPreferences.setMockInitialValues({
        'tg.adhkar_notifications_enabled': false,
        'tg.wird_notifications_enabled': true,
      });
      expect(await service.isEnabled(), isFalse);
      expect(await service.isWirdEnabled(), isTrue);

      SharedPreferences.setMockInitialValues({
        'tg.adhkar_notifications_enabled': true,
        'tg.wird_notifications_enabled': false,
      });
      expect(await service.isEnabled(), isTrue);
      expect(await service.isWirdEnabled(), isFalse);
    });
  });

  test('the English lines exist and differ from the Arabic', () async {
    final en = await AppLocalizations.delegate.load(const Locale('en'));
    final ar = await AppLocalizations.delegate.load(const Locale('ar'));
    final enLines = [
      en.notifWird0, en.notifWird1, en.notifWird2, en.notifWird3,
      en.notifWird4, en.notifWird5, en.notifWird6,
    ];
    final arLines = [
      ar.notifWird0, ar.notifWird1, ar.notifWird2, ar.notifWird3,
      ar.notifWird4, ar.notifWird5, ar.notifWird6,
    ];
    expect(enLines, hasLength(NotificationService.wirdLineCount));
    expect(enLines.toSet(), hasLength(NotificationService.wirdLineCount));
    for (var i = 0; i < enLines.length; i++) {
      expect(enLines[i].trim(), isNotEmpty);
      expect(enLines[i], isNot(arLines[i]),
          reason: 'line $i was never translated');
    }
    expect(en.notifWirdTitle, isNot(ar.notifWirdTitle));
  });
}
