/// What to listen to with the screen dark.
///
/// Plan item 2.2b names three audio sources and rules out a fourth: no TTS,
/// because there is no Arabic voice good enough (owner's decision). Two of the
/// three are reachable today — a parent's own recording, and the reciters
/// already bundled for the Qur'an screen. The third, recorded adhkar, needs
/// audio files that do not exist in the repo yet; it is not stubbed here,
/// because an empty section that never fills is worse than one that is honest
/// about not being built.
///
/// The recitation entries are short surahs on purpose. everyayah serves one
/// file per verse, so al-Baqarah would be a 286-item playlist assembled on a
/// child's phone; the last juz' is where a child listening at bedtime actually
/// is, and each surah here is a handful of files.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_routes.dart';
import '../../l10n/app_localizations.dart';
import '../quran/models/surah_names.dart';
import '../quran/providers/quran_providers.dart';
import 'narration_store.dart';

/// Surah numbers offered for listening, shortest-first within the last juz'.
///
/// Kept explicit rather than computed from a length threshold: this is a
/// content decision about what a child is likely to be memorising, and it
/// should change by someone editing this list, not by a constant drifting.
const _kListeningSurahs = <int>[
  112, 113, 114, 111, 110, 108, 107, 106, 105, 103, 102, 101, 100,
  99, 97, 95, 94, 93, 92, 91, 87, 78, 67, 36, 55,
];

class ScreenOffPickerScreen extends ConsumerStatefulWidget {
  const ScreenOffPickerScreen({super.key});

  @override
  ConsumerState<ScreenOffPickerScreen> createState() =>
      _ScreenOffPickerScreenState();
}

class _ScreenOffPickerScreenState extends ConsumerState<ScreenOffPickerScreen> {
  Set<String> _narrations = const {};

  @override
  void initState() {
    super.initState();
    _loadNarrations();
  }

  Future<void> _loadNarrations() async {
    final keys = await NarrationStore.instance.available();
    if (mounted) setState(() => _narrations = keys);
  }

  /// One request per verse, in order. The count comes from the bundled Qur'an
  /// text, so a surah is never truncated to a guessed length.
  List<String> _surahPlaylist(int surah, Map<String, List<dynamic>> data) {
    final reciter = ref.read(reciterProvider);
    final verses = data['$surah']?.length ?? 0;
    final s = surah.toString().padLeft(3, '0');
    return [
      for (var ayah = 1; ayah <= verses; ayah++)
        'https://everyayah.com/data/${reciter.id}/$s${ayah.toString().padLeft(3, '0')}.mp3',
    ];
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final quran = ref.watch(quranDataProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.screenOffPickerTitle)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          Text(
            l10n.screenOffPickerIntro,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.6),
          ),
          const SizedBox(height: 24),

          if (_narrations.isNotEmpty) ...[
            _SectionTitle(l10n.screenOffSectionParentVoice),
            for (final key in _narrations)
              _Row(
                icon: '🎙️',
                label: key.startsWith('story_')
                    ? key.substring('story_'.length)
                    : key,
                onTap: () async {
                  final found = await NarrationStore.instance.find(key);
                  if (found == null || !context.mounted) return;
                  await Navigator.of(context).push(
                    AppRoutes.screenOffPlayer(
                        title: l10n.screenOffSectionParentVoice,
                        source: found.path),
                  );
                },
              ),
            const SizedBox(height: 24),
          ],

          _SectionTitle(l10n.screenOffSectionQuran),
          quran.when(
            loading: () => const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (_, _) => Text(l10n.screenOffQuranUnavailable),
            data: (data) => Column(
              children: [
                for (final surah in _kListeningSurahs)
                  if ((data['$surah']?.length ?? 0) > 0)
                    _Row(
                      icon: '📖',
                      label: surahNames[surah - 1],
                      onTap: () => Navigator.of(context).push(
                        AppRoutes.screenOffPlayer(
                          title: surahNames[surah - 1],
                          source: '',
                          playlist: _surahPlaylist(surah, data),
                        ),
                      ),
                    ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(text,
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w800)),
      );
}

class _Row extends StatelessWidget {
  const _Row({required this.icon, required this.label, required this.onTap});

  final String icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Text(icon, style: const TextStyle(fontSize: 22)),
        title: Text(label),
        onTap: onTap,
      );
}
