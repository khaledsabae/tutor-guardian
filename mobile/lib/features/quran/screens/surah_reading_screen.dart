import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:just_audio/just_audio.dart';
import 'package:scrollable_positioned_list/scrollable_positioned_list.dart';

import '../../../theme/app_theme.dart';
import '../models/reciters.dart';
import '../models/surah_names.dart';
import '../providers/quran_providers.dart';

/// The daily wird (portion) target — at least this many verses.
const int kDailyWirdVerses = 10;

class SurahReadingScreen extends ConsumerStatefulWidget {
  final int chapterNumber;
  final int initialVerse;
  final Map<String, List<dynamic>> quranData;

  const SurahReadingScreen({
    super.key,
    required this.chapterNumber,
    required this.initialVerse,
    required this.quranData,
  });

  @override
  ConsumerState<SurahReadingScreen> createState() => _SurahReadingScreenState();
}

class _SurahReadingScreenState extends ConsumerState<SurahReadingScreen> {
  final ItemScrollController _itemScroll = ItemScrollController();
  final ItemPositionsListener _positions = ItemPositionsListener.create();

  // ── Audio (recitation) ────────────────────────────────────────────────────
  // Per-ayah recitation streamed from everyayah.com (no API key, stable CDN).
  // Reciter is user-selectable via reciterProvider (defaults to Husary).
  final AudioPlayer _player = AudioPlayer();
  StreamSubscription<PlayerState>? _stateSub;
  int? _playingVerse; // 1-based verse currently reciting; null when stopped
  int _playToken = 0; // guards against stale async plays (rapid taps)

  late int _currentChapter;
  int _currentVerse = 1; // 1-based; the top-most visible verse
  late int _wirdStart; // verse the daily wird began at this session
  Timer? _saveDebounce;

