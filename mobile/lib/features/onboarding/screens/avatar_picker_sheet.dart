/// Avatar emoji picker — modal bottom sheet.
///
/// Shows a grid of curated, child-friendly emojis grouped by theme.
/// Tapping an emoji returns it via [Navigator.pop].
library;

import 'package:flutter/material.dart';

import '../../../theme/app_theme.dart';

const List<String> kAvatarEmojis = [
  // Faces
  '👧', '👦', '👶', '🧒',
  '🧒🏽', '👧🏽', '🧒🏼', '👧🏼',
  '🧒🏿', '👧🏿',
  // Family / roles
  '👨‍👩‍👧', '👨‍👩‍👦', '👨‍👩‍👧‍👦', '👨‍👩‍👧‍👦‍👶',
  // Animals
  '🐱', '🐶', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯', '🦁', '🐮', '🐷', '🐸', '🐵', '🐔', '🦄',
  // Nature
  '🌸', '🌺', '🌻', '🌷', '🌹', '🌳', '🌴', '⭐', '🌙', '☀️', '🌈', '⚡',
  // Activities
  '📚', '✏️', '🎨', '🎵', '⚽', '🏀', '🧩', '🎮',
];

class AvatarPickerSheet extends StatelessWidget {
  const AvatarPickerSheet({super.key, required this.initial});
  final String? initial;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(Icons.emoji_emotions_outlined,
                    color: AppTheme.primary),
                const SizedBox(width: 8),
                Text(
                  'اختر صورة طفلك',
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                const Spacer(),
                IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Expanded(
              child: GridView.builder(
                itemCount: kAvatarEmojis.length,
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 6,
                  crossAxisSpacing: 6,
                  mainAxisSpacing: 6,
                ),
                itemBuilder: (context, i) {
                  final emoji = kAvatarEmojis[i];
                  final isSelected = emoji == initial;
                  return InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: () => Navigator.of(context).pop(emoji),
                    child: Container(
                      decoration: BoxDecoration(
                        color: isSelected
                            ? AppTheme.primary.withValues(alpha: 0.15)
                            : AppTheme.surfaceAlt,
                        borderRadius: BorderRadius.circular(12),
                        border: isSelected
                            ? Border.all(
                                color: AppTheme.primary, width: 2)
                            : null,
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        emoji,
                        style: const TextStyle(fontSize: 28),
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
