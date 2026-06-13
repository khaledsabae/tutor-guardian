import 'package:flame/game.dart';
import 'package:flutter/material.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import 'healthy_hero_game.dart';

class HealthyHeroGameScreen extends StatefulWidget {
  const HealthyHeroGameScreen({super.key});

  @override
  State<HealthyHeroGameScreen> createState() => _HealthyHeroGameScreenState();
}

class _HealthyHeroGameScreenState extends State<HealthyHeroGameScreen> {
  HealthyHeroGame? _game;
  bool _isGameOver = false;
  bool _started = false;
  int _finalScore = 0;

  @override
  void initState() {
    super.initState();
    _initGame();
  }

  void _initGame() {
    setState(() {
      _isGameOver = false;
      _started = false;
      _finalScore = 0;
      _game = HealthyHeroGame(
        onGameOver: (score) {
          setState(() {
            _isGameOver = true;
            _finalScore = score;
          });
        },
      );
    });
    // Hold the simulation on the intro until the player taps "ابدأ".
    WidgetsBinding.instance.addPostFrameCallback((_) => _game?.pauseEngine());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF38BDF8),
      appBar: AppBar(
        title: const Text('رحلة البطل الصحي 🩺', style: TextStyle(color: Colors.white)),
        backgroundColor: const Color(0xFF0369A1),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: Stack(
        children: [
          if (_game != null) GameWidget(game: _game!),

          // How-to-play / learning goal overlay.
          if (!_started && !_isGameOver)
            _IntroOverlay(
              onStart: () {
                _game?.resumeEngine();
                setState(() => _started = true);
              },
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
                        'احذر! 👾',
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.dangerFg,
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'لقد اصطدمت بوحش السكريات والسهر!\nتذكر أن الأكل الصحي والنوم المبكر يمنحاك طاقة للقفز عالياً.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 16, height: 1.5),
                      ),
                      const SizedBox(height: 20),
                      Text(
                        'النتيجة: $_finalScore',
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

class _IntroOverlay extends StatelessWidget {
  const _IntroOverlay({required this.onStart});
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Container(
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
              const Text('🦸🍎', style: TextStyle(fontSize: 44)),
              const SizedBox(height: 12),
              const Text(
                'رحلة البطل الصحي',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 10),
              const Text(
                'اضغط على الشاشة ليقفز البطل!\n'
                'اجمع 🍎🥦🥕💧 الطعام الصحي،\n'
                'واقفز فوق 🍬🍔🥤 الحلويات والوجبات السريعة.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 15, height: 1.7),
              ),
              const SizedBox(height: 20),
              BouncyButton(label: 'ابدأ اللعب 🎮', onTap: onStart),
            ],
          ),
        ),
      ),
    );
  }
}
