import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../theme/design_tokens.dart';
import 'bouncy_button.dart';

/// Friendly empty/error state: big emoji, bold title, soft subtitle,
/// optional action button. Replaces the bare icon+text placeholders.
class EmptyState extends StatelessWidget {
  final String emoji;
  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  const EmptyState({
    super.key,
    required this.emoji,
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(emoji, style: const TextStyle(fontSize: 72))
                .animate()
                .scale(
                  begin: const Offset(.6, .6),
                  duration: Dt.slow,
                  curve: Curves.easeOutBack,
                ),
            const SizedBox(height: 16),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
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
                style: const TextStyle(
                  fontSize: 14,
                  color: Dt.inkSoft,
                  height: 1.5,
                ),
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
}
