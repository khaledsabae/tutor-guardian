/// The story reader — «ورق مقصوص» (2026-10, docs/STORIES_AUDIT.md).
///
/// A story is a short stack of paper leaves:
///
///   1. Noor's opening leaf — the cover scene, the title, and two ways in:
///      «اسمعها من نور» (only when a recording exists) or «نقرؤها معًا»;
///   2. the story's pages — a drawn scene of layered paper above large text;
///      while a recording plays, the sentence being heard is lit;
///   3. «وقفة مع نور» after the page the story names — the child picks what
///      they would do, and nothing is graded;
///   4. the end leaf — the story's anchor text, questions to talk about, and
///      its challenge, kept as a promise through «سأجرّبها» like a lesson's.
///
/// What it deliberately is not: no music and no ambient soundtrack (a soft
/// paper sound on a turn is the only sound effect — Khaled's standing rule),
/// no gate in front of the story (the bedtime adhkar are offered at the end,
/// not demanded at the start), and no network video.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../core/haptics.dart';
import '../../../core/motion.dart';
import '../../../core/sound_fx.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_colors.dart';
import '../../child_memory/data/placeholder_names.dart';
import '../../companion/providers/companion_providers.dart';
import '../../companion/widgets/noor_face.dart';
import '../../companion/widgets/noor_presence.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../../screen_off/narration_store.dart';
import '../../stories/living/living_picture.dart';
import '../../stories/living/living_picture_catalog.dart';
import '../../../state/chat_notifier.dart' show tgClientProvider;
import '../../stories/experiment/story_experiment.dart';
import '../../stories/experiment/story_rating_card.dart';
import '../../stories/living/story_cover.dart';
import '../../stories/narration/story_narration.dart';
import '../../stories/narration/word_cues.dart';
import '../../stories/scene/story_scene.dart';
import '../../stories/scene/story_scene_catalog.dart';
import '../data/story_models.dart';
import '../providers/progress_providers.dart';
import '../services/bedtime_audio_service.dart';
import '../widgets/next_step_sheet.dart';

/// Text sizes the reader cycles through, on top of the system's own scale.
const kStoryTextSizes = [1.0, 1.18, 1.36];

/// One leaf of the reader.
sealed class StoryLeaf {
  const StoryLeaf();
}

class IntroLeaf extends StoryLeaf {
  const IntroLeaf();
}

class PageLeaf extends StoryLeaf {
  const PageLeaf(this.index);

  /// 0-based index into `story.pages`.
  final int index;
}

class PauseLeaf extends StoryLeaf {
  const PauseLeaf(this.pause);
  final StoryPause pause;
}

class EndLeaf extends StoryLeaf {
  const EndLeaf();
}

/// The leaves of [story], in reading order. Pure, so the order is testable.
List<StoryLeaf> storyLeaves(Story story) {
  final pause = story.pause;
  final pauseAfter = pause == null
      ? -1
      : story.pages.indexWhere((p) => p.pageNumber == pause.afterPage);
  return [
    const IntroLeaf(),
    for (var i = 0; i < story.pages.length; i++) ...[
      PageLeaf(i),
      if (i == pauseAfter && i < story.pages.length - 1) PauseLeaf(pause!),
    ],
    const EndLeaf(),
  ];
}

class StoryReaderScreen extends ConsumerStatefulWidget {
  const StoryReaderScreen({
    super.key,
    required this.story,
    this.narrationLoader = loadNarration,
    this.playerFactory,
    this.motionArm,
    this.storyEvents,
  });

  final Story story;
  final NarrationLoader narrationLoader;

  /// Null → just_audio. Tests hand in a fake.
  final NarrationPlayerFactory? playerFactory;

  /// The «صورة حيّة» arm (`motion` / `static`). Null → this device's arm
  /// (story_experiment.dart). Tests pin one.
  final String? motionArm;

  /// Where the experiment's events go. Null → GA4 + the backend.
  final StoryEventSink? storyEvents;

  @override
  ConsumerState<StoryReaderScreen> createState() => StoryReaderScreenState();
}

class StoryReaderScreenState extends ConsumerState<StoryReaderScreen> {
  late final List<StoryLeaf> _leaves = storyLeaves(widget.story);
  final PageController _pager = PageController();

  int _leaf = 0;
  int _textSize = 0;

  StoryNarration? _narration;
  NarrationPlayer? _player;
  StreamSubscription<Duration>? _positionSub;
  StreamSubscription<void>? _completedSub;

  /// The reader is in «اسمعها من نور»: pages play, and turn when they end.
  bool _listening = false;
  bool _playing = false;
  int? _sentence;

  /// The page recording's position, for a living picture to follow — fed
  /// only once the current leaf's recording has loaded ([_clockLeaf]), so a
  /// position left over from the page before never reaches the new page.
  final ValueNotifier<Duration> _clock = ValueNotifier(Duration.zero);
  int? _clockLeaf;

