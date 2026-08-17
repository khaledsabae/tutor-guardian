/// «بدائل بلا شاشة» — the section the age gate points at.
///
/// The refusal shown to the parent of a child under two carried three
/// activities inside its own message text, with a comment in the policy file
/// saying that was a placeholder until this screen existed. A gate whose only
/// exit is a screen that does not exist reads as a dead end, and the whole
/// argument of the product is that there is something better to do — not that
/// there is nothing to do.
///
/// A bundled asset rather than an endpoint: this is the first screen the
/// parent of an infant sees, they may well open it with no connectivity, and
/// the content has no state to sync. The stories already work this way.
library;

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/tg_client.dart';
import '../../l10n/app_localizations.dart';

/// Bands in the order a parent should see them, matching the policy file's
/// own band names so a link from a refusal lands on the right section.
const _kBandOrder = ['under-2', '2-3', '4-6', '7-9'];

const _kBandLabels = {
  'under-2': 'أقل من سنتين',
  '2-3': 'سنتان – ٣',
  '4-6': '٤ – ٦',
  '7-9': '٧ – ٩',
};

final offscreenActivitiesProvider =
    FutureProvider<Map<String, dynamic>>((ref) async {
  // Locale-aware, with the Arabic file as the fallback rather than an empty
  // state. This screen is where the under-2 age gate sends a parent it has
  // just refused — showing them nothing there would turn a redirect into a
  // dead end, which is the exact defect the section was built to fix.
  final lang = TgClient.uiLanguage;
  if (lang != null && lang.startsWith('en')) {
    try {
      final en = await rootBundle
          .loadString('assets/data/offscreen_activities_en.json');
      return (jsonDecode(en) as Map<String, dynamic>)['bands']
          as Map<String, dynamic>;
    } catch (_) {
      // Asset missing from the bundle — fall through to Arabic.
    }
  }
  final raw = await rootBundle.loadString('assets/data/offscreen_activities.json');
  return (jsonDecode(raw) as Map<String, dynamic>)['bands'] as Map<String, dynamic>;
});

class OffscreenActivitiesScreen extends ConsumerStatefulWidget {
  const OffscreenActivitiesScreen({super.key, this.initialBand});

  /// Which band to open on — passed by the refusal that sent the parent here,
  /// so they land on their own child's age rather than on a list to scroll.
  final String? initialBand;

  @override
  ConsumerState<OffscreenActivitiesScreen> createState() =>
      _OffscreenActivitiesScreenState();
}

class _OffscreenActivitiesScreenState
    extends ConsumerState<OffscreenActivitiesScreen> {
  late String _band = _kBandOrder.contains(widget.initialBand)
      ? widget.initialBand!
      : _kBandOrder.first;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final async = ref.watch(offscreenActivitiesProvider);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.offscreenTitle)),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(l10n.offscreenUnavailable, textAlign: TextAlign.center),
          ),
        ),
        data: (bands) {
          final band = bands[_band] as Map<String, dynamic>?;
          final activities =
              (band?['activities'] as List<dynamic>? ?? const []);
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
            children: [
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    for (final b in _kBandOrder)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          label: Text(_kBandLabels[b] ?? b),
                          selected: _band == b,
                          onSelected: (_) => setState(() => _band = b),
                        ),
                      ),
                  ],
                ),
              ),
              if (band?['note'] != null) ...[
                const SizedBox(height: 16),
                Text(
                  band!['note'] as String,
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium
                      ?.copyWith(height: 1.7),
                ),
              ],
              const SizedBox(height: 16),
              for (final raw in activities)
                _ActivityCard(activity: raw as Map<String, dynamic>),
            ],
          );
        },
      ),
    );
  }
}

class _ActivityCard extends StatelessWidget {
  const _ActivityCard({required this.activity});

  final Map<String, dynamic> activity;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final materials =
        (activity['materials'] as List<dynamic>? ?? const []).cast<String>();
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    activity['title_ar'] as String? ?? '',
                    style: theme.textTheme.titleSmall
                        ?.copyWith(fontWeight: FontWeight.w800),
                  ),
                ),
                Text(
                  '${activity['minutes'] ?? 0} '
                  '${AppLocalizations.of(context).missionMinutesShort}',
                  style: theme.textTheme.labelMedium
                      ?.copyWith(color: theme.colorScheme.outline),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              activity['instruction_ar'] as String? ?? '',
              style: theme.textTheme.bodyMedium?.copyWith(height: 1.7),
            ),
            if (materials.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                '${AppLocalizations.of(context).offscreenMaterials}: '
                '${materials.join('، ')}',
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.outline),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
