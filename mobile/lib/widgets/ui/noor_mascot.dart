import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

/// «نور» — the app mascot, still and at rest: the calm face of the
/// «ورق مقصوص» set (assets/svg/noor/noor_calm.svg), on a transparent ground.
/// For a Noor that breathes, blinks and changes expression use NoorFace or
/// NoorPresence; this one is for quiet placements (settings, backup).
///
/// Decorative: the text beside it carries the meaning. A file that fails to
/// parse leaves an empty box of the same size, so the layout never breaks.
class NoorMascot extends StatelessWidget {
  const NoorMascot({super.key, this.size = 56});

  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: SvgPicture.asset(
        'assets/svg/noor/noor_calm.svg',
        width: size,
        height: size,
        excludeFromSemantics: true,
        errorBuilder: (_, _, _) => const SizedBox.shrink(),
      ),
    );
  }
}
