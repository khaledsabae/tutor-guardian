/// BrandGlyph — the app's icon set («جولة الحرفة», item 1; «ورق مقصوص»,
/// 2026-10-14).
///
/// No emoji as graphics: a colored Noto emoji is a foreign illustration
/// style slamming into the app's own, and it renders differently on every
/// vendor. Every glyph here is one hand-cut SVG under assets/svg/icons/ —
/// the paper-cut set the owner chose: ivory, emerald, gold and coral layers,
/// each with a solid paper shadow — so an icon is identical on every device.
///
/// The icons are multi-colour by design and are never tinted: a ColorFilter
/// would flatten the paper layers into one silhouette. They were thin-line
/// [CustomPainter]s in one colour until then, and ~30 call sites still pass a
/// `color:`; see [BrandGlyph.color] for what it means now. Static by design:
/// no animation, no repeat.
library;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../theme/app_colors.dart';

/// The icon catalogue. Grows here — one value, one file
/// `assets/svg/icons/<value>.svg` (test/svg_assets_test.dart pins the pairing)
/// — never as an ad-hoc painter or emoji elsewhere.
enum BrandIcon {
  /// The brand mark — a thin crescent, opening toward the top-right.
  crescent,

  /// Full moon with craters (bedtime surfaces).
  fullMoon,

  /// Eight-point sparkle star.
  star,

  /// Ramadan fanous: ring, cap, glass body, flame, foot.
  lantern,

  /// Open book with a centre spine (lessons, library).
  openBook,

  /// A stem with paired leaves (growth, review, living things).
  sprig,

  /// Envelope (invites, share).
  envelope,

  /// Gift box with lid, ribbon and bow (rewards).
  gift,

  /// Speech bubble with tail (chat, questions).
  speechBubble,

  /// A winding trail from a start dot to a lit destination (paths).
  path,

  /// Pointed Islamic arch door with sill and handle (gates, milestones).
  door,

  /// A lit dot with rays — a small light (tips, ideas in the abstract).
  lightDot,

  /// Drawn coin: two concentric circles (currency). Readable at 16px.
  coin,

  /// Globe: circle, meridian and equator (language, world).
  globe,

  /// Flame (login streak).
  flame,

  /// Medal with ribbons (badges, achievements).
  medal,

  /// Sun with radiating rays (daytime).
  sun,
}

/// One brand icon.
///
/// ```dart
/// BrandGlyph(BrandIcon.gift, size: 24)
/// ```
///
/// Glyphs are decorative by default — the text next to one carries the
/// meaning. Give a [semanticLabel] only when the glyph is the meaning.
class BrandGlyph extends StatelessWidget {
  const BrandGlyph(
    this.icon, {
    super.key,
    this.size = 24,
    this.color,
    this.semanticLabel,
  });

  final BrandIcon icon;

  /// Logical pixels, square; the 48 design grid scales linearly.
  final double size;

  /// Kept for source compatibility, but it no longer recolours anything —
  /// a multi-colour paper icon cannot take one colour. What it still says is
  /// whether the glyph is *quiet*: a muted role — the theme's `outline` /
  /// `outlineVariant` / disabled colour, the palette's `textSecondary` /
  /// `inkSoft` — or any colour under 60% alpha draws the icon at 45%
  /// opacity (an unlit lantern, a disabled row). Every other colour is
  /// ignored and the icon shows in its own colours. See [isMuted].
  final Color? color;

  /// When null (the default) the glyph paints with no semantics node of its
  /// own, exactly like the emoji `Text`s it replaces did not carry a label.
  final String? semanticLabel;

  /// The file for [icon].
  static String assetFor(BrandIcon icon) => 'assets/svg/icons/${icon.name}.svg';

  /// The opacity a muted glyph is drawn at.
  static const double mutedOpacity = .45;

  /// Whether [color], passed by a call site, asks for the quiet look.
  static bool isMuted(BuildContext context, Color? color) {
    if (color == null) return false;
    if (color.a < .6) return true;
    final theme = Theme.of(context);
    final palette = context.colors;
    return {
      theme.colorScheme.outline,
      theme.colorScheme.outlineVariant,
      theme.disabledColor,
      palette.textSecondary,
      palette.inkSoft,
    }.contains(color);
  }

  @override
  Widget build(BuildContext context) {
    Widget glyph = SvgPicture.asset(
      assetFor(icon),
      width: size,
      height: size,
      excludeFromSemantics: true,
      // A missing icon is a build defect (svg_assets_test pins the set);
      // keep the space so the row around it does not shift.
      placeholderBuilder: (_) => SizedBox.square(dimension: size),
      errorBuilder: (_, _, _) => SizedBox.square(dimension: size),
    );
    if (isMuted(context, color)) {
      glyph = Opacity(opacity: mutedOpacity, child: glyph);
    }
    glyph = SizedBox.square(dimension: size, child: glyph);
    if (semanticLabel != null) {
      glyph = Semantics(label: semanticLabel, child: glyph);
    }
    return glyph;
  }
}

/// Squircle tile with a brand glyph — the drawn successor to [EmojiHero],
/// for the hero spots on coloured gradient cards.
class GlyphHero extends StatelessWidget {
  const GlyphHero(
    this.icon, {
    super.key,
    this.size = 56,
    this.color,
    this.background = const Color(0x33FFFFFF),
    this.radius = 18,
  });

  final BrandIcon icon;
  final double size;

  /// Passed on to [BrandGlyph.color]: only a muted role changes anything.
  final Color? color;
  final Color background;
  final double radius;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(radius),
      ),
      child: BrandGlyph(icon, size: size * .62, color: color),
    );
  }
}
