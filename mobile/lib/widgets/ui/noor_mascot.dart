import 'package:flutter/material.dart';

/// «نور» — the app mascot (a friendly glowing lantern).
///
/// Renders the bundled asset, degrading gracefully to an empty box if the
/// asset is ever missing (so the layout never breaks). `BoxFit.contain`
/// keeps the lantern's tall aspect ratio; medium filtering smooths the
/// downscale from the 1024² source.
class NoorMascot extends StatelessWidget {
  const NoorMascot({super.key, this.size = 56});

  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Image.asset(
        'assets/images/mascot/wave.png',
        fit: BoxFit.contain,
        filterQuality: FilterQuality.medium,
        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
      ),
    );
  }
}
