/// «ركن الطفل» — after the hand-over gate, one paper scene for the child.
///
/// The game study (scratch/game-study/REPORT.md, the «كبير» phone of
/// mockup_world_3_levels.png) asked for the spirit of a child's world without
/// a game engine: a short story, a short game, the day's task away from the
/// screen — and an end. This is that, built from what the app already has:
///
///  * **the story** is the day's story from the existing library
///    (`storiesProvider`), read in [CornerStoryView];
///  * **the game** — switched off for this launch
///    ([kChildCornerGameEnabled]: the games' questions are written for
///    parents) — is one level of one of the four existing games, played in
///    their own [EduGameRunner] with `quiet: true` — no score, no star burst,
///    no results dialog, no coins credited;
///  * **the task** is today's card from `child_missions`, fetched once when the
///    corner opens, so it is there even if the session closes underneath;
///  * **time** is [CornerCandle], a paper candle that only grows shorter —
///    never a number, and still under reduced motion.
///
/// Only what the child's band is allowed appears ([childCornerActivitiesFor]):
/// a 4-6 child has no game here at all, not a locked one. Each part is billed
/// on its own server surface (`story`, `game`, `mission`), moved with
/// [ChildModeNotifier.switchSurface] as the child goes.
///
/// The session ends on the task, always: when the child chooses it, when both
/// story and game are done, or when the candle burns down (or the connection
/// goes). The task's one button closes the session and the corner asks for
/// the device back — «أعِد الجهاز إلى أهلك — شكرًا لك». There are no coins,
/// no points, no streak, nothing to come back for tomorrow.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/analytics.dart';
import '../../l10n/app_localizations.dart';
import '../../state/chat_notifier.dart';
import '../../theme/app_colors.dart';
import '../../widgets/ui/brand_glyph.dart';
import '../companion/widgets/noor_face.dart';
import '../companion/widgets/noor_presence.dart';
import '../games/shared/edu_game_models.dart';
import '../games/shared/edu_game_shell.dart';
import '../handover/child_surface_policy.dart';
import '../onboarding/providers/onboarding_providers.dart';
import '../program/data/story_models.dart';
import '../routine/providers/child_mode_providers.dart';
import '../routine/services/child_mode_secure_storage.dart';
import 'corner_picks.dart';
import 'corner_scene.dart';
import 'corner_story_view.dart';
import 'paper_candle.dart';

/// "Now", for the day's picks. A provider so a test can hold the day still.
final childCornerNowProvider = Provider<DateTime Function()>(
  (_) => DateTime.now,
);

/// The entry point the game events carry for a game played in the corner.
const kChildCornerGameSource = 'child_corner';

enum CornerPhase { home, story, game, mission, done }

enum _NoorSays { intro, afterStory, afterGame, timeUp }

class ChildCornerScreen extends ConsumerStatefulWidget {
  const ChildCornerScreen({super.key});

  @override
  ConsumerState<ChildCornerScreen> createState() => ChildCornerScreenState();
}

class ChildCornerScreenState extends ConsumerState<ChildCornerScreen> {
  final CandleClock _clock = CandleClock();

  CornerPhase _phase = CornerPhase.home;

  /// Visible for tests.
  @visibleForTesting
  CornerPhase get phase => _phase;

  _NoorSays _noor = _NoorSays.intro;

  late final String _band;
  late final List<String> _activities;

  Story? _story;
  bool _storyDone = false;

  CornerGame? _game;
  EduQuestionPack? _pack;
  int _level = 1;
  bool _gameDone = false;

  Map<String, dynamic>? _mission;
  bool _missionLoaded = false;

  /// A surface switch in flight: its close-then-open passes through a state
  /// with no session, which is not the time running out.
  bool _switching = false;

  @override
  void initState() {
    super.initState();
    final state = ref.read(childModeProvider);
    _band = state.cornerBand ?? kFallbackChildSurfaceBand;
    _activities = childCornerActivitiesFor(
      _band,
      withGame: ref.read(childCornerGameEnabledProvider),
    );
    _observe(state);
    if (state.error == kChildModeHandedBack) _phase = CornerPhase.done;
    unawaited(Analytics.childCornerOpened(_band));
    unawaited(_loadStory());
    unawaited(_loadMission());
  }

