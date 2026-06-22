/// Quiz Game Screen — "اختبر معلوماتك التربوية"
///
/// A gamified quiz experience with timer, score tracking,
/// and educational feedback after each question.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:lottie/lottie.dart';

import '../../../config/app_config.dart';
import '../../../core/analytics.dart';
import '../../share/share_service.dart';
import '../../share/shareable_moment_card.dart';

import '../../../theme/app_theme.dart';

class QuizGameScreen extends ConsumerStatefulWidget {
  const QuizGameScreen({super.key});

  @override
  ConsumerState<QuizGameScreen> createState() => _QuizGameScreenState();
}

class _QuizGameScreenState extends ConsumerState<QuizGameScreen> {
  List<Map<String, dynamic>> _questions = [];
  int _currentIndex = 0;
  int _score = 0;
  int _selectedAnswer = -1;
  bool _answered = false;
  bool _loading = true;
  String? _error;
  int _timeLeft = 15;
  Timer? _timer;
  bool _showResultsLottie = false;

  @override
  void initState() {
    super.initState();
    _fetchQuestions();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _fetchQuestions() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final uri =
          Uri.parse('${AppConfig.apiBaseUrl}/api/program/quiz?count=10');
      final resp = await http.get(uri).timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        final data = json.decode(resp.body) as Map<String, dynamic>;
        final list = (data['questions'] as List)
            .map((e) => e as Map<String, dynamic>)
            .toList();
        setState(() {
          _questions = list;
          _loading = false;
          _currentIndex = 0;
          _score = 0;
        });
        _startTimer();
      } else {
        setState(() {
          _error = 'خطأ في تحميل الأسئلة';
          _loading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'تعذر الاتصال بالخادم';
        _loading = false;
      });
    }
  }

  void _startTimer() {
    _timer?.cancel();
    setState(() => _timeLeft = 15);
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) {
        t.cancel();
        return;
      }
      if (_timeLeft <= 1) {
        t.cancel();
        if (!_answered) _onAnswer(-1); // time's up
      } else {
        setState(() => _timeLeft--);
      }
    });
  }

  void _onAnswer(int index) {
    if (_answered) return;
    _timer?.cancel();
    final correct = _questions[_currentIndex]['answer'] as int;
    setState(() {
      _selectedAnswer = index;
      _answered = true;
      if (index == correct) _score += 10;
    });
  }

  void _nextQuestion() {
    if (_currentIndex >= _questions.length - 1) {
      // Trigger brand-aligned celebration on the results screen.
      setState(() {
        _currentIndex = _questions.length;
        _showResultsLottie = true;
      });
      return;
    }
    setState(() {
      _currentIndex++;
      _selectedAnswer = -1;
      _answered = false;
    });
    _startTimer();
  }

  void _restart() {
    setState(() {
      _currentIndex = 0;
      _score = 0;
      _selectedAnswer = -1;
      _answered = false;
      _showResultsLottie = false;
    });
    _fetchQuestions();
  }

  // ── Domain label helpers ─────────────────────────────────────────────

  String _domainLabel(String d) {
    switch (d) {
      case 'islamic_parenting':
        return 'تربية إسلامية';
      case 'medical':
        return 'صحة';
      case 'cyber':
        return 'أمان رقمي';
      case 'development':
        return 'تنمية';
      default:
        return d;
    }
  }

  Color _domainColor(String d) {
    switch (d) {
      case 'islamic_parenting':
        return const Color(0xFF2E7D32);
      case 'medical':
        return const Color(0xFF1565C0);
      case 'cyber':
        return const Color(0xFF6A1B9A);
      case 'development':
        return const Color(0xFFE65100);
      default:
        return AppTheme.primary;
    }
  }

  // ── Build ───────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final total = _questions.length * 10;
    final pct = _questions.isEmpty ? 0 : (_score / total * 100).round();
    return Scaffold(
      appBar: AppBar(
        title: const Text('🧠 اختبر معلوماتك'),
        centerTitle: true,
      ),
      body: Stack(
        children: [
          // Brand-aligned star field behind the results.
          if (_showResultsLottie && pct >= 60)
            Positioned.fill(
              child: IgnorePointer(
                child: Lottie.asset(
                  'assets/animations/celebration_stars.json',
                  repeat: false,
                ),
              ),
            ),
          SafeArea(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? _buildError()
                    : _currentIndex >= _questions.length
                        ? _buildResults()
                        : _buildQuestion(),
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.wifi_off, size: 64, color: Colors.grey),
          const SizedBox(height: 16),
          Text(_error!, style: const TextStyle(fontSize: 18)),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _fetchQuestions,
            icon: const Icon(Icons.refresh),
            label: const Text('إعادة المحاولة'),
          ),
        ],
      ),
    );
  }

  Future<void> _shareResult() async {
    final total = _questions.length * 10;
    final pct = (_score / total * 100).round();
    String praise;
    if (pct >= 80) {
      praise = 'ممتاز! 🏆';
    } else if (pct >= 50) {
      praise = 'جيد! 👏';
    } else {
      praise = 'واصل التعلم 💪';
    }
    await Analytics.shareMoment('quiz');
    await ShareService.shareMomentCard(
      fileTag: 'quiz_result',
      message: 'حصلت على $_score من $total نقطة في اختبار «المربّي» 🤍\\n'
          '$praise — جرّب أنت كمان:',
      card: ShareableMomentCard(
        emoji: pct >= 80 ? '🏆' : (pct >= 50 ? '👏' : '💪'),
        eyebrow: 'نتيجة الاختبار',
        headline: '$_score / $total نقطة',
        body: '$praise — واصل التعلم يوميًا مع المربّي.',
        icon: Icons.quiz_outlined,
      ),
    );
  }

  Widget _buildResults() {
    final total = _questions.length * 10;
    final pct = (_score / total * 100).round();
    String emoji;
    String msg;
    if (pct >= 80) {
      emoji = '🏆';
      msg = 'ممتاز! أنت مربي واعٍ';
    } else if (pct >= 50) {
      emoji = '👏';
      msg = 'جيد! واصل التعلم';
    } else {
      emoji = '💪';
      msg = 'لا بأس، كل يوم فرصة للتعلم';
    }
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            if (pct >= 80)
              SizedBox(
                height: 140,
                child: Lottie.asset(
                  'assets/animations/success_check.json',
                  repeat: false,
                ),
              )
            else
              Text(emoji, style: const TextStyle(fontSize: 72))
                  .animate()
                  .scale(duration: 600.ms, curve: Curves.elasticOut),
            const SizedBox(height: 16),
            Text(msg,
                style: const TextStyle(
                    fontSize: 22, fontWeight: FontWeight.bold),
                textAlign: TextAlign.center),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 20),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [
                  AppTheme.primary.withValues(alpha: 0.1),
                  AppTheme.primary.withValues(alpha: 0.05),
                ]),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                children: [
                  Text('$_score / $total',
                      style: const TextStyle(
                          fontSize: 48,
                          fontWeight: FontWeight.w900,
                          color: AppTheme.primary)),
                  Text('نقطة',
                      style: TextStyle(fontSize: 16, color: Colors.grey[600])),
                ],
              ),
            ),
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _shareResult,
                icon: const Icon(Icons.share),
                label: const Text('شارك نتيجتك 🤍'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  textStyle: const TextStyle(fontSize: 18),
                ),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _restart,
                icon: const Icon(Icons.replay),
                label: const Text('العب مرة أخرى'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  textStyle: const TextStyle(fontSize: 18),
                ),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: () => Navigator.pop(context),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: const Text('العودة'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuestion() {
    final q = _questions[_currentIndex];
    final choices = q['choices'] as List;
    final correct = q['answer'] as int;
    final domain = q['domain'] as String;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Progress + Timer row
          Row(
            children: [
              // Domain chip
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: _domainColor(domain).withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(_domainLabel(domain),
                    style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: _domainColor(domain))),
              ),
              const Spacer(),
              // Question counter
              Text(
                '${_currentIndex + 1} / ${_questions.length}',
                style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Colors.grey[600]),
              ),
            ],
          ),
          const SizedBox(height: 8),
          // Timer bar
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: _timeLeft / 15,
              minHeight: 6,
              backgroundColor: Colors.grey[200],
              valueColor: AlwaysStoppedAnimation(
                  _timeLeft <= 5 ? Colors.red : AppTheme.primary),
            ),
          ),
          const SizedBox(height: 4),
          Align(
            alignment: Alignment.centerLeft,
            child: Text('$_timeLeft ث',
                style: TextStyle(
                    fontSize: 13,
                    color: _timeLeft <= 5 ? Colors.red : Colors.grey[500])),
          ),
          const SizedBox(height: 16),
          // Score
          Row(
            children: [
              const Icon(Icons.stars_rounded,
                  color: Color(0xFFFFD700), size: 20),
              const SizedBox(width: 4),
              Text('$_score نقطة',
                  style: const TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 15)),
            ],
          ),
          const SizedBox(height: 20),
          // Question text
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                    color: Colors.black.withValues(alpha: 0.06),
                    blurRadius: 12,
                    offset: const Offset(0, 4))
              ],
            ),
            child: Text(
              q['question'] as String,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              textAlign: TextAlign.right,
            ),
          )
              .animate()
              .fadeIn(duration: 300.ms)
              .slideX(begin: 0.05, end: 0, duration: 300.ms),
          const SizedBox(height: 20),
          // Choices
          ...List.generate(choices.length, (i) {
            final isSelected = _selectedAnswer == i;
            final isCorrect = i == correct;
            Color bgColor = Theme.of(context).colorScheme.surface;
            Color borderColor = Colors.grey.shade300;
            if (_answered) {
              if (isCorrect) {
                bgColor = const Color(0xFFE8F5E9);
                borderColor = const Color(0xFF4CAF50);
              } else if (isSelected && !isCorrect) {
                bgColor = const Color(0xFFFFEBEE);
                borderColor = const Color(0xFFE53935);
              }
            } else if (isSelected) {
              borderColor = AppTheme.primary;
            }

            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: InkWell(
                onTap: _answered ? null : () => _onAnswer(i),
                borderRadius: BorderRadius.circular(14),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    color: bgColor,
                    border: Border.all(color: borderColor, width: 1.5),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 28,
                        height: 28,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: _answered && isCorrect
                              ? const Color(0xFF4CAF50)
                              : _answered && isSelected && !isCorrect
                                  ? const Color(0xFFE53935)
                                  : Colors.grey.shade200,
                        ),
                        child: _answered
                            ? Icon(
                                isCorrect ? Icons.check : (isSelected ? Icons.close : null),
                                size: 16,
                                color: Colors.white,
                              )
                            : Text(
                                String.fromCharCode(0x0623 + i), // أ ب ت ث
                                style: TextStyle(
                                    fontSize: 14, color: Colors.grey[700]),
                              ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(choices[i] as String,
                            style: const TextStyle(fontSize: 15)),
                      ),
                    ],
                  ),
                ),
              ),
            );
          }),
          // Comment area (after answering)
          if (_answered) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF8E1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFFFD54F)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('💡', style: TextStyle(fontSize: 20)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      q['comment'] as String,
                      style: const TextStyle(fontSize: 14, height: 1.5),
                    ),
                  ),
                ],
              ),
            ).animate().fadeIn(duration: 400.ms),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _nextQuestion,
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                child: Text(
                  _currentIndex < _questions.length - 1
                      ? 'السؤال التالي'
                      : 'عرض النتائج',
                  style: const TextStyle(fontSize: 16),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}