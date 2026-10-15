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

/// «وقفة» — the moment inside a story where Noor stops and asks the child
/// what they would do, before the page that answers it.
///
/// Optional per story (`pause` in stories.json). Gentle guidance, never a
/// score (Khaled, 2026-10-15): no right/wrong, no points, no ✓/✗. The caring
/// choice ([caring]) is met with [affirm], warm and naming the value; the
/// other with [nudge] — the feeling acknowledged, then a question that points
/// back at the story's value — and the child may choose again or read on.
/// A question with no caring option (a "what did you love today?") has
/// [caring] null and every answer meets [affirm].
class StoryPause {
  /// The question appears after this page (1-based, as `pageNumber`).
  final int afterPage;
  final String question;
  final List<String> options;

  /// Index of the caring/prosocial option, or null when every answer is one.
  final int? caring;

  /// Noor's reply to the caring choice (or to any choice when [caring] is null).
  final String? affirm;

  /// Noor's reply to the other choice: understanding, then a question.
  final String? nudge;

  const StoryPause({
    required this.afterPage,
    required this.question,
    required this.options,
    this.caring,
    this.affirm,
    this.nudge,
  });

  /// Whether choosing [option] is met with the gentle nudge rather than the
  /// affirmation. Never true without a nudge to say.
  bool nudges(int option) =>
      caring != null && option != caring && (nudge?.isNotEmpty ?? false);

  /// What Noor says to [option]; null → the reader's generic line.
  String? replyTo(int option) => nudges(option) ? nudge : affirm;

  /// Null when the block is malformed — a broken pause must never cost the
  /// reader the story around it.
  static StoryPause? tryParse(Object? json) {
    if (json is! Map) return null;
    final after = json['afterPage'];
    final question = json['question'];
    final options = json['options'];
    if (after is! int || question is! String || question.trim().isEmpty) {
      return null;
    }
    if (options is! List || options.length < 2) return null;
    final opts = [
      for (final o in options)
        if (o is String && o.trim().isNotEmpty) o.trim(),
    ];
    if (opts.length < 2) return null;
    final caring = json['caring'];
    String? text(Object? v) =>
        v is String && v.trim().isNotEmpty ? v.trim() : null;
    return StoryPause(
      afterPage: after,
      question: question.trim(),
      options: opts,
      caring: caring is int && caring >= 0 && caring < opts.length ? caring : null,
      affirm: text(json['affirm']),
      nudge: text(json['nudge']),
    );
  }
}

/// The age range a story is written for, read from its free-text label
/// («3-6 سنوات», «4-7 years», «٥–٨») — Arabic-Indic digits included.
/// Null when the label carries no two numbers.
({int min, int max})? ageRangeOf(String? label) {
  if (label == null) return null;
  const arabicDigits = '٠١٢٣٤٥٦٧٨٩';
  final western = String.fromCharCodes(
    label.runes.map((r) {
      final i = arabicDigits.indexOf(String.fromCharCode(r));
      return i >= 0 ? 0x30 + i : r;
    }),
  );
  final nums = RegExp(
    r'\d+',
  ).allMatches(western).map((m) => int.parse(m[0]!)).toList();
  if (nums.length < 2) return null;
  final a = nums[0], b = nums[1];
  return a <= b ? (min: a, max: b) : (min: b, max: a);
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

  /// Target developmental stage (e.g. '3-6 سنوات' / 'الروضة').
  final String? ageGroup;

  /// Core ethical / behavioral category (e.g. 'الصدق والأمانة').
  final String? category;

  /// Smart questions for parent-child guided dialogue after reading.
  final List<String> discussionQuestions;

  /// Hadith, Ayah, or prophetic wisdom anchoring the story's moral.
  final String? islamicValue;

  /// Concrete practical action challenge for the child to apply tomorrow.
  final String? actionChallenge;

  /// Noor's mid-story question to the child, if the story has one.
  final StoryPause? pause;

  Story({
    required this.id,
    required this.title,
    required this.description,
    required this.coverImage,
    required this.themeColor,
    this.videoFile,
    required this.pages,
    this.language = 'ar',
    this.ageGroup,
    this.category,
    this.discussionQuestions = const [],
    this.islamicValue,
    this.actionChallenge,
    this.pause,
  });

  factory Story.fromJson(Map<String, dynamic> json) {
    var pagesList = json['pages'] as List;
    List<StoryPage> parsedPages = pagesList
        .map((i) => StoryPage.fromJson(i as Map<String, dynamic>))
        .toList();

    return Story(
      id: json['id'] as String,
      title: json['title'] as String,
      description: json['description'] as String,
      coverImage: json['coverImage'] as String,
      themeColor: json['themeColor'] as String,
      videoFile: json['videoFile'] as String?,
      pages: parsedPages,
      language: (json['language'] as String?) ?? 'ar',
      ageGroup: json['ageGroup'] as String?,
      category: json['category'] as String?,
      discussionQuestions:
          (json['discussionQuestions'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      islamicValue: json['islamicValue'] as String?,
      actionChallenge: json['actionChallenge'] as String?,
      pause: StoryPause.tryParse(json['pause']),
    );
  }

  /// Whether the story has a looping ambient video cover.
  ///
  /// Kept for old clients only: since the paper-cut reader (2026-10) the app
  /// draws its covers and never plays these. The server copy of stories.json
  /// still names the files because versions in the field read it.
  bool get hasVideo => videoFile != null && videoFile!.isNotEmpty;

  /// Whether the story includes post-reading guided debriefing.
  bool get hasDebrief =>
      discussionQuestions.isNotEmpty ||
      (islamicValue != null && islamicValue!.isNotEmpty) ||
      (actionChallenge != null && actionChallenge!.isNotEmpty);
}

/// Which story library to load, given the locale the user chose (or `null`
/// when they never chose and the device decides).
///
/// Mirrors how `MaterialApp` resolves the UI: `supportedLocales` is
/// `[ar, en]`, so anything that is not English falls to Arabic — including the
/// French devices that are 11% of the base. Content that disagreed with the
/// chrome about that would be worse than content that follows it.
String contentLanguageFor(Locale? appLocale) {
  final code = (appLocale ?? PlatformDispatcher.instance.locale).languageCode
      .toLowerCase();
  return code == 'en' ? 'en' : 'ar';
}

/// Remote path and bundled asset for a story library, per language.
({String remote, String asset}) storySourcesFor(String language) =>
    language == 'en'
    ? (remote: '/docs/stories.en.json', asset: 'assets/data/stories_en.json')
    : (remote: '/docs/stories.json', asset: 'assets/data/stories.json');

List<Story> _parseStories(String body) => (jsonDecode(body) as List<dynamic>)
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
