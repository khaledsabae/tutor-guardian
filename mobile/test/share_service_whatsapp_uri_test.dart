// Regression test for the WhatsApp share link.
//
// The URL was built as '...?text=\${Uri.encodeComponent(text)}'. The escaped
// `$` turned the interpolation into literal text, so every WhatsApp share sent
// the characters `${Uri.encodeComponent(text)}` instead of the message and the
// install link. canLaunchUrl still matched the https handler, so the fallback
// to the system share sheet never ran and nothing surfaced the failure.

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/share/share_service.dart';

void main() {
  group('WhatsApp share URI', () {
    test('carries the encoded message, not the interpolation source', () {
      const message = 'ما شاء الله، أتمّ محمد أول صلاة';
      const text = '$message\n\nhttps://example.test/install';

      final uri = ShareService.whatsAppUri(text);

      expect(uri.host, 'wa.me');
      expect(uri.toString(), isNot(contains(r'${Uri.encodeComponent')));
      expect(uri.queryParameters['text'], text);
      expect(uri.queryParameters['text'], contains(message));
    });

    test('install link is a real absolute URL', () {
      final url = ShareService.installUrlFor(referralCode: 'ABC123');
      final parsed = Uri.parse(url);

      expect(parsed.hasScheme, isTrue);
      expect(parsed.host, isNotEmpty);
      expect(url, contains('ABC123'));
    });
  });
}
