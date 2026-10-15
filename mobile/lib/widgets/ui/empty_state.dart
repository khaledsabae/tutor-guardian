import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../theme/design_tokens.dart';
import 'art_image.dart';
import 'bouncy_button.dart';

/// Friendly empty/error state: big drawn icon (or legacy emoji), bold
/// title, soft subtitle, optional action button. Replaces the bare
/// icon+text placeholders.
class EmptyState extends StatelessWidget {
  /// Leading graphic, drawn (BrandGlyph) — the emoji-free successor to
  /// [emoji] (جولة الحرفة). Falls back to the emoji when null.
  final Widget? icon;

  final String emoji;
  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  /// Optional illustration shown instead of [icon]/[emoji] — an
  /// assets/svg/art/ scene, or any bundled image ([ArtImage] picks the
  /// renderer). Falls back to [icon]/[emoji] if the asset is missing.
  final String? imageAsset;

  const EmptyState({
    super.key,
    this.icon,
    this.emoji = '',
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
    this.imageAsset,
  });

  @override
  Widget build(BuildContext context) {
    final fallback = icon ?? Text(emoji, style: const TextStyle(fontSize: 72));
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ExcludeSemantics(
              child:
                  (imageAsset != null
                          ? _paperDisc(
                              context,
                              ArtImage(
                                imageAsset!,
                                height: 160,
                                fallback: (_) => fallback,
                              ),
                            )
                          : fallback)
                      .animate()
                      .scale(
                        begin: const Offset(.6, .6),
                        duration: Dt.slow,
                        curve: Curves.easeOutBack,
                      ),
            ),
            const SizedBox(height: 16),
            Text(
              title,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: Dt.ink,
              ),
            ),
            if (subtitle != null) ...[
              const SizedBox(height: 8),
              Text(
                subtitle!,
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 14, color: Dt.inkSoft, height: 1.5),
              ),
            ],
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 20),
              BouncyButton(
                label: actionLabel!,
                onTap: onAction,
                expanded: false,
              ),
            ],
          ],
        ).animate().fadeIn(duration: 400.ms).slideY(begin: .06),
      ),
    );
  }

  /// The paper art is cut in deep emerald, which sinks into a dark page; at
  /// night it sits on a cream paper moon so its outlines still read.
  static Widget _paperDisc(BuildContext context, Widget art) {
    if (Theme.of(context).brightness != Brightness.dark) return art;
    return Container(
      width: 184,
      height: 184,
      alignment: Alignment.center,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        color: Color(0xE6FBF1DE), // audit-ok: a cream paper moon behind dark-cut art on a dark page — deliberate, dark mode only
      ),
      child: SizedBox(width: 150, child: art),
    );
  }
}
