import 'dart:math' as math;

import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:lottie/lottie.dart';

import '../../core/motion.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/design_tokens.dart';
import 'bouncy_button.dart';
import 'package:almorabbi/core/haptics.dart';

/// How loud a celebration is («نور والقناديل» phase 1 — مستويات الاحتفال).
///
/// One celebration API, two volumes, so that a quiet "well done" and a full
/// milestone feel like the same product deciding how big this moment is —
/// not like two screens that were built separately.
enum CelebrationTier {
  /// Confetti + Lottie stars + success haptic. Reserved for the moments the
  /// parent earns rarely: finishing a lesson, a journey milestone.
  milestone,

  /// Dialog + haptic only. The moment is acknowledged, not staged — quiz
  /// results, follow-up answers, child-mode streaks.
  quiet,
}

/// A badge surfaced inside a celebration dialog (e.g. «أول خطوة 🌱» on the
/// very first lesson) instead of a second, silent window.
typedef CelebrationBadge = ({String emoji, String title});

/// Full-screen celebration: confetti burst + scale-in dialog with a big
/// emoji. The reward moment for completing a lesson / acing a quiz.
Future<void> showCelebration(
  BuildContext context, {
  required String emoji,
  required String title,
  required String message,
  String? buttonLabel,
  String? imageAsset,
  Future<void> Function()? onShare,
  String? shareLabel,
  CelebrationTier tier = CelebrationTier.milestone,
  CelebrationBadge? badge,
}) {
  // Milestone = success + confetti, once (UX_UI_ROADMAP §4.2). Covers lesson
  // completion, journey milestones and habit streaks in one place.
  Haptics.success();
  // Reduced motion (core/motion.dart): the dialog itself is information, the
  // confetti burst and star rain are decoration — decoration is what the
  // setting asks to drop. The entrance transitions collapse on their own
  // (Flutter runs controllers at 5% under the setting).
  final effects =
      tier == CelebrationTier.milestone && !reduceMotion(context);
  return showGeneralDialog<void>(
    context: context,
    barrierColor: Colors.black54,
    barrierDismissible: false,
    barrierLabel: title,
    transitionDuration: Dt.base,
    pageBuilder: (dialogContext, _, _) => _CelebrationDialog(
      emoji: emoji,
      title: title,
      message: message,
      buttonLabel: buttonLabel,
      imageAsset: imageAsset,
      onShare: onShare,
      shareLabel: shareLabel,
      effects: effects,
      badge: badge,
    ),
    transitionBuilder: (_, anim, _, child) => ScaleTransition(
      scale: CurvedAnimation(parent: anim, curve: Curves.easeOutBack),
      child: FadeTransition(opacity: anim, child: child),
    ),
  );
}

class _CelebrationDialog extends StatefulWidget {
  final String emoji;
  final String title;
  final String message;
  final String? buttonLabel;
  final String? imageAsset;
  final Future<void> Function()? onShare;
  final String? shareLabel;

  /// Whether the confetti burst and Lottie stars are shown at all (quiet
  /// tier, or the system asked for less motion).
  final bool effects;
  final CelebrationBadge? badge;

  const _CelebrationDialog({
    required this.emoji,
    required this.title,
    required this.message,
    required this.buttonLabel,
    this.imageAsset,
    this.onShare,
    this.shareLabel,
    required this.effects,
    this.badge,
  });

  @override
  State<_CelebrationDialog> createState() => _CelebrationDialogState();
}

class _CelebrationDialogState extends State<_CelebrationDialog> {
  late final ConfettiController _confetti =
      ConfettiController(duration: const Duration(milliseconds: 1500));
  bool _sharing = false;

  Future<void> _handleShare() async {
    if (_sharing) return;
    setState(() => _sharing = true);
    try {
      await widget.onShare!();
    } finally {
      if (mounted) setState(() => _sharing = false);
    }
  }

  @override
  void initState() {
    super.initState();
    if (widget.effects) _confetti.play();
  }

  @override
  void dispose() {
    _confetti.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.topCenter,
      children: [
        Center(
          child: Dialog(
            backgroundColor: Dt.surface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(Dt.rSheet),
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  (widget.imageAsset != null
                          ? Image.asset(
                              widget.imageAsset!,
                              width: 110,
                              height: 110,
                              fit: BoxFit.contain,
                              filterQuality: FilterQuality.medium,
                              errorBuilder: (_, _, _) => Text(
                                widget.emoji,
                                style: const TextStyle(fontSize: 80),
                              ),
                            )
                          : Text(widget.emoji,
                              style: const TextStyle(fontSize: 80)))
                      .animate()
                      .scale(
                        begin: const Offset(.3, .3),
                        duration: Dt.slow,
                        curve: Curves.easeOutBack,
                      ),
                  const SizedBox(height: 12),
                  Text(
                    widget.title,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      color: Dt.ink,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    widget.message,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 15,
                      color: Dt.inkSoft,
                      height: 1.5,
                    ),
                  ),
                  if (widget.badge != null) ...[
                    const SizedBox(height: 14),
                    // The badge earned *by this moment* rides inside it — one
                    // window, one story, instead of a credit the parent never
                    // sees (phase 1: هدية اليوم والشارات).
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: Dt.accent.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(Dt.rChip),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(widget.badge!.emoji,
                              style: const TextStyle(fontSize: 16)),
                          const SizedBox(width: 6),
                          Flexible(
                            child: Text(
                              widget.badge!.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w800,
                                color: Dt.ink,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 24),
                  if (widget.onShare != null) ...[
                    BouncyButton(
                      label: _sharing
                          ? AppLocalizations.of(context).sharePreparing
                          : widget.shareLabel ??
                              AppLocalizations.of(context).shareThisMoment,
                      color: Dt.primary,
                      onTap: _sharing ? () {} : _handleShare,
                    ),
                    const SizedBox(height: 10),
                  ],
                  BouncyButton(
                    label: widget.buttonLabel ??
                        AppLocalizations.of(context).continueBtn,
                    color: Dt.accent,
                    onTap: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
            ),
          ),
        ),
        // Burst from the top center, raining over the dialog.
        if (widget.effects)
          Padding(
            padding: const EdgeInsets.only(top: 120),
            child: ConfettiWidget(
              confettiController: _confetti,
              blastDirectionality: BlastDirectionality.explosive,
              blastDirection: math.pi / 2,
              emissionFrequency: 0.6,
              numberOfParticles: 30,
              maxBlastForce: 18,
              minBlastForce: 6,
              gravity: .3,
              colors: [
                Dt.primary,
                Dt.accent,
                Color(0xFF8B5CF6),
                Color(0xFFFB7185),
                Dt.success,
              ],
            ),
          ),
        // Brand-aligned gentle Lottie stars behind the dialog.
        if (widget.effects)
          Positioned.fill(
            child: IgnorePointer(
              child: Lottie.asset(
                'assets/animations/celebration_stars.json',
                fit: BoxFit.contain,
                repeat: false,
              ),
            ),
          ),
      ],
    );
  }
}