  /// A leaf whose recording would not load: its picture stops following.
  int? _silentLeaf;
  final Map<int, List<WordCue>> _cues = {};

  int? _pauseChoice;
  int _questionsShown = 2;
  bool _tried = false;
  String? _parentRecording;

  @visibleForTesting
  int get leaf => _leaf;
  @visibleForTesting
  bool get listening => _listening;
  @visibleForTesting
  int? get litSentence => _sentence;
  @visibleForTesting
  List<StoryLeaf> get leaves => _leaves;

  List<String> get _pageTexts => [for (final p in widget.story.pages) p.text];

  bool get _canListen => _narration?.covers(_pageTexts) ?? false;

  // ── «صورة حيّة» experiment ─────────────────────────────────────────────
  /// This device's arm, once known; until then the picture keeps still and
  /// events wait in [_pendingEvents].
  String? _arm;
  final List<(String, Map<String, Object?>)> _pendingEvents = [];
  late final StoryEventSink _events =
      widget.storyEvents ?? storyEventsTo(ref.read(tgClientProvider));
  bool _finished = false;
  int? _lastPage;

  @visibleForTesting
  String? get motionArm => _arm;

  bool get _pictureMoves => _arm == 'motion';

  /// dispose() may not read the context; the last value it had is kept.
  bool _reduceMotionAtClose = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduceMotionAtClose = reduceMotion(context);
  }

  void _event(String name, {int? page, int? rating}) {
    final params = <String, Object?>{
      'story_id': widget.story.id,
      'lang': widget.story.language,
      'narration_on': _listening,
      'reduce_motion': reduceMotion(context),
      'page_index': ?page,
      'rating': ?rating,
    };
    if (_arm == null) {
      _pendingEvents.add((name, params));
    } else {
      _events(name, {...params, 'variant': _arm});
    }
  }

  Future<void> _resolveArm() async {
    String arm;
    try {
      arm = widget.motionArm ?? await ref.read(storyMotionArmProvider.future);
    } catch (_) {
      arm = 'static';
    }
    if (!mounted) return;
    setState(() => _arm = arm);
    for (final (name, params) in _pendingEvents) {
      _events(name, {...params, 'variant': arm});
    }
    _pendingEvents.clear();
  }

  @override
  void initState() {
    super.initState();
    StoryWakeLock.keepAwake();
    unawaited(_loadNarration());
    unawaited(_findParentRecording());
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _event('story_opened');
      unawaited(_resolveArm());
    });
  }

  Future<void> _loadNarration() async {
    final n = await widget.narrationLoader(
      widget.story.id,
      widget.story.language,
    );
    if (!mounted || n == null) return;
    setState(() => _narration = n);
  }

  Future<void> _findParentRecording() async {
    try {
      final found = await NarrationStore.instance.find(
        narrationKeyFor(widget.story.id),
      );
      if (mounted && found != null) {
        setState(() => _parentRecording = found.path);
      }
    } catch (_) {
      // No recordings store (tests, a first run): nothing to offer.
    }
  }

  @override
  void dispose() {
    if (!_finished && _arm != null) {
      _events('story_closed_early', {
        'story_id': widget.story.id,
        'lang': widget.story.language,
        'narration_on': _listening,
        'reduce_motion': _reduceMotionAtClose,
        'page_index': _lastPage,
        'variant': _arm,
      });
    }
    _positionSub?.cancel();
    _completedSub?.cancel();
    unawaited(_player?.dispose());
    _clock.dispose();
    _pager.dispose();
    StoryWakeLock.allowSleep();
    super.dispose();
  }

  // ── turning ───────────────────────────────────────────────────────────
  void goTo(int leaf) {
    if (leaf < 0 || leaf >= _leaves.length) return;
    if (!_pager.hasClients) return;
    if (reduceMotion(context)) {
      _pager.jumpToPage(leaf);
    } else {
      _pager.animateToPage(
        leaf,
        duration: const Duration(milliseconds: 520),
        curve: Curves.easeInOutCubic,
      );
    }
  }

  void _onLeafChanged(int leaf) {
    setState(() {
      _leaf = leaf;
      _sentence = null;
    });
    final l = _leaves[leaf];
    if (l is PageLeaf) {
      _lastPage = l.index;
      _event('story_page_viewed', page: l.index);
    } else if (l is EndLeaf && !_finished) {
      _finished = true;
      _event('story_finished', page: _lastPage);
    }
    _clockLeaf = null;
    _clock.value = Duration.zero;
    unawaited(SoundFx.page());
    unawaited(_playCurrent());
  }

  // ── narration ─────────────────────────────────────────────────────────
  NarrationPage? _recordingFor(int leaf) {
    final l = _leaves[leaf];
    if (l is! PageLeaf) return null;
    return _narration?.pageFor(l.index, widget.story.pages[l.index].text);
  }

  NarrationPlayer _ensurePlayer() {
    final existing = _player;
    if (existing != null) return existing;
    final p = (widget.playerFactory ?? JustAudioNarrationPlayer.new)();
    _positionSub = p.position.listen((pos) {
      final rec = _recordingFor(_leaf);
      final s = rec?.sentenceAt(pos);
      if (_clockLeaf == _leaf) _clock.value = pos;
      if (mounted && s != _sentence) setState(() => _sentence = s);
    });
    _completedSub = p.completed.listen((_) => _onPageHeard());
    return _player = p;
  }

  Future<void> _playCurrent() async {
    final rec = _recordingFor(_leaf);
    if (!_listening || rec == null) {
      if (_playing) {
        await _player?.stop();
        if (mounted) setState(() => _playing = false);
      }
      return;
    }
    final player = _ensurePlayer();
    final leafAtStart = _leaf;
    try {
      await player.load(rec.uri);
      if (!mounted || _leaf != leafAtStart || !_listening) return;
      _clock.value = Duration.zero;
      _clockLeaf = leafAtStart;
      await player.play();
      if (mounted) setState(() => _playing = true);
    } catch (_) {
      // A page that will not load is skipped in silence; the text is there.
      if (mounted) {
        setState(() {
          _playing = false;
          _silentLeaf = leafAtStart;
        });
      }
    }
  }

  void _onPageHeard() {
    if (!mounted) return;
    setState(() {
      _playing = false;
      _sentence = null;
    });
    if (!_listening) return;
    final heard = _leaf;
    Future.delayed(const Duration(milliseconds: 900), () {
      if (!mounted || !_listening || _leaf != heard) return;
      // A recording carries the child to the next leaf — but never past the
      // pause: that question is the child's to answer, not the narrator's.
      if (heard + 1 < _leaves.length && _leaves[heard + 1] is PageLeaf) {
        goTo(heard + 1);
      } else if (heard + 1 < _leaves.length) {
        goTo(heard + 1);
        setState(() => _listening = _leaves[heard + 1] is! EndLeaf);
      }
    });
  }

  Future<void> _toggleListening() async {
    if (!_canListen) return;
    unawaited(Haptics.selection());
    if (_listening && _playing) {
      await _player?.pause();
      setState(() {
        _listening = false;
        _playing = false;
      });
      return;
    }
    setState(() => _listening = true);
    if (_leaves[_leaf] is IntroLeaf) {
      goTo(1);
    } else {
      await _playCurrent();
    }
  }

  void _startReading({required bool listen}) {
    setState(() => _listening = listen && _canListen);
    if (_leaf == 1) {
      unawaited(_playCurrent());
    } else {
      goTo(1);
    }
  }

  // ── the end leaf's actions ────────────────────────────────────────────
  Future<void> _tryChallenge(String challenge) async {
    final childId = ref.read(activeChildIdProvider);
    if (childId == null) return;
    unawaited(Haptics.selection());
    final l10n = AppLocalizations.of(context);
    final name = _childName();
    final slot = await showNextStepSheet(
      context,
      tryThis: challenge,
      childName: name == null || isDefaultChildName(name)
          ? l10n.noorYourChild
          : name,
    );
    if (slot == null || !mounted) return;
    setState(() => _tried = true);
    unawaited(
      ref
          .read(companionMemoryProvider.notifier)
          .keepPromise(
            childId: childId,
            step: challenge,
            slot: slot,
            source: 'story',
          ),
    );
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(l10n.promiseSaved)));
  }

  /// The active child's name, or null (none yet, or preferences not loaded).
  String? _childName() {
    try {
      return ref.read(activeChildProfileProvider)?.name;
    } catch (_) {
      return null;
    }
  }

  Future<void> _recordNarration() async {
    final saved = await Navigator.of(context).push(
      AppRoutes.recordNarration(
        storyKey: narrationKeyFor(widget.story.id),
        storyText: _pageTexts.join('\n\n'),
      ),
    );
    if (saved == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context).storyNarrationSaved),
        ),
      );
      unawaited(_findParentRecording());
    }
  }

  void _listenInParentVoice() {
    final path = _parentRecording;
    if (path == null) return;
    Navigator.of(
      context,
    ).push(AppRoutes.screenOffPlayer(title: widget.story.title, source: path));
  }

  // ── build ─────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final l10n = AppLocalizations.of(context);
    final storyDir = directionOfLanguage(widget.story.language);
    final appDir = Directionality.of(context);

    return Scaffold(
      backgroundColor: colors.background,
      body: SafeArea(
        child: Column(
          children: [
            _TopBar(
              title: widget.story.title,
              language: widget.story.language,
              canListen: _canListen && _leaves[_leaf] is PageLeaf,
              playing: _listening && _playing,
              onListen: _toggleListening,
              onTextSize: () => setState(
                () => _textSize = (_textSize + 1) % kStoryTextSizes.length,
              ),
            ),
            Expanded(
              child: Directionality(
                // Pages turn the way the story's language reads.
                textDirection: storyDir,
                child: PageView.builder(
                  controller: _pager,
                  itemCount: _leaves.length,
                  onPageChanged: _onLeafChanged,
                  itemBuilder: (context, i) => AnimatedBuilder(
                    animation: _pager,
                    builder: (context, child) {
                      final page =
                          _pager.hasClients && _pager.position.haveDimensions
                          ? (_pager.page ?? _leaf.toDouble())
                          : _leaf.toDouble();
                      return _PaperTurn(
                        offset: i - page,
                        rtl: storyDir == TextDirection.rtl,
                        child: _buildLeaf(i, i - page, appDir),
                      );
                    },
                  ),
                ),
              ),
            ),
            _BottomBar(
              leaf: _leaf,
              leafCount: _leaves.length,
              pageLabel: switch (_leaves[_leaf]) {
                PageLeaf(:final index) => l10n.storyPageOf(
                  index + 1,
                  widget.story.pages.length,
                ),
                _ => null,
              },
              onPrev: _leaf > 0 ? () => goTo(_leaf - 1) : null,
              onNext: _leaf < _leaves.length - 1 ? () => goTo(_leaf + 1) : null,
            ),
          ],
        ),
      ),
    );
  }

  /// The narrator for a living picture on leaf [i] to follow — while one is
  /// reading it, and only then.
  LivingCues? _livingCuesFor(int i, int page) {
    if (i != _leaf || !_listening || _silentLeaf == i) return null;
    final picture = livingPictureFor(widget.story.id, page);
    final rec = _recordingFor(i);
    if (picture == null || rec == null) return null;
    final cues = _cues[page] ??= wordCuesFor(
      [for (final r in picture.regions) r.cue],
      rec.text,
      rec.sentences,
    );
    return cues.isEmpty ? null : LivingCues(cues: cues, clock: _clock);
  }

  Widget _buildLeaf(int i, double offset, TextDirection appDir) {
    final leaf = _leaves[i];
    final view = switch (leaf) {
      IntroLeaf() => _IntroLeafView(
        story: widget.story,
        canListen: _canListen,
        hasParentRecording: _parentRecording != null,
        onListen: () => _startReading(listen: true),
        onRead: () => _startReading(listen: false),
        onRecord: _recordNarration,
        onParentVoice: _listenInParentVoice,
      ),
      PageLeaf(:final index) => _StoryPageView(
        story: widget.story,
        index: index,
        parallax: offset,
        livingCues: _pictureMoves ? _livingCuesFor(i, index) : null,
        pictureMoves: _pictureMoves,
        textScale: kStoryTextSizes[_textSize],
        recording: i == _leaf ? _recordingFor(i) : null,
        litSentence: i == _leaf ? _sentence : null,
      ),
      PauseLeaf(:final pause) => _PauseLeafView(
        pause: pause,
        language: widget.story.language,
        choice: _pauseChoice,
        onChoose: (c) {
          unawaited(Haptics.selection());
          setState(() => _pauseChoice = c);
        },
        onChooseAgain: () => setState(() => _pauseChoice = null),
        onContinue: () {
          setState(() => _listening = _listening && _canListen);
          goTo(i + 1);
        },
      ),
      EndLeaf() => _EndLeafView(
        story: widget.story,
        rating: StoryRatingCard(
          storyId: widget.story.id,
          onRated: (r) => _event('story_rated', rating: r, page: _lastPage),
        ),
        childName: _childName(),
        questionsShown: _questionsShown,
        onMoreQuestion: () => setState(() => _questionsShown++),
        canTry: ref.watch(activeChildIdProvider) != null,
        tried: _tried,
        onTry: _tryChallenge,
        onAdhkar: () => Navigator.of(context).push(AppRoutes.bedtimeAdhkar()),
        onAnother: () => Navigator.of(context).maybePop(),
        onInvite: () {
          unawaited(Analytics.prideInviteTapped('story_end'));
          Navigator.of(context).push(AppRoutes.invite());
        },
      ),
    };
    // Noor's leaves are the app speaking, in the app's direction; a page is
    // the story's, and the PageView around it already reads that way.
    return leaf is PageLeaf
        ? view
        : Directionality(textDirection: appDir, child: view);
  }
}

