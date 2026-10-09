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

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/analytics.dart';
import '../../l10n/app_localizations.dart';
import '../../state/chat_notifier.dart';
import '../coins/coins_providers.dart';
import '../../widgets/ui/error_retry_view.dart';
import 'mission_confirmations.dart';
import 'package:almorabbi/widgets/ui/loading_view.dart';

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

  /// «كلمة طيبة» — the selected quick-praise chip's text, or null when the
  /// parent sends none. Tapping a selected chip clears it again.
  String? _praiseChip;

  /// The optional short line the parent writes themselves.
  final _praiseController = TextEditingController();

  @override
  void dispose() {
    _praiseController.dispose();
    super.dispose();
  }

  /// The note that rides with tonight's confirmations: the chip, the parent's
  /// own line, or both. Empty when the parent sent no kind word at all.
  String get _praiseNote {
    final chip = _praiseChip;
    final own = _praiseController.text.trim();
    if (chip != null && own.isNotEmpty) return '$chip — $own';
    return chip ?? own;
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    // Read before the first await: this screen can be gone by the time any
    // answer comes back, and paying must not depend on it. (Called from
    // initState, so nothing that reads an inherited widget is taken here.)
    final client = ref.read(tgClientProvider);
    final coins = ref.read(coinsProvider.notifier);

    // A batch whose answer was lost is resent beside tonight's list, not
    // before it: on a flaky network the resend can take the whole request
    // timeout, and the list must not wait behind it. The resend is the only
    // way left to pay cards the server applied but never answered for.
    final flushing = MissionConfirmations.flush(client)
        .then<MissionConfirmResult?>((r) => r, onError: (Object _) => null);

    try {
      final items = await client.fetchPendingMissions();
      if (mounted) setState(() { _pending = items; _error = null; });
    } catch (e) {
      if (mounted) {
        final message = describeFailure(AppLocalizations.of(context), e);
        setState(() { _error = message; _pending = const []; });
      }
    }

    final flushed = await flushing;
    if (flushed == null) return;
    if (flushed.coins > 0) {
      await coins.refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(
                AppLocalizations.of(context).missionCoinsEarned(flushed.coins))));
      }
    }
    // The resend may have settled cards the list fetched beside it still shows.
    if (flushed.settled > 0 && mounted && !_sending) {
      try {
        final items = await client.fetchPendingMissions();
        if (mounted && !_sending) setState(() => _pending = items);
      } catch (_) {}
    }
  }

  Future<void> _send() async {
    final pending = _pending;
    if (pending == null || pending.isEmpty || _sending) return;
    setState(() => _sending = true);
    final client = ref.read(tgClientProvider);
    final coins = ref.read(coinsProvider.notifier);
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context);

    // Every card is settled in one call, including the excluded ones — a card
    // marked "not yet" is answered `confirmed: false`, not left pending. If it
    // were left, tonight's digest would carry it again tomorrow, which is how
    // a nudge becomes nagging.
    //
    // The kind word rides only with the confirmed cards: a note on a "not
    // yet" would reach the child as a contradiction. It is part of the item
    // map itself, so it lives in the outbox with the confirmation and survives
    // every retry — not just the first attempt.
    final note = _praiseNote;
    final items = <Map<String, dynamic>>[];
    for (final card in pending) {
      final confirmed = !_excluded.contains(card['mission_id'] as int);
      items.add({
        'mission_id': card['mission_id'],
        'confirmed': confirmed,
        if (confirmed && note.isNotEmpty) 'note': note,
      });
    }

    if (note.isNotEmpty) {
      // One event per praised band, not per card: three children in one
      // family is one evening of praise, not three.
      final bands = {
        for (final card in pending)
          if (!_excluded.contains(card['mission_id'] as int))
            if (card['age_band'] is String) card['age_band'] as String,
      };
      for (final band in bands) {
        unawaited(Analytics.praiseSent(band));
      }
    }

    try {
      // Prayer Journey cards come back with what they earned (MOBILE_API
      // §11.4.7); the device pays them, each mission once. Outbox, sending and
      // paying all live outside this screen, so leaving it mid-request no
      // longer loses the coins.
      final result = await MissionConfirmations.send(client, items);
      if (result.coins > 0) {
        await coins.refresh(); // the wallet outlives this screen
        messenger.showSnackBar(
            SnackBar(content: Text(l10n.missionCoinsEarned(result.coins))));
      }
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      // Any failure, not just an HTTP one: a spinner with no way out is the
      // worst answer. The batch stays in the outbox for the next try.
      if (!mounted) return;
      setState(() { _sending = false; _error = describeFailure(l10n, e); });
    }
  }

  /// The «كلمة طيبة» section: three fixed chips (they are fixed l10n strings,
  /// not du'as — nothing here is pulled from family_adhkar) and one short
  /// optional line of the parent's own.
  Widget _praiseSection(AppLocalizations l10n) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          Text(l10n.praiseSectionTitle,
              style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final chip in [
                l10n.praiseChipAhsant,
                l10n.praiseChipBarakAllahuFik,
                l10n.praiseChipProud,
              ])
                FilterChip(
                  label: Text(chip),
                  selected: _praiseChip == chip,
                  onSelected: (on) =>
                      setState(() => _praiseChip = on ? chip : null),
                ),
            ],
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _praiseController,
            maxLength: 80,
            textInputAction: TextInputAction.done,
            decoration: InputDecoration(
              hintText: l10n.praiseOwnWordsHint,
              isDense: true,
              counterText: '',
              border: const OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() {}),
          ),
        ],
      );

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final pending = _pending;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.missionsPendingTitle)),
      body: pending == null
          ? const LoadingView(count: 3)
          : pending.isEmpty
              ? _Empty(message: _error ?? l10n.missionsPendingEmpty)
              : Column(
                  children: [
                    Expanded(
                      child: ListView.separated(
                        padding: const EdgeInsets.all(16),
                        // One item more than the cards: the kind-word section
                        // rides at the end of the list, so the send button
                        // keeps its fixed place whatever the font scale.
                        itemCount: pending.length + 1,
                        separatorBuilder: (_, _) => const SizedBox(height: 8),
                        itemBuilder: (context, i) {
                          if (i == pending.length) return _praiseSection(l10n);
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
                                '${card['estimated_minutes'] ?? 0} ${l10n.missionMinutesShort}'
                                // A Prayer Journey card says what it earns.
                                '${_coinsOf(card) > 0 ? ' · 🪙 ${l10n.programsCoins(_coinsOf(card))}' : ''}',
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

/// Coins a pending card carries — only Prayer Journey cards have any.
int _coinsOf(Map<String, dynamic> card) => (card['coins'] as num?)?.toInt() ?? 0;

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
