/// Quiz player — P0.1 (replaces the second AssetPlaceholderScreen).
///
/// Loads one or more quiz decks (their ids come from lesson-assets
/// metadata), merges the questions, and presents them as a multiple-
/// choice quiz: question → 4 options → instant feedback → next → final
/// score with the option to retry.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
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
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => _ErrorState(
          onRetry: () =>
              ref.invalidate(quizDecksProvider(quizIds.join(','))),
        ),
        data: (decks) {
          final questions = decks.expand((d) => d.questions).toList();
          if (questions.isEmpty) {
            return const Center(
              child: Text('لا توجد أسئلة متاحة لهذا الدرس حالياً'),
            );
          }
          return _QuizRunner(questions: questions);
        },
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final VoidCallback onRetry;
  const _ErrorState({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('تعذّر تحميل الاختبار'),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('إعادة المحاولة'),
          ),
        ],
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
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: LinearProgressIndicator(
                  value: progress,
                  minHeight: 6,
                  backgroundColor: AppTheme.surfaceAlt,
                ),
              ),
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
    Color borderColor = const Color(0xFFE5E7EB);
    Color bgColor = AppTheme.surface;
    IconData? trailingIcon;
    Color? trailingColor;

    if (showFeedback) {
      if (option.isCorrect) {
        borderColor = AppTheme.success;
        bgColor = const Color(0xFFD4EDDA);
        trailingIcon = Icons.check_circle;
        trailingColor = AppTheme.success;
      } else if (selected) {
        borderColor = AppTheme.dangerFg;
        bgColor = AppTheme.dangerBg;
        trailingIcon = Icons.cancel;
        trailingColor = AppTheme.dangerFg;
      }
    } else if (selected) {
      borderColor = AppTheme.primary;
    }

    final letter = String.fromCharCode('أ'.codeUnitAt(0) + index);

    return Material(
      color: bgColor,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: showFeedback ? null : onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            border: Border.all(color: borderColor, width: 1.5),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 28,
                height: 28,
                alignment: Alignment.center,
                decoration: const BoxDecoration(
                  color: AppTheme.surfaceAlt,
                  shape: BoxShape.circle,
                ),
                child: Text(
                  letter,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  option.text,
                  style: const TextStyle(height: 1.5, fontSize: 15),
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

class _Summary extends StatelessWidget {
  final int total;
  final int correct;
  final VoidCallback onRetry;

  const _Summary({
    required this.total,
    required this.correct,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final pct = total == 0 ? 0 : (correct * 100 / total).round();
    final color = pct >= 80
        ? AppTheme.success
        : pct >= 50
            ? AppTheme.warningFg
            : AppTheme.dangerFg;
    final verdict = pct >= 80
        ? 'ما شاء الله! أداء ممتاز.'
        : pct >= 50
            ? 'جيد. راجع الدروس التي أخطأت فيها.'
            : 'لا بأس — المراجعة خير من الندم. اقرأ الدرس مرة أخرى.';

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.emoji_events, color: color, size: 80),
            const SizedBox(height: 16),
            Text(
              'نتيجتك',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              '$correct / $total',
              style: TextStyle(
                fontSize: 56,
                fontWeight: FontWeight.w800,
                color: color,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '$pct%',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              verdict,
              textAlign: TextAlign.center,
              style: const TextStyle(height: 1.55),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              key: const Key('quiz_retry_button'),
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('أعد المحاولة'),
              style: FilledButton.styleFrom(
                minimumSize: const Size(180, 48),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
