import 'dart:math' as math;

import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:lottie/lottie.dart';

import '../../theme/design_tokens.dart';
import 'bouncy_button.dart';

/// Full-screen celebration: confetti burst + scale-in dialog with a big
/// emoji. The reward moment for completing a lesson / acing a quiz.
Future<void> showCelebration(
  BuildContext context, {
  required String emoji,
  required String title,
  required String message,
  String buttonLabel = 'متابعة',
  String? imageAsset,
  Future<void> Function()? onShare,
  String shareLabel = 'شارك هذه اللحظة 🤍',
}) {
  return showGeneralDialog<void>(
    context: context,
    barrierColor: Colors.black54,
    barrierDismissible: false,
    barrierLabel: title,
    transitionDuration: Dt.base,
    pageBuilder: (dialogContext, _, __) => _CelebrationDialog(
      emoji: emoji,
      title: title,
      message: message,
      buttonLabel: buttonLabel,
      imageAsset: imageAsset,
      onShare: onShare,
      shareLabel: shareLabel,
    ),
    transitionBuilder: (_, anim, __, child) => ScaleTransition(
      scale: CurvedAnimation(parent: anim, curve: Curves.easeOutBack),
      child: FadeTransition(opacity: anim, child: child),
    ),
  );
}

class _CelebrationDialog extends StatefulWidget {
  final String emoji;
  final String title;
  final String message;
  final String buttonLabel;
  final String? imageAsset;
  final Future<void> Function()? onShare;
  final String shareLabel;

  const _CelebrationDialog({
    required this.emoji,
    required this.title,
    required this.message,
    required this.buttonLabel,
    this.imageAsset,
    this.onShare,
    this.shareLabel = 'شارك هذه اللحظة 🤍',
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
    _confetti.play();
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
            backgroundColor: Colors.white,
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
                              errorBuilder: (_, __, ___) => Text(
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
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      color: Dt.ink,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    widget.message,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 15,
                      color: Dt.inkSoft,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 24),
                  if (widget.onShare != null) ...[
                    BouncyButton(
                      label: _sharing ? 'جاري التحضير…' : widget.shareLabel,
                      color: Dt.primary,
                      onTap: _sharing ? () {} : _handleShare,
                    ),
                    const SizedBox(height: 10),
                  ],
                  BouncyButton(
                    label: widget.buttonLabel,
                    color: Dt.accent,
                    onTap: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
            ),
          ),
        ),
        // Burst from the top center, raining over the dialog.
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
            colors: const [
              Dt.primary,
              Dt.accent,
              Color(0xFF8B5CF6),
              Color(0xFFFB7185),
              Dt.success,
            ],
          ),
        ),
        // Brand-aligned gentle Lottie stars behind the dialog.
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
