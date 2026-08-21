/// The bottom sheet that finally shows what an ayah means.
///
/// Direction is decided by the content, not by the chrome: tafsir arrives in
/// Arabic for every user, including the 27% whose interface is English. Wrap
/// it in `ContentDirectionality` and an English-locale parent still reads it
/// right-aligned with its punctuation in the right place.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../models/surah_names.dart';
import '../providers/tafsir_providers.dart';

/// Opens the tafsir sheet for [surah]:[ayah].
Future<void> showTafsirSheet(
  BuildContext context, {
  required int surah,
  required int ayah,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _TafsirSheet(surah: surah, ayah: ayah),
  );
}

class _TafsirSheet extends ConsumerWidget {
  final int surah;
  final int ayah;

  const _TafsirSheet({required this.surah, required this.ayah});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final async = ref.watch(ayahExplanationProvider((surah, ayah)));
    final surahName =
        (surah >= 1 && surah <= surahNames.length) ? surahNames[surah - 1] : '';

    return DraggableScrollableSheet(
      initialChildSize: 0.6,
      minChildSize: 0.35,
      maxChildSize: 0.92,
      expand: false,
      builder: (context, scrollController) {
        return Container(
          decoration: BoxDecoration(
            color: Dt.surface,
            borderRadius:
                const BorderRadius.vertical(top: Radius.circular(20)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 8),
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppTheme.textSecondary.withValues(alpha: .3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                child: Row(
                  children: [
                    Icon(Icons.menu_book_rounded,
                        size: 20, color: AppTheme.primary),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        l10n.tafsirTitle,
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ),
                    // The ayah reference is Arabic content (surah name), so it
                    // gets the content direction rather than the chrome's.
                    ContentDirectionality(
                      languageCode: 'ar',
                      child: Text(
                        '$surahName — ${_arabicNum(ayah)}',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: async.when(
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
                  error: (_, _) => _Message(
                    icon: Icons.wifi_off_rounded,
                    text: l10n.tafsirUnavailable,
                    onRetry: () => ref
                        .invalidate(ayahExplanationProvider((surah, ayah))),
                    retryLabel: l10n.retry,
                  ),
                  data: (x) => _Body(
                    explanation: x,
                    scrollController: scrollController,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _Body extends StatelessWidget {
  final AyahExplanation explanation;
  final ScrollController scrollController;

  const _Body({required this.explanation, required this.scrollController});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    // Nothing structured survived. The backend's own formatted blob — which
    // includes its «تعذّر جلب التفسير» fallback — is still better than a blank
    // sheet, but if even that is empty we say so plainly.
    if (explanation.isEmpty && explanation.formatted.isEmpty) {
      return _Message(icon: Icons.info_outline, text: l10n.tafsirEmpty);
    }

    return ListView(
      controller: scrollController,
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        if (explanation.isEmpty)
          _ContentBlock(attribution: null, text: explanation.formatted)
        else
          ...explanation.entries.map(
            (e) => _ContentBlock(attribution: e.attribution, text: e.text),
          ),
        if (explanation.nuzool != null) ...[
          const SizedBox(height: 8),
          Text(
            l10n.tafsirNuzool,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppTheme.primary,
            ),
          ),
          const SizedBox(height: 8),
          _ContentBlock(
            attribution: explanation.nuzoolAttribution,
            text: explanation.nuzool!,
          ),
        ],
      ],
    );
  }
}

/// One attributed passage.
///
/// [attribution] is rendered whenever it exists, above the text and never
/// collapsed away — an unattributed statement about the meaning of an ayah is
/// the thing this whole feature must not produce.
class _ContentBlock extends StatelessWidget {
  final String? attribution;
  final String text;

  const _ContentBlock({required this.attribution, required this.text});

  @override
  Widget build(BuildContext context) {
    return ContentDirectionality(
      languageCode: 'ar',
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.primary.withValues(alpha: .05),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (attribution != null && attribution!.isNotEmpty) ...[
              Text(
                attribution!,
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.primary,
                ),
              ),
              const SizedBox(height: 8),
            ],
            Text(
              text,
              style: GoogleFonts.tajawal(
                fontSize: 16,
                height: 1.9,
                color: AppTheme.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Message extends StatelessWidget {
  final IconData icon;
  final String text;
  final VoidCallback? onRetry;
  final String? retryLabel;

  const _Message({
    required this.icon,
    required this.text,
    this.onRetry,
    this.retryLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 40, color: AppTheme.textSecondary),
            const SizedBox(height: 12),
            Text(
              text,
              textAlign: TextAlign.center,
              style: TextStyle(color: AppTheme.textSecondary),
            ),
            if (onRetry != null && retryLabel != null) ...[
              const SizedBox(height: 16),
              TextButton(onPressed: onRetry, child: Text(retryLabel!)),
            ],
          ],
        ),
      ),
    );
  }
}

String _arabicNum(int n) {
  const digits = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
  return n.toString().split('').map((c) => digits[int.parse(c)]).join();
}
