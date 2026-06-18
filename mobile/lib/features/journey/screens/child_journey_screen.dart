/// «رحلة الطفل» — the per-child keepsake timeline (Phase 1).
///
/// Shows the milestones a parent has logged for one child (a treasured
/// record they build over years) plus a calm list of suggested spiritual
/// milestones still to come. Logging a milestone celebrates it and credits
/// coins once (reusing the existing on-device reward path). Fully local.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../coins/coins_providers.dart';
import '../data/journey_milestones.dart';
import '../data/journey_store.dart';
import '../providers/journey_providers.dart';

class ChildJourneyScreen extends ConsumerWidget {
  const ChildJourneyScreen({
    super.key,
    required this.childId,
    required this.childName,
    this.ageGroup,
  });

  final int childId;
  final String childName;

  /// The child's age band (wire value, e.g. `4-6`) — drives the
  /// developmental-milestone section. Null hides that section.
  final String? ageGroup;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncLogged = ref.watch(childJourneyProvider(childId));
    return Scaffold(
      appBar: AppBar(title: Text('رحلة $childName')),
      body: asyncLogged.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text('تعذّر تحميل الرحلة.\n$e', textAlign: TextAlign.center),
          ),
        ),
        data: (logged) {
          // Logged milestones, newest first — the keepsake timeline.
          final entries = logged.values.toList()
            ..sort((a, b) => b.achievedAt.compareTo(a.achievedAt));
          // Catalogue milestones not yet marked — gentle "what's next".
          final suggestions = spiritualMilestones
              .where((m) => !logged.containsKey(m.key))
              .toList();
          final devSuggestions = developmentalMilestonesFor(ageGroup)
              .where((m) => !logged.containsKey(m.key))
              .toList();

          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              _Header(name: childName, count: entries.length),
              const SizedBox(height: 16),
              if (entries.isEmpty)
                const _EmptyTimeline()
              else
                for (var i = 0; i < entries.length; i++)
                  _TimelineCard(
                    entry: entries[i],
                    onDelete: () => _confirmDelete(context, ref, entries[i]),
                  )
                      .animate(delay: (60 * (i % 8)).ms)
                      .fadeIn(duration: Dt.base)
                      .slideX(begin: .06),
              const SizedBox(height: 24),
              if (suggestions.isNotEmpty) ...[
                const _SectionLabel('محطات إيمانية 🕌'),
                const SizedBox(height: 10),
                for (final m in suggestions)
                  _SuggestedTile(
                    milestone: m,
                    onTap: () => _showLogSheet(context, ref, milestone: m),
                  ),
                const SizedBox(height: 20),
              ],
              if (devSuggestions.isNotEmpty) ...[
                const _SectionLabel('محطات نمائية 📈 (حسب العمر)'),
                const SizedBox(height: 10),
                for (final m in devSuggestions)
                  _SuggestedTile(
                    milestone: m,
                    onTap: () => _showLogSheet(context, ref, milestone: m),
                  ),
                const SizedBox(height: 20),
              ],
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: () => _showLogSheet(context, ref),
                icon: const Icon(Icons.add_circle_outline),
                label: const Text('سجّل محطة من عندك'),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(50),
                  side: BorderSide(
                    color: AppTheme.primary.withValues(alpha: 0.5),
                  ),
                  foregroundColor: AppTheme.primary,
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _confirmDelete(
    BuildContext context,
    WidgetRef ref,
    MilestoneEntry entry,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('حذف المحطة'),
        content: Text('هل تريد حذف «${entry.title}» من رحلة $childName؟'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('إلغاء'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppTheme.dangerFg),
            child: const Text('حذف'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await ref.read(childJourneyProvider(childId).notifier).remove(entry.key);
  }

  /// Bottom sheet to log a milestone — either a catalogue [milestone] (note
  /// optional) or a fully custom one (title + note).
  Future<void> _showLogSheet(
    BuildContext context,
    WidgetRef ref, {
    JourneyMilestone? milestone,
  }) async {
    final result = await showModalBottomSheet<_LogResult>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => _LogSheet(milestone: milestone),
    );
    if (result == null) return;

    final key = milestone?.key ??
        'custom_${DateTime.now().millisecondsSinceEpoch}';
    await ref.read(childJourneyProvider(childId).notifier).log(
          key: key,
          title: result.title,
          emoji: milestone?.emoji ?? '💛',
          note: result.note,
        );
    // Celebrate once, ever, per child+milestone — reuses the coins ledger.
    await ref
        .read(coinsProvider.notifier)
        .creditBadges([journeyRewardId(childId, key)]);

    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('ما شاء الله 🎉 محطة جديدة في رحلة $childName'),
          backgroundColor: AppTheme.primary,
        ),
      );
    }
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.name, required this.count});
  final String name;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topRight,
          end: Alignment.bottomLeft,
          colors: [Color(0xFF7E57C2), Color(0xFF9575CD)],
        ),
        borderRadius: BorderRadius.circular(Dt.rCard),
        boxShadow: Dt.softShadow(const Color(0xFF7E57C2)),
      ),
      child: Row(
        children: [
          const Text('🌟', style: TextStyle(fontSize: 40)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'رحلة $name',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  count == 0
                      ? 'ابدأ بتسجيل أول محطة في رحلته'
                      : 'سجّلت $count محطة — سجلّ تعتزّ به 💛',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: .92),
                    fontSize: 13,
                    height: 1.4,
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

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Text(
        text,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w800,
              color: AppTheme.textPrimary,
            ),
      ),
    );
  }
}

