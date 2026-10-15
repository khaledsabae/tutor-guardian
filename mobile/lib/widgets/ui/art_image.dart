import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

/// One bundled illustration, whatever its format.
///
/// The «ورق مقصوص» art set (assets/svg/) is SVG; a path that still names a
/// raster (a story cover, an older asset) stays an [Image.asset]. Callers
/// that receive a path from data — a milestone's badge, a celebration's
/// picture — use this so they never have to know which one they hold.
///
/// [fallback] stands in when the asset cannot be loaded or parsed: a bundled
/// file that fails is a build defect, and the layout around it should stay
/// intact rather than collapse. Decorative unless [semanticLabel] is given.
class ArtImage extends StatelessWidget {
  const ArtImage(
    this.asset, {
    super.key,
    this.width,
    this.height,
    this.fit = BoxFit.contain,
    this.alignment = Alignment.center,
    this.semanticLabel,
    this.fallback,
  });

  final String asset;
  final double? width;
  final double? height;
  final BoxFit fit;
  final Alignment alignment;
  final String? semanticLabel;
  final WidgetBuilder? fallback;

  bool get isSvg => asset.toLowerCase().endsWith('.svg');

  @override
  Widget build(BuildContext context) {
    Widget orFallback(BuildContext context) =>
        fallback?.call(context) ?? SizedBox(width: width, height: height);
    if (isSvg) {
      return SvgPicture.asset(
        asset,
        width: width,
        height: height,
        fit: fit,
        alignment: alignment,
        semanticsLabel: semanticLabel,
        excludeFromSemantics: semanticLabel == null,
        // Hold the layout while the picture parses (a frame or two), so the
        // text under an illustration does not jump when it arrives.
        placeholderBuilder: (_) => SizedBox(width: width, height: height),
        errorBuilder: (context, _, _) => orFallback(context),
      );
    }
    final dpr = MediaQuery.maybeDevicePixelRatioOf(context) ?? 1.0;
    return Image.asset(
      asset,
      width: width,
      height: height,
      fit: fit,
      alignment: alignment,
      // Decode at the drawn size, never the full source.
      cacheWidth: width == null ? null : (width! * dpr).round(),
      filterQuality: FilterQuality.medium,
      semanticLabel: semanticLabel,
      excludeFromSemantics: semanticLabel == null,
      errorBuilder: (context, _, _) => orFallback(context),
    );
  }
}
