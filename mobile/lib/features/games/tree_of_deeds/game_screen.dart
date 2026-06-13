/// Tree of Deeds Game Screen — P1.4 Improved (شجرة الأخلاق 🌳).
library;

import 'package:flutter/material.dart';
import 'package:flame/game.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import 'tree_of_deeds_game.dart';
import '../shared/game_utils.dart';

class TreeOfDeedsGameScreen extends ConsumerStatefulWidget {
  const TreeOfDeedsGameScreen({super.key});

  @override
  ConsumerState<TreeOfDeedsGameScreen> createState() => _TreeOfDeedsGameScreenState();
}

class _TreeOfDeedsGameScreenState extends ConsumerState<TreeOfDeedsGameScreen> {
  GameProgress? _progress;
  int _selectedLevel = 1;
  bool _isGameOver = false;
  int _finalScore = 0;
  bool _levelCompleted = false;

  @override
  void initState() {
    super.initState();
    _loadProgress();
  }

  Future<void> _loadProgress() async {
    final prefs = await SharedPreferences.getInstance();
    final json = prefs.getString('game_progress_tree_of_deeds');
    if (json != null) {
      setState(() => _progress = GameProgress.fromJson(Map<String, dynamic>.from(
        Map<String, dynamic>.from(json as Map),
      )));
      _selectedLevel = _progress!.highestLevel;
    }
  }

  Future<void> _saveProgress() async {
    if (_progress != null) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('game_progress_tree_of_deeds',
        _progress!.toJson().toString());
    }
  }

  void _initGame(int level) {
    final gameConfig = TreeOfDeedsConfig.forLevel(level);
    setState(() {
      _isGameOver = false;
      _finalScore = 0;
      _levelCompleted = false;
      _selectedLevel = level;
    });

    _game = TreeOfDeedsGame(
      gameConfig: gameConfig,
      onGameComplete: (score, completed, playedLevel) {
        _handleGameComplete(score, completed, level);
      },
    );
  }

  TreeOfDeedsGame? _game;

  void _handleGameComplete(int score, bool completed, int level) {
    setState(() {
      _isGameOver = true;
      _finalScore = score;
      _levelCompleted = completed;
    });

    _progress ??= GameProgress(gameId: 4);
    _progress!.recordGame(level, score, completed);
    _saveProgress();

    if (completed && level < 10) {
      _showLevelCompleteDialog(score, level);
    } else {
      _showGameOverDialog(score, completed, level);
    }
  }

  void _showGameOverDialog(int score, bool completed, int level) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF422006),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Dt.rCard)),
        title: Row(
          children: [
            Icon(completed ? Icons.check_circle : Icons.close,
                color: completed ? AppTheme.success : AppTheme.dangerFg, size: 28),
            const SizedBox(width: 8),
            Text(
              completed ? 'تم إكمال المستوى!' : 'انتهت اللعبة',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              completed
                  ? 'مستوى $level مكتمل! شجرتك نمت بأعمالك الصالحة.'
                  : 'انتهت المحاولات. تذكر: الأعمال السيئة تضر بالشجرة، والأعمال الصالحة تنميها.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white70, fontSize: 16, height: 1.5),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFF59E0B).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFF59E0B).withValues(alpha: 0.3)),
              ),
              child: Column(
                children: [
                  Text('الحسنات: $score',
                      style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white)),
                  Text('المستوى: $level / 10',
                      style: TextStyle(fontSize: 14, color: Colors.grey[400])),
                ],
              ),
            ),
          ],
        ),
        actions: [
          if (completed && level < 10)
            TextButton(
              onPressed: () {
                Navigator.pop(ctx);
                _initGame(level + 1);
              },
              child: const Text('المستوى التالي ▶', style: TextStyle(fontSize: 16, color: Color(0xFFF59E0B))),
            ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              _initGame(level);
            },
            child: const Text('إعادة اللعب', style: TextStyle(fontSize: 16)),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              setState(() {
                _isGameOver = false;
                _game = null;
              });
            },
            child: const Text('العودة', style: TextStyle(fontSize: 16)),
          ),
        ],
      ),
    );
  }

  void _showLevelCompleteDialog(int score, int level) {
    _showGameOverDialog(score, true, level);
  }

  @override
  Widget build(BuildContext context) {
    final theme = GameTheme.treeOfDeeds;

    // Show the running game as soon as a level is picked; the level grid
    // only renders when no game is active.
    if (_game != null) {
      return Scaffold(
        backgroundColor: theme.backgroundColor,
        body: GameWidget(game: _game!),
      );
    }

    return Scaffold(
      backgroundColor: theme.backgroundColor,
      appBar: AppBar(
        title: Text(theme.name, style: TextStyle(color: theme.textColor)),
        backgroundColor: const Color(0xFFD97706),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Card(
                color: const Color(0xFFF5F5DC),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(Dt.rCard),
                  side: BorderSide(color: theme.accentColor.withValues(alpha: 0.3)),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Text('🌳', style: TextStyle(fontSize: 32)),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(theme.name,
                                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: theme.textColor)),
                                const SizedBox(height: 4),
                                Text(
                                  'نمّ شجرتك بالأعمال الصالحة! اسقط النجوم والأعمال الصالحة على الشجرة لتنميها. '
                                  'اضغط على السحب السوداء (الأعمال السيئة) لتدميرها قبل أن تصل للشجرة. '
                                  'كل عمل صالح ينمي الشجرة ويزيد درجاتك.',
                                  style: const TextStyle(color: Color(0xFF78350F), height: 1.5),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: const Color(0xFF22C55E).withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text('⭐🌟🌈 ', style: TextStyle(fontSize: 14)),
                                Text('عمل صالح - اسقط', style: TextStyle(fontSize: 14, color: Color(0xFF22C55E), fontWeight: FontWeight.w600)),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: const Color(0xFFEF4444).withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text('☁️🌪️😡 ', style: TextStyle(fontSize: 14)),
                                Text('عمل سيء - اضغط لتدمير', style: TextStyle(fontSize: 14, color: Color(0xFFEF4444), fontWeight: FontWeight.w600)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 24),

              if (_progress != null) ...[
                Text('تقدمك', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: theme.textColor)),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: _ProgressStat(
                        label: 'أعلى مستوى',
                        value: '${_progress!.highestLevel} / 10',
                        color: theme.accentColor,
                        icon: Icons.star,
                      ),
                    ),
                    Expanded(
                      child: _ProgressStat(
                        label: 'إجمالي الحسنات',
                        value: _progress!.totalScore.toString(),
                        color: const Color(0xFFF59E0B),
                        icon: Icons.eco,
                      ),
                    ),
                    Expanded(
                      child: _ProgressStat(
                        label: 'المحاور المكتملة',
                        value: '${_progress!.gamesPlayed}',
                        color: const Color(0xFF22C55E),
                        icon: Icons.check_circle,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
              ],

              Text('اختر المستوى', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: theme.textColor)),
              const SizedBox(height: 12),
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 5,
                  childAspectRatio: 1.0,
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                ),
                itemCount: 10,
                itemBuilder: (context, index) {
                  final level = index + 1;
                  final unlocked = _progress == null ? level == 1 : level <= _progress!.highestLevel;
                  final completed = _progress?.levelBestScores.containsKey(level) ?? false;
                  final bestScore = _progress?.levelBestScores[level] ?? 0;

                  return _LevelCard(
                    level: level,
                    unlocked: unlocked,
                    completed: completed,
                    bestScore: bestScore,
                    onTap: unlocked ? () => _initGame(level) : null,
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProgressStat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  final IconData icon;

  const _ProgressStat({
    required this.label,
    required this.value,
    required this.color,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xFFFEF3C7),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(Dt.rCard),
        side: BorderSide(color: color.withValues(alpha: 0.3)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 8),
            Text(value, style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: color)),
            Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[700])),
          ],
        ),
      ),
    );
  }
}

