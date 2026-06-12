/// Quiz player — P0.1 (replaces the second AssetPlaceholderScreen).
///
/// Loads one or more quiz decks (their ids come from lesson-assets
/// metadata), merges the questions, and presents them as a multiple-
/// choice quiz: question → 4 options → instant feedback → next → final
/// score with the option to retry.
library;

import 'dart:math' as math;

import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/animated_progress_bar.dart';
import '../../../widgets/ui/count_up_text.dart';
import '../../../widgets/ui/empty_state.dart';
import '../../../widgets/ui/progress_ring.dart';
import '../../../widgets/ui/skeleton.dart';
import '../models/quiz_deck.dart';
import '../providers/lesson_assets_provider.dart';

class QuizScreen extends ConsumerWidget {
  final List<String> quizIds;
  const QuizScreen({super.key, required this.quizIds});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final decksAsync =
        ref.watch(quizDecksProvider(quizIds.join(',')));

    return Scaffold(
      appBar: AppBar(title: const Text('❓ اختبر نفسك')),
      body: decksAsync.when(
        loading: () => const SingleChildScrollView(
          physics: NeverScrollableScrollPhysics(),
          child: SkeletonList(count: 5, itemHeight: 90),
        ),
        error: (e, _) => EmptyState(
          emoji: '📡',
          title: 'تعذّر تحميل الاختبار',
          actionLabel: 'إعادة المحاولة',
          onAction: () =>
              ref.invalidate(quizDecksProvider(quizIds.join(','))),
        ),
        data: (decks) {
          final questions = decks.expand((d) => d.questions).toList();
          if (questions.isEmpty) {
            return const EmptyState(
              emoji: '❓',
              title: 'لا توجد أسئلة متاحة لهذا الدرس حالياً',
            );
          }
          return _QuizRunner(questions: questions);
        },
      ),
    );
  }
}

/// The stateful quiz runner: tracks current index, selected option,
/// answer correctness, and a final summary screen with retry.
class _QuizRunner extends StatefulWidget {
  final List<QuizQuestion> questions;
  const _QuizRunner({required this.questions});

  @override
  State<_QuizRunner> createState() => _QuizRunnerState();
}

class _QuizRunnerState extends State<_QuizRunner> {
  int _index = 0;
  int? _selectedOptionIndex;
  bool _showFeedback = false;
  int _correctCount = 0;

  void _selectOption(int optionIndex) {
    if (_showFeedback) return; // ignore taps after answer is locked
    setState(() {
      _selectedOptionIndex = optionIndex;
      _showFeedback = true;
      if (widget.questions[_index].options[optionIndex].isCorrect) {
        _correctCount += 1;
      }
    });
  }

  void _next() {
    if (_index < widget.questions.length - 1) {
      setState(() {
        _index += 1;
        _selectedOptionIndex = null;
        _showFeedback = false;
      });
    } else {
      setState(() {
        // jump to summary view
        _index = widget.questions.length;
      });
    }
  }

  void _retry() {
    setState(() {
      _index = 0;
      _selectedOptionIndex = null;
      _showFeedback = false;
      _correctCount = 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_index >= widget.questions.length) {
      return _Summary(
        total: widget.questions.length,
        correct: _correctCount,
        onRetry: _retry,
      );
    }
    final q = widget.questions[_index];
    return _QuestionView(
      question: q,
      index: _index,
      total: widget.questions.length,
      selectedOptionIndex: _selectedOptionIndex,
      showFeedback: _showFeedback,
      onSelect: _selectOption,
      onNext: _next,
    );
  }
}

class _QuestionView extends StatelessWidget {
  final QuizQuestion question;
  final int index;
  final int total;
  final int? selectedOptionIndex;
  final bool showFeedback;
  final ValueChanged<int> onSelect;
  final VoidCallback onNext;

