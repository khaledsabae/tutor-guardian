// The bookshelf must not hold a video decoder open for every story.
//
// It used to create and play a VideoPlayerController for each story the moment
// the shelf opened. With ten stories that is ten concurrent network decoders,
// each holding a MediaCodec instance and a surface texture — more than low-end
// Android devices allow at once, and all of them downloading simultaneously on
// mobile data, for books the reader cannot see.
//
// The policy is tested here rather than through the mounted shelf: the book
// covers shimmer on an infinite repeat, so pumpAndSettle never returns and the
// binding fails the test on pending timers.

import 'package:flutter_test/flutter_test.dart';

import 'package:almorabbi/features/program/data/story_models.dart';
import 'package:almorabbi/features/program/screens/story_bookshelf_screen.dart';

Story _story(int i, {String? videoFile = 'docs/stories/story.mp4'}) => Story(
      id: 'story_$i',
      title: 'قصة $i',
      description: 'وصف',
      coverImage: 'assets/images/stories/cover.png',
      themeColor: '#123456',
      videoFile: videoFile,
      pages: const [],
    );

void main() {
  group('videoWindowFor', () {
    test('keeps the centred story and one neighbour either side', () {
      final stories = List.generate(10, _story);

      expect(videoWindowFor(centered: 4, stories: stories), {3, 4, 5});
      expect(videoWindowFor(centered: 0, stories: stories), {0, 1});
      expect(videoWindowFor(centered: 9, stories: stories), {8, 9});
    });

    test('never grows with the library', () {
      for (final size in [10, 50, 200]) {
        final stories = List.generate(size, _story);
        for (final centered in [0, size ~/ 2, size - 1]) {
          expect(
            videoWindowFor(centered: centered, stories: stories).length,
            lessThanOrEqualTo(3),
            reason: 'library of $size centred on $centered',
          );
        }
      }
    });

    test('skips stories that have no video', () {
      final stories = [
        _story(0),
        _story(1, videoFile: null),
        _story(2),
        _story(3, videoFile: null),
      ];

      expect(videoWindowFor(centered: 1, stories: stories), {0, 2});
      expect(videoWindowFor(centered: 3, stories: stories), {2});
    });

    test('returns nothing when no story has a video', () {
      final stories = [for (var i = 0; i < 4; i++) _story(i, videoFile: null)];

      expect(videoWindowFor(centered: 0, stories: stories), isEmpty);
      expect(videoWindowFor(centered: 2, stories: stories), isEmpty);
    });

    test('stays inside the list at either edge', () {
      final stories = List.generate(3, _story);

      expect(videoWindowFor(centered: -1, stories: stories), {0});
      expect(videoWindowFor(centered: 99, stories: stories), isEmpty);
    });
  });
}
