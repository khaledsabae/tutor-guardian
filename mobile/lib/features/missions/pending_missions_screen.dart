/// The evening screen: every mission a child says they did, waiting on a
/// parent who was not there when they said it.
///
/// This is the second half of the asynchronous confirmation loop. The first
/// half is the child tapping "I did it" and not waiting — which is only
/// humane if the parent is given one place, once a day, to answer all of it.
/// A per-card notification would put the parent back in the loop the child
/// was freed from.
///
/// The default action is "confirm all", and each row can be excluded before
/// sending. That order is deliberate: a parent scanning at 9pm should have to
/// act only on the exception, and the common case is that the child did it.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/tg_client.dart';
import '../../l10n/app_localizations.dart';
import '../../state/chat_notifier.dart';

class PendingMissionsScreen extends ConsumerStatefulWidget {
  const PendingMissionsScreen({super.key});

  @override
  ConsumerState<PendingMissionsScreen> createState() =>
      _PendingMissionsScreenState();
}

class _PendingMissionsScreenState extends ConsumerState<PendingMissionsScreen> {
  List<Map<String, dynamic>>? _pending;
  String? _error;
  bool _sending = false;

  /// Mission ids the parent has explicitly marked "not yet". Everything not in
  /// here is confirmed when they send.
  final Set<int> _excluded = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final items = await ref.read(tgClientProvider).fetchPendingMissions();
      if (mounted) setState(() { _pending = items; _error = null; });
    } on TgApiError catch (e) {
      if (mounted) setState(() { _error = e.toString(); _pending = const []; });
    }
  }

  Future<void> _send() async {
    final pending = _pending;
    if (pending == null || pending.isEmpty || _sending) return;
    setState(() => _sending = true);

    // Every card is settled in one call, including the excluded ones — a card
    // marked "not yet" is answered `confirmed: false`, not left pending. If it
    // were left, tonight's digest would carry it again tomorrow, which is how
    // a nudge becomes nagging.
    final items = [
      for (final card in pending)
        {
          'mission_id': card['mission_id'],
          'confirmed': !_excluded.contains(card['mission_id'] as int),
        }
    ];

    try {
      await ref.read(tgClientProvider).confirmMissions(items);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on TgApiError catch (e) {
      if (!mounted) return;
      setState(() { _sending = false; _error = e.toString(); });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final pending = _pending;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.missionsPendingTitle)),
      body: pending == null
          ? const Center(child: CircularProgressIndicator())
          : pending.isEmpty
              ? _Empty(message: _error ?? l10n.missionsPendingEmpty)
              : Column(
                  children: [
                    Expanded(
                      child: ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: pending.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 8),
                        itemBuilder: (context, i) {
                          final card = pending[i];
                          final id = card['mission_id'] as int;
                          final excluded = _excluded.contains(id);
                          return Card(
                            elevation: 0,
                            color: excluded
                                ? theme.colorScheme.surfaceContainerHighest
                                : null,
                            child: ListTile(
                              title: Text(card['title_ar'] as String? ?? ''),
                              subtitle: Text(
                                '${card['child_name'] ?? ''} · '
                                '${card['estimated_minutes'] ?? 0} ${l10n.missionMinutesShort}',
                              ),
                              trailing: TextButton(
                                onPressed: () => setState(() {
                                  excluded
                                      ? _excluded.remove(id)
                                      : _excluded.add(id);
                                }),
                                child: Text(excluded
                                    ? l10n.missionMarkDone
                                    : l10n.missionMarkNotYet),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    if (_error != null)
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: Text(_error!,
                            style: TextStyle(color: theme.colorScheme.error)),
                      ),
                    SafeArea(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: FilledButton(
                          onPressed: _sending ? null : _send,
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(52),
                          ),
                          child: Text(
                            _excluded.isEmpty
                                ? l10n.missionConfirmAll
                                : l10n.missionConfirmRest(
                                    pending.length - _excluded.length),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text(message, textAlign: TextAlign.center),
        ),
      );
}
