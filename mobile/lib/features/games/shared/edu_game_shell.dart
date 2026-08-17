/// Generic educational game shell that hosts level selection and the game
/// runner. Each domain-specific game only needs to provide its theme and a
/// factory that builds questions for a given level.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lottie/lottie.dart';

import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/error_retry_view.dart';
import '../../coins/coins_providers.dart';
import '../../routine/providers/child_mode_providers.dart';
import '../../routine/widgets/quiet_time_bar.dart';
import 'edu_game_models.dart';
import 'edu_game_ui.dart';

/// Shell that hosts the educational mini-game UI for a single domain.
///
/// The questions used to arrive as a `switch (level)` over ~600 Dart literals
/// per game. They are now a JSON pack under `assets/content/games/`, keyed by
/// [EduGameTheme.id] — so a game supplies a theme and nothing else.
class EduGameShell extends ConsumerStatefulWidget {
  final EduGameTheme theme;

  const EduGameShell({
    super.key,
    required this.theme,
  });

  @override
  ConsumerState<EduGameShell> createState() => _EduGameShellState();
}

class _EduGameShellState extends ConsumerState<EduGameShell> {
  EduGameProgress _progress = const EduGameProgress(gameId: '');
  EduQuestionPack _pack = EduQuestionPack.empty;
  Object? _packError;
  bool _loading = true;