  const _QuestionView({
    required this.question,
    required this.index,
    required this.total,
    required this.selectedOptionIndex,
    required this.showFeedback,
    required this.onSelect,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    final progress = (index + 1) / total;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    'سؤال ${index + 1} من $total',
                    style: const TextStyle(
                      color: AppTheme.textSecondary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const Spacer(),
                  if (showFeedback && selectedOptionIndex != null)
                    _AnswerIcon(
                      isCorrect: question
                          .options[selectedOptionIndex!].isCorrect,
                    ),
                ],
              ),
              const SizedBox(height: 8),
              AnimatedProgressBar(value: progress, height: 12),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            children: [
              Text(
                question.question,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  height: 1.55,
                ),
              ),
              if (question.text != null && question.text!.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  question.text!,
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontStyle: FontStyle.italic,
                    height: 1.5,
                  ),
                ),
              ],
              if (question.hint != null && question.hint!.isNotEmpty) ...[
                const SizedBox(height: 12),
                _HintCard(text: question.hint!),
              ],
              const SizedBox(height: 16),
              for (var i = 0; i < question.options.length; i++) ...[
                _OptionTile(
                  option: question.options[i],
                  index: i,
                  selected: selectedOptionIndex == i,
                  showFeedback: showFeedback,
                  onTap: () => onSelect(i),
                ),
                const SizedBox(height: 10),
              ],
              if (showFeedback &&
                  selectedOptionIndex != null &&
                  question.options[selectedOptionIndex!].rationale !=
                      null) ...[
                const SizedBox(height: 4),
                _RationaleCard(
                  text:
                      question.options[selectedOptionIndex!].rationale!,
                ),
              ],
            ],
          ),
        ),
        if (showFeedback)
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: FilledButton.icon(
                key: const Key('quiz_next_button'),
                onPressed: onNext,
                icon: const Icon(Icons.arrow_forward),
                label: Text(
                  index < total - 1 ? 'السؤال التالي' : 'عرض النتيجة',
                ),
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(50),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _HintCard extends StatelessWidget {
  final String text;
  const _HintCard({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.lightbulb_outline,
              size: 18, color: AppTheme.textSecondary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: AppTheme.textSecondary,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _OptionTile extends StatelessWidget {
  final QuizOption option;
  final int index;
  final bool selected;
  final bool showFeedback;
  final VoidCallback onTap;

  const _OptionTile({
    required this.option,
    required this.index,
    required this.selected,
    required this.showFeedback,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    // Duolingo-style option: white pill with a darker bottom edge.
    Color edgeColor = const Color(0xFFE3DCCE);
    Color bgColor = AppTheme.surface;
    Color letterBg = AppTheme.surfaceAlt;
    Color letterFg = AppTheme.textPrimary;
    IconData? trailingIcon;
    Color? trailingColor;
    final isCorrectFeedback = showFeedback && option.isCorrect;
    final isWrongFeedback = showFeedback && selected && !option.isCorrect;

    if (isCorrectFeedback) {
      edgeColor = const Color(0xFF15803D);
      bgColor = AppTheme.success;
      letterBg = Colors.white.withValues(alpha: .25);
      letterFg = Colors.white;
      trailingIcon = Icons.check_circle;
      trailingColor = Colors.white;
    } else if (isWrongFeedback) {
      edgeColor = const Color(0xFF9F1239);
      bgColor = const Color(0xFFFB7185);
      letterBg = Colors.white.withValues(alpha: .25);
      letterFg = Colors.white;
      trailingIcon = Icons.cancel;
      trailingColor = Colors.white;
    } else if (selected) {
      edgeColor = AppTheme.primary;
    }

    final onColored = isCorrectFeedback || isWrongFeedback;
    final letter = String.fromCharCode('أ'.codeUnitAt(0) + index);

    Widget tile = Material(
      color: bgColor,
      borderRadius: BorderRadius.circular(Dt.rButton),
      child: InkWell(
        onTap: showFeedback ? null : onTap,
        borderRadius: BorderRadius.circular(Dt.rButton),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(color: edgeColor, width: 4)),
            borderRadius: BorderRadius.circular(Dt.rButton),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 28,
                height: 28,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: letterBg,
                  shape: BoxShape.circle,
                ),
                child: Text(
                  letter,
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    color: letterFg,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  option.text,
                  style: TextStyle(
                    height: 1.5,
                    fontSize: 15,
                    color: onColored ? Colors.white : AppTheme.textPrimary,
                    fontWeight:
                        onColored ? FontWeight.w700 : FontWeight.w500,
                  ),
                ),
              ),
              if (trailingIcon != null) ...[
                const SizedBox(width: 8),
                Icon(trailingIcon, color: trailingColor, size: 22),
              ],
            ],
          ),
        ),
      ),
    );

    if (isCorrectFeedback) {
      tile = tile.animate().scale(
            begin: const Offset(1, 1),
            end: const Offset(1.03, 1.03),
            duration: 180.ms,
            curve: Curves.easeOutBack,
          ).then().scale(
            begin: const Offset(1.03, 1.03),
            end: const Offset(1, 1),
            duration: 180.ms,
          );
    } else if (isWrongFeedback) {
      tile = tile.animate().shake(hz: 5, offset: const Offset(4, 0));
    }
    return tile;
  }
}

