/// Browsing surface for the parenting-content pack.
///
/// 281 attributed items — 142 ayahs, 124 tips, 15 hadiths — have shipped in
/// `family_adhkar.ar.json` since the reminder feature was built, and the only
/// way to see any of them was to wait for the daily notification. One item a
/// day is a 281-day tour of content the user already has on disk.
///
/// **Grouping is by kind, not by topic.** The pack carries a `topic` per item,
/// but 160-odd distinct topics across 281 items means almost every group would
/// hold exactly one thing. Topic is shown on the card, where it reads as a
/// label; kind and free-text search are what actually narrow 281 items down.
///
/// **`source` is always rendered.** Four pre-commit guards exist to keep every
/// item's citation honest — book and number for a hadith, surah and ayah for a
/// verse. Dropping it at the last step, in the widget, would waste all of that.
library;

import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../data/family_adhkar.dart';

class AdhkarScreen extends StatefulWidget {
  const AdhkarScreen({super.key});

  @override
  State<AdhkarScreen> createState() => _AdhkarScreenState();
}

class _AdhkarScreenState extends State<AdhkarScreen> {
  /// `null` = every kind.
  String? _kind;
  String _query = '';

  List<ParentingContent> get _filtered {
    final q = _query.trim();
    return FamilyAdhkar.items.where((c) {
      if (_kind != null && c.kind != _kind) return false;
      if (q.isEmpty) return true;
      return c.text.contains(q) ||
          c.topic.contains(q) ||
          c.source.contains(q);
    }).toList(growable: false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final items = _filtered;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.adhkarTitle), centerTitle: true),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              onChanged: (v) => setState(() => _query = v),
              decoration: InputDecoration(
                hintText: l10n.adhkarSearchHint,
                prefixIcon: const Icon(Icons.search_rounded),
                isDense: true,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(Dt.rButton),
                ),
              ),
            ),
          ),
          SizedBox(
            height: 40,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              children: [
                _kindChip(null, l10n.adhkarKindAll),
                const SizedBox(width: 8),
                _kindChip('verse', l10n.adhkarKindVerse),
                const SizedBox(width: 8),
                _kindChip('hadith', l10n.adhkarKindHadith),
                const SizedBox(width: 8),
                _kindChip('tip', l10n.adhkarKindTip),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: Align(
              alignment: AlignmentDirectional.centerStart,
              child: Text(
                l10n.adhkarCount('${items.length}'),
                style:
                    TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ),
          ),
          Expanded(
            child: items.isEmpty
                ? Center(
                    child: Text(
                      l10n.adhkarNoResults,
                      style: TextStyle(color: AppTheme.textSecondary),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                    itemCount: items.length,
                    itemBuilder: (context, i) => _AdhkarCard(item: items[i]),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _kindChip(String? kind, String label) => ChoiceChip(
        label: Text(label),
        selected: _kind == kind,
        onSelected: (_) => setState(() => _kind = kind),
      );
}

class _AdhkarCard extends StatelessWidget {
  final ParentingContent item;

  const _AdhkarCard({required this.item});

  @override
  Widget build(BuildContext context) {
    // Off the item, not off a hard-coded 'ar'. That was right while the pack
    // was Arabic and only Arabic; since 2026-08-22 the 124 tips load in English
    // for an English reader, and pinning the direction rendered them
    // right-aligned with the full stop on the wrong side of the line.
    //
    // The eight tips that quote scripture are mixed: mostly English around an
    // Arabic ayah or hadith. Character counting gives those to LTR, which is
    // the direction of the sentence doing the talking, and the quotation keeps
    // its own direction inside it.
    return ContentDirectionality(
      text: item.text,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Dt.surface,
          borderRadius: BorderRadius.circular(Dt.rCard),
          border: Border.all(
            color: AppTheme.primary.withValues(alpha: .12),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(_kindEmoji(item.kind),
                    style: const TextStyle(fontSize: 14)),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    item.topic,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.primary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              item.text,
              style: TextStyle(
                fontSize: 16,
                height: 1.9,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 10),
            // Citation, not a caption — never hidden behind a tap.
            Text(
              item.source,
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
          ],
        ),
      ),
    );
  }

  static String _kindEmoji(String kind) => switch (kind) {
        'verse' => '📖',
        'hadith' => '🕌',
        _ => '💡',
      };
}
