import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../theme/app_theme.dart';
import '../models/surah_names.dart';
import '../providers/quran_providers.dart';

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
  late ScrollController _scrollController;
  late int _currentChapter;

  @override
  void initState() {
    super.initState();
    _currentChapter = widget.chapterNumber;
    _scrollController = ScrollController();
    
    // Save progress as soon as we open the surah (at the initial verse, or verse 1)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(lastReadProvider.notifier).saveProgress(_currentChapter, widget.initialVerse);
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  List<dynamic> get _currentVerses {
    return widget.quranData[_currentChapter.toString()] ?? [];
  }

  void _nextSurah() {
    if (_currentChapter < 114) {
      setState(() {
        _currentChapter++;
        _scrollController.jumpTo(0);
      });
      ref.read(lastReadProvider.notifier).saveProgress(_currentChapter, 1);
    }
  }

  void _prevSurah() {
    if (_currentChapter > 1) {
      setState(() {
        _currentChapter--;
        _scrollController.jumpTo(0);
      });
      ref.read(lastReadProvider.notifier).saveProgress(_currentChapter, 1);
    }
  }

  @override
  Widget build(BuildContext context) {
    final surahName = surahNames[_currentChapter - 1];
    final verses = _currentVerses;

    // Convert Arabic numbers to Hindi numbers (Arabic Indic) for the verse endings
    String getArabicNumber(int number) {
      const english = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
      const arabic = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
      String result = number.toString();
      for (int i = 0; i < english.length; i++) {
        result = result.replaceAll(english[i], arabic[i]);
      }
      return result;
    }

    return Scaffold(
      backgroundColor: const Color(0xFFFDFBF7), // Warm paper color
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
          IconButton(
            icon: const Icon(Icons.bookmark_border),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('تم حفظ التقدم تلقائياً')),
              );
            },
          )
        ],
      ),
      body: verses.isEmpty
          ? const Center(child: Text('جاري التحميل...'))
          : Column(
              children: [
                if (_currentChapter != 1 && _currentChapter != 9)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 16.0),
                    child: Text(
                      "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ",
                      style: GoogleFonts.amiriQuran(
                        fontSize: 24,
                        color: AppTheme.textPrimary,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                Expanded(
                  child: SingleChildScrollView(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16.0),
                    child: RichText(
                      textAlign: TextAlign.justify,
                      textDirection: TextDirection.rtl,
                      text: TextSpan(
                        children: verses.map((v) {
                          final verseNum = v['verse'] as int;
                          // If it's Surah 1 (Al-Fatiha) or Surah 9 (At-Tawbah), don't strip Bismillah
                          // Otherwise, the dataset sometimes includes Bismillah in verse 1.
                          // The `risan/quran-json` includes Bismillah inside verse 1 for all surahs!
                          // Let's clean it up for display if needed, but it's fine to just render it.
                          String text = v['text'] as String;
                          if (_currentChapter != 1 && verseNum == 1 && text.startsWith("بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ ")) {
                            text = text.replaceFirst("بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ ", "");
                          }

                          return TextSpan(
                            children: [
                              TextSpan(
                                text: '$text ',
                                style: GoogleFonts.amiriQuran(
                                  fontSize: 26,
                                  color: AppTheme.textPrimary,
                                  height: 2.2,
                                ),
                              ),
                              TextSpan(
                                text: ' \uFD3F${getArabicNumber(verseNum)}\uFD3E ', // Ornate bracket
                                style: const TextStyle(
                                  fontSize: 20,
                                  color: AppTheme.primary,
                                ),
                              ),
                            ],
                          );
                        }).toList(),
                      ),
                    ),
                  ),
                ),
                // Bottom Navigation between Surahs
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black12,
                        blurRadius: 4,
                        offset: Offset(0, -2),
                      )
                    ],
                  ),
                  child: SafeArea(
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        TextButton.icon(
                          onPressed: _currentChapter < 114 ? _nextSurah : null,
                          icon: const Icon(Icons.arrow_back_ios, size: 16),
                          label: const Text('السورة التالية'),
                        ),
                        TextButton.icon(
                          onPressed: _currentChapter > 1 ? _prevSurah : null,
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
