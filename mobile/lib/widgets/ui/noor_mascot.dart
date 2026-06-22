import 'package:flutter/material.dart';

/// «نور» — the app mascot, now the unified brand identity: the serene
/// crescent-moon face (crescent + book + sprout + star), replacing the old
/// lantern. Square 1024² source, `BoxFit.contain`; degrades gracefully to an
/// empty box if the asset is ever missing so the layout never breaks.
class NoorMascot extends StatelessWidget {
  const NoorMascot({super.key, this.size = 56});

  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Image.asset(
        'assets/images/generated/mascot_serene.webp',
        fit: BoxFit.contain,
        filterQuality: FilterQuality.medium,
        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
      ),
    );
  }
}