  bool _gameAsked = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // The game needs the language the child is reading the app in, which is
    // an inherited lookup — not allowed from initState.
    if (!_gameAsked) {
      _gameAsked = true;
      unawaited(_loadGame(Localizations.localeOf(context)));
    }
  }

  DateTime get _now => ref.read(childCornerNowProvider)();
  int get _salt => ref.read(childModeProvider).childId ?? 0;

  bool get _offersStory => _activities.contains('story');
  bool get _offersGame => _activities.contains('game');

  Future<void> _loadStory() async {
    if (!_offersStory) return;
    try {
      final stories = await ref.read(storiesProvider.future);
      if (!mounted) return;
      setState(() => _story = cornerStoryFor(stories, _now, salt: _salt));
    } catch (_) {
      // No library at all: the corner simply has no story card today.
    }
  }

  Future<void> _loadGame(Locale locale) async {
    if (!_offersGame) return;
    final language = contentLanguageFor(locale);
    if (!cornerGamesSpeak(language)) return;
    final game = pickOfTheDay(cornerGames(), _now, salt: _salt);
    if (game == null) return;
    try {
      final pack = await EduGameContent.load(game.theme.id);
      final progress = await EduGameProgressService.instance.load(
        game.theme.id,
      );
      if (!mounted || pack.isEmpty) return;
      final level = cornerLevelFor(progress, pack);
      if (pack.forLevel(level).isEmpty) return;
      setState(() {
        _game = game;
        _pack = pack;
        _level = level;
      });
    } catch (_) {
      // A pack that will not load is a game the corner does not offer.
    }
  }

  Future<void> _loadMission() async {
    try {
      final token = await getChildToken();
      if (token != null) {
        final today = await ref.read(tgClientProvider).fetchChildMission(token);
        _mission = today?.mission;
      }
    } catch (_) {
      // Offline or no bank: the corner's own small task stands in.
    }
    if (mounted) setState(() => _missionLoaded = true);
  }

  // ── The session underneath ───────────────────────────────────────────────

  void _observe(ChildModeState state) {
    if (state.sessionId != null) _clock.observe(state.remainingSeconds);
  }

  bool _timeUp(ChildModeState state) {
    if (_switching) return false;
    final e = state.error;
    if (e == kChildModeBudgetSpent ||
        e == kChildModeOffline ||
        e == kChildModeErrorSessionExpired) {
      return true;
    }
    return state.sessionId != null && (state.remainingSeconds ?? 1) <= 0;
  }

  void _onSession(ChildModeState state) {
    if (!mounted) return;
    setState(() => _observe(state));
    if (state.error == kChildModeHandedBack) {
      if (_phase != CornerPhase.done) setState(() => _phase = CornerPhase.done);
      return;
    }
    if (_phase == CornerPhase.mission || _phase == CornerPhase.done) return;
    if (_timeUp(state)) _toMission('time');
  }

  /// Move the session to [surface]. False when the server would not: then the
  /// day's time is spent or the connection is gone, and the task is next.
  Future<bool> _switchTo(String surface) async {
    setState(() => _switching = true);
    final ok = await ref
        .read(childModeProvider.notifier)
        .switchSurface(surface);
    if (!mounted) return false;
    setState(() => _switching = false);
    if (!ok) _toMission('time');
    return ok;
  }

  // ── Steps ─────────────────────────────────────────────────────────────────

  Future<void> _openStory() async {
    final story = _story;
    if (story == null || _storyDone) return;
    unawaited(Analytics.childCornerPicked('story', story.id));
    if (!await _switchTo('story')) return;
    setState(() => _phase = CornerPhase.story);
  }

  void _storyClosed(bool finished) {
    setState(() {
      _phase = CornerPhase.home;
      if (finished) {
        _storyDone = true;
        _noor = _NoorSays.afterStory;
      }
    });
    _afterStep();
  }

  Future<void> _openGame() async {
    final game = _game;
    if (game == null || _gameDone) return;
    unawaited(Analytics.childCornerPicked('game', game.id));
    unawaited(Analytics.gameOpened(game.id, kChildCornerGameSource));
    if (!await _switchTo('game')) return;
    unawaited(
      Analytics.gameLevelStarted(game.id, _level, kChildCornerGameSource),
    );
    setState(() => _phase = CornerPhase.game);
  }

  /// The level's progress is kept — the next visit carries on from it — but
  /// nothing is credited: no coins, and no score shown anywhere.
  Future<void> _gameCompleted(EduGameResult result) async {
    final game = _game;
    if (game == null) return;
    unawaited(
      Analytics.gameCompleted(
        gameId: game.id,
        level: result.level,
        completed: result.completed,
        stars: result.stars,
        score: result.score,
        entryPoint: kChildCornerGameSource,
      ),
    );
    final service = EduGameProgressService.instance;
    final progress = await service.load(game.theme.id);
    await service.save(progress.recordGame(result.level, result));
  }

  void _gameLeft(EduGameResult? result) {
    setState(() {
      _phase = CornerPhase.home;
      // Once per visit, played out or not: the corner is short on purpose.
      _gameDone = true;
      if (result != null) _noor = _NoorSays.afterGame;
    });
    _afterStep();
  }

  /// Back in the corner: if the time ran out meanwhile, or there is nothing
  /// left before the task, the task is next.
  void _afterStep() {
    final state = ref.read(childModeProvider);
    if (_timeUp(state)) {
      _toMission('time');
      return;
    }
    final storyLeft = _story != null && !_storyDone;
    final gameLeft = _game != null && !_gameDone;
    if ((_storyDone || _gameDone) && !storyLeft && !gameLeft) {
      _toMission('all_done');
    }
  }

  void _toMission(String reason) {
    if (_phase == CornerPhase.mission || _phase == CornerPhase.done) return;
    if (reason == 'time') {
      _clock.burnOut();
      _noor = _NoorSays.timeUp;
    }
    setState(() => _phase = CornerPhase.mission);
    unawaited(Analytics.childCornerMission(reason));
    // Billed as the task while it is read. Refused when the day's time is
    // spent — the card is already here, so that changes nothing on screen.
    if (reason != 'time') {
      unawaited(ref.read(childModeProvider.notifier).switchSurface('mission'));
    }
  }

  Future<void> _goToTask() async {
    unawaited(Analytics.childCornerEnded(story: _storyDone, game: _gameDone));
    setState(() => _phase = CornerPhase.done);
    await ref.read(childModeProvider.notifier).handBack();
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  String _missionTitle(AppLocalizations l10n) {
    final title = _mission?['title_ar'];
    return title is String && title.trim().isNotEmpty
        ? title
        : l10n.childCornerMissionFallbackTitle;
  }

  String _missionBody(AppLocalizations l10n) {
    if (_mission == null) return l10n.childCornerMissionFallbackBody;
    final body = _mission?['instruction_ar'];
    return body is String ? body : '';
  }

  Widget _candle({bool compact = false}) {
    // Handed back, the session is over: no clock left to show.
    if (!_clock.known || _phase == CornerPhase.done) {
      return const SizedBox.shrink();
    }
    return CornerCandle(
      fraction: _clock.fraction,
      exitRitual: ref.read(childModeProvider).exitRitual,
      compact: compact,
    );
  }

  String _childName(AppLocalizations l10n) {
    try {
      final profile = ref.read(activeChildProfileProvider);
      final id = ref.read(childModeProvider).childId;
      if (profile != null && (id == null || profile.id == id)) {
        return profile.name;
      }
    } catch (_) {
      // Preferences not loaded: the generic name.
    }
    return l10n.childFallbackName;
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<ChildModeState>(
      childModeProvider,
      (_, next) => _onSession(next),
    );

    final Widget body = switch (_phase) {
      CornerPhase.story => CornerStoryView(
        key: const ValueKey('child_corner_story_view'),
        story: _story!,
        clock: _candle(compact: true),
        onClose: _storyClosed,
      ),
      CornerPhase.game => EduGameRunner(
        key: const ValueKey('child_corner_game_view'),
        theme: _game!.theme,
        level: _level,
        questions: _pack!.forLevel(_level),
        onComplete: (result) => unawaited(_gameCompleted(result)),
        quiet: true,
        onQuietLeave: _gameLeft,
        clock: Align(
          alignment: AlignmentDirectional.centerStart,
          child: _candle(compact: true),
        ),
      ),
      _ => _scene(context),
    };

    return PopScope(
      // The device goes back by hand, never by gesture. Back in a story is
      // "close the story"; in the game it pauses (the runner's own scope).
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && _phase == CornerPhase.story) _storyClosed(false);
      },
      child: Scaffold(
        backgroundColor: context.colors.corner.ground,
        body: AnimatedSwitcher(
          duration: const Duration(milliseconds: 250),
          child: KeyedSubtree(key: ValueKey(_phase), child: body),
        ),
      ),
    );
  }

  Widget _scene(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final paper = c.corner;

    final noorFace = switch (_phase) {
      CornerPhase.done => NoorFaceState.tender,
      _ when _noor == _NoorSays.afterStory || _noor == _NoorSays.afterGame =>
        NoorFaceState.happy,
      _ => NoorFaceState.calm,
    };
    // On the task Noor speaks only when there is something to say (the
    // candle ran out, or praise for what was just done); at the end the card
    // below says it all.
    final String? noorLine = switch (_noor) {
      _ when _phase == CornerPhase.done => null,
      _NoorSays.afterStory => l10n.childCornerNoorAfterStory,
      _NoorSays.afterGame => l10n.childCornerNoorAfterGame,
      _NoorSays.timeUp => l10n.childCornerTimeUp,
      _NoorSays.intro when _phase == CornerPhase.mission => null,
      _NoorSays.intro =>
        _game != null
            ? l10n.childCornerNoorLine
            : l10n.childCornerNoorLineNoGame,
    };

    final List<Widget> cards = switch (_phase) {
      CornerPhase.mission => [_missionStep(context)],
      CornerPhase.done => [_doneStep(context)],
      _ => [
        if (_story != null) ...[
          _ActivityCard(
            key: const ValueKey('child_corner_story'),
            glyph: BrandIcon.openBook,
            label: l10n.childCornerStoryLabel,
            title: _story!.title,
            titleDirection: _story!.language == 'en'
                ? TextDirection.ltr
                : TextDirection.rtl,
            hint: _storyDone
                ? l10n.childCornerStoryDone
                : l10n.childCornerStoryHint,
            done: _storyDone,
            onTap: _storyDone || _switching ? null : _openStory,
          ),
          const SizedBox(height: 16),
        ],
        if (_game != null) ...[
          _ActivityCard(
            key: const ValueKey('child_corner_game'),
            glyph: _game!.glyph,
            label: l10n.childCornerGameLabel,
            title: _game!.label(l10n),
            hint: _gameDone
                ? l10n.childCornerGameDone
                : l10n.childCornerGameHint,
            done: _gameDone,
            onTap: _gameDone || _switching ? null : _openGame,
          ),
          const SizedBox(height: 16),
        ],
        _missionTeaser(context),
      ],
    };

    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        key: const ValueKey('child_corner_scroll'),
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: constraints.maxHeight),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ColoredBox(
                color: paper.sky,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
                      child: _sky(context, noorFace, noorLine),
                    ),
                    const CornerHills(),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: cards,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// The sky: the greeting, the candle, and Noor's line.
  ///
  /// Side by side at normal sizes. When the type is large a row would squeeze
  /// each into a sliver and push the story below the fold, so Noor moves up
  /// beside the name, the candle sits under it, and Noor's line takes the
  /// full width.
  Widget _sky(BuildContext context, NoorFaceState face, String? noorLine) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final paper = context.colors.corner;
    final large = MediaQuery.textScalerOf(context).scale(10) > 13;

    final greeting = Semantics(
      header: true,
      child: Text(
        l10n.childCornerGreeting(_childName(l10n)),
        style: theme.textTheme.headlineSmall?.copyWith(
          color: paper.ink,
          fontWeight: FontWeight.w800,
          height: 1.35,
        ),
      ),
    );
    final Widget? line = noorLine == null
        ? null
        : CornerPaperCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Semantics(
              liveRegion: true,
              child: Text(
                noorLine,
                key: const ValueKey('child_corner_noor_line'),
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: paper.ink,
                  height: 1.55,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          );
    final candle = _candle();

    if (large) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: greeting),
              const SizedBox(width: 8),
              NoorPresence(size: 52, face: face),
            ],
          ),
          const SizedBox(height: 10),
          Align(alignment: AlignmentDirectional.centerStart, child: candle),
          if (line != null) ...[const SizedBox(height: 12), line],
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: greeting),
            const SizedBox(width: 8),
            Flexible(child: candle),
          ],
        ),
        const SizedBox(height: 14),
        Row(
          children: [
            NoorPresence(size: 64, face: face),
            const SizedBox(width: 12),
            if (line != null) Expanded(child: line),
          ],
        ),
      ],
    );
  }

  /// The corner's last card, always there: what comes after, and the way to
  /// it now.
  Widget _missionTeaser(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final paper = context.colors.corner;
    return CornerPaperCard(
      key: const ValueKey('child_corner_mission_card'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const ExcludeSemantics(
                child: BrandGlyph(BrandIcon.path, size: 36),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.childCornerMissionLabel,
                      style: theme.textTheme.labelLarge?.copyWith(
                        color: paper.ink.withValues(alpha: .8),
                      ),
                    ),
                    Text(
                      _missionLoaded ? _missionTitle(l10n) : '…',
                      style: theme.textTheme.titleMedium?.copyWith(
                        color: paper.ink,
                        fontWeight: FontWeight.w800,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Align(
            alignment: AlignmentDirectional.centerEnd,
            child: CornerGoldButton(
              key: const ValueKey('child_corner_to_mission'),
              label: l10n.childCornerToMission,
              onPressed: _switching ? null : () => _toMission('chosen'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _missionStep(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final paper = context.colors.corner;
    final body = _missionLoaded ? _missionBody(l10n) : '';
    return CornerPaperCard(
      key: const ValueKey('child_corner_mission_step'),
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const ExcludeSemantics(
            child: Center(child: BrandGlyph(BrandIcon.path, size: 56)),
          ),
          const SizedBox(height: 8),
          Text(
            l10n.childCornerMissionNow,
            textAlign: TextAlign.center,
            style: theme.textTheme.labelLarge?.copyWith(
              color: paper.ink.withValues(alpha: .8),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            _missionLoaded ? _missionTitle(l10n) : '…',
            textAlign: TextAlign.center,
            style: theme.textTheme.headlineSmall?.copyWith(
              color: paper.ink,
              fontWeight: FontWeight.w800,
              height: 1.4,
            ),
          ),
          if (body.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              body,
              textAlign: TextAlign.center,
              style: theme.textTheme.titleMedium?.copyWith(
                color: paper.ink,
                height: 1.6,
              ),
            ),
          ],
          if (_mission?['needs_outdoors'] == true) ...[
            const SizedBox(height: 8),
            Text(
              l10n.missionOutdoorsHint,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: paper.ink.withValues(alpha: .8),
              ),
            ),
          ],
          const SizedBox(height: 20),
          CornerGoldButton(
            key: const ValueKey('child_corner_mission_go'),
            label: l10n.childCornerMissionGo,
            onPressed: _missionLoaded ? _goToTask : null,
          ),
        ],
      ),
    );
  }

  Widget _doneStep(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final paper = context.colors.corner;
    return CornerPaperCard(
      key: const ValueKey('child_corner_done'),
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            l10n.childCornerDoneMission(_missionTitle(l10n)),
            textAlign: TextAlign.center,
            style: theme.textTheme.titleMedium?.copyWith(
              color: paper.ink,
              height: 1.6,
            ),
          ),
          const SizedBox(height: 16),
          Semantics(
            liveRegion: true,
            child: Text(
              l10n.childReturnDevice,
              textAlign: TextAlign.center,
              style: theme.textTheme.titleLarge?.copyWith(
                color: paper.ink,
                fontWeight: FontWeight.w800,
                height: 1.6,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// A story or game card in the valley.
class _ActivityCard extends StatelessWidget {
  const _ActivityCard({
    super.key,
    required this.glyph,
    required this.label,
    required this.title,
    required this.hint,
    required this.done,
    required this.onTap,
    this.titleDirection,
  });

  final BrandIcon glyph;
  final String label;
  final String title;
  final String hint;
  final bool done;
  final VoidCallback? onTap;
  final TextDirection? titleDirection;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final paper = context.colors.corner;
    Widget titleText = Text(
      title,
      style: theme.textTheme.titleMedium?.copyWith(
        color: paper.ink,
        fontWeight: FontWeight.w800,
        height: 1.4,
      ),
    );
    if (titleDirection != null) {
      titleText = Directionality(
        textDirection: titleDirection!,
        child: titleText,
      );
    }
    return CornerPaperCard(
      onTap: onTap,
      child: Row(
        children: [
          ExcludeSemantics(child: BrandGlyph(glyph, size: 40)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: paper.ink.withValues(alpha: .8),
                  ),
                ),
                titleText,
                const SizedBox(height: 2),
                Row(
                  children: [
                    if (done) ...[
                      const ExcludeSemantics(
                        child: BrandGlyph(BrandIcon.star, size: 16),
                      ),
                      const SizedBox(width: 6),
                    ],
                    Flexible(
                      child: Text(
                        hint,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: paper.ink.withValues(alpha: .85),
                          fontWeight: done ? FontWeight.w700 : null,
                        ),
                      ),
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
}
