/// Custom story generator — spend coins to create a personalized,
/// value-teaching Arabic story starring the active child. Generation
/// runs on the local model server-side.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/ui/bouncy_button.dart';
import '../../state/chat_notifier.dart' show tgClientProvider;
import '../onboarding/providers/onboarding_providers.dart';
import 'coins_providers.dart';
import 'coins_service.dart';

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

  Future<void> _generate() async {
    final theme = _theme;
    if (theme == null) return;
    final coins = ref.read(coinsProvider);
    if (coins.balance < CoinsService.storyCost) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('رصيدك من العملات لا يكفي.')),
      );
      return;
    }
    final profile = ref.read(activeChildProfileProvider);
    final name = profile?.name ?? 'بطلنا الصغير';
    final age = profile?.ageGroup ?? '4-6';

    setState(() => _loading = true);
    try {
      final story = await ref.read(tgClientProvider).generateStory(
            childName: name,
            ageGroup: age,
            theme: theme,
          );
      // Only deduct coins after a successful generation.
      await ref.read(coinsProvider.notifier).spend(CoinsService.storyCost);
      if (mounted) setState(() => _story = story);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تعذّر توليد القصة: $e'),
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
        title: const Text('قصة مخصصة 📖'),
        actions: [
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Text('🪙 ${coins.balance}',
                  style: const TextStyle(
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
              'اختر قيمة تربوية، وسنؤلّف قصة قصيرة بطلها طفلك 🌟',
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
                  ? 'جارٍ تأليف القصة…'
                  : 'توليد قصة (${CoinsService.storyCost} 🪙)',
              color: Dt.accent,
              onTap: (_theme == null || _loading) ? null : _generate,
            ),
            if (_loading) ...[
              const SizedBox(height: 24),
              const Center(child: CircularProgressIndicator()),
              const SizedBox(height: 8),
              const Center(
                child: Text('قد يستغرق هذا لحظات…',
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
            BouncyButton(
              label: 'قصة أخرى',
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