  @override
  void initState() {
    super.initState();
    _currentChapter = widget.chapterNumber;
    _currentVerse = widget.initialVerse.clamp(1, 1 << 20);
    _wirdStart = _currentVerse;
    _positions.itemPositions.addListener(_onScroll);

    // Auto-advance the recitation ayah-by-ayah down the surah.
    _stateSub = _player.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        final cur = _playingVerse;
        if (cur != null && cur < _verses.length) {
          _playFrom(cur + 1);
        } else {
          if (mounted) setState(() => _playingVerse = null);
        }
      }
      if (mounted) setState(() {}); // refresh play/pause icon
    });

    // Jump to the saved verse once the list is laid out, then persist.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_currentVerse > 1 && _itemScroll.isAttached) {
        _itemScroll.jumpTo(index: _currentVerse - 1);
      }
      _persist();
    });
  }

  void _onScroll() {
    final positions = _positions.itemPositions.value;
    if (positions.isEmpty) return;
    // The first item whose leading edge is at/after the top of the viewport.
    final topIndex = positions
        .where((p) => p.itemTrailingEdge > 0)
        .reduce((a, b) => a.itemLeadingEdge < b.itemLeadingEdge ? a : b)
        .index;
    final verse = topIndex + 1;
    if (verse != _currentVerse) {
      _currentVerse = verse;
      _saveDebounce?.cancel();
      _saveDebounce = Timer(const Duration(milliseconds: 600), _persist);
      setState(() {}); // refresh the wird progress chip
    }
  }

  void _persist() {
    ref
        .read(lastReadProvider.notifier)
        .saveProgress(_currentChapter, _currentVerse);
  }

  @override
  void dispose() {
    _saveDebounce?.cancel();
    _stateSub?.cancel();
    _player.dispose();
    _positions.itemPositions.removeListener(_onScroll);
    _persist(); // final save on exit
    super.dispose();
  }

  List<dynamic> get _verses =>
      widget.quranData[_currentChapter.toString()] ?? const [];

  // ── Audio controls ──────────────────────────────────────────────────────
  String _ayahUrl(int surah, int ayah) {
    final reciter = ref.read(reciterProvider);
    final s = surah.toString().padLeft(3, '0');
    final a = ayah.toString().padLeft(3, '0');
    return 'https://everyayah.com/data/${reciter.id}/$s$a.mp3';
  }

  void _pickReciter() {
    final current = ref.read(reciterProvider);
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Text(
                'اختر القارئ',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
            ),
            for (final r in kReciters)
              ListTile(
                title: Text(
                  r.name,
                  style: GoogleFonts.amiriQuran(
                    fontSize: 22,
                    color: AppTheme.textPrimary,
                  ),
                ),
                trailing: r.id == current.id
                    ? const Icon(Icons.check_circle, color: AppTheme.primary)
                    : null,
                onTap: () {
                  Navigator.pop(ctx);
                  _onReciterSelected(r);
                },
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  void _onReciterSelected(Reciter reciter) {
    ref.read(reciterProvider.notifier).select(reciter);
    setState(() {});
    // If a recitation is in progress, restart the current ayah in the new voice.
    final cur = _playingVerse;
    if (cur != null) _playFrom(cur);
  }

  Future<void> _playFrom(int verse) async {
    if (verse < 1 || verse > _verses.length) return;
    final token = ++_playToken;
    setState(() {
      _playingVerse = verse;
    });
    _scrollToPlaying(verse);
    try {
      // Stable streaming source (everyayah CDN). Kept on the non-experimental
      // just_audio API on purpose — correctness/reliability first for Quran.
      await _player.setUrl(_ayahUrl(_currentChapter, verse));
      if (token != _playToken || !mounted) return; // superseded by a newer tap
      await _player.play();
    } catch (_) {
      if (mounted && token == _playToken) {
        setState(() {
          _playingVerse = null;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('تعذّر تشغيل التلاوة. تأكد من اتصالك بالإنترنت.'),
          ),
        );
      }
    }
  }

  void _toggleAudio() {
    if (_player.playing) {
      _player.pause();
    } else if (_playingVerse != null &&
        _player.processingState != ProcessingState.completed) {
      _player.play(); // resume current ayah
    } else {
      _playFrom(_currentVerse); // start from the verse at the top of the screen
    }
  }

  void _stopAudio() {
    _playToken++; // invalidate any in-flight play
    _player.stop();
    setState(() => _playingVerse = null);
  }

  void _scrollToPlaying(int verse) {
    if (_itemScroll.isAttached) {
      _itemScroll.scrollTo(
        index: verse - 1,
        duration: const Duration(milliseconds: 400),
        alignment: 0.35,
      );
    }
  }

  void _goToSurah(int chapter) {
    _stopAudio();
    setState(() {
      _currentChapter = chapter.clamp(1, 114);
      _currentVerse = 1;
      _wirdStart = 1;
    });
    if (_itemScroll.isAttached) _itemScroll.jumpTo(index: 0);
    _persist();
  }

  static String _arabicNum(int n) {
    const en = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
    const ar = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
    var s = n.toString();
    for (var i = 0; i < en.length; i++) {
      s = s.replaceAll(en[i], ar[i]);
    }
    return s;
  }

  @override
  Widget build(BuildContext context) {
    final surahName = surahNames[_currentChapter - 1];
    final verses = _verses;
    final wirdDone = (_currentVerse - _wirdStart) >= kDailyWirdVerses;
    final wirdProgress =
        ((_currentVerse - _wirdStart).clamp(0, kDailyWirdVerses)) /
            kDailyWirdVerses;
    final isPlaying = _player.playing;

    return Scaffold(
      backgroundColor: const Color(0xFFFDFBF7),
      appBar: AppBar(
        backgroundColor: const Color(0xFFFDFBF7),
        elevation: 0,
        title: Text(
          surahName,
          style: GoogleFonts.amiriQuran(
            color: AppTheme.textPrimary,
            fontSize: 24,
            fontWeight: FontWeight.bold,
          ),
        ),
        centerTitle: true,
        iconTheme: const IconThemeData(color: AppTheme.textPrimary),
        actions: [
          // Choose the reciter (Husary / Minshawy / Maher / Ghamdi).
          IconButton(
            key: const Key('quran_reciter_button'),
            tooltip: 'القارئ',
            icon: const Icon(Icons.record_voice_over, color: AppTheme.primary),
            onPressed: _pickReciter,
          ),
          // Listen / pause the whole surah, ayah by ayah.
          IconButton(
            key: const Key('quran_listen_button'),
            tooltip: isPlaying ? 'إيقاف التلاوة' : 'استماع',
            icon: Icon(
              isPlaying
                  ? Icons.pause_circle_filled
                  : Icons.play_circle_fill,
              color: AppTheme.primary,
              size: 30,
            ),
            onPressed: _toggleAudio,
          ),
        ],
      ),
      body: verses.isEmpty
          ? const Center(child: Text('جاري التحميل...'))
          : Column(
              children: [
                // Daily wird progress strip
                Container(
                  margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: wirdDone
                        ? AppTheme.success.withValues(alpha: .12)
                        : AppTheme.primary.withValues(alpha: .08),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Row(
                    children: [
                      Text(wirdDone ? '✅' : '📖',
                          style: const TextStyle(fontSize: 18)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          wirdDone
                              ? 'أكملت ورد اليوم، بارك الله فيك!'
                              : 'ورد اليوم: ${(_currentVerse - _wirdStart).clamp(0, kDailyWirdVerses)} / $kDailyWirdVerses آيات',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: wirdDone
                                ? AppTheme.success
                                : AppTheme.primary,
                          ),
                        ),
                      ),
                      if (!wirdDone)
                        SizedBox(
                          width: 80,
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: LinearProgressIndicator(
                              value: wirdProgress,
                              minHeight: 6,
                              backgroundColor: Colors.white,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                if (_currentChapter != 1 && _currentChapter != 9)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12.0),
                    child: Text(
                      'بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ',
                      style: GoogleFonts.amiriQuran(
                          fontSize: 24, color: AppTheme.textPrimary),
                      textAlign: TextAlign.center,
                    ),
                  ),
                Expanded(
                  child: ScrollablePositionedList.builder(
                    itemScrollController: _itemScroll,
                    itemPositionsListener: _positions,
                    padding: const EdgeInsets.all(16),
                    itemCount: verses.length,
                    itemBuilder: (context, i) {
                      final v = verses[i];
                      final verseNum = v['verse'] as int;
                      var text = v['text'] as String;
                      if (_currentChapter != 1 &&
                          verseNum == 1 &&
                          text.startsWith(
                              'بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ ')) {
                        text = text.replaceFirst(
                            'بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ ', '');
                      }
                      final isActive = verseNum == _playingVerse;
                      return GestureDetector(
                        // Tap a verse to start the recitation from it.
                        onTap: () => _playFrom(verseNum),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 250),
                          margin: const EdgeInsets.only(bottom: 6),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: isActive
                                ? AppTheme.primary.withValues(alpha: .10)
                                : Colors.transparent,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: RichText(
                            textAlign: TextAlign.justify,
                            textDirection: TextDirection.rtl,
                            text: TextSpan(children: [
                              TextSpan(
                                text: '$text ',
                                style: GoogleFonts.amiriQuran(
                                  fontSize: 26,
                                  color: isActive
                                      ? AppTheme.primary
                                      : AppTheme.textPrimary,
                                  height: 2.2,
                                ),
                              ),
                              TextSpan(
                                text: ' ﴿${_arabicNum(verseNum)}﴾ ',
                                style: const TextStyle(
                                    fontSize: 20, color: AppTheme.primary),
                              ),
                            ]),
                          ),
                        ),
                      );
                    },
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    boxShadow: [
                      BoxShadow(
                          color: Colors.black12,
                          blurRadius: 4,
                          offset: Offset(0, -2))
                    ],
                  ),
                  child: SafeArea(
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        TextButton.icon(
                          onPressed: _currentChapter < 114
                              ? () => _goToSurah(_currentChapter + 1)
                              : null,
                          icon: const Icon(Icons.arrow_back_ios, size: 16),
                          label: const Text('السورة التالية'),
                        ),
                        // Central listen pill mirrors the AppBar control so the
                        // "قراءة + استماع" action is reachable at the bottom too.
                        TextButton.icon(
                          key: const Key('quran_listen_pill'),
                          onPressed: _toggleAudio,
                          icon: Icon(
                            isPlaying ? Icons.pause : Icons.headphones,
                            size: 18,
                            color: AppTheme.primary,
                          ),
                          label: Text(
                            isPlaying ? 'إيقاف' : 'استماع',
                            style: const TextStyle(color: AppTheme.primary),
                          ),
                        ),
                        TextButton.icon(
                          onPressed: _currentChapter > 1
                              ? () => _goToSurah(_currentChapter - 1)
                              : null,
                          icon: const Icon(Icons.arrow_forward_ios, size: 16),
                          label: const Text('السورة السابقة'),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}
