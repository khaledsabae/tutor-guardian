import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../models/surah_names.dart';
import '../providers/quran_providers.dart';
import 'surah_reading_screen.dart';

class QuranScreen extends ConsumerWidget {
  const QuranScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final quranDataAsync = ref.watch(quranDataProvider);
    final lastReadAsync = ref.watch(lastReadProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'الورد اليومي',
          style: GoogleFonts.amiriQuran(
            fontSize: 26,
            fontWeight: FontWeight.bold,
          ),
        ),
        centerTitle: true,
      ),
      body: quranDataAsync.when(
        data: (quranData) {
          return Column(
            children: [
              // Last Read Banner
              lastReadAsync.when(
                data: (lastRead) {
                  if (lastRead == null) return const SizedBox.shrink();
                  final surahName = surahNames[lastRead.chapter - 1];
                  return GestureDetector(
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => SurahReadingScreen(
                            chapterNumber: lastRead.chapter,
                            initialVerse: lastRead.verse,
                            quranData: quranData,
                          ),
                        ),
                      );
                    },
                    child: Container(
                      margin: const EdgeInsets.all(16),
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [AppTheme.primary, Color(0xFF0369A1)],
                        ),
                        borderRadius: BorderRadius.circular(Dt.rCard),
                        boxShadow: Dt.cardShadow,
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.menu_book, color: Colors.white, size: 32),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'إكمال القراءة',
                                  style: TextStyle(
                                    color: Colors.white70,
                                    fontSize: 12,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'سورة $surahName - آية ${lastRead.verse}',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const Icon(Icons.arrow_forward_ios, color: Colors.white, size: 16),
                        ],
                      ),
                    ),
                  );
                },
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
              ),

              // Surah List
              Expanded(
                child: ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  itemCount: 114,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final chapterNum = index + 1;
                    final surahName = surahNames[index];
                    final chapterData = quranData[chapterNum.toString()];
                    final verseCount = chapterData?.length ?? 0;

                    return ListTile(
                      contentPadding: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
                      leading: Container(
                        width: 40,
                        height: 40,
                        decoration: const BoxDecoration(
                          color: AppTheme.surfaceAlt,
                          shape: BoxShape.circle,
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          '$chapterNum',
                          style: const TextStyle(
                            color: AppTheme.primary,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      title: Text(
                        surahName,
                        style: GoogleFonts.amiriQuran(
                          fontSize: 20,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      subtitle: Text(
                        'آياتها: $verseCount',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => SurahReadingScreen(
                              chapterNumber: chapterNum,
                              initialVerse: 1,
                              quranData: quranData,
                            ),
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Text('حدث خطأ أثناء تحميل المصحف: $err'),
        ),
      ),
    );
  }
}
