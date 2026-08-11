// These links leave the app and land on a public page, so a wrong one sends a
// parent to a stranger's profile with our name attached to the tap.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/core/social_links.dart';
import 'package:almorabbi/features/program/widgets/follow_us_row.dart';
import 'package:almorabbi/l10n/app_localizations.dart';

void main() {
  group('social links', () {
    test('every link is https and absolute', () {
      expect(kSocialLinks, isNotEmpty);
      for (final l in kSocialLinks) {
        final uri = Uri.tryParse(l.url);
        expect(uri, isNotNull, reason: '${l.name}: unparseable');
        expect(uri!.scheme, 'https', reason: '${l.name}: not https');
        expect(uri.host, isNotEmpty, reason: '${l.name}: no host');
        expect(l.name.trim(), isNotEmpty);
      }
    });

    test('each platform appears once', () {
      final hosts = kSocialLinks.map((l) => l.url).toSet();
      expect(hosts.length, kSocialLinks.length, reason: 'duplicate link');
      final names = kSocialLinks.map((l) => l.name).toSet();
      expect(names.length, kSocialLinks.length, reason: 'duplicate platform');
    });

    test('each link points at the host it claims', () {
      // A copy-paste that leaves an Instagram URL under the Facebook chip is
      // invisible in review and obvious to a user.
      const expected = {
        'Telegram': 't.me',
        'Facebook': 'facebook.com',
        'Instagram': 'instagram.com',
        'TikTok': 'tiktok.com',
      };
      for (final l in kSocialLinks) {
        final host = expected[l.name];
        expect(host, isNotNull, reason: '${l.name}: no expected host declared');
        expect(Uri.parse(l.url).host, endsWith(host!), reason: l.name);
      }
    });

    test('Telegram uses the public username, not an invite link', () {
      // t.me/+HASH links are revocable. A shipped app cannot be updated when
      // one is, so it would keep sending parents to a dead page.
      final tg = kSocialLinks.firstWhere((l) => l.name == 'Telegram');
      expect(tg.url, isNot(contains('/+')));
      expect(tg.url, isNot(contains('joinchat')));
    });

    test('no link is a bare profile root', () {
      // "https://instagram.com" with no handle is the failure mode of a
      // half-filled config, and it still opens fine — so nothing catches it.
      for (final l in kSocialLinks) {
        expect(Uri.parse(l.url).pathSegments.where((s) => s.isNotEmpty), isNotEmpty,
            reason: '${l.name}: link has no path');
      }
    });
  });

  testWidgets('the row offers every link as a tappable chip', (t) async {
    await t.pumpWidget(MaterialApp(
      locale: const Locale('ar'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(body: SingleChildScrollView(child: FollowUsRow())),
    ));
    await t.pumpAndSettle();
    expect(find.text('تابعنا'), findsOneWidget);
    for (final l in kSocialLinks) {
      expect(find.text(l.name), findsOneWidget, reason: '${l.name} missing');
    }
    expect(find.byType(InkWell), findsNWidgets(kSocialLinks.length));
  });
}