/// A leaf leans like turning paper while it is between rest positions.
class _PaperTurn extends StatelessWidget {
  const _PaperTurn({
    required this.offset,
    required this.rtl,
    required this.child,
  });

  /// This leaf's distance from rest: 0 at rest, ±1 a full leaf away.
  final double offset;
  final bool rtl;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (reduceMotion(context) || offset.abs() < .001) return child;
    final d = offset.clamp(-1.0, 1.0);
    // The leaf hinges on the edge nearest the spine — the side it is
    // leaving towards — and dims as it folds.
    final towardsEnd = (d < 0) != rtl;
    return Opacity(
      opacity: (1 - d.abs() * .35).clamp(0.0, 1.0),
      child: Transform(
        alignment: towardsEnd ? Alignment.centerRight : Alignment.centerLeft,
        transform: Matrix4.identity()
          ..setEntry(3, 2, .0012)
          ..rotateY((rtl ? -d : d) * .55),
        child: child,
      ),
    );
  }
}

/// A living painted page, framed like the scene card.
class _LivingCard extends StatelessWidget {
  const _LivingCard({
    required this.picture,
    this.cues,
    this.fallback,
    this.moves = true,
  });

  final LivingPicture picture;
  final LivingCues? cues;
  final Widget? fallback;
  final bool moves;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        boxShadow: [
          BoxShadow(color: colors.paperShadow, offset: const Offset(4, 5)),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(22),
        child: LivingPictureView(
          picture: picture,
          cues: cues,
          animate: moves,
          fallback: fallback,
        ),
      ),
    );
  }
}

