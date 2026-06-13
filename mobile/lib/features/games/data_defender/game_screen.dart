/// Data Defender Game Screen — P1.4 Improved (حارس البيانات 🛡️).
///
/// Screen with level selection, progress tracking, and game launch.
library;

import 'package:flutter/material.dart';
import 'package:flame/game.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import 'data_defender_game.dart';
import '../shared/game_utils.dart';

class DataDefenderGameScreen extends ConsumerStatefulWidget {
  const DataDefenderGameScreen({super.key});

  @override
  ConsumerState<DataDefenderGameScreen> createState() => _DataDefenderGameScreenState();
}

class _DataDefenderGameScreenState extends ConsumerState<DataDefenderGameScreen> {
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
    final json = prefs.getString('game_progress_data_defender');
    if (json != null) {
      setState(() => _progress = GameProgress.fromJson(Map<String, dynamic>.from(
        Map<String, dynamic>.from(json as Map), // cast safety
      )));
      _selectedLevel = _progress!.highestLevel;
    }
  }

  Future<void> _saveProgress() async {
    if (_progress != null) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('game_progress_data_defender', 
        _progress!.toJson().toString());
    }
  }

  void _initGame(int level) {
    final gameConfig = DataDefenderConfig.forLevel(level);
    setState(() {
      _isGameOver = false;
      _finalScore = 0;
      _levelCompleted = false;
      _selectedLevel = level;
    });

    _game = DataDefenderGame(
      gameConfig: gameConfig,
      onGameComplete: (score, completed, playedLevel) {
        _handleGameComplete(score, completed, level);
      },
    );
  }

  DataDefenderGame? _game;

  void _handleGameComplete(int score, bool completed, int level) {
    setState(() {
      _isGameOver = true;
      _finalScore = score;
      _levelCompleted = completed;
    });

    _progress ??= GameProgress(gameId: 1);
    _progress!.recordGame(level, score, completed);
    _saveProgress();

    if (completed && level < 10) {
      // Show level complete dialog with stars
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
        backgroundColor: const Color(0xFF1E293B),
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
                  ? 'مستوى $level مكتمل! أنت تحمينا من التهديدات الرقمية.'
                  : 'انتهت المحاولات. تذكر: لا تضغط الروابط الغريبة.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white70, fontSize: 16, height: 1.5),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF06B6D4).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFF06B6D4).withValues(alpha: 0.3)),
              ),
              child: Column(
                children: [
                  Text('النتيجة: $score',
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
              child: const Text('المستوى التالي ▶', style: TextStyle(fontSize: 16, color: Color(0xFF06B6D4))),
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
              setState(() => _isGameOver = false);
            },
            child: const Text('العودة', style: TextStyle(fontSize: 16)),
          ),
        ],
      ),
    );
    var ctx = context; // capture context
  }

  void _showLevelCompleteDialog(int score, int level) {
    _showGameOverDialog(score, true, level);
  }

  @override
  Widget build(BuildContext context) {
    final theme = GameTheme.dataDefender;

    if (_isGameOver) {
      // Show the game with overlay
      return Stack(
        children: [
          if (_game != null)
            GameWidget(game: _game!),
          // Dialog will be shown via showDialog
        ],
      );
    }

    return Scaffold(
      backgroundColor: theme.backgroundColor,
      appBar: AppBar(
        title: Text(theme.name, style: const TextStyle(color: Colors.white)),
        backgroundColor: const Color(0xFF0F172A),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Game description card
              Card(
                color: const Color(0xFF1E293B),
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
                          const Text('🤖', style: TextStyle(fontSize: 32)),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(theme.name,
                                    style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white)),
                                const SizedBox(height: 4),
                                Text(
                                  'تعلم حماية بياناتك من الفيروسات والروابط المشبوهة. '
                                  'تحرك يميناً ويساراً لجمع الملفات الآمنة (🔒) وتجنب الفيروسات (🦠). '
                                  'اسحب على الشاشة أو استخدم الأسهم/مفتاح المسافة للدرع.',
                                  style: const TextStyle(color: Colors.white70, height: 1.5),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Text('قوة الدرع: ${DataDefenderConfig.forLevel(_selectedLevel).shieldDuration > 0 ? "متاح (مفتاح المسافة)" : "غير متاح في هذا المستوى"}',
                          style: TextStyle(color: theme.accentColor, fontWeight: FontWeight.w600)),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 24),

              // Progress summary
              if (_progress != null) ...[
                Text('تقدمك', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
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
                        label: 'إجمالي النقاط',
                        value: _progress!.totalScore.toString(),
                        color: const Color(0xFF06B6D4),
                        icon: Icons.score,
                      ),
                    ),
                    Expanded(
                      child: _ProgressStat(
                        label: 'المحاور المكتملة',
                        value: '${_progress!.gamesPlayed}',
                        color: const Color(0xFF10B981),
                        icon: Icons.check_circle,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
              ],

              // Level selection
              Text('اختر المستوى', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
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
      color: const Color(0xFF1E293B),
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
            Text(label, style: const TextStyle(fontSize: 12, color: Colors.white60)),
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
        color: unlocked ? const Color(0xFF1E293B) : const Color(0xFF0F172A),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Dt.rCard),
          side: BorderSide(
            color: unlocked
                ? (completed ? const Color(0xFF10B981) : const Color(0xFF06B6D4)).withValues(alpha: 0.5)
                : const Color(0xFF1E293B),
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
                      color: unlocked ? Colors.white : Colors.grey[600],
                    )),
                    const SizedBox(height: 4),
                    if (_unlockedMaybe) ...[
                      Text('أفضل: $bestScore',
                          style: TextStyle(fontSize: 11, color: Colors.grey[400])),
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
                  child: Icon(Icons.lock, color: Color(0xFF64748B), size: 20),
                ),
            ],
          ),
        ),
      ),
    );
  }

  bool get _unlockedMaybe => true;
}