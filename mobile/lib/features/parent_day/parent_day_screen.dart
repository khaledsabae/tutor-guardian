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
    // Scaffold, and its absence is why this screen rendered as a page of
    // enormous red text on black with yellow underlines.
    //
    // That is Flutter drawing Text with no Material ancestor. This screen is
    // pushed as its own route, and MaterialPageRoute does not supply Material
    // — Scaffold does, and there was none. It shipped that way in sprint 2
    // and every widget test passed straight through it, because a test wraps
    // the widget in MaterialApp and hands it the Material the real app never
    // did. The tests were testing a tree the user does not get.
    return Scaffold(
      appBar: AppBar(title: const Text('اليوم مع طفلي')),
      body: _body(context),
    );
  }

  Widget _body(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_day == null) {
      return Center(child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(_error ?? 'لا توجد بيانات اليوم.',
            textAlign: TextAlign.center),
      ));
    }

    // Every read below is defensive, and that is not belt-and-braces.
    //
    // This screen rendered as a black page of large red text on a real device
    // — the Flutter error box — because a hard cast on a payload key threw
    // during build. A parent dashboard has no business crashing over a field
    // the server did not send: it should show what it has and stay quiet
    // about the rest. `as Map<String, dynamic>` on a key that is absent, or
    // null, or arrives from an older backend, is a crash; `?? const {}` is a
    // missing row.
    final day = _day!;
    Map<String, dynamic> obj(String key) {
      final v = day[key];
      return v is Map<String, dynamic> ? v : const {};
    }

    int num_(Map<String, dynamic> m, String key) {
      final v = m[key];
      return v is num ? v.round() : 0;
    }

    final screen = obj('screen');
    final listening = obj('listening');
    final mission = day['mission'] is Map<String, dynamic>
        ? day['mission'] as Map<String, dynamic>
        : null;
    final agreement = day['agreement'] is Map<String, dynamic>
        ? day['agreement'] as Map<String, dynamic>
        : null;
    final month = obj('month');
    final sessions = (day['sessions'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .toList();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('اليوم مع ${day['child_name']}',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 16),

          _MeterRow(
            icon: '⏱',
            label: 'شاشة',
            seconds: num_(screen, 'counted_seconds'),
            budgetSeconds: num_(screen, 'budget_seconds'),
          ),
          const SizedBox(height: 10),
          _MeterRow(
            icon: '🎧',
            label: 'سماع (الشاشة مطفية)',
            seconds: num_(listening, 'counted_seconds'),
            budgetSeconds: num_(listening, 'budget_seconds'),
            muted: true,
          ),
          const SizedBox(height: 8),
          const Text(
            'الاثنان ليسا رقمًا واحدًا. السماع والشاشة مطفية ليس وقت شاشة، '
            'ولذلك له عدّاده وحده.',
            style: TextStyle(fontSize: 11, height: 1.6),
          ),

          const Divider(height: 32),

          if (mission != null) ...[
            const Text('مهمة اليوم',
                style: TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text('${mission['title_ar']} — ${mission['instruction_ar']}',
                style: const TextStyle(height: 1.7)),
            const SizedBox(height: 8),
            _MissionStatus(status: '${mission['status'] ?? ''}'),
            // The claim is only half a loop. Without a way through to the
            // confirm list, a parent who opened the app before 9pm could see
            // "says he did it" and had nowhere to answer it — the digest was
            // the only door, and the digest was not scheduled.
            if (mission['status'] == 'claimed') ...[
              const SizedBox(height: 8),
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: TextButton(
                  onPressed: () async {
                    final settled = await Navigator.push(
                        context, AppRoutes.pendingMissions());
                    if (settled == true) await _load();
                  },
                  child: const Text('أكّدها'),
                ),
              ),
            ],
            const Divider(height: 32),
          ],

          const Text('الميثاق', style: TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          if (agreement == null)
            Row(
              children: [
                const Expanded(child: Text('لا يوجد ميثاق موقّع بعد.',
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
                  ? 'نشط — وموعد مراجعته قد فات. اجلسوا وراجعوه معًا.'
                  : 'نشط · المراجعة ${agreement['next_review_date'] ?? ''}'
                    ' · ${agreement['clauses_on_parent']} بنود عليك',
              style: const TextStyle(height: 1.7),
            ),

          const Divider(height: 32),

          // What the child actually did, in order. Rule 6: the child is told
          // «بابا يرى» — this is the screen that makes that true. It is a
          // list of surfaces and minutes, not of content: the point is that a
          // parent can see the shape of the time, not read over a shoulder.
          const Text('سجل اليوم',
              style: TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          if (sessions.isEmpty)
            const Text('لا توجد جلسات اليوم.', style: TextStyle(height: 1.6))
          else
            for (final s in sessions)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  '${_surfaceLabel(s['surface'] as String?)} · '
                  '${(num_(s, 'counted_seconds') / 60).round()} دقيقة'
                  '${s['ended_reason'] == null ? ' · جارية الآن' : ''}',
                  style: const TextStyle(height: 1.7, fontSize: 13),
                ),
              ),

          const Divider(height: 32),

          Text(
            month['ratio'] == null
                ? 'هذا الشهر: ${month['confirmed_missions']} مهمة مؤكَّدة.'
                : 'هذا الشهر: ${month['screen_minutes']} دقيقة شاشة '
                  'نتج عنها ${month['off_screen_minutes']} دقيقة نشاط '
                  'خارج الشاشة.',
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
      'claimed' => 'يقول إنه أنجزها — تنتظر تأكيدك مساءً',
      'confirmed' => 'تأكدت ✓',
      'not_done' => 'ليس بعد',
      'expired' => 'انقضى وقتها',
      _ => 'لم تبدأ بعد',
    };
    return Text(text, style: const TextStyle(height: 1.6));
  }
}

/// Surface names as a parent would say them.
///
/// Deliberately not the raw policy keys: `screen_off` and `habit` are the
/// server's vocabulary, and a log a parent cannot read is not transparency.
String _surfaceLabel(String? surface) => switch (surface) {
      'screen_off' => 'سماع (الشاشة مطفية)',
      'mission' => 'مهمة',
      'story' => 'قصة',
      'game' => 'لعبة',
      'habit' => 'ميزان العادات',
      'drill' => 'تمرين',
      'agreement' => 'الميثاق',
      _ => surface ?? 'غير معروف',
    };
