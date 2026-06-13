import 'package:flame/game.dart';
import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import 'emotion_maze_game.dart';

class EmotionMazeGameScreen extends StatefulWidget {
  const EmotionMazeGameScreen({super.key});

  @override
  State<EmotionMazeGameScreen> createState() => _EmotionMazeGameScreenState();
}

class _EmotionMazeGameScreenState extends State<EmotionMazeGameScreen> {
  EmotionMazeGame? _game;
  bool _isGameOver = false;
  int _finalScore = 0;

  @override
  void initState() {
    super.initState();
    _initGame();
  }

  void _initGame() {
    setState(() {
      _isGameOver = false;
      _finalScore = 0;
      _game = EmotionMazeGame(
        onGameOver: (score) {
          setState(() {
            _isGameOver = true;
            _finalScore = score;
          });
        },
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1E293B),
      appBar: AppBar(
        title: const Text('متاهة المشاعر 🧠', style: TextStyle(color: Colors.white)),
        backgroundColor: const Color(0xFF0F172A),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: Stack(
        children: [
          if (_game != null)
            GameWidget(
              game: _game!,
            ),
          
          if (_isGameOver)
            Container(
              color: Colors.black54,
              child: Center(
                child: Container(
                  margin: const EdgeInsets.symmetric(horizontal: 24),
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(Dt.rCard),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        'رد فعل خاطئ! 🛑',
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.dangerFg,
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'لقد اخترت الباب الذي يمثل رد الفعل السلبي (الصراخ أو التكسير).\nتذكر دائماً أن تأخذ نفساً عميقاً وتختار الباب الإيجابي لتعبر بأمان!',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 16, height: 1.5),
                      ),
                      const SizedBox(height: 20),
                      Text(
                        'الأبواب التي تجاوزتها: $_finalScore',
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.primary,
                        ),
                      ),
                      const SizedBox(height: 24),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          Expanded(
                            child: BouncyButton(
                              label: 'العودة',
                              color: AppTheme.surfaceAlt,
                              onTap: () => Navigator.of(context).pop(),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: BouncyButton(
                              label: 'إعادة اللعب',
                              color: AppTheme.primary,
                              onTap: _initGame,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
