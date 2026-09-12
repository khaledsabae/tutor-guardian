import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:almorabbi/features/program/data/story_models.dart';

void main() {
  group('Story model and kindergarten enrichment', () {
    test('parses enriched story with discussion questions and Islamic value', () {
      final json = {
        'id': 'badr_broken_toy',
        'title': 'بدر واللعبة المكسورة',
        'description': 'قصة تربوية',
        'coverImage': 'docs/stories/cover.png',
        'themeColor': '0xFF0F766E',
        'ageGroup': '3-6 سنوات',
        'category': 'الصدق والشجاعة',
        'discussionQuestions': [
          'ما الذي كان يمكن أن يحدث لو كذب بدر؟',
          'هل الاعتراف بالخطأ يحتاج إلى شجاعة؟'
        ],
        'islamicValue': 'قال رسول الله ﷺ: عليكم بالصدق',
        'actionChallenge': 'تحدي الصدق اليومي',
        'pages': [
          {
            'pageNumber': 1,
            'text': 'كان بدر يلعب...',
            'image': 'docs/stories/1.png',
          }
        ]
      };

      final story = Story.fromJson(json);

      expect(story.id, 'badr_broken_toy');
      expect(story.title, 'بدر واللعبة المكسورة');
      expect(story.ageGroup, '3-6 سنوات');
      expect(story.category, 'الصدق والشجاعة');
      expect(story.discussionQuestions.length, 2);
      expect(story.islamicValue, contains('عليكم بالصدق'));
      expect(story.actionChallenge, 'تحدي الصدق اليومي');
      expect(story.hasDebrief, isTrue);
      expect(story.pages.length, 1);
    });

    test('backward compatibility: legacy story without debrief fields defaults safely', () {
      final json = {
        'id': 'legacy_story',
        'title': 'قصة قديمة',
        'description': 'وصف',
        'coverImage': 'docs/stories/legacy.png',
        'themeColor': '0xFF123456',
        'pages': []
      };

      final story = Story.fromJson(json);

      expect(story.id, 'legacy_story');
      expect(story.ageGroup, isNull);
      expect(story.category, isNull);
      expect(story.discussionQuestions, isEmpty);
      expect(story.islamicValue, isNull);
      expect(story.actionChallenge, isNull);
      expect(story.hasDebrief, isFalse);
    });

    test('both docs/stories.json and mobile/assets/data/stories.json are valid and contain all 19 stories', () {
      final docsFile = File('../docs/stories.json');
      final assetsFile = File('assets/data/stories.json');

      expect(docsFile.existsSync(), isTrue);
      expect(assetsFile.existsSync(), isTrue);

      final docsStories = (jsonDecode(docsFile.readAsStringSync()) as List)
          .map((e) => Story.fromJson(e as Map<String, dynamic>))
          .toList();

      final assetsStories = (jsonDecode(assetsFile.readAsStringSync()) as List)
          .map((e) => Story.fromJson(e as Map<String, dynamic>))
          .toList();

      expect(docsStories.length, 19);
      expect(assetsStories.length, 19);

      // Verify Kindergarten stories exist
      final badr = docsStories.firstWhere((s) => s.id == 'badr_broken_toy');
      expect(badr.ageGroup, '3-6 سنوات');
      expect(badr.discussionQuestions, isNotEmpty);
      expect(badr.islamicValue, isNotEmpty);
      expect(badr.actionChallenge, isNotEmpty);
      expect(badr.hasDebrief, isTrue);

      final sarah = docsStories.firstWhere((s) => s.id == 'sarah_basil_sprout');
      expect(sarah.ageGroup, '3-6 سنوات');
      expect(sarah.hasDebrief, isTrue);
    });
  });
}