/// The scene, framed as a paper card on its solid offset shadow.
class _SceneCard extends StatelessWidget {
  const _SceneCard({
    required this.scene,
    this.parallax = 0,
    this.heroTag,
    this.label,
    this.coverOf,
  });

  final StoryScene scene;
  final double parallax;

  /// Show this story's painted cover when it has one (story_cover.dart).
  final String? coverOf;
  final String? heroTag;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    Widget card = DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        boxShadow: [
          BoxShadow(color: colors.paperShadow, offset: const Offset(4, 5)),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(22),
        child: coverOf == null
            ? StorySceneView(
                scene: scene,
                parallax: parallax,
                semanticLabel: label,
              )
            : Semantics(
                image: true,
                label: label,
                child: StoryCoverPicture(
                  storyId: coverOf!,
                  fallback: StorySceneView(scene: scene, parallax: parallax),
                ),
              ),
      ),
    );
    if (heroTag != null) card = Hero(tag: heroTag!, child: card);
    return card;
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.title,
    required this.language,
    required this.canListen,
    required this.playing,
    required this.onListen,
    required this.onTextSize,
  });

  final String title;
  final String language;
  final bool canListen;
  final bool playing;
  final VoidCallback onListen;
  final VoidCallback onTextSize;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Padding(
      padding: const EdgeInsetsDirectional.fromSTEB(4, 4, 8, 0),
      child: Row(
        children: [
          IconButton(
            tooltip: l10n.storyClose,
            icon: const Icon(Icons.close_rounded),
            color: colors.ink,
            onPressed: () => Navigator.of(context).maybePop(),
          ),
          Expanded(
            child: ContentDirectionality(
              languageCode: language,
              text: title,
              child: Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: colors.ink,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ),
          if (canListen)
            IconButton(
              tooltip: playing ? l10n.storyPauseListening : l10n.storyListen,
              icon: Icon(
                playing ? Icons.pause_circle_rounded : Icons.headphones_rounded,
              ),
              color: colors.primary,
              onPressed: onListen,
            ),
          IconButton(
            tooltip: l10n.storyTextSize,
            icon: const Icon(Icons.format_size_rounded),
            color: colors.ink,
            onPressed: onTextSize,
          ),
        ],
      ),
    );
  }
}