  /// Where this game was entered from, read off the route. See [GameSources].
  String _source = GameSources.unknown;
  bool _openLogged = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Not initState: ModalRoute.of registers an inherited-widget dependency.
    // Guarded because didChangeDependencies can fire more than once per mount,
    // and the contract is one game_opened per shell.
    //
    // Both game events are emitted from here rather than from the call sites,
    // so a new entry point that forgets to name itself lands in
    // GameSources.unknown instead of vanishing from the numbers entirely.
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map && args['source'] is String) {
      _source = args['source'] as String;
    }
    if (!_openLogged) {
      _openLogged = true;
      unawaited(Analytics.gameOpened(widget.theme.id, _source));
    }
  }

  /// Loads progress **and** the question pack behind the spinner this screen
  /// already showed. `EduQuestionBuilder` was synchronous and `rootBundle` is
  /// not; preloading here keeps the question path synchronous rather than
  /// pushing a `Future` down into the runner.
  Future<void> _load() async {
    final progress = await EduGameProgressService.instance.load(widget.theme.id);
    EduQuestionPack pack = EduQuestionPack.empty;
    Object? error;
    try {
      pack = await EduGameContent.load(widget.theme.id);
      if (pack.isEmpty) error = StateError('empty pack for ${widget.theme.id}');
    } catch (e) {
      // A game whose pack will not load must say so. Falling through to level
      // selection would hand the player a level that opens onto no questions.
      error = e;
    }
    if (mounted) {
      setState(() {
        _progress = progress;
        _pack = pack;
        _packError = error;
        _loading = false;
      });
    }
  }

  Future<void> _retryLoad() async {
    EduGameContent.resetCacheForTesting();
    setState(() {
      _loading = true;
      _packError = null;
    });
    await _load();
  }

  Future<void> _save(EduGameProgress progress) async {
    await EduGameProgressService.instance.save(progress);
    if (mounted) {
      setState(() => _progress = progress);
    }
  }

  void _play(int level) {
    unawaited(Analytics.gameLevelStarted(widget.theme.id, level, _source));
    final questions = _pack.forLevel(level);
    if (questions.isEmpty) return;
    Navigator.of(context).push(
      AppRoutes.gameRunner(
        theme: widget.theme,
        level: level,
        questions: questions,
        onComplete: (result) async {
          // Logged here rather than in the runner because this closure is the
          // only place that knows the entry point. A replay re-enters _finish
          // and fires a second game_completed at the same level — correct, and
          // it keeps the event count reconcilable against `attempts`.
          unawaited(Analytics.gameCompleted(
            gameId: widget.theme.id,
            level: level,
            completed: result.completed,
            stars: result.stars,
            score: result.score,
            entryPoint: _source,
          ));
          final newProgress = _progress.recordGame(level, result);
          await _save(newProgress);

          // Award coins for correct answers + completion bonus.
          final coinsNotifier = ref.read(coinsProvider.notifier);
          final earned = result.score;
          await coinsNotifier.creditGameEarnings(earned);
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        backgroundColor: widget.theme.backgroundColor,
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_packError != null) {
      return Scaffold(
        backgroundColor: widget.theme.backgroundColor,
        appBar: AppBar(
          backgroundColor: widget.theme.surfaceColor,
          foregroundColor: widget.theme.textColor,
          title: Text(widget.theme.name),
        ),
        body: ErrorRetryView(error: _packError!, onRetry: _retryLoad),
      );
    }

    return EduLevelSelectionScreen(
      theme: widget.theme,
      progress: _progress,
      onPlay: _play,
      onBack: () => Navigator.of(context).pop(),
    );
  }
}

/// The actual question-by-question runner.
class EduGameRunner extends ConsumerStatefulWidget {
  final EduGameTheme theme;
  final int level;
  final List<EduQuestion> questions;
  final void Function(EduGameResult result) onComplete;

  const EduGameRunner({
    super.key,
    required this.theme,
    required this.level,
    required this.questions,
    required this.onComplete,
  });

  @override
  ConsumerState<EduGameRunner> createState() => _EduGameRunnerState();
}

class _EduGameRunnerState extends ConsumerState<EduGameRunner> {
  late int _lives;
  late int _index;
  int _correctCount = 0;
  int _score = 0;
  bool _showFeedback = false;
  int? _selectedOptionIndex;
  bool _paused = false;
  bool _finished = false;
  bool _showMiniStarBurst = false;

  /// How long this level has actually been on screen.
  ///
  /// There was no time tracking in any of the four games — the only way out
  /// was answering every question or losing three lives, and a child who did
  /// neither could sit here indefinitely. The server bills by heartbeat, but
  /// the cap has to be visible here too or the game plays on past the budget
  /// while the session dies quietly underneath it.
  final Stopwatch _elapsed = Stopwatch();
  Timer? _capTimer;

  /// Set when the surface ended mid-level: the closing screen replaces the
  /// results dialog, and neither "next level" nor "play again" is offered.
  bool _closedByBudget = false;

  @override
  void initState() {
    super.initState();
    _lives = 3;
    _index = 0;
    _elapsed.start();
    _watchTheBudget();
  }

  /// The cap is whatever the server said when the session opened — never a
  /// constant compiled into the client, which is a limit a client can edit.
  void _watchTheBudget() {
    final remaining = ref.read(childModeProvider).remainingSeconds;
    if (remaining == null || remaining <= 0) return;
    _capTimer = Timer(Duration(seconds: remaining), () {
      if (mounted && !_finished) {
        setState(() => _closedByBudget = true);
        _finish();
      }
    });
  }

  @override
  void dispose() {
    _capTimer?.cancel();
    _elapsed.stop();
    super.dispose();
  }

  EduQuestion get _currentQuestion => widget.questions[_index];

  int get _targetScore {
    final total = widget.questions.length;
    // Need at least 70% correct to complete the level.
    return (total * 0.7).ceil();
  }

  void _selectOption(int optionIndex) {
    if (_showFeedback || _paused || _finished) return;

    setState(() {
      _selectedOptionIndex = optionIndex;
      _showFeedback = true;
    });

    final option = _currentQuestion.options[optionIndex];
    if (option.isCorrect) {
      _correctCount++;
      final points = 10 + (widget.level - 1); // slight scaling per level
      _score += points;
      lightHaptic();
      // small brand-aligned celebration on each correct answer
      _playMiniStarBurst();
    } else {
      _lives--;
      errorHaptic();
    }

    Future.delayed(const Duration(milliseconds: 1800), _advance);
  }

  void _advance() {
    if (!mounted) return;

    if (_index < widget.questions.length - 1 && _lives > 0) {
      setState(() {
        _index++;
        _selectedOptionIndex = null;
        _showFeedback = false;
      });
      return;
    }

    _finish();
  }

  void _finish() {
    final correctNeeded = _targetScore;
    final completed = _correctCount >= correctNeeded && _lives > 0;

    // Star rating based on remaining lives and accuracy.
    int stars = 0;
    if (completed) {
      if (_correctCount == widget.questions.length) {
        stars = 3;
      } else if (_lives >= 2) {
        stars = 2;
      } else {
        stars = 1;
      }
    }

    // Completion bonus.
    if (completed) _score += 50;

    final result = EduGameResult(
      level: widget.level,
      score: _score,
      correctAnswers: _correctCount,
      totalQuestions: widget.questions.length,
      completed: completed,
      stars: stars,
    );

    widget.onComplete(result);

    if (!mounted) return;
    setState(() => _finished = true);
    _capTimer?.cancel();
    _elapsed.stop();

    // The exit ritual. A game that ends by dropping the child back to a menu
    // teaches that the way out of a screen is another screen, and a game that
    // offers "play again" at the exact moment the budget ran out teaches that
    // limits are negotiable. When the surface is over there is one button, and
    // it goes outside.
    final inChildMode = ref.read(childModeProvider).active;
    final surfaceOver = _closedByBudget || ref.read(childModeProvider).exitRitual;

    if (inChildMode && surfaceOver) {
      unawaited(ref.read(childModeProvider.notifier).endSession(
            reason: _closedByBudget ? 'budget_exhausted' : 'completed',
          ));
      showEduClosingScreen(
        context: context,
        theme: widget.theme,
        result: result,
        onLeave: () {
          Navigator.of(context).pop();
          Navigator.of(context).pop();
        },
      );
      return;
    }

    showEduResultDialog(
      context: context,
      theme: widget.theme,
      result: result,
      onNext: completed && widget.level < 10
          ? () {
              Navigator.of(context).pop();
              Navigator.of(context).pop();
            }
          : null,
      onReplay: () {
        Navigator.of(context).pop();
        _resetGame();
      },
      onExit: () {
        Navigator.of(context).pop();
        Navigator.of(context).pop();
      },
    );
  }

  void _resetGame() {
    setState(() {
      _lives = 3;
      _index = 0;
      _correctCount = 0;
      _score = 0;
      _showFeedback = false;
      _selectedOptionIndex = null;
      _finished = false;
      _showMiniStarBurst = false;
    });
  }


  void _playMiniStarBurst() {
    if (!mounted) return;
    setState(() => _showMiniStarBurst = true);
    Future.delayed(const Duration(milliseconds: 1800), () {
      if (mounted) setState(() => _showMiniStarBurst = false);
    });
  }
  void _togglePause() => setState(() => _paused = !_paused);

  @override
  Widget build(BuildContext context) {
    final question = _currentQuestion;
    final progress = (_index) / widget.questions.length;

    return Scaffold(
      backgroundColor: widget.theme.backgroundColor,
      appBar: AppBar(
        backgroundColor: widget.theme.surfaceColor,
        foregroundColor: widget.theme.textColor,
        title: Text(AppLocalizations.of(context)
            .eduGameLevelTitle(widget.theme.name, widget.level)),
        actions: [
          IconButton(
            icon: Icon(_paused ? Icons.play_arrow : Icons.pause),
            onPressed: _togglePause,
          ),
        ],
      ),
      body: PopScope(
        canPop: _finished,
        onPopInvokedWithResult: (didPop, result) {
          if (!didPop && !_finished) {
            _togglePause();
          }
        },
        child: SafeArea(
          child: Stack(
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _Hud(
                      lives: _lives,
                      score: _score,
                      progress: progress,
                      theme: widget.theme,
                    ),
                    // The session clock, above the game's own progress bar and
                    // visually quieter than it. A child mid-level otherwise
                    // gets no warning at all before the cap fires — the timer
                    // that closes this screen has been reading
                    // `remainingSeconds` since sprint 1 while nothing showed
                    // it. No candle glyph here: it would compete with the
                    // game's artwork, and the bar alone carries it.
                    const SizedBox(height: 10),
                    const QuietTimeBar(showCandle: false),
                    const SizedBox(height: 16),
                    Expanded(
                      child: SingleChildScrollView(
                        child: _QuestionCard(
                          theme: widget.theme,
                          question: question,
                          showFeedback: _showFeedback,
                          selectedIndex: _selectedOptionIndex,
                          onSelect: _selectOption,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              if (_showMiniStarBurst)
                Positioned.fill(
                  child: IgnorePointer(
                    child: Lottie.asset(
                      'assets/animations/celebration_stars.json',
                      repeat: false,
                      onLoaded: (_) {},
                    ),
                  ),
                ),
              if (_paused)
                EduPauseOverlay(
                  theme: widget.theme,
                  onResume: _togglePause,
                  onRestart: () {
                    _togglePause();
                    _resetGame();
                  },
                  onQuit: () => Navigator.of(context).pop(),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Hud extends StatelessWidget {
  final int lives;
  final int score;
  final double progress;
  final EduGameTheme theme;

  const _Hud({
    required this.lives,
    required this.score,
    required this.progress,
    required this.theme,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: theme.surfaceColor,
        borderRadius: BorderRadius.circular(Dt.rCard),
      ),
      child: Row(
        children: [
          Row(
            children: [
              for (int i = 0; i < 3; i++)
                Icon(
                  i < lives ? Icons.favorite : Icons.favorite_border,
                  color: i < lives ? AppTheme.dangerFg : Colors.white24,
                  size: 24,
                ),
            ],
          ),
          const SizedBox(width: 16),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                value: progress,
                backgroundColor: Colors.white12,
                color: theme.accentColor,
                minHeight: 8,
              ),
            ),
          ),
          const SizedBox(width: 16),
          Text(
            '$score',
            style: TextStyle(
              color: theme.textColor,
              fontWeight: FontWeight.bold,
              fontSize: 20,
            ),
          ),
        ],
      ),
    );
  }
}

class _QuestionCard extends StatelessWidget {
  final EduGameTheme theme;
  final EduQuestion question;
  final bool showFeedback;
  final int? selectedIndex;
  final ValueChanged<int> onSelect;

  const _QuestionCard({
    required this.theme,
    required this.question,
    required this.showFeedback,
    required this.selectedIndex,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    final optionLetters =
        AppLocalizations.of(context).eduGameOptionLetters.split(',');

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: theme.surfaceColor,
        borderRadius: BorderRadius.circular(Dt.rCard),
        border: Border.all(color: theme.accentColor.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (question.emoji != null) ...[
            Center(child: Text(question.emoji!, style: const TextStyle(fontSize: 56))),
            const SizedBox(height: 12),
          ],
          if (question.category != null) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: theme.accentColor.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                question.category!,
                textAlign: TextAlign.center,
                style: TextStyle(color: theme.accentColor, fontWeight: FontWeight.w600),
              ),
            ),
            const SizedBox(height: 12),
          ],
          Text(
            question.question,
            textAlign: TextAlign.right,
            textDirection: TextDirection.rtl,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: theme.textColor,
                  fontWeight: FontWeight.bold,
                  height: 1.5,
                ),
          ),
          if (question.context != null) ...[
            const SizedBox(height: 12),
            Text(
              question.context!,
              textAlign: TextAlign.right,
              textDirection: TextDirection.rtl,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: theme.textColor.withValues(alpha: 0.75),
                    height: 1.5,
                  ),
            ),
          ],
          const SizedBox(height: 24),
          ...question.options.asMap().entries.map((entry) {
            final idx = entry.key;
            final option = entry.value;
            final selected = selectedIndex == idx;
            final state = _resolveOptionState(
              selected: selected,
              showFeedback: showFeedback,
              isCorrect: option.isCorrect,
            );
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _OptionButton(
                theme: theme,
                letter: optionLetters[idx],
                text: option.text,
                state: state,
                rationale: (showFeedback && selected) ? option.rationale : null,
                onTap: () => onSelect(idx),
              ),
            );
          }),
        ],
      ),
    );
  }

  static _OptionState _resolveOptionState({
    required bool selected,
    required bool showFeedback,
    required bool isCorrect,
  }) {
    if (!showFeedback) return selected ? _OptionState.selectedCorrect : _OptionState.idle;
    if (isCorrect) return _OptionState.correctReveal;
    if (selected) return _OptionState.selectedWrong;
    return _OptionState.disabled;
  }
}

