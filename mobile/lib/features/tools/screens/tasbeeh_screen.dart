/// Tasbeeh counter.
///
/// Fully local: no network, no permission, no content. The whole screen is one
/// large tap target on purpose — a thumb should find it without looking, since
/// the eyes are usually elsewhere while the tongue is busy.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../data/hijri_date.dart' show arabicDigits;
import '../data/tasbeeh_store.dart';

/// The dhikr phrases offered above the counter. Arabic content, rendered with
/// the content's own direction rather than the chrome's.
const List<String> kTasbeehPhrases = <String>[
  'سُبْحَانَ اللَّهِ',
  'الْحَمْدُ لِلَّهِ',
  'اللَّهُ أَكْبَرُ',
  'لَا إِلَٰهَ إِلَّا اللَّهُ',
  'أَسْتَغْفِرُ اللَّهَ',
];

class TasbeehScreen extends ConsumerStatefulWidget {
  const TasbeehScreen({super.key});

  @override
  ConsumerState<TasbeehScreen> createState() => _TasbeehScreenState();
}

class _TasbeehScreenState extends ConsumerState<TasbeehScreen> {
  TasbeehStore? _store;
  TasbeehState _state = TasbeehState.initial;
  int _phrase = 0;
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    final store = TasbeehStore(prefs);
    setState(() {
      _store = store;
      _state = store.load();
      _ready = true;
    });
  }

  void _persist() => _store?.save(_state);

  void _increment() {
    final wasComplete = _state.isComplete;
    setState(() => _state = _state.copyWith(count: _state.count + 1));
    // Haptics carry the count when the screen is not being watched: a light
    // tick per bead, a heavier one the moment the target is reached.
    if (!wasComplete && _state.isComplete) {
      HapticFeedback.heavyImpact();
    } else {
      HapticFeedback.selectionClick();
    }
    _persist();
  }

  void _reset() {
    setState(() => _state = _state.copyWith(count: 0));
    _persist();
  }

  void _setTarget(int? target) {
    setState(() {
      _state = target == null
          ? _state.copyWith(clearTarget: true)
          : _state.copyWith(target: target);
    });
    _persist();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final target = _state.target;
    final complete = _state.isComplete;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.tasbeehTitle),
        centerTitle: true,
        actions: [
          IconButton(
            tooltip: l10n.tasbeehReset,
            onPressed: _ready ? _reset : null,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: !_ready
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // ── Target picker ───────────────────────────────────────────
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                  child: Wrap(
                    alignment: WrapAlignment.center,
                    spacing: 8,
                    children: [
                      for (final t in kTasbeehTargets)
                        ChoiceChip(
                          label: Text(t == null
                              ? l10n.tasbeehFree
                              : arabicDigits(t)),
                          selected: target == t,
                          onSelected: (_) => _setTarget(t),
                        ),
                    ],
                  ),
                ),

                // ── Phrase picker ───────────────────────────────────────────
                Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 12),
                  child: ContentDirectionality(
                    languageCode: 'ar',
                    child: SizedBox(
                      height: 40,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: kTasbeehPhrases.length,
                        separatorBuilder: (_, _) => const SizedBox(width: 8),
                        itemBuilder: (context, i) => ChoiceChip(
                          label: Text(kTasbeehPhrases[i]),
                          selected: _phrase == i,
                          onSelected: (_) => setState(() => _phrase = i),
                        ),
                      ),
                    ),
                  ),
                ),

                // ── The counter itself ──────────────────────────────────────
                Expanded(
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: _increment,
                    child: Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          ContentDirectionality(
                            languageCode: 'ar',
                            child: Text(
                              kTasbeehPhrases[_phrase],
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                          ),
                          const SizedBox(height: 24),
                          AnimatedContainer(
                            duration: Dt.fast,
                            width: 180,
                            height: 180,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: complete
                                  ? Dt.accentGradient
                                  : Dt.primaryGradient,
                            ),
                            alignment: Alignment.center,
                            child: Text(
                              arabicDigits(_state.count),
                              style: const TextStyle(
                                fontSize: 52,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                              ),
                            ),
                          ),
                          const SizedBox(height: 20),
                          if (target != null)
                            SizedBox(
                              width: 200,
                              child: ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                child: LinearProgressIndicator(
                                  value: (_state.count / target).clamp(0, 1),
                                  minHeight: 8,
                                  backgroundColor: Dt.track,
                                ),
                              ),
                            ),
                          const SizedBox(height: 12),
                          Text(
                            complete
                                ? l10n.tasbeehComplete
                                : (target == null
                                    ? l10n.tasbeehTapHint
                                    : l10n.tasbeehProgress(
                                        arabicDigits(_state.count),
                                        arabicDigits(target),
                                      )),
                            style: TextStyle(
                              color: complete
                                  ? AppTheme.success
                                  : AppTheme.textSecondary,
                              fontWeight:
                                  complete ? FontWeight.w700 : FontWeight.w400,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}