class _BottomBar extends StatelessWidget {
  const _BottomBar({
    required this.leaf,
    required this.leafCount,
    required this.pageLabel,
    required this.onPrev,
    required this.onNext,
  });

  final int leaf;
  final int leafCount;
  final String? pageLabel;
  final VoidCallback? onPrev;
  final VoidCallback? onNext;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 10),
      child: Row(
        children: [
          IconButton.filledTonal(
            tooltip: l10n.storyPrevPage,
            onPressed: onPrev,
            icon: const Icon(Icons.arrow_back_rounded),
          ),
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _LeafDots(leaf: leaf, count: leafCount),
                if (pageLabel != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    pageLabel!,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: colors.textSecondary,
                      fontSize: 12.5,
                    ),
                  ),
                ],
              ],
            ),
          ),
          IconButton.filled(
            tooltip: l10n.storyNextPage,
            onPressed: onNext,
            icon: const Icon(Icons.arrow_forward_rounded),
          ),
        ],
      ),
    );
  }
}

class _LeafDots extends StatelessWidget {
  const _LeafDots({required this.leaf, required this.count});
  final int leaf;
  final int count;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return ExcludeSemantics(
      child: Wrap(
        alignment: WrapAlignment.center,
        spacing: 5,
        runSpacing: 4,
        children: [
          for (var i = 0; i < count; i++)
            AnimatedContainer(
              duration: const Duration(milliseconds: 220),
              width: i == leaf ? 18 : 7,
              height: 7,
              decoration: BoxDecoration(
                color: i == leaf ? colors.primary : colors.track,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
        ],
      ),
    );
  }
}

/// A rounded paper sheet for text: the live surface, so dark mode is dark.
class _Sheet extends StatelessWidget {
  const _Sheet({required this.child, this.padding = const EdgeInsets.all(18)});
  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: colors.track),
        boxShadow: [BoxShadow(color: colors.track, offset: const Offset(3, 4))],
      ),
      child: child,
    );
  }
}