enum _OptionState { idle, selectedCorrect, selectedWrong, correctReveal, disabled }

class _OptionButton extends StatelessWidget {
  final EduGameTheme theme;
  final String letter;
  final String text;
  final _OptionState state;
  final String? rationale;
  final VoidCallback onTap;

  const _OptionButton({
    required this.theme,
    required this.letter,
    required this.text,
    required this.state,
    this.rationale,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color fg;
    Color border;
    switch (state) {
      case _OptionState.idle:
        bg = theme.surfaceColor;
        fg = theme.textColor;
        border = Colors.white24;
        break;
      case _OptionState.selectedCorrect:
        bg = AppTheme.success.withValues(alpha: 0.15);
        fg = AppTheme.success;
        border = AppTheme.success;
        break;
      case _OptionState.selectedWrong:
        bg = AppTheme.dangerFg.withValues(alpha: 0.15);
        fg = AppTheme.dangerFg;
        border = AppTheme.dangerFg;
        break;
      case _OptionState.correctReveal:
        bg = AppTheme.success.withValues(alpha: 0.12);
        fg = AppTheme.success;
        border = AppTheme.success;
        break;
      case _OptionState.disabled:
        bg = theme.surfaceColor;
        fg = theme.textColor.withValues(alpha: 0.4);
        border = Colors.white12;
        break;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        BouncyTap(
          onTap: state == _OptionState.idle || state == _OptionState.selectedCorrect
              ? onTap
              : null,
          child: AnimatedContainer(
            duration: 250.ms,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            decoration: BoxDecoration(
              color: bg,
              border: Border.all(color: border, width: 1.5),
              borderRadius: BorderRadius.circular(Dt.rButton),
            ),
            child: Row(
              textDirection: TextDirection.rtl,
              children: [
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: border.withValues(alpha: 0.15),
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Text(
                      letter,
                      style: TextStyle(
                        color: fg,
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    text,
                    textAlign: TextAlign.right,
                    textDirection: TextDirection.rtl,
                    style: TextStyle(
                      color: fg,
                      fontSize: 16,
                      height: 1.4,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                if (state == _OptionState.selectedCorrect || state == _OptionState.correctReveal)
                  Icon(Icons.check_circle, color: AppTheme.success)
                else if (state == _OptionState.selectedWrong)
                  Icon(Icons.cancel, color: AppTheme.dangerFg)
              ],
            ),
          ),
        ),
        if (rationale != null && rationale!.isNotEmpty) ...[
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: state == _OptionState.selectedCorrect
                  ? AppTheme.success.withValues(alpha: 0.08)
                  : AppTheme.dangerFg.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              rationale!,
              textAlign: TextAlign.right,
              textDirection: TextDirection.rtl,
              style: TextStyle(
                color: theme.textColor.withValues(alpha: 0.9),
                height: 1.5,
              ),
            ),
          ),
        ],
      ],
    );
  }
}

/// Extension on [CoinsNotifier] so games can credit small per-question earnings.
///
/// This used to write `coins.balance` in SharedPreferences directly, which put
/// the four games outside every rule CoinsService enforces — including the
/// daily earning ceiling, which is precisely the limit that stops a game from
/// being a coin mint. It goes through `earn` now, and is capped like anything
/// else that credits coins.
extension GameCoins on CoinsNotifier {
  Future<void> creditGameEarnings(int amount) => earn(amount);
}