/// The welcome hero — the «ورق مقصوص» scene with «نور» in its sky.
///
/// assets/svg/art/onboarding_welcome.svg (360×240) is an emerald card: hills,
/// an open book with a sprout, a path, stars — and an empty 90×90 patch of
/// sky centred at (280, 70), left for Noor. He is not baked into the scene so
/// that he can be himself there: [NoorPresence], breathing and blinking, in
/// his window. Used by the language page of onboarding and by the
/// «إيه الجديد؟» update splash (which used to loop an mp4 of the old art).
library;

import 'package:flutter/material.dart';

import '../../../widgets/ui/art_image.dart';
import '../../companion/widgets/noor_face.dart';
import '../../companion/widgets/noor_presence.dart';

const kWelcomeHeroAsset = 'assets/svg/art/onboarding_welcome.svg';

/// The scene's design size and Noor's patch of sky, in its units.
const _scene = Size(360, 240);
const _noorCentre = Offset(280, 70);
const _noorSlot = 90.0;

class WelcomeHero extends StatelessWidget {
  const WelcomeHero({
    super.key,
    this.mood = NoorMood.calm,
    this.face,
    this.fallback,
  });

  /// Noor's halo and, unless [face] says otherwise, his expression.
  final NoorMood mood;
  final NoorFaceState? face;

  /// Shown instead of the scene if it cannot be loaded — a bundled file
  /// that fails is a build defect, but the page around it should hold.
  final WidgetBuilder? fallback;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: _scene.width / _scene.height,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final scale = constraints.maxWidth / _scene.width;
          final slot = _noorSlot * scale;
          return Stack(
            children: [
              Positioned.fill(
                child: ArtImage(
                  kWelcomeHeroAsset,
                  fit: BoxFit.contain,
                  fallback: fallback,
                ),
              ),
              Positioned(
                left: (_noorCentre.dx - _noorSlot / 2) * scale,
                top: (_noorCentre.dy - _noorSlot / 2) * scale,
                width: slot,
                height: slot,
                // NoorPresence's footprint is its window ×1.3 (the halo), so
                // the window is sized for the whole halo to fit the slot.
                child: Center(
                  child: NoorPresence(size: slot / 1.3, mood: mood, face: face),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
