/// A "go forward" chevron that points the way the language reads.
///
/// The codebase had accumulated three different icons for this one meaning —
/// `arrow_back_ios_new`, `chevron_left` and `arrow_forward_ios` — which in an
/// RTL-first app meant some of them pointed at the screen edge instead of at
/// the destination. Forward is leftwards in Arabic and rightwards in English;
/// this picks the glyph explicitly rather than relying on the framework's
/// per-icon auto-mirroring, which differs between icons and is easy to get
/// silently wrong.
library;

import 'package:flutter/material.dart';

import '../../theme/design_tokens.dart';

class DirectionalChevron extends StatelessWidget {
  const DirectionalChevron({super.key, this.size = 18, this.color});

  final double size;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final isRtl = Directionality.of(context) == TextDirection.rtl;
    return Icon(
      isRtl ? Icons.chevron_left : Icons.chevron_right,
      size: size,
      color: color ?? Dt.inkSoft,
      // Pinned to LTR so the framework cannot mirror the glyph a second time
      // and undo the choice above.
      textDirection: TextDirection.ltr,
    );
  }
}
