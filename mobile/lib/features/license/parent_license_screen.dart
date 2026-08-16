/// The parent's half of the internet licence.
///
/// Two things live here, and the second is the one that matters.
///
/// **The talking points.** For each situation the child has met, how to open
/// the conversation about it. This is the half that teaches; the practice
/// only measures.
///
/// **The grant, which is refused until they have talked.** The button that
/// grants a level is disabled until the parent records that the conversation
/// happened, and the server refuses it too (409) so a client bug cannot skip
/// the step. Without it this is a certificate the app issues to itself.
///
/// Every string says «اتفقنا» and none says «فُتح». The app has no authority
/// over the child's browser, YouTube or WhatsApp — a screen claiming a level
/// was "unlocked" tells a parent something is protected that is not, and a
/// family that relaxes supervision on a protection that does not exist is
/// worse off than with no feature at all.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/tg_client.dart';
import '../../state/chat_notifier.dart' show tgClientProvider;
import '../program/providers/progress_providers.dart' show activeChildIdProvider;

/// What each level means as an agreement — never as a permission.
const _kLevelAgreement = {
  'stranger': 'نتفرّج ونحن في نفس الأوضة، والشاشة باينة.',
  'signal': 'يدوّر ويتصفّح، ويحكي لنا عن اللي لقاه.',
  'contact': 'يراسل ناس إحنا عارفينهم بأسمائهم.',
  'footprint': 'يدخل جروبات وألعاب جماعية.',
  'public': 'حساب عام، ومراجعة كل شهر.',
};

const _kLevelTitle = {
  'stranger': 'الغريب',
  'signal': 'الإعلان والخبر',
  'contact': 'المراسلة',
  'footprint': 'الأثر الرقمي',
  'public': 'العلني',
};

class ParentLicenseScreen extends ConsumerStatefulWidget {
  const ParentLicenseScreen({super.key});

  @override
  ConsumerState<ParentLicenseScreen> createState() =>
      _ParentLicenseScreenState();
}

class _ParentLicenseScreenState extends ConsumerState<ParentLicenseScreen> {
  Map<String, dynamic>? _summary;
  String? _error;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final childId = ref.read(activeChildIdProvider);
    if (childId == null) {
      setState(() => _error = 'اختر طفلاً أولاً.');
      return;
    }
    try {
      final data = await ref.read(tgClientProvider).fetchLicenseSummary(childId);
      if (mounted) setState(() { _summary = data; _error = null; });
    } on TgApiError catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _talked(String levelKey) async {
    final childId = ref.read(activeChildIdProvider);
    if (childId == null || _busy) return;
    setState(() => _busy = true);
    try {
      await ref.read(tgClientProvider).recordLicenseTalk(childId, levelKey);
      await _load();
    } on TgApiError catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _grant(String levelKey) async {
    final childId = ref.read(activeChildIdProvider);
    if (childId == null || _busy) return;
    setState(() => _busy = true);
    try {
      await ref.read(tgClientProvider).grantLicenseLevel(childId, levelKey);
      await _load();
    } on TgApiError {
      // The server refuses a grant before the practice is done and the talk is
      // recorded. Surface it as the reason rather than as a failure.
      if (mounted) {
        setState(() => _error =
            'لسه بدري. لازم المواقف تخلص، وتسجّل إنكم اتكلمتوا.');
      }
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final data = _summary;

    return Scaffold(
      appBar: AppBar(title: const Text('رخصة الإنترنت')),
      body: data == null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(_error ?? '...', textAlign: TextAlign.center),
              ),
            )
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  // Said once, plainly, at the top. Everything below is an
                  // agreement between a family, not a setting on a device.
                  Text(
                    'الرخصة دي اتفاق بينكم، مش إعداد على الجهاز. '
                    'التطبيق مايقدرش يقفل ولا يفتح حاجة على موبايل ابنك — '
                    'اللي بيتغيّر هو اللي اتفقتوا عليه، وإنتوا اللي بتنفّذوه.',
                    style: theme.textTheme.bodySmall?.copyWith(height: 1.7),
                  ),
                  const Divider(height: 28),
                  _LevelCard(
                    levelKey: data['level_key'] as String,
                    status: data['status'] as String,
                    progress: data['progress'] as Map<String, dynamic>,
                    talkedAt: data['talked_at'] as String?,
                    busy: _busy,
                    onTalked: () => _talked(data['level_key'] as String),
                    onGrant: () => _grant(data['level_key'] as String),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 10),
                    Text(_error!,
                        style: TextStyle(color: theme.colorScheme.error)),
                  ],
                  const Divider(height: 32),
                  Text('مواقف عدّى عليها',
                      style: theme.textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 4),
                  Text(
                    'مش مكتوب هنا إجابته. المكتوب هو إزاي تفتح الكلام.',
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: theme.colorScheme.outline),
                  ),
                  const SizedBox(height: 12),
                  for (final point in (data['talking_points'] as List<dynamic>? ??
                          const [])
                      .cast<Map<String, dynamic>>())
                    _TalkingPoint(point: point),
                ],
              ),
            ),
    );
  }
}

