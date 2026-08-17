/// Custom story generator — spend coins to create a personalized,
/// value-teaching Arabic story starring the active child. Generation
/// runs on the local model server-side.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/analytics.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/ui/bouncy_button.dart';
import '../../state/chat_notifier.dart' show tgClientProvider;
import '../program/providers/progress_providers.dart' show activeChildIdProvider;
import '../onboarding/providers/onboarding_providers.dart';
import '../../core/app_routes.dart';
import '../screen_off/narration_store.dart';
import 'coins_providers.dart';

const _themes = <(String, String, String)>[
  ('honesty', '🤝', 'الصدق والأمانة'),
  ('courage', '🦁', 'الشجاعة'),
  ('mercy', '💗', 'الرحمة والرفق'),
  ('parents', '👨‍👩‍👧', 'بر الوالدين'),
  ('sharing', '🎁', 'المشاركة والكرم'),
  ('patience', '🧘', 'الصبر'),
  ('cleanliness', '🧼', 'النظافة'),
  ('gratitude', '🌟', 'الشكر'),
  ('prayer', '🕌', 'حب الصلاة'),
];

class StoryScreen extends ConsumerStatefulWidget {
  const StoryScreen({super.key});

  @override
  ConsumerState<StoryScreen> createState() => _StoryScreenState();
}

class _StoryScreenState extends ConsumerState<StoryScreen> {
  String? _theme;
  bool _loading = false;
  String? _story;
  bool _hasNarration = false;

  /// A stable handle for this story so a recording can be found again. The
  /// theme is enough: one recording per value, which is what a family will
  /// actually make.
  String get _storyKey => 'story_${_theme ?? "none"}';

  Future<void> _refreshNarration() async {
    final found = await NarrationStore.instance.find(_storyKey);
    if (mounted) setState(() => _hasNarration = found != null);
  }

  // Stories are free. They used to cost 50 coins, which made the reward for
  // engaging with the app more time inside the app — the exact loop the rest
  // of this product tells parents to be wary of. If a story should be earned,
  // it gets earned by something that happens away from the screen, not by a
  // balance.
  Future<void> _generate() async {
    final theme = _theme;
    if (theme == null) return;
    final profile = ref.read(activeChildProfileProvider);
    final name = profile?.name ?? 'بطلنا الصغير';
    final age = profile?.ageGroup ?? '4-6';

    setState(() => _loading = true);
    try {
      final story = await ref.read(tgClientProvider).generateStory(
            childName: name,
            ageGroup: age,
            theme: theme,
            childId: ref.read(activeChildIdProvider),
          );
      unawaited(Analytics.storyGenerated(theme));
      if (mounted) setState(() => _story = story);
      await _refreshNarration();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppLocalizations.of(context).storyError(e.toString())),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final coins = ref.watch(coinsProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context).storyTitle),
        actions: [
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Text('🪙 ${coins.balance}',
                  style: TextStyle(
                      fontWeight: FontWeight.w800, color: Dt.accentDeep)),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_story == null) ...[
            Text(
              AppLocalizations.of(context).storyThemeIntro,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                    height: 1.5,
                  ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (key, emoji, label) in _themes)
                  ChoiceChip(
                    label: Text('$emoji $label'),
                    selected: _theme == key,
                    selectedColor: AppTheme.primary,
                    labelStyle: TextStyle(
                      color: _theme == key ? Colors.white : AppTheme.textPrimary,
                      fontWeight: FontWeight.w700,
                    ),
                    onSelected: (_) => setState(() => _theme = key),
                  ),
              ],
            ),
            const SizedBox(height: 24),
            BouncyButton(
              label: _loading
                  ? AppLocalizations.of(context).storyGenerating
                  : AppLocalizations.of(context).storyGenerateFree,
              color: Dt.accent,
              onTap: (_theme == null || _loading) ? null : _generate,
            ),
            if (_loading) ...[
              const SizedBox(height: 24),
              const Center(child: CircularProgressIndicator()),
              const SizedBox(height: 8),
              Center(
                child: Text(AppLocalizations.of(context).storyLoading,
                    style: TextStyle(color: AppTheme.textMuted)),
              ),
            ],
          ] else ...[
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(Dt.rCard),
                boxShadow: Dt.cardShadow,
              ),
              child: Text(
                _story!,
                style: const TextStyle(fontSize: 16, height: 1.9),
              ),
            ),
            const SizedBox(height: 16),
            // The bridge, not the substitute: a parent reads it once and the
            // child hears it in their voice afterwards — including on nights
            // the parent is not there.
            OutlinedButton.icon(
              onPressed: () async {
                await Navigator.push(
                  context,
                  AppRoutes.recordNarration(
                      storyKey: _storyKey, storyText: _story ?? ''),
                );
                await _refreshNarration();
              },
              icon: const Icon(Icons.mic),
              label: Text(AppLocalizations.of(context).storyRecordInYourVoice),
            ),
            if (_hasNarration) ...[
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () async {
                  final found = await NarrationStore.instance.find(_storyKey);
                  if (found == null || !context.mounted) return;
                  await Navigator.push(
                    context,
                    AppRoutes.screenOffPlayer(
                        title: AppLocalizations.of(context).storyTitle,
                        source: found.path),
                  );
                },
                icon: const Icon(Icons.nightlight_round),
                label: Text(AppLocalizations.of(context).storyListenScreenOff),
              ),
            ],
            const SizedBox(height: 16),
            BouncyButton(
              label: AppLocalizations.of(context).storyAnother,
              onTap: () => setState(() {
                _story = null;
                _theme = null;
              }),
            ),
          ],
        ],
      ),
    );
  }
}
