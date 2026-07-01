import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
  final List<StoryPage> pages;

  Story({
    required this.id,
    required this.title,
    required this.description,
    required this.coverImage,
    required this.themeColor,
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
      pages: parsedPages,
    );
  }
}

/// Provider to load stories from the local JSON asset.
final storiesProvider = FutureProvider<List<Story>>((ref) async {
  final jsonString = await rootBundle.loadString('assets/data/stories.json');
  final List<dynamic> jsonList = jsonDecode(jsonString) as List<dynamic>;
  return jsonList.map((json) => Story.fromJson(json as Map<String, dynamic>)).toList();
});
