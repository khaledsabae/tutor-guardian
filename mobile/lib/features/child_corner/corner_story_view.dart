/// The corner's story: the day's story, read one page at a time on paper.
///
/// Deliberately not the bookshelf's reader. That screen is the parent's: it
/// ends on the parent's actions — «سأجرّبها مع …», invite a friend, the
/// bedtime adhkar, another story — none of which belongs in a child's hands,
/// and every one of which would lead the child out of the corner. This view
/// reads the same story from the same library (`storiesProvider`: the
/// server's `/docs/stories*.json`, the bundled copy when it cannot be
/// reached) and ends on one button: back to the corner.
///
/// The text is laid out in the story's own language, not the interface's
/// (see [Story.language]).
library;

import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../../theme/app_colors.dart';
import '../../widgets/ui/art_image.dart';
import '../../widgets/ui/brand_glyph.dart';
import '../program/data/story_models.dart';
import 'corner_scene.dart';

class CornerStoryView extends StatefulWidget {
  const CornerStoryView({
    super.key,
    required this.story,
    required this.clock,
    required this.onClose,
  });

  final Story story;

  /// The candle, drawn by the corner.
  final Widget clock;

  /// Called with true when the story was read to its end, false when the
  /// child closed it before.
  final ValueChanged<bool> onClose;

  @override
  State<CornerStoryView> createState() => CornerStoryViewState();
}

class CornerStoryViewState extends State<CornerStoryView> {
  int _leaf = 0;

  int get _leaves => widget.story.pages.length + 1;
  bool get _atEnd => _leaf == _leaves - 1;

  void _go(int delta) => setState(() {
    _leaf = (_leaf + delta).clamp(0, _leaves - 1);
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final paper = context.colors.corner;
    final large = MediaQuery.textScalerOf(context).scale(10) > 13;
    final storyDir = widget.story.language == 'en'
        ? TextDirection.ltr
        : TextDirection.rtl;

    final Widget leaf;
    if (_atEnd) {
      leaf = Column(
        key: const ValueKey('child_corner_story_end'),
        mainAxisSize: MainAxisSize.min,
        children: [
          const ExcludeSemantics(
            child: SizedBox(
              height: 120,
              child: ArtImage('assets/svg/noor/noor_reading.svg'),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            l10n.childCornerStoryEnd,
            textAlign: TextAlign.center,
            style: theme.textTheme.headlineSmall?.copyWith(
              color: paper.ink,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 20),
          CornerGoldButton(
            key: const ValueKey('child_corner_story_back'),
            label: l10n.childCornerBackToCorner,
            onPressed: () => widget.onClose(true),
          ),
        ],
      );
    } else {
      final page = widget.story.pages[_leaf];
      leaf = Column(
        key: ValueKey('child_corner_story_page_$_leaf'),
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Noor reading along: the library's own pictures are network
          // images, some of them missing — paper art is always there.
          const ExcludeSemantics(
            child: SizedBox(
              height: 84,
              child: ArtImage('assets/svg/noor/noor_reading.svg'),
            ),
          ),
          const SizedBox(height: 12),
          Directionality(
            textDirection: storyDir,
            child: Text(
              page.text,
              textAlign: TextAlign.start,
              style: theme.textTheme.titleLarge?.copyWith(
                color: paper.ink,
                height: 1.8,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      );
    }

    return Container(
      color: paper.ground,
      child: SafeArea(
        top: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              color: paper.sky,
              padding: const EdgeInsetsDirectional.fromSTEB(4, 8, 12, 4),
              child: Row(
                children: [
                  IconButton(
                    key: const ValueKey('child_corner_story_close'),
                    tooltip: l10n.childCornerStoryClose,
                    icon: Icon(Icons.close_rounded, color: paper.ink),
                    onPressed: () => widget.onClose(false),
                  ),
                  Expanded(
                    child: Directionality(
                      textDirection: storyDir,
                      child: Text(
                        widget.story.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.titleMedium?.copyWith(
                          color: paper.ink,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ),
                  if (!large) ...[
                    const SizedBox(width: 8),
                    Flexible(child: widget.clock),
                  ],
                ],
              ),
            ),
            // With large type the title and the candle each get a row,
            // rather than both breaking mid-word.
            if (large)
              ColoredBox(
                color: paper.sky,
                child: Padding(
                  padding: const EdgeInsetsDirectional.fromSTEB(16, 0, 16, 4),
                  child: Align(
                    alignment: AlignmentDirectional.centerStart,
                    child: widget.clock,
                  ),
                ),
              ),
            const CornerHills(height: 40),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) => SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                  child: ConstrainedBox(
                    // Centred in the valley when the page is short; scrolls
                    // when the type is large.
                    constraints: BoxConstraints(
                      minHeight: (constraints.maxHeight - 24).clamp(0, 1e9),
                    ),
                    child: Center(
                      child: SizedBox(
                        width: double.infinity,
                        child: CornerPaperCard(
                          padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
                          child: AnimatedSwitcher(
                            duration: const Duration(milliseconds: 220),
                            child: leaf,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
            if (!_atEnd)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Row(
                  children: [
                    TextButton(
                      key: const ValueKey('child_corner_story_previous'),
                      style: TextButton.styleFrom(
                        foregroundColor: context.colors.paperIvory,
                      ),
                      onPressed: _leaf == 0 ? null : () => _go(-1),
                      child: Text(l10n.childCornerStoryPrevious),
                    ),
                    Expanded(
                      child: _Dots(
                        index: _leaf,
                        count: widget.story.pages.length,
                      ),
                    ),
                    CornerGoldButton(
                      key: const ValueKey('child_corner_story_next'),
                      label: l10n.childCornerStoryNext,
                      onPressed: () => _go(1),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Where in the story the child is — dots, not "3 / 6".
class _Dots extends StatelessWidget {
  const _Dots({required this.index, required this.count});

  final int index;
  final int count;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Semantics(
      label: AppLocalizations.of(
        context,
      ).childCornerStoryPage(index + 1, count),
      excludeSemantics: true,
      child: Wrap(
        alignment: WrapAlignment.center,
        spacing: 6,
        runSpacing: 6,
        children: [
          for (var i = 0; i < count; i++)
            i == index
                ? const BrandGlyph(BrandIcon.star, size: 14)
                : Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: c.paperIvory.withValues(alpha: .45),
                      shape: BoxShape.circle,
                    ),
                  ),
        ],
      ),
    );
  }
}
