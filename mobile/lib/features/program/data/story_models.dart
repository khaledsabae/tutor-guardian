import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../../../config/app_config.dart';

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

  Story({
    required this.id,
    required this.title,
    required this.description,
    required this.coverImage,
    required this.themeColor,
    this.videoFile,
    required this.pages,
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
    );
  }

  /// Whether the story has a looping ambient video cover.
  bool get hasVideo => videoFile != null && videoFile!.isNotEmpty;
}

/// Provider to load stories from VPS remote server with local asset fallback.
final storiesProvider = FutureProvider<List<Story>>((ref) async {
  try {
    final response = await http
        .get(Uri.parse('${AppConfig.apiBaseUrl}/docs/stories.json'))
        .timeout(const Duration(seconds: 4));
    if (response.statusCode == 200) {
      final List<dynamic> jsonList = jsonDecode(response.body) as List<dynamic>;
      return jsonList.map((json) => Story.fromJson(json as Map<String, dynamic>)).toList();
    }
  } catch (_) {
    // Silent fallback to local asset bundle on network timeout/error
  }
  final jsonString = await rootBundle.loadString('assets/data/stories.json');
  final List<dynamic> jsonList = jsonDecode(jsonString) as List<dynamic>;
  return jsonList.map((json) => Story.fromJson(json as Map<String, dynamic>)).toList();
});
