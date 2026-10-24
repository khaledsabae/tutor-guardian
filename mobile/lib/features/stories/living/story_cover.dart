/// A story's cover on the shelf and on its first leaf: the painted cover
/// (`docs/stories/<id>_cover.png`) for a story told with its paintings, or the
/// given paper-cut [fallback] — for the other stories, and whenever the
/// painting cannot be loaded.
library;

import 'package:flutter/material.dart';

import '../scene/story_scene.dart';
import 'living_picture.dart';
import 'living_picture_catalog.dart';

class StoryCoverPicture extends StatelessWidget {
  const StoryCoverPicture({
    super.key,
    required this.storyId,
    required this.fallback,
  });

  final String storyId;
  final Widget fallback;

  @override
  Widget build(BuildContext context) {
    final cover = livingCoverFor(storyId);
    if (cover == null) return fallback;
    return AspectRatio(
      aspectRatio: kSceneAspect,
      child: Image(
        image: livingImage(cover),
        fit: BoxFit.cover,
        // The paintings put faces in the upper middle.
        alignment: const Alignment(0, -.25),
        excludeFromSemantics: true,
        frameBuilder: (context, child, frame, sync) => sync
            ? child
            : AnimatedOpacity(
                opacity: frame == null ? 0 : 1,
                duration: const Duration(milliseconds: 300),
                child: child,
              ),
        errorBuilder: (context, error, stack) => fallback,
      ),
    );
  }
}