class _LevelCard extends StatelessWidget {
  const _LevelCard({
    required this.levelKey,
    required this.status,
    required this.progress,
    required this.talkedAt,
    required this.busy,
    required this.onTalked,
    required this.onGrant,
  });

  final String levelKey;
  final String status;
  final Map<String, dynamic> progress;
  final String? talkedAt;
  final bool busy;
  final VoidCallback onTalked;
  final VoidCallback onGrant;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final done = progress['done'] as int? ?? 0;
    final total = progress['total'] as int? ?? 0;
    final practiceDone = total > 0 && done >= total;

    return Card(
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_kLevelTitle[levelKey] ?? levelKey,
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text('اللي هنتفق عليه: ${_kLevelAgreement[levelKey] ?? ''}',
                style: theme.textTheme.bodyMedium?.copyWith(height: 1.7)),
            const SizedBox(height: 14),
            if (total == 0)
              Text('المستوى ده لسه بدري — مافيش مواقف متجهّزة له.',
                  style: theme.textTheme.bodyMedium)
            else ...[
              LinearProgressIndicator(value: total == 0 ? 0 : done / total),
              const SizedBox(height: 8),
              Text('$done من $total مواقف', style: theme.textTheme.bodySmall),
              const SizedBox(height: 14),
              // The talk is a step in the path, not a checkbox next to it.
              // Its button comes first and the grant stays disabled until it
              // is done — the server enforces the same order.
              if (talkedAt == null)
                FilledButton.tonal(
                  onPressed: busy || !practiceDone ? null : onTalked,
                  child: Text(practiceDone
                      ? 'اتكلمنا في المواقف دي'
                      : 'لسه فيه مواقف ماخلصتش'),
                )
              else
                Row(
                  children: [
                    const Text('✅ '),
                    Expanded(
                      child: Text('اتكلمتوا فيها.',
                          style: theme.textTheme.bodyMedium),
                    ),
                  ],
                ),
              const SizedBox(height: 8),
              if (status != 'granted')
                FilledButton(
                  onPressed:
                      busy || talkedAt == null || !practiceDone ? null : onGrant,
                  child: const Text('سجّل إننا اتفقنا على المستوى ده'),
                )
              else
                Text('متفقين عليه.',
                    style: theme.textTheme.bodyMedium
                        ?.copyWith(fontWeight: FontWeight.w700)),
            ],
          ],
        ),
      ),
    );
  }
}

class _TalkingPoint extends StatelessWidget {
  const _TalkingPoint({required this.point});
  final Map<String, dynamic> point;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(point['situation_ar'] as String? ?? '',
                style: theme.textTheme.bodyMedium
                    ?.copyWith(fontWeight: FontWeight.w700, height: 1.6)),
            const SizedBox(height: 8),
            Text(point['talking_point_ar'] as String? ?? '',
                style: theme.textTheme.bodyMedium?.copyWith(height: 1.8)),
          ],
        ),
      ),
    );
  }
}
