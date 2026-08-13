// Content direction follows the content, not the chrome.
//
// The reader screen used to hard-code `TextDirection.rtl` around the story
// text. That was right while every story was Arabic and wrong the moment
// English stories shipped. The mirror-image bug is just as easy: take the
// direction from `Directionality.of(context)` and an Arabic story that arrived
// as a silent fallback renders left-aligned under an English UI.
//
// So the rule under test is: the language of the string decides, and nothing
// else does.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/l10n/content_direction.dart';
import 'package:almorabbi/features/program/data/story_models.dart';

void main() {
  group('directionOfLanguage', () {
    test('Arabic is right to left, English is left to right', () {
      expect(directionOfLanguage('ar'), TextDirection.rtl);
      expect(directionOfLanguage('en'), TextDirection.ltr);
    });

    test('accepts the shapes a language tag actually arrives in', () {
      for (final tag in ['AR', 'ar_SA', 'ar-EG', ' ar ']) {
        expect(directionOfLanguage(tag), TextDirection.rtl, reason: tag);
      }
      expect(directionOfLanguage('en_US'), TextDirection.ltr);
    });

    test('an unknown code is left to right, not a guess', () {
      // Far likelier to be a language we have not shipped than an RTL one we
      // forgot — and French is 11% of this app's users.
      expect(directionOfLanguage('fr'), TextDirection.ltr);
      expect(directionOfLanguage(''), TextDirection.ltr);
    });

    test('the other right-to-left languages are covered before they ship', () {
      for (final code in ['he', 'fa', 'ur', 'ps', 'ckb', 'dv']) {
        expect(directionOfLanguage(code), TextDirection.rtl, reason: code);
      }
    });
  });

  group('directionOfText', () {
    test('reads plain prose in either script', () {
      expect(directionOfText('Yusuf planted the seed.'), TextDirection.ltr);
      expect(directionOfText('يوسف ولد طيب يحب الطبيعة'), TextDirection.rtl);
    });

    test('an English page holding an ayah stays an English page', () {
      // This is the real shape of the translated stories: English narration
      // around an Arabic ayah that must not be translated. First-strong
      // detection would flip the whole paragraph; counting does not.
      const page = 'Fatima noticed how tired her mother was. She remembered '
          'the words of Allah: ﴿وَبِالْوَالِدَيْنِ إِحْسَانًا﴾ — interpretation of the '
          'meaning: And do ihsan to parents. So she decided to bring '
          'happiness to her mother’s heart.';
      expect(directionOfText(page), TextDirection.ltr);
    });

    test('an Arabic page holding a Latin word stays an Arabic page', () {
      expect(
        directionOfText('حمزة تذكر الآية الكريمة في حلقته القرآنية Quran'),
        TextDirection.rtl,
      );
    });

    test('no directional letters means no answer, not a default', () {
      expect(directionOfText(''), isNull);
      expect(directionOfText('123 — 🌟'), isNull);
    });
  });

  group('ContentDirectionality.resolve', () {
    test('a declared language beats what the characters look like', () {
      // An Arabic story whose page happens to be mostly transliteration is
      // still Arabic. The tag is evidence; counting is inference.
      expect(
        ContentDirectionality.resolve(languageCode: 'ar', text: 'Bismillah'),
        TextDirection.rtl,
      );
    });

    test('falls back to the script when nothing is tagged', () {
      expect(
        ContentDirectionality.resolve(text: 'قصة قبل النوم'),
        TextDirection.rtl,
      );
    });

    test('with no signal at all it uses the stated fallback', () {
      expect(ContentDirectionality.resolve(), TextDirection.ltr);
      expect(
        ContentDirectionality.resolve(fallback: TextDirection.rtl),
        TextDirection.rtl,
      );
    });
  });

  testWidgets('does not inherit the chrome direction', (tester) async {
    // The mixed screen: English UI, Arabic story. If this widget ever reaches
    // for Directionality.of(context) this test goes red.
    late TextDirection seen;
    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr, // the app chrome
        child: ContentDirectionality(
          languageCode: 'ar', // the content
          child: Builder(
            builder: (context) {
              seen = Directionality.of(context);
              return const SizedBox.shrink();
            },
          ),
        ),
      ),
    );
    expect(seen, TextDirection.rtl);
  });

  group('story library selection', () {
    test('English readers get the English library, everyone else Arabic', () {
      expect(contentLanguageFor(const Locale('en')), 'en');
      expect(contentLanguageFor(const Locale('ar')), 'ar');
      // supportedLocales is [ar, en], so MaterialApp resolves French to
      // Arabic. Content that disagreed with the chrome would be worse.
      expect(contentLanguageFor(const Locale('fr')), 'ar');
    });

    test('each language names both a remote file and a bundled one', () {
      // Both halves, or an English reader silently drops to Arabic on the
      // first 4-second timeout.
      final en = storySourcesFor('en');
      expect(en.remote, '/docs/stories.en.json');
      expect(en.asset, 'assets/data/stories_en.json');

      final ar = storySourcesFor('ar');
      expect(ar.remote, '/docs/stories.json');
      expect(ar.asset, 'assets/data/stories.json');
    });

    test('a story with no language tag is Arabic', () {
      final story = Story.fromJson(const {
        'id': 'hope_sprout',
        'title': 'يوسف وغرسة الأمل',
        'description': 'قصة تربوية',
        'coverImage': 'docs/stories/hope_sprout_cover.png',
        'themeColor': '0xFF0D9488',
        'pages': <Map<String, dynamic>>[],
      });
      expect(story.language, 'ar');
    });

    test('a tagged story keeps its tag', () {
      final story = Story.fromJson(const {
        'id': 'hope_sprout',
        'title': 'Yusuf and the Seed of Hope',
        'description': 'A story about patience',
        'coverImage': 'docs/stories/hope_sprout_cover.png',
        'themeColor': '0xFF0D9488',
        'language': 'en',
        'pages': <Map<String, dynamic>>[],
      });
      expect(story.language, 'en');
    });
  });
}
