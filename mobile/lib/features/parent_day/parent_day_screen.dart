/// What a parent sees about today.
///
/// Screen minutes and listening minutes are two rows, never one total. That
/// is the whole editorial position of the product rendered as layout: forty
/// minutes of a dark screen and a recitation is not the same thing as forty
/// minutes of a game, and a single «٤٠ دقيقة اليوم» tells a parent nothing
/// they can act on.
///
/// The month's leverage is shown as a sentence, not a gauge, and there is no
/// target next to it. Its numerator is `estimated_minutes` — a number written
/// in a JSON file in this repo — so a goal of ×10 would be met by editing
/// content rather than by a family doing anything different. It is worth
/// saying out loud once a month and worth nothing as a KPI.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_routes.dart';
import '../../state/chat_notifier.dart' show tgClientProvider;
import '../program/providers/progress_providers.dart' show activeChildIdProvider;

class ParentDayScreen extends ConsumerStatefulWidget {
  const ParentDayScreen({super.key});

  @override
  ConsumerState<ParentDayScreen> createState() => _ParentDayScreenState();
}

class _ParentDayScreenState extends ConsumerState<ParentDayScreen> {
  Map<String, dynamic>? _day;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final childId = ref.read(activeChildIdProvider);
    if (childId == null) {
      setState(() { _loading = false; _error = 'اختر طفلاً أولاً.'; });
      return;
    }
    try {
      final day = await ref.read(tgClientProvider).fetchChildDay(childId);
      if (mounted) setState(() { _day = day; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_day == null) {
      return Center(child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(_error ?? 'مافيش بيانات النهارده.',
            textAlign: TextAlign.center),
      ));
    }

    final day = _day!;
    final screen = day['screen'] as Map<String, dynamic>;
    final listening = day['listening'] as Map<String, dynamic>;
    final mission = day['mission'] as Map<String, dynamic>?;
    final agreement = day['agreement'] as Map<String, dynamic>?;
    final month = day['month'] as Map<String, dynamic>;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('النهارده مع ${day['child_name']}',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 16),

          _MeterRow(
            icon: '⏱',
            label: 'شاشة',
            seconds: screen['counted_seconds'] as int,
            budgetSeconds: screen['budget_seconds'] as int,
          ),
          const SizedBox(height: 10),
          _MeterRow(
            icon: '🎧',
            label: 'سماع (الشاشة مطفية)',
            seconds: listening['counted_seconds'] as int,
            budgetSeconds: listening['budget_seconds'] as int,
            muted: true,
          ),
          const SizedBox(height: 8),
          const Text(
            'الاتنين مش رقم واحد. السماع والشاشة مطفية مش وقت شاشة، '
            'وعلشان كده ليه عدّاده لوحده.',
            style: TextStyle(fontSize: 11, height: 1.6),
          ),

          const Divider(height: 32),

          if (mission != null) ...[
            const Text('مهمة النهارده',
                style: TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text('${mission['title_ar']} — ${mission['instruction_ar']}',
                style: const TextStyle(height: 1.7)),
            const SizedBox(height: 8),
            _MissionStatus(status: mission['status'] as String),
            const Divider(height: 32),
          ],

          const Text('الميثاق', style: TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          if (agreement == null)
            Row(
              children: [
                const Expanded(child: Text('مافيش ميثاق موقّع لسه.',
                    style: TextStyle(height: 1.6))),
                TextButton(
                  onPressed: () => Navigator.push(context, AppRoutes.agreement()),
                  child: const Text('افتحه'),
                ),
              ],
            )
          else
            Text(
              agreement['review_due'] == true
                  ? 'نشط — وموعد مراجعته فات. اقعدوا راجعوه مع بعض.'
                  : 'نشط · المراجعة ${agreement['next_review_date'] ?? ''}'
                    ' · ${agreement['clauses_on_parent']} بنود عليك',
              style: const TextStyle(height: 1.7),
            ),

          const Divider(height: 32),

          Text(
            month['ratio'] == null
                ? 'الشهر ده: ${month['confirmed_missions']} مهمة مؤكَّدة.'
                : 'الشهر ده: ${month['screen_minutes']} دقيقة شاشة '
                  'نتج عنها ${month['off_screen_minutes']} دقيقة نشاط '
                  'برّه الشاشة.',
            style: const TextStyle(height: 1.8, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

class _MeterRow extends StatelessWidget {
  const _MeterRow({
    required this.icon,
    required this.label,
    required this.seconds,
    required this.budgetSeconds,
    this.muted = false,
  });

  final String icon;
  final String label;
  final int seconds;
  final int budgetSeconds;
  final bool muted;

  @override
  Widget build(BuildContext context) {
    final minutes = (seconds / 60).round();
    final budget = (budgetSeconds / 60).round();
    final fraction = budgetSeconds == 0 ? 0.0 : (seconds / budgetSeconds).clamp(0.0, 1.0);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(icon),
            const SizedBox(width: 8),
            Expanded(child: Text(label)),
            Text('$minutes من $budget دقيقة',
                style: const TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: LinearProgressIndicator(
            value: fraction.toDouble(),
            minHeight: 8,
            // No red at the top end: a parent reading a bar is not being
            // scored, and the app has no business implying they failed.
            color: muted ? Colors.teal.shade200 : Colors.teal,
            backgroundColor: Colors.black12,
          ),
        ),
      ],
    );
  }
}

class _MissionStatus extends StatelessWidget {
  const _MissionStatus({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final text = switch (status) {
      'claimed' => 'بيقول إنه عملها — مستنية تأكيدك المسا',
      'confirmed' => 'اتأكدت ✓',
      'not_done' => 'لسه',
      'expired' => 'عدّى وقتها',
      _ => 'لسه ما بدأش',
    };
    return Text(text, style: const TextStyle(height: 1.6));
  }
}