class _EmptyTimeline extends StatelessWidget {
  const _EmptyTimeline();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(Dt.rCard),
      ),
      child: const Row(
        children: [
          Text('🕊️', style: TextStyle(fontSize: 28)),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              'كل طفل رحلة فريدة. سجّل أول محطة من المحطات القادمة بالأسفل.',
              style: TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 13,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TimelineCard extends StatelessWidget {
  const _TimelineCard({required this.entry, required this.onDelete});
  final MilestoneEntry entry;
  final VoidCallback onDelete;

  String _date(DateTime d) {
    final l = d.toLocal();
    return '${l.year}/${l.month.toString().padLeft(2, '0')}/'
        '${l.day.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        boxShadow: Dt.cardShadow,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppTheme.surfaceAlt,
              borderRadius: BorderRadius.circular(22),
            ),
            child: Text(entry.emoji, style: const TextStyle(fontSize: 22)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  _date(entry.achievedAt),
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppTheme.textMuted,
                  ),
                ),
                if (entry.note.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    entry.note,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppTheme.textSecondary,
                      height: 1.4,
                    ),
                  ),
                ],
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline,
                color: AppTheme.textMuted, size: 20),
            tooltip: 'حذف المحطة',
            visualDensity: VisualDensity.compact,
            onPressed: onDelete,
          ),
        ],
      ),
    );
  }
}

class _SuggestedTile extends StatelessWidget {
  const _SuggestedTile({required this.milestone, required this.onTap});
  final JourneyMilestone milestone;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFFE4E7EC)),
          ),
          child: Row(
            children: [
              Opacity(
                opacity: 0.6,
                child:
                    Text(milestone.emoji, style: const TextStyle(fontSize: 24)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      milestone.title,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      milestone.description,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                    if (milestone.concernNote != null) ...[
                      const SizedBox(height: 4),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.info_outline,
                              size: 13, color: Color(0xFFB26A00)),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              milestone.concernNote!,
                              style: const TextStyle(
                                fontSize: 11,
                                color: Color(0xFFB26A00),
                                height: 1.35,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              const Icon(Icons.add_circle_outline,
                  color: AppTheme.primary, size: 22),
            ],
          ),
        ),
      ),
    );
  }
}

class _LogResult {
  const _LogResult(this.title, this.note);
  final String title;
  final String note;
}

class _LogSheet extends StatefulWidget {
  const _LogSheet({this.milestone});
  final JourneyMilestone? milestone;

  @override
  State<_LogSheet> createState() => _LogSheetState();
}

class _LogSheetState extends State<_LogSheet> {
  late final TextEditingController _titleCtrl;
  late final TextEditingController _noteCtrl;

  @override
  void initState() {
    super.initState();
    _titleCtrl = TextEditingController();
    _noteCtrl = TextEditingController();
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final m = widget.milestone;
    final isCustom = m == null;
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(m?.emoji ?? '💛', style: const TextStyle(fontSize: 28)),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  m?.title ?? 'محطة جديدة',
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (isCustom) ...[
            TextField(
              controller: _titleCtrl,
              maxLength: 60,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'عنوان المحطة',
                hintText: 'مثال: قال أول كلمة طيبة',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 8),
          ],
          TextField(
            controller: _noteCtrl,
            maxLength: JourneyStore.kMaxNoteLength,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'ملاحظة (اختياري)',
              hintText: 'دوّن لحظة تتذكرها…',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () {
                final title = isCustom ? _titleCtrl.text.trim() : m.title;
                if (title.isEmpty) return;
                Navigator.of(context).pop(
                  _LogResult(title, _noteCtrl.text.trim()),
                );
              },
              icon: const Icon(Icons.check),
              label: const Text('سجّل المحطة'),
              style: ElevatedButton.styleFrom(
                minimumSize: const Size.fromHeight(50),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