class _LevelCard extends StatelessWidget {
  final int level;
  final bool unlocked;
  final bool completed;
  final int bestScore;
  final VoidCallback? onTap;

  const _LevelCard({
    required this.level,
    required this.unlocked,
    required this.completed,
    required this.bestScore,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return BouncyTap(
      onTap: onTap,
      child: Card(
        color: unlocked ? const Color(0xFFFEF3C7) : const Color(0xFFFDE68A),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Dt.rCard),
          side: BorderSide(
            color: unlocked
                ? (completed ? const Color(0xFF10B981) : const Color(0xFFF59E0B)).withValues(alpha: 0.5)
                : const Color(0xFFD97706),
            width: 2),
        ),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(Dt.rCard),
          child: Stack(
            children: [
              Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text('$level', style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: unlocked ? const Color(0xFF422006) : Colors.grey[600],
                    )),
                    const SizedBox(height: 4),
                    if (unlocked) ...[
                      Text('أفضل: $bestScore',
                          style: TextStyle(fontSize: 11, color: Colors.grey[700])),
                    ],
                  ],
                ),
              ),
              if (completed)
                const Positioned(
                  top: 4,
                  right: 4,
                  child: Icon(Icons.check_circle, color: Color(0xFF10B981), size: 20),
                ),
              if (!unlocked)
                const Positioned(
                  top: 4,
                  right: 4,
                  child: Icon(Icons.lock, color: Color(0xFFB45309), size: 20),
                ),
            ],
          ),
        ),
      ),
    );
  }
}