class _IntroLeafView extends StatelessWidget {
  const _IntroLeafView({
    required this.story,
    required this.canListen,
    required this.hasParentRecording,
    required this.onListen,
    required this.onRead,
    required this.onRecord,
    required this.onParentVoice,
  });

  final Story story;
  final bool canListen;
  final bool hasParentRecording;
  final VoidCallback onListen;
  final VoidCallback onRead;
  final VoidCallback onRecord;
  final VoidCallback onParentVoice;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 8, 18, 24),
      children: [
        // The picture leads, but never pushes the two ways in off a short
        // screen: at most about a third of the height.
        Center(
          child: SizedBox(
            width: math.min(
              MediaQuery.sizeOf(context).width,
              MediaQuery.sizeOf(context).height * .32 * kSceneAspect,
            ),
            child: _SceneCard(
              scene: coverSceneFor(story.id),
              coverOf: story.id,
              heroTag: 'story-cover-${story.id}',
              label: story.title,
            ),
          ),
        ),
        const SizedBox(height: 18),
        ContentDirectionality(
          languageCode: story.language,
          text: story.title,
          child: Text(
            story.title,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              color: colors.ink,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        if (story.ageGroup != null || story.category != null) ...[
          const SizedBox(height: 8),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            runSpacing: 6,
            children: [
              for (final t in [story.category, story.ageGroup])
                if (t != null && t.isNotEmpty)
                  _Tag(text: t, language: story.language),
            ],
          ),
        ],
        const SizedBox(height: 18),
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const NoorPresence(size: 56, face: NoorFaceState.calm),
            const SizedBox(width: 12),
            Expanded(
              child: _Sheet(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 12,
                ),
                child: Text(
                  l10n.storyNoorIntro,
                  style: TextStyle(
                    color: colors.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    height: 1.5,
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 18),
        if (canListen) ...[
          FilledButton.icon(
            onPressed: onListen,
            icon: const Icon(Icons.headphones_rounded),
            label: Text(l10n.storyListenWithNoor),
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(52),
            ),
          ),
          const SizedBox(height: 10),
        ],
        (canListen ? OutlinedButton.icon : FilledButton.icon)(
          onPressed: onRead,
          icon: const Icon(Icons.menu_book_rounded),
          label: Text(l10n.storyReadTogether),
          style: ButtonStyle(
            minimumSize: WidgetStateProperty.all(const Size.fromHeight(52)),
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          alignment: WrapAlignment.center,
          children: [
            TextButton.icon(
              onPressed: onRecord,
              icon: const Icon(Icons.mic_none_rounded),
              label: Text(l10n.storyRecordInYourVoice),
            ),
            if (hasParentRecording)
              TextButton.icon(
                onPressed: onParentVoice,
                icon: const Icon(Icons.record_voice_over_rounded),
                label: Text(l10n.storyListenInParentVoice),
              ),
          ],
        ),
      ],
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag({required this.text, required this.language});
  final String text;
  final String language;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      decoration: BoxDecoration(
        color: colors.surfaceAlt,
        borderRadius: BorderRadius.circular(14),
      ),
      child: ContentDirectionality(
        languageCode: language,
        text: text,
        child: Text(
          text,
          style: TextStyle(
            color: colors.textSecondary,
            fontSize: 12.5,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _StoryPageView extends StatelessWidget {
  const _StoryPageView({
    required this.story,
    required this.index,
    required this.parallax,
    required this.textScale,
    required this.recording,
    required this.litSentence,
    this.livingCues,
    this.pictureMoves = true,
  });

  final Story story;
  final int index;
  final double parallax;
  final LivingCues? livingCues;

  /// The «صورة حيّة» arm: false → the same painting, still.
  final bool pictureMoves;
  final double textScale;
  final NarrationPage? recording;
  final int? litSentence;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = story.pages[index].text;
    final style = TextStyle(
      fontSize: 20 * textScale,
      height: 1.85,
      fontWeight: FontWeight.w600,
      color: colors.ink,
    );
    final lit = litSentence == null || recording == null
        ? null
        : recording!.sentences[litSentence!];
    final span = lit == null
        ? TextSpan(text: text, style: style)
        : TextSpan(
            style: style,
            children: [
              TextSpan(text: text.substring(0, lit.from)),
              TextSpan(
                text: text.substring(lit.from, lit.to),
                style: TextStyle(
                  backgroundColor: colors.paperGold.withValues(
                    alpha: colors.isDark ? .28 : .45,
                  ),
                ),
              ),
              TextSpan(text: text.substring(lit.to)),
            ],
          );
    // Large text (the system's, or the reader's own size button) needs the
    // room more than the picture does.
    final bigText =
        MediaQuery.textScalerOf(context).scale(1) * textScale > 1.25;
    return LayoutBuilder(
      builder: (context, box) {
        final living = livingPictureFor(story.id, index);
        final sceneWidth = living != null
            // The painted pages are square: give them the room.
            ? math.min(box.maxWidth - 32, box.maxHeight * (bigText ? .3 : .52))
            : math.min(
                box.maxWidth - 32,
                box.maxHeight * (bigText ? .26 : .46) * kSceneAspect,
              );
        return Column(
          children: [
            const SizedBox(height: 6),
            SizedBox(
              width: sceneWidth,
              child: living != null
                  ? _LivingCard(
                      picture: living,
                      cues: livingCues,
                      moves: pictureMoves,
                      // Offline, or a server without the painting: the
                      // page's paper-cut scene.
                      fallback: StorySceneView(
                        scene: sceneFor(story.id, index),
                      ),
                    )
                  : _SceneCard(
                      scene: sceneFor(story.id, index),
                      parallax: parallax,
                    ),
            ),
            const SizedBox(height: 14),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
                child: _Sheet(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
                  child: SingleChildScrollView(
                    child: ContentDirectionality(
                      languageCode: story.language,
                      text: text,
                      child: Text.rich(
                        span,
                        key: ValueKey('story-text-$index'),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _PauseLeafView extends StatelessWidget {
  const _PauseLeafView({
    required this.pause,
    required this.language,
    required this.choice,
    required this.onChoose,
    required this.onChooseAgain,
    required this.onContinue,
  });

  final StoryPause pause;
  final String language;
  final int? choice;
  final ValueChanged<int> onChoose;
  final VoidCallback onChooseAgain;
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final picked = choice;
    final nudged = picked != null && pause.nudges(picked);
    final reply = picked == null ? null : pause.replyTo(picked);
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      children: [
        Center(
          child: NoorPresence(
            size: 96,
            // Thinking while the child decides; tender when Noor gently asks
            // them to think again; happy at a caring choice.
            face: picked == null
                ? NoorFaceState.thinking
                : nudged
                ? NoorFaceState.tender
                : NoorFaceState.happy,
          ),
        ),
        const SizedBox(height: 14),
        Text(
          l10n.storyPauseTitle,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            color: colors.primary,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 10),
        ContentDirectionality(
          languageCode: language,
          text: pause.question,
          child: Text(
            pause.question,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: colors.ink,
              fontSize: 21,
              height: 1.6,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(height: 18),
        for (var i = 0; i < pause.options.length; i++) ...[
          _ChoiceButton(
            text: pause.options[i],
            language: language,
            selected: choice == i,
            onTap: () => onChoose(i),
          ),
          const SizedBox(height: 10),
        ],
        if (picked != null) ...[
          const SizedBox(height: 6),
          ContentDirectionality(
            languageCode: reply == null ? l10n.localeName : language,
            text: reply ?? l10n.storyPauseThanks,
            child: Text(
              reply ?? l10n.storyPauseThanks,
              key: const ValueKey('story-pause-reply'),
              textAlign: TextAlign.center,
              style: TextStyle(
                color: colors.ink,
                fontSize: 17,
                height: 1.6,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(height: 14),
          // Never a wall: after a nudge the child may choose again, or simply
          // read on and let the story show what its hero did.
          if (nudged) ...[
            OutlinedButton.icon(
              onPressed: onChooseAgain,
              icon: const Icon(Icons.replay_rounded),
              label: Text(l10n.storyPauseChooseAgain),
              style: OutlinedButton.styleFrom(
                minimumSize: const Size.fromHeight(48),
              ),
            ),
            const SizedBox(height: 10),
          ],
          FilledButton.icon(
            onPressed: onContinue,
            icon: const Icon(Icons.auto_stories_rounded),
            label: Text(l10n.storyContinue),
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(50),
            ),
          ),
        ],
      ],
    );
  }
}

class _ChoiceButton extends StatelessWidget {
  const _ChoiceButton({
    required this.text,
    required this.language,
    required this.selected,
    required this.onTap,
  });

  final String text;
  final String language;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Semantics(
      button: true,
      selected: selected,
      child: Material(
        color: selected ? colors.primary : colors.surface,
        borderRadius: BorderRadius.circular(18),
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: Border.all(
                color: selected ? colors.primary : colors.track,
                width: 2,
              ),
            ),
            child: ContentDirectionality(
              languageCode: language,
              text: text,
              child: Text(
                text,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: selected ? colors.onPrimary : colors.ink,
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  height: 1.4,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _EndLeafView extends StatelessWidget {
  const _EndLeafView({
    required this.story,
    required this.questionsShown,
    required this.onMoreQuestion,
    required this.canTry,
    required this.tried,
    required this.onTry,
    required this.onAdhkar,
    required this.onAnother,
    required this.onInvite,
    this.childName,
    this.rating,
  });

  final Story story;
  final String? childName;

  /// «هل أعجبتك الحكاية؟» (story_rating_card.dart), first on the leaf.
  final Widget? rating;
  final int questionsShown;
  final VoidCallback onMoreQuestion;
  final bool canTry;
  final bool tried;
  final ValueChanged<String> onTry;
  final VoidCallback onAdhkar;
  final VoidCallback onAnother;
  final VoidCallback onInvite;

  Widget _heading(BuildContext context, IconData icon, String text) {
    final colors = context.colors;
    return Row(
      children: [
        Icon(icon, size: 20, color: colors.primary),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            style: TextStyle(
              color: colors.primary,
              fontSize: 15,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ],
    );
  }

  Widget _content(BuildContext context, String text, {double size = 16}) {
    final colors = context.colors;
    return ContentDirectionality(
      languageCode: story.language,
      text: text,
      child: Text(
        text,
        style: TextStyle(
          color: colors.ink,
          fontSize: size,
          height: 1.6,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final questions = story.discussionQuestions;
    final value = story.islamicValue;
    final challenge = story.actionChallenge;
    final name = childName;
    final tryLabel = name == null || isDefaultChildName(name)
        ? l10n.chatTryWithMyChild
        : l10n.chatTryWith(name);
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 24),
      children: [
        ?rating,
        const Center(child: NoorPresence(size: 96, mood: NoorMood.proud)),
        const SizedBox(height: 12),
        Text(
          l10n.storyTheEnd,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            color: colors.ink,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 16),
        if (value != null && value.isNotEmpty) ...[
          _Sheet(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _heading(
                  context,
                  Icons.auto_awesome_rounded,
                  l10n.storyValueTitle,
                ),
                const SizedBox(height: 8),
                _content(context, value),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ],
        if (questions.isNotEmpty) ...[
          _Sheet(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _heading(context, Icons.forum_rounded, l10n.storyTalkTitle),
                const SizedBox(height: 10),
                for (
                  var i = 0;
                  i < math.min(questionsShown, questions.length);
                  i++
                )
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 26,
                          height: 26,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: colors.primary,
                            shape: BoxShape.circle,
                          ),
                          child: Text(
                            '${i + 1}',
                            style: TextStyle(
                              color: colors.onPrimary,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(child: _content(context, questions[i])),
                      ],
                    ),
                  ),
                if (questionsShown < questions.length)
                  Align(
                    alignment: AlignmentDirectional.centerStart,
                    child: TextButton.icon(
                      onPressed: onMoreQuestion,
                      icon: const Icon(Icons.add_comment_rounded),
                      label: Text(l10n.storyMoreQuestion),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ],
        if (challenge != null && challenge.isNotEmpty) ...[
          _Sheet(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _heading(context, Icons.flag_rounded, l10n.storyChallengeTitle),
                const SizedBox(height: 8),
                _content(context, challenge),
                if (canTry) ...[
                  const SizedBox(height: 12),
                  tried
                      ? Row(
                          children: [
                            Icon(
                              Icons.check_circle_rounded,
                              color: colors.successText,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                l10n.promiseSaved,
                                style: TextStyle(
                                  color: colors.successText,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ],
                        )
                      : FilledButton.tonalIcon(
                          onPressed: () => onTry(challenge),
                          icon: const Icon(Icons.handshake_rounded),
                          label: Text(tryLabel),
                        ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 10,
          runSpacing: 10,
          children: [
            OutlinedButton.icon(
              onPressed: onAdhkar,
              icon: const Icon(Icons.nights_stay_rounded),
              label: Text(l10n.storyBedtimeAdhkar),
            ),
            FilledButton.icon(
              onPressed: onAnother,
              icon: const Icon(Icons.auto_stories_rounded),
              label: Text(l10n.storyAnother),
            ),
          ],
        ),
        const SizedBox(height: 6),
        TextButton(
          onPressed: onInvite,
          child: Text(
            l10n.prideStoryInvite,
            textAlign: TextAlign.center,
            style: TextStyle(color: colors.textSecondary, fontSize: 13),
          ),
        ),
      ],
    );
  }
}
