/// Text direction for **content**, decided by the content itself.
///
/// Why this is not `Directionality.of(context)`
/// --------------------------------------------
/// The app chrome takes its direction from the app locale in `main.dart`, and
/// that is correct — menus, back buttons and page transitions belong to the
/// interface, not to the text inside it. Content is a different question.
///
/// A mixed screen is the normal case here, not the exotic one. A parent whose
/// UI is English opens a story; the network fetch times out; the bundled
/// Arabic file loads. The chrome is still English, the paragraph is Arabic,
/// and the paragraph needs RTL. Inherit direction from the context and that
/// Arabic paragraph renders left-aligned with its punctuation adrift. Hard-code
/// RTL instead — which is what `story_reader_screen.dart` did while every story
/// was Arabic — and the English stories arrive right-aligned.
///
/// So direction follows the language of the string being rendered. Nothing
/// else.
library;

import 'package:flutter/widgets.dart';

/// Languages written right to left, by ISO 639-1/639-3 code.
///
/// Only `ar` ships today; the rest cost nothing and mean a future translation
/// does not have to remember to come back here.
const Set<String> _rtlLanguages = <String>{
  'ar', // Arabic
  'arc', // Aramaic
  'ckb', // Sorani Kurdish
  'dv', // Divehi
  'fa', // Persian
  'he', 'iw', // Hebrew (old and new codes)
  'ps', // Pashto
  'sd', // Sindhi
  'ug', // Uyghur
  'ur', // Urdu
  'yi', 'ji', // Yiddish (old and new codes)
};

/// Arabic, Hebrew, Syriac, Thaana and the Arabic supplements/presentation
/// forms — the ranges that carry strong RTL letters.
final RegExp _rtlScript = RegExp(
  r'[֐-׿؀-ۿ܀-ݏހ-޿'
  r'ࢠ-ࣿיִ-ﭏﭐ-﷿ﹰ-﻿]',
);

/// Latin, Greek and Cyrillic letters — strong LTR.
final RegExp _ltrScript = RegExp(r'[A-Za-zÀ-ɏͰ-ϿЀ-ӿ]');

/// The direction a string in [languageCode] is written in.
///
/// Accepts anything a `Locale.languageCode`, an `.arb` file name or a JSON
/// `language` field is likely to hold: `ar`, `AR`, `ar_SA`, `ar-EG`. A code we
/// do not know is left-to-right, because an unknown code is far more likely to
/// be a language we have not shipped than a right-to-left one we forgot.
TextDirection directionOfLanguage(String languageCode) {
  final base = languageCode.trim().toLowerCase().split(RegExp(r'[_-]')).first;
  return _rtlLanguages.contains(base) ? TextDirection.rtl : TextDirection.ltr;
}

/// The direction a string is written in, read off its own characters.
///
/// The fallback for content that arrives without a language tag. Returns
/// `null` when the string carries no directional letters at all (empty, digits,
/// emoji, punctuation) — a caller that gets `null` has no signal and should say
/// so rather than guess.
///
/// Majority of strong letters, not first-strong. First-strong is the Unicode
/// default and it is wrong for this content: an English story page that opens
/// on the name «ياسين», or quotes an ayah before its first English word, is
/// still an English page. Counting keeps the embedded Arabic — which is exactly
/// what these stories contain — from flipping the paragraph around it.
TextDirection? directionOfText(String text) {
  final rtl = _rtlScript.allMatches(text).length;
  final ltr = _ltrScript.allMatches(text).length;
  if (rtl == 0 && ltr == 0) return null;
  return rtl > ltr ? TextDirection.rtl : TextDirection.ltr;
}

/// Renders [child] in the direction of the content, not of the app locale.
///
/// Give it a [languageCode] when the content is tagged (stories carry
/// `language` in their JSON). Give it [text] when it is not, and the script
/// decides. Give it both and the tag wins — a declared language is evidence,
/// character counting is inference.
///
/// With neither signal, [fallback] applies (left-to-right unless you say
/// otherwise). It deliberately does not reach for `Directionality.of(context)`:
/// that is the chrome's direction, and inheriting it is the bug this widget
/// exists to prevent.
class ContentDirectionality extends StatelessWidget {
  final String? languageCode;
  final String? text;
  final TextDirection fallback;
  final Widget child;

  const ContentDirectionality({
    super.key,
    this.languageCode,
    this.text,
    this.fallback = TextDirection.ltr,
    required this.child,
  });

  /// The direction this widget will impose, exposed for callers that need the
  /// value itself (a `textAlign`, a padding side) rather than a wrapper.
  static TextDirection resolve({
    String? languageCode,
    String? text,
    TextDirection fallback = TextDirection.ltr,
  }) {
    if (languageCode != null && languageCode.trim().isNotEmpty) {
      return directionOfLanguage(languageCode);
    }
    if (text != null) {
      final detected = directionOfText(text);
      if (detected != null) return detected;
    }
    return fallback;
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: resolve(
        languageCode: languageCode,
        text: text,
        fallback: fallback,
      ),
      child: child,
    );
  }
}
