/// «رمضان عائلتنا» as a shareable image — the program's viral surface.
///
/// Built from the server's `card` and nothing else: the headline, the lines
/// (already filtered by the content's `min_to_show` — never re-add one) and
/// the closing. The children's fasting (`family_only`) is not a parameter
/// here, so it cannot reach the image by accident; the card carries no names,
/// ages, photos or typed text by construction (MOBILE_API §11.3.7).
///
/// Same frame, brand line and QR as every other shared moment
/// ([ShareCardFrame], [ShareCardBrandFooter]).
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../l10n/content_direction.dart';
import '../../../theme/app_theme.dart';
import '../../share/shareable_moment_card.dart';
import '../data/programs_models.dart';

class RamadanRecapShareCard extends StatelessWidget {
  const RamadanRecapShareCard({super.key, required this.card});

  final RecapCard card;

  @override
  Widget build(BuildContext context) {
    // The capture tree is left-to-right; the card's own language decides.
    final dir = ContentDirectionality.resolve(
      text: card.headline,
      fallback: TextDirection.rtl,
    );
    // A fixed 1080×1080 picture: the parent's text scale must not reflow it
    // (at 200% the preview overflowed by a third). The same numbers stay
    // readable at any size in the in-app list under the preview. The capture
    // tree has no MediaQuery at all, hence maybeOf.
    final mq = MediaQuery.maybeOf(context);
    final image = _image(dir);
    return mq == null
        ? image
        : MediaQuery(data: mq.copyWith(textScaler: TextScaler.noScaling), child: image);
  }

  Widget _image(TextDirection dir) {
    return Directionality(
      textDirection: dir,
      child: ShareCardFrame(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('🌙', style: TextStyle(fontSize: 84)),
            const SizedBox(height: 18),
            if (card.title != null) ...[
              ShareCardEyebrow(card.title!),
              const SizedBox(height: 22),
            ],
            Text(
              card.headline,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.cairo(
                fontSize: 40,
                fontWeight: FontWeight.w800,
                color: AppTheme.textPrimary,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 22),
            for (final line in card.lines.take(7))
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  line,
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.cairo(
                    fontSize: 27,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                    height: 1.45,
                  ),
                ),
              ),
            if (card.closing != null) ...[
              const SizedBox(height: 16),
              Text(
                card.closing!,
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.cairo(
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.primary,
                  height: 1.45,
                ),
              ),
            ],
            const SizedBox(height: 26),
            const ShareCardBrandFooter(
              icon: Icons.nightlight_round,
              qrSize: 96,
            ),
          ],
        ),
      ),
    );
  }
}

/// The text that travels with the shared image: the server's own `share_text`
/// (it carries the family's attributed invite link), or — from a server that
/// sent none — the card's visible lines. Never anything from `family_only`:
/// this function is given the card alone.
String recapShareMessage(RecapCard card) =>
    card.shareText ?? [card.headline, ...card.lines, ?card.closing].join('\n');
