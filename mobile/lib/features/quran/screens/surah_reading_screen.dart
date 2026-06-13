import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:scrollable_positioned_list/scrollable_positioned_list.dart';

import '../../../theme/app_theme.dart';
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
    _positions.itemPositions.removeListener(_onScroll);
    _persist(); // final save on exit
    super.dispose();
  }

  List<dynamic> get _verses =>
      widget.quranData[_currentChapter.toString()] ?? const [];

  void _goToSurah(int chapter) {
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
                      return Container(
                        margin: const EdgeInsets.only(bottom: 6),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4),
                        child: RichText(
                          textAlign: TextAlign.justify,
                          textDirection: TextDirection.rtl,
                          text: TextSpan(children: [
                            TextSpan(
                              text: '$text ',
                              style: GoogleFonts.amiriQuran(
                                fontSize: 26,
                                color: AppTheme.textPrimary,
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
