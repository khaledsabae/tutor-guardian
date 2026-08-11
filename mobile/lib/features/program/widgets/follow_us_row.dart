/// «تابعنا» — one quiet row of the app's own channels, in Settings.
///
/// A row of chips rather than three more full-width settings rows: these are
/// the least important thing on the screen and should not read as three
/// separate decisions. Each chip carries the platform's name in text, so it is
/// legible even where the mark is only approximated.
library;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart'
    show launchUrl, canLaunchUrl, LaunchMode;

import '../../../core/social_links.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';

class FollowUsRow extends StatelessWidget {
  const FollowUsRow({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(right: 4, left: 4, bottom: 2),
          child: Text(
            l10n.settingsFollowUs,
            style: const TextStyle(
              fontWeight: FontWeight.w800,
              fontSize: 15,
              color: AppTheme.textPrimary,
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(right: 4, left: 4, bottom: 12),
          child: Text(
            l10n.settingsFollowUsDesc,
            style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
          ),
        ),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            for (final link in kSocialLinks) _SocialChip(link: link),
          ],
        ),
      ],
    );
  }
}

class _SocialChip extends StatelessWidget {
  const _SocialChip({required this.link});

  final SocialLink link;

  Future<void> _open() async {
    final uri = Uri.parse(link.url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: link.name,
      child: InkWell(
        onTap: _open,
        borderRadius: BorderRadius.circular(24),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          decoration: BoxDecoration(
            // The brand colour at a whisper — enough to tell the three apart
            // at a glance, not enough to pull the eye away from the settings
            // above it.
            color: link.colour.withValues(alpha: .07),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: link.colour.withValues(alpha: .18)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _Mark(link: link),
              const SizedBox(width: 8),
              Text(
                link.name,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: link.colour,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The platform's mark. Material ships a Facebook glyph; the other two are
/// composed, since a wrong-but-confident logo reads worse than a simple shape
/// next to the name that is already spelled out beside it.
class _Mark extends StatelessWidget {
  const _Mark({required this.link});

  final SocialLink link;

  @override
  Widget build(BuildContext context) {
    switch (link.name) {
      case 'Facebook':
        return Icon(Icons.facebook, size: 18, color: link.colour);
      case 'Instagram':
        return _InstagramGlyph(colour: link.colour);
      default:
        return Icon(Icons.music_note_rounded, size: 18, color: link.colour);
    }
  }
}

class _InstagramGlyph extends StatelessWidget {
  const _InstagramGlyph({required this.colour});

  final Color colour;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 18,
      height: 18,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            decoration: BoxDecoration(
              border: Border.all(color: colour, width: 1.6),
              borderRadius: BorderRadius.circular(5.5),
            ),
          ),
          Container(
            width: 7.5,
            height: 7.5,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: colour, width: 1.6),
            ),
          ),
          Positioned(
            top: 2.6,
            right: 2.6,
            child: Container(
              width: 2.2,
              height: 2.2,
              decoration: BoxDecoration(shape: BoxShape.circle, color: colour),
            ),
          ),
        ],
      ),
    );
  }
}
