import 'dart:convert';
import 'dart:ui' show Locale, PlatformDispatcher;

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../../../config/app_config.dart';
import '../../onboarding/providers/onboarding_providers.dart';

class StoryPage {
  final int pageNumber;
  final String text;
  final String image;

  StoryPage({
    required this.pageNumber,
    required this.text,
    required this.image,
  });

  factory StoryPage.fromJson(Map<String, dynamic> json) {
    return StoryPage(
      pageNumber: json['pageNumber'] as int,
      text: json['text'] as String,
      image: json['image'] as String,
    );
  }
}

class Story {
  final String id;
  final String title;
  final String description;
  final String coverImage;
  final String themeColor;
  final String? videoFile;
  final List<StoryPage> pages;

  /// The language this story's *text* is written in — not the app's language.
  ///
  /// The two come apart routinely: the English file can fail to load and the
  /// Arabic bundle answer in its place, leaving an English UI around an Arabic
  /// paragraph. Whatever renders this story reads direction and typography off
  /// this field, never off the surrounding `Directionality`.
  ///
  /// Defaults to `ar`: the Arabic files predate the field and carry no tag.
  final String language;

  Story({
    required this.id,
    required this.title,
    required this.description,
    required this.coverImage,
    required this.themeColor,
    this.videoFile,
    required this.pages,
    this.language = 'ar',
  });

  factory Story.fromJson(Map<String, dynamic> json) {
    var pagesList = json['pages'] as List;
    List<StoryPage> parsedPages =
        pagesList.map((i) => StoryPage.fromJson(i as Map<String, dynamic>)).toList();

    return Story(
      id: json['id'] as String,
      title: json['title'] as String,
      description: json['description'] as String,
      coverImage: json['coverImage'] as String,
      themeColor: json['themeColor'] as String,
      videoFile: json['videoFile'] as String?,
      pages: parsedPages,
      language: (json['language'] as String?) ?? 'ar',
    );
  }

  /// Whether the story has a looping ambient video cover.
  bool get hasVideo => videoFile != null && videoFile!.isNotEmpty;
}

/// Which story library to load, given the locale the user chose (or `null`
/// when they never chose and the device decides).
///
/// Mirrors how `MaterialApp` resolves the UI: `supportedLocales` is
/// `[ar, en]`, so anything that is not English falls to Arabic — including the
/// French devices that are 11% of the base. Content that disagreed with the
/// chrome about that would be worse than content that follows it.
String contentLanguageFor(Locale? appLocale) {
  final code =
      (appLocale ?? PlatformDispatcher.instance.locale).languageCode.toLowerCase();
  return code == 'en' ? 'en' : 'ar';
}

/// Remote path and bundled asset for a story library, per language.
({String remote, String asset}) storySourcesFor(String language) =>
    language == 'en'
        ? (remote: '/docs/stories.en.json', asset: 'assets/data/stories_en.json')
        : (remote: '/docs/stories.json', asset: 'assets/data/stories.json');

List<Story> _parseStories(String body) =>
    (jsonDecode(body) as List<dynamic>)
        .map((json) => Story.fromJson(json as Map<String, dynamic>))
        .toList();

/// Loads the story library in the reader's language: network first, bundled
/// asset on timeout.
///
/// 🚨 Both halves have to exist per language, and that is the whole point of
/// this provider. The network fetch has a 4-second timeout and falls back
/// **silently** — so shipping `stories.en.json` to the server without bundling
/// `stories_en.json` in the app would not fail loudly; it would drop an English
/// reader into Arabic on the first slow connection, with no error to explain
/// it. That is why `pubspec.yaml` names the English asset explicitly.
///
/// The last resort is still Arabic. A missing English bundle is a packaging
/// bug, and answering with a story the reader cannot read is better than
/// answering with an exception — but the returned `Story.language` says `ar`,
/// so the reader lays it out right-to-left and the mismatch stays legible
/// instead of becoming a rendering defect.
final storiesProvider = FutureProvider<List<Story>>((ref) async {
  final language = contentLanguageFor(ref.watch(appLocaleProvider));
  final sources = storySourcesFor(language);

  try {
    final response = await http
        .get(Uri.parse('${AppConfig.apiBaseUrl}${sources.remote}'))
        .timeout(const Duration(seconds: 4));
    if (response.statusCode == 200) {
      return _parseStories(response.body);
    }
  } catch (_) {
    // Silent fallback to local asset bundle on network timeout/error
  }

  try {
    return _parseStories(await rootBundle.loadString(sources.asset));
  } catch (_) {
    if (language == 'ar') rethrow;
  }
  return _parseStories(await rootBundle.loadString('assets/data/stories.json'));
});
