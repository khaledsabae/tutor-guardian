/// «هل أعجبتك الحكاية؟» — one small question at a story's end, the same in
/// both arms of the «صورة حيّة» experiment (it never asks about the motion:
/// the still arm could not answer that). Three faces, skippable — nothing
/// waits on it and closing the story is never blocked — and asked at most
/// once per story per device.
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import 'story_experiment.dart';

class StoryRatingCard extends StatefulWidget {
  const StoryRatingCard({
    super.key,
    required this.storyId,
    required this.onRated,
  });

  final String storyId;

  /// 3 = 😍, 2 = 🙂, 1 = 😐.
  final ValueChanged<int> onRated;

  @override
  State<StoryRatingCard> createState() => StoryRatingCardState();
}

class StoryRatingCardState extends State<StoryRatingCard> {
  /// null while reading the device's memory of this story.
  bool? _askedBefore;
  int? _rated;

  @override
  void initState() {
    super.initState();
    SharedPreferences.getInstance().then(
      (prefs) {
        if (!mounted) return;
        setState(
          () => _askedBefore =
              prefs.getBool(storyRatedKey(widget.storyId)) ?? false,
        );
      },
      onError: (Object _) {
        if (mounted) setState(() => _askedBefore = true);
      },
    );
  }

  Future<void> _rate(int rating) async {
    if (_rated != null) return;
    setState(() => _rated = rating);
    widget.onRated(rating);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(storyRatedKey(widget.storyId), true);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (_askedBefore != false) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final faces = [
      (3, '😍', l10n.storyRateLoved),
      (2, '🙂', l10n.storyRateLiked),
      (1, '😐', l10n.storyRateOkay),
    ];
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: colors.paperGold.withValues(alpha: .6)),
      ),
      child: AnimatedSwitcher(
        duration: const Duration(milliseconds: 250),
        child: _rated != null
            ? Padding(
                key: const ValueKey('thanks'),
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Text(
                  l10n.storyRateThanks,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: colors.ink,
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              )
            : Column(
                key: const ValueKey('ask'),
                children: [
                  Text(
                    l10n.storyRateQuestion,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: colors.ink,
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      for (final (value, face, label) in faces)
                        Semantics(
                          button: true,
                          label: label,
                          excludeSemantics: true,
                          child: InkResponse(
                            key: ValueKey('story-rate-$value'),
                            radius: 34,
                            onTap: () => _rate(value),
                            child: Padding(
                              padding: const EdgeInsets.all(8),
                              child: Text(
                                face,
                                style: const TextStyle(fontSize: 38),
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
      ),
    );
  }
}
