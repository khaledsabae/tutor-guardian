/// «كلمة طيبة» — the note a parent sends with the evening confirmation,
/// shown to the child the next time they hold the phone.
///
/// Three rules from the plan shape this file:
///  * **Once, as a moment.** The header stays until the child taps it away
///    or six seconds pass, and never shows twice for the same note
///    ([PraiseMemory] keys on the mission row the praise settled, which is
///    unique across the device's children).
///  * **By band.** 4–6 read a sticker and nothing else — the warmth arrives
///    without a sentence they must decode; 7–12 get the sticker and the text;
///    13–18 get one text line, because a teenager knows what a star sticker
///    means and would rather not say. Prenatal–3 are unaffected (no mission
///    bank, no praise to show).
///  * **Never in the way.** It is a header above the card, not a dialog and
///    not a gate; the child's main action stays reachable from the first
///    frame, and the only motion is a one-shot entrance that stops by itself.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../l10n/app_localizations.dart';
import '../../theme/app_colors.dart';
import '../companion/widgets/noor_face.dart';
import '../../widgets/ui/brand_glyph.dart';

/// How a band sees the praise. [none] for prenatal–3 and anything unreadable.
enum PraiseDisplay { none, sticker, stickerAndText, textOnly }

/// The display form for a child-surface band ("under-2" … "16-18").
PraiseDisplay praiseDisplayFor(String? band) {
  switch (band) {
    case '4-6':
      return PraiseDisplay.sticker;
    case '7-9':
    case '10-12':
      return PraiseDisplay.stickerAndText;
    case '13-15':
    case '16-18':
      return PraiseDisplay.textOnly;
    default:
      return PraiseDisplay.none;
  }
}

/// Which notes this device has already shown. SharedPreferences, not secure
/// storage: a mission row id is not a secret, and the child surface must be
/// able to read it without the parent's storage.
abstract final class PraiseMemory {
  static const _key = 'missions.praise_shown';

  /// Enough history for a nightly-praising family to never see a repeat,
  /// small enough that the list never grows without end.
  static const _keep = 20;

  static Future<bool> alreadyShown(
    SharedPreferences prefs,
    int missionId,
  ) async => prefs.getStringList(_key)?.contains('$missionId') ?? false;

  static Future<void> markShown(SharedPreferences prefs, int missionId) async {
    final ids = prefs.getStringList(_key) ?? <String>[];
    ids.add('$missionId');
    await prefs.setStringList(
      _key,
      ids.length > _keep ? ids.sublist(ids.length - _keep) : ids,
    );
  }
}

/// The moment itself (جولة الحرفة, item 3): «نور» delivers the note — a
/// small drawn face beside a tilted paper card carrying the words, big.
/// It stays until the child taps it away or six seconds pass, whichever
/// comes first. It never blocks the child's main action — the caller
/// places it above the card and the card is usable from the first frame.
class PraiseHeader extends StatefulWidget {
  const PraiseHeader({
    super.key,
    required this.note,
    required this.display,
    this.onGone,
  });

  final String note;
  final PraiseDisplay display;
  final VoidCallback? onGone;

  @override
  State<PraiseHeader> createState() => _PraiseHeaderState();
}

class _PraiseHeaderState extends State<PraiseHeader> {
  Timer? _expiry;

  @override
  void initState() {
    super.initState();
    // Six seconds, tops — the tap is the honoured way out; the timer only
    // guarantees the header cannot linger over a child who walked away.
    _expiry = Timer(const Duration(seconds: 6), _gone);
  }

  @override
  void dispose() {
    _expiry?.cancel();
    super.dispose();
  }

  void _gone() {
    if (mounted) widget.onGone?.call();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final theme = Theme.of(context);
    final showSticker =
        widget.display == PraiseDisplay.sticker ||
        widget.display == PraiseDisplay.stickerAndText;
    final showText =
        widget.display == PraiseDisplay.stickerAndText ||
        widget.display == PraiseDisplay.textOnly;

    // The paper card: surface-coloured, softly squared, tilted like a note
    // someone propped against the screen. The tilt is static — it is the
    // paper's character, not motion, so reduce-motion keeps it whole.
    final paper = Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(14),
          topRight: Radius.circular(18),
          bottomLeft: Radius.circular(18),
          bottomRight: Radius.circular(10),
        ),
        border: Border.all(color: colors.accent.withValues(alpha: .35)),
        boxShadow: [
          BoxShadow(
            color: colors.primary.withValues(alpha: .10),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showSticker)
            // One-shot entrance: it scales in once and stops. Nothing here
            // loops, so a CI journey with animations disabled loses nothing.
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.6, end: 1),
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeOutBack,
              builder: (context, scale, child) =>
                  Transform.scale(scale: scale, child: child),
              child: BrandGlyph(
                BrandIcon.star,
                size: 40,
                color: colors.accent,
                semanticLabel: l10n.praiseFromFamily,
              ),
            ),
          if (showSticker && showText) const SizedBox(height: 6),
          if (showText) ...[
            Text(
              l10n.praiseFromFamily,
              textAlign: TextAlign.center,
              style: theme.textTheme.labelMedium?.copyWith(
                color: colors.textSecondary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              widget.note,
              textAlign: TextAlign.center,
              // Big: this is the moment a child reads about themselves.
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.headlineSmall?.copyWith(
                color: colors.primary,
                fontWeight: FontWeight.w800,
                height: 1.35,
              ),
            ),
          ],
        ],
      ),
    );

    return Semantics(
      label: l10n.praiseFromFamily,
      button: true,
      child: GestureDetector(
        // A tap anywhere on the moment thanks نور and clears the way.
        onTap: _gone,
        behavior: HitTestBehavior.opaque,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // «نور» delivers it — the tender amber face, small.
            NoorFace(size: 44, state: NoorFaceState.tender),
            const SizedBox(width: 10),
            Expanded(
              child: Transform.rotate(
                angle: -0.035, // ≈2°: propped, not falling over
                child: paper,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
