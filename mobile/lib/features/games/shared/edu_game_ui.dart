/// Shared level selection screen, pause overlay, and result dialog for the
/// redesigned educational mini-games.
library;

import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import 'edu_game_models.dart';

/// Generic level selection / game lobby for any EduGameTheme.
class EduLevelSelectionScreen extends StatelessWidget {
  final EduGameTheme theme;
  final EduGameProgress progress;
  final void Function(int level) onPlay;
  final VoidCallback onBack;

  const EduLevelSelectionScreen({
    super.key,
    required this.theme,
    required this.progress,
    required this.onPlay,
    required this.onBack,
  });

  @override
  Widget build(BuildContext context) {
    final highest = progress.highestUnlockedLevel;

    return Scaffold(
      backgroundColor: theme.backgroundColor,
      appBar: AppBar(
        backgroundColor: theme.surfaceColor,
        foregroundColor: theme.textColor,
        title: Text(theme.name),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: onBack,
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _HeroCard(theme: theme, progress: progress),
              const SizedBox(height: 20),
              Text(
                'اختر المستوى',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: theme.textColor,
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: GridView.builder(
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                    childAspectRatio: 0.9,
                  ),
                  itemCount: 10,
                  itemBuilder: (context, index) {
                    final level = index + 1;
                    final levelProgress = progress.levels[level];
                    final unlocked = level <= highest;
                    final stars = levelProgress?.bestStars ?? 0;
                    return _LevelCard(
                      theme: theme,
                      level: level,
                      unlocked: unlocked,
                      stars: stars,
                      bestScore: levelProgress?.bestScore ?? 0,
                      onTap: unlocked ? () => onPlay(level) : null,
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HeroCard extends StatelessWidget {
  final EduGameTheme theme;
  final EduGameProgress progress;
  const _HeroCard({required this.theme, required this.progress});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: AlignmentDirectional.topStart,
          end: AlignmentDirectional.bottomEnd,
          colors: [theme.accentColor.withValues(alpha: 0.25), theme.surfaceColor],
        ),
borderRadius: BorderRadius.circular(Dt.rCard),
        border: Border.all(color: theme.accentColor.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Text(theme.heroEmoji, style: const TextStyle(fontSize: 56)),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  theme.name,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: theme.textColor,
                        fontWeight: FontWeight.bold,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  theme.description,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: theme.textColor.withValues(alpha: 0.8),
                        height: 1.4,
                      ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    _MiniStat(label: 'المحاولات', value: '${progress.gamesPlayed}'),
                    const SizedBox(width: 16),
                    _MiniStat(label: 'النقاط', value: '${progress.totalScore}'),
                    const SizedBox(width: 16),
                    _MiniStat(
                      label: 'النجوم',
                      value: '${_totalStars(progress)}',
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  static int _totalStars(EduGameProgress progress) {
    return progress.levels.values.fold(
      0,
      (sum, level) => sum + level.bestStars,
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String label;
  final String value;
  const _MiniStat({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.bold,
            fontSize: 16,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.7),
            fontSize: 11,
          ),
        ),
      ],
    );
  }
}

class _LevelCard extends StatelessWidget {
  final EduGameTheme theme;
  final int level;
  final bool unlocked;
  final int stars;
  final int bestScore;
  final VoidCallback? onTap;

  const _LevelCard({
    required this.theme,
    required this.level,
    required this.unlocked,
    required this.stars,
    required this.bestScore,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final tier = GameTier.values[min((level - 1) ~/ 2, GameTier.values.length - 1)];

    return Opacity(
      opacity: unlocked ? 1.0 : 0.45,
      child: Material(
        color: theme.surfaceColor,
        borderRadius: BorderRadius.circular(Dt.rCard),
        child: InkWell(
          borderRadius: BorderRadius.circular(Dt.rCard),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(Dt.rCard),
              border: Border.all(
                color: unlocked ? tier.color.withValues(alpha: 0.5) : Colors.white24,
              ),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  '$level',
                  style: TextStyle(
                    color: unlocked ? theme.textColor : Colors.white38,
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  tier.label,
                  style: TextStyle(
                    color: unlocked ? tier.color : Colors.white38,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    for (int i = 0; i < 3; i++)
                      Icon(
                        i < stars ? Icons.star : Icons.star_border,
                        color: i < stars ? Colors.amber : Colors.white30,
                        size: 16,
                      ),
                  ],
                ),
                if (bestScore > 0) ...[
                  const SizedBox(height: 4),
                  Text(
                    'أفضل: $bestScore',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.6),
                      fontSize: 10,
                    ),
                  ),
                ],
                if (!unlocked)
                  const Icon(Icons.lock, color: Colors.white38, size: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Pause overlay with resume / restart / quit actions.
class EduPauseOverlay extends StatelessWidget {
  final EduGameTheme theme;
  final VoidCallback onResume;
  final VoidCallback onRestart;
  final VoidCallback onQuit;

  const EduPauseOverlay({
    super.key,
    required this.theme,
    required this.onResume,
    required this.onRestart,
    required this.onQuit,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black.withValues(alpha: 0.7),
      child: Center(
        child: Container(
          margin: const EdgeInsets.all(32),
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: theme.surfaceColor,
            borderRadius: BorderRadius.circular(Dt.rCard),
            border: Border.all(color: theme.accentColor.withValues(alpha: 0.3)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '⏸️ توقفت',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: theme.textColor,
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 24),
              _PauseButton(
                theme: theme,
                icon: Icons.play_arrow,
                label: 'استئناف',
                onTap: onResume,
              ),
              const SizedBox(height: 12),
              _PauseButton(
                theme: theme,
                icon: Icons.replay,
                label: 'إعادة المستوى',
                onTap: onRestart,
              ),
              const SizedBox(height: 12),
              _PauseButton(
                theme: theme,
                icon: Icons.exit_to_app,
                label: 'خروج',
                isDestructive: true,
                onTap: onQuit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PauseButton extends StatelessWidget {
  final EduGameTheme theme;
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool isDestructive;

  const _PauseButton({
    required this.theme,
    required this.icon,
    required this.label,
    required this.onTap,
    this.isDestructive = false,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        style: ElevatedButton.styleFrom(
          backgroundColor: isDestructive
              ? AppTheme.dangerFg
              : theme.accentColor.withValues(alpha: 0.15),
          foregroundColor: isDestructive ? Colors.white : theme.accentColor,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        icon: Icon(icon),
        label: Text(label, style: const TextStyle(fontSize: 16)),
        onPressed: onTap,
      ),
    );
  }
}

/// Result dialog shown after a game session.
class EduResultDialog extends StatelessWidget {
  final EduGameTheme theme;
  final EduGameResult result;
  final VoidCallback? onNext;
  final VoidCallback onReplay;
  final VoidCallback onExit;

  const EduResultDialog({
    super.key,
    required this.theme,
    required this.result,
    this.onNext,
    required this.onReplay,
    required this.onExit,
  });

  @override
  Widget build(BuildContext context) {
    final hasNext = onNext != null && result.completed;

    return PopScope(
      canPop: false,
      child: AlertDialog(
        backgroundColor: theme.surfaceColor,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Dt.rCard)),
        title: Row(
          children: [
            Icon(
              result.completed ? Icons.check_circle : Icons.close,
              color: result.completed ? AppTheme.success : AppTheme.dangerFg,
              size: 28,
            ),
            const SizedBox(width: 8),
            Text(
              result.completed ? 'مستوى مكتمل! 🎉' : 'انتهت اللعبة',
              style: TextStyle(
                color: theme.textColor,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (int i = 0; i < 3; i++)
                  Icon(
                    i < result.stars ? Icons.star : Icons.star_border,
                    color: i < result.stars ? Colors.amber : Colors.white30,
                    size: 36,
                  )
                      .animate()
                      .scale(delay: Duration(milliseconds: i * 150), duration: 300.ms),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              '${result.correctAnswers} / ${result.totalQuestions} إجابات صحيحة',
              style: TextStyle(color: theme.textColor, fontSize: 18),
            ),
            const SizedBox(height: 8),
            Text(
              'النقاط: ${result.score}',
              style: TextStyle(
                color: theme.accentColor,
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            if (!result.completed)
              Text(
                'حاول تاني! كل محاولة بتعلّمك أكتر.',
                textAlign: TextAlign.center,
                style: TextStyle(color: theme.textColor.withValues(alpha: 0.7)),
              ),
          ],
        ),
        actions: [
          if (hasNext)
            TextButton(
              onPressed: onNext,
              child: Text('المستوى التالي ▶', style: TextStyle(color: theme.accentColor, fontSize: 16)),
            ),
          TextButton(
            onPressed: onReplay,
            child: Text('إعادة', style: TextStyle(color: theme.textColor, fontSize: 16)),
          ),
          TextButton(
            onPressed: onExit,
            child: const Text('خروج', style: TextStyle(fontSize: 16)),
          ),
        ],
      ),
    );
  }
}

/// Helper to show the result dialog from a game runner.
Future<void> showEduResultDialog({
  required BuildContext context,
  required EduGameTheme theme,
  required EduGameResult result,
  VoidCallback? onNext,
  required VoidCallback onReplay,
  required VoidCallback onExit,
}) {
  return showDialog(
    context: context,
    barrierDismissible: false,
    builder: (_) => EduResultDialog(
      theme: theme,
      result: result,
      onNext: onNext,
      onReplay: onReplay,
      onExit: onExit,
    ),
  );
}

/// Short haptic feedback helper.
void lightHaptic() => HapticFeedback.lightImpact();
void mediumHaptic() => HapticFeedback.mediumImpact();
void errorHaptic() => HapticFeedback.heavyImpact();
