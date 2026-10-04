/// Two columns whose rows are as tall as their tallest cell.
///
/// The replacement for `GridView.count(childAspectRatio: …)` on Home. A fixed
/// aspect ratio fixes each cell's height, so the cell cannot grow with the
/// text: the stats chips overflowed by 2px on a 360dp phone at normal size and
/// by 35px at 200% text, and the shortcut labels were clipped.
library;

import 'package:flutter/widgets.dart';

class TwoColumnRows extends StatelessWidget {
  const TwoColumnRows({
    super.key,
    required this.children,
    this.spacing = 8,
  });

  final List<Widget> children;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var i = 0; i < children.length; i += 2) ...[
          if (i > 0) SizedBox(height: spacing),
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(child: children[i]),
                SizedBox(width: spacing),
                Expanded(
                  child: i + 1 < children.length
                      ? children[i + 1]
                      : const SizedBox.shrink(),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
