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
import '../../l10n/app_localizations.dart';
import '../../state/chat_notifier.dart' show tgClientProvider;
import '../program/providers/progress_providers.dart' show activeChildIdProvider;

/// What each level means as an agreement — never as a permission.
///
/// Looked up rather than held in a const map: these strings are read by
/// parents, 38% of whom are not reading in Arabic.
String _levelAgreement(AppLocalizations l10n, String key) => switch (key) {
      'stranger' => l10n.licenseAgreeStranger,
      'signal' => l10n.licenseAgreeSignal,
      'contact' => l10n.licenseAgreeContact,
      'footprint' => l10n.licenseAgreeFootprint,
      'public' => l10n.licenseAgreePublic,
      _ => '',
    };

String _levelTitle(AppLocalizations l10n, String key) => switch (key) {
      'stranger' => l10n.licenseLevelStranger,
      'signal' => l10n.licenseLevelSignal,
      'contact' => l10n.licenseLevelContact,
      'footprint' => l10n.licenseLevelFootprint,
      'public' => l10n.licenseLevelPublic,
      _ => key,
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

  /// Set when there is no active child. Rendered in build rather than read
  /// here: _load runs from initState, and AppLocalizations.of(context) before
  /// initState completes is a dependOnInheritedWidget error in debug.
  bool _noChild = false;

  Future<void> _load() async {
    final childId = ref.read(activeChildIdProvider);
    if (childId == null) {
      setState(() => _noChild = true);
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
        setState(() =>
            _error = AppLocalizations.of(context).licenseTooEarly);
      }
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final data = _summary;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.licenseTitle)),
      body: data == null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  _noChild
                      ? l10n.licensePickChildFirst
                      : (_error ?? l10n.licenseLoading),
                  textAlign: TextAlign.center,
                ),
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
                    l10n.licenseNotASetting,
                    style: theme.textTheme.bodySmall?.copyWith(height: 1.7),
                  ),
                  const Divider(height: 28),
                  _LevelCard(
                    // Defensive: three hard casts here used to take the whole
                    // screen down if the server omitted any of them.
                    levelKey: '${data['level_key'] ?? 'stranger'}',
                    status: '${data['status'] ?? 'practising'}',
                    progress: data['progress'] is Map<String, dynamic>
                        ? data['progress'] as Map<String, dynamic>
                        : const {},
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
                  Text(l10n.licenseMetSituations,
                      style: theme.textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 4),
                  Text(
                    l10n.licenseMetSituationsHint,
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: theme.colorScheme.outline),
                  ),
                  const SizedBox(height: 12),
                  for (final point in (data['talking_points'] as List<dynamic>? ??
                          const [])
                      .whereType<Map<String, dynamic>>())
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
    final l10n = AppLocalizations.of(context);
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
            Text(_levelTitle(l10n, levelKey),
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text('${l10n.licenseAgreementPrefix}: '
                '${_levelAgreement(l10n, levelKey)}',
                style: theme.textTheme.bodyMedium?.copyWith(height: 1.7)),
            const SizedBox(height: 14),
            if (total == 0)
              Text(l10n.licenseNotReadyYet,
                  style: theme.textTheme.bodyMedium)
            else ...[
              LinearProgressIndicator(value: total == 0 ? 0 : done / total),
              const SizedBox(height: 8),
              Text(l10n.licenseProgress(done, total),
                  style: theme.textTheme.bodySmall),
              const SizedBox(height: 14),
              // The talk is a step in the path, not a checkbox next to it.
              // Its button comes first and the grant stays disabled until it
              // is done — the server enforces the same order.
              if (talkedAt == null)
                FilledButton.tonal(
                  onPressed: busy || !practiceDone ? null : onTalked,
                  child: Text(practiceDone
                      ? l10n.licenseTalkedButton
                      : l10n.licenseUnfinished),
                )
              else
                Row(
                  children: [
                    const Text('✅ '),
                    Expanded(
                      child: Text(l10n.licenseTalkedDone,
                          style: theme.textTheme.bodyMedium),
                    ),
                  ],
                ),
              const SizedBox(height: 8),
              if (status != 'granted')
                FilledButton(
                  onPressed:
                      busy || talkedAt == null || !practiceDone ? null : onGrant,
                  child: Text(l10n.licenseGrantButton),
                )
              else
                Text(l10n.licenseGranted,
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