class _RationaleCard extends StatelessWidget {
  final String text;
  const _RationaleCard({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline,
              size: 18, color: AppTheme.textSecondary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: AppTheme.textSecondary,
                height: 1.55,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AnswerIcon extends StatelessWidget {
  final bool isCorrect;
  const _AnswerIcon({required this.isCorrect});

  @override
  Widget build(BuildContext context) {
    return Icon(
      isCorrect ? Icons.check_circle : Icons.cancel,
      color: isCorrect ? AppTheme.success : AppTheme.dangerFg,
      size: 22,
    );
  }
}

class _Summary extends StatefulWidget {
  final int total;
  final int correct;
  final VoidCallback onRetry;

  const _Summary({
    required this.total,
    required this.correct,
    required this.onRetry,
  });

  @override
  State<_Summary> createState() => _SummaryState();
}

class _SummaryState extends State<_Summary> {
  late final ConfettiController _confetti =
      ConfettiController(duration: const Duration(milliseconds: 1500));

  int get _pct => widget.total == 0
      ? 0
      : (widget.correct * 100 / widget.total).round();

  @override
  void initState() {
    super.initState();
    if (_pct >= 80) _confetti.play();
  }

  @override
  void dispose() {
    _confetti.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pct = _pct;
    final color = pct >= 80
        ? AppTheme.success
        : pct >= 50
            ? Dt.accentDeep
            : AppTheme.dangerFg;
    final emoji = pct >= 80
        ? '🏆'
        : pct >= 50
            ? '🌟'
            : '💪';
    final verdict = pct >= 80
        ? 'ما شاء الله! أداء ممتاز.'
        : pct >= 50
            ? 'جيد. راجع الدروس التي أخطأت فيها.'
            : 'لا بأس — المراجعة خير من الندم. اقرأ الدرس مرة أخرى.';

    return Stack(
      alignment: Alignment.topCenter,
      children: [
        Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(emoji, style: const TextStyle(fontSize: 80))
                    .animate()
                    .scale(
                      begin: const Offset(.3, .3),
                      duration: Dt.slow,
                      curve: Curves.easeOutBack,
                    ),
                const SizedBox(height: 16),
                Text(
                  'نتيجتك',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 16),
                ProgressRing(
                  value: widget.total == 0
                      ? 0
                      : widget.correct / widget.total,
                  size: 130,
                  strokeWidth: 12,
                  color: color,
                  center: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CountUpText(
                        widget.correct,
                        suffix: ' / ${widget.total}',
                        style: TextStyle(
                          fontSize: 26,
                          fontWeight: FontWeight.w800,
                          color: color,
                        ),
                      ),
                      Text(
                        '$pct%',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: color,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  verdict,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    height: 1.55,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  key: const Key('quiz_retry_button'),
                  onPressed: widget.onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('أعد المحاولة'),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size(180, 48),
                  ),
                ),
              ],
            ),
          ),
        ),
        ConfettiWidget(
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
      ],
    );
  }
}
