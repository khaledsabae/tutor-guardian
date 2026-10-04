/// «جرّبت النصيحة؟ نفعت؟» — the follow-up sheet (MOBILE_API §9.4).
///
/// One sheet for both ways in: the Today card (with the follow-up already in
/// hand, and maybe the outcome the parent tapped) and the `/followup/{id}`
/// deep link a follow-up push carries (fetched here, in any status). Four
/// answers, an optional note, a thank-you — or "don't ask about this". A
/// follow-up that is no longer pending shows its result instead of buttons.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/tg_client.dart';
import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_colors.dart';
import '../data/memory_models.dart';
import '../data/placeholder_names.dart';
import '../device_proof/device_proof_service.dart';
import '../providers/memory_providers.dart';
import 'memory_errors.dart';
import 'proof_views.dart';

/// Where a follow-up was answered from (`followup_answered.source`).
abstract final class FollowupSource {
  static const today = 'today';
  static const push = 'push';
}

/// The note's limit on the server (`MAX_NOTE_CHARS`).
const int kFollowupNoteMaxChars = 300;

/// The label of an outcome, as offered and as reported back.
String outcomeLabel(AppLocalizations l10n, String outcome) => switch (outcome) {
      FollowupOutcome.worked => l10n.followupWorked,
      FollowupOutcome.partly => l10n.followupPartly,
      FollowupOutcome.didntWork => l10n.followupDidntWork,
      _ => l10n.followupDidntTry,
    };

/// Open the sheet for [followupId]. [initial] skips the fetch; [preselected]
/// is the outcome the parent already tapped on the card.
Future<void> showFollowupSheet(
  BuildContext context, {
  required int followupId,
  required String source,
  Followup? initial,
  String? preselected,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    routeSettings: const RouteSettings(name: Screens.followup),
    builder: (_) => FollowupSheet(
      followupId: followupId,
      source: source,
      initial: initial,
      preselected: preselected,
    ),
  );
}

class FollowupSheet extends ConsumerStatefulWidget {
  const FollowupSheet({
    super.key,
    required this.followupId,
    required this.source,
    this.initial,
    this.preselected,
  });

  final int followupId;
  final String source;
  final Followup? initial;
  final String? preselected;

  @override
  ConsumerState<FollowupSheet> createState() => _FollowupSheetState();
}

class _FollowupSheetState extends ConsumerState<FollowupSheet> {
  final TextEditingController _note = TextEditingController();
  Followup? _followup;

  /// What the server said about memory with the follow-up (null: not said —
  /// an older server, or the follow-up came from the Today card).
  bool? _memoryEnabled;
  Object? _loadError;
  bool _loading = false;
  String? _outcome;
  bool _sending = false;
  String? _error;
  FollowupAnswer? _answer;

  @override
  void initState() {
    super.initState();
    _followup = widget.initial;
    _outcome = widget.preselected;
    if (_followup == null) unawaited(_load());
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final view =
          await ref.read(memoryRepositoryProvider).followup(widget.followupId);
      if (!mounted) return;
      setState(() {
        _followup = view.followup;
        _memoryEnabled = view.memoryEnabled;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadError = e;
        _loading = false;
      });
    }
  }

  Future<void> _send() async {
    final outcome = _outcome;
    final f = _followup;
    if (outcome == null || f == null || _sending) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    // Held before the await: the sheet may be swiped away meanwhile, and the
    // Today list must still learn that this one was answered.
    final container = ProviderScope.containerOf(context, listen: false);
    try {
      final answer = await container.read(memoryRepositoryProvider).answer(
            f.id,
            outcome: outcome,
            note: _note.text.trim().isEmpty ? null : _note.text.trim(),
          );
      // Counted only when kept: an answer given while memory was off is not
      // a reply the loop can use.
      if (answer.remembered) {
        unawaited(Analytics.followupAnswered(outcome, widget.source));
      }
      container.invalidate(dueFollowupsProvider);
      container.invalidate(childMemoryProvider(f.childId));
      if (!mounted) return;
      setState(() {
        _answer = answer;
        _sending = false;
      });
    } on TgApiError catch (e) {
      if (!mounted) return;
      if (e.code == 'followup_closed') {
        // Answered elsewhere meanwhile: show what it says now.
        container.invalidate(dueFollowupsProvider);
        setState(() => _sending = false);
        await _load();
        return;
      }
      setState(() {
        _sending = false;
        _error = describeActionFailure(context, e);
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        _error = describeActionFailure(context, e);
      });
    }
  }

  /// "Turn memory on" from a paused follow-up: switching on needs a proven
  /// session (the repository proves and retries), then the follow-up is read
  /// again — the server now says whether an answer would be kept.
  Future<void> _turnMemoryOn() async {
    if (_sending) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    final container = ProviderScope.containerOf(context, listen: false);
    try {
      await container.read(memoryRepositoryProvider).setEnabled(true);
      container
        ..invalidate(memorySettingsProvider)
        ..invalidate(dueFollowupsProvider);
      if (!mounted) return;
      setState(() {
        _sending = false;
        _memoryEnabled = null;
      });
      await _load();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        _error = describeActionFailure(context, e);
      });
    }
  }

  Future<void> _dismiss() async {
    final f = _followup;
    if (f == null || _sending) return;
    final l10n = AppLocalizations.of(context);
    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() {
      _sending = true;
      _error = null;
    });
    final container = ProviderScope.containerOf(context, listen: false);
    try {
      await container.read(memoryRepositoryProvider).dismiss(f.id);
      if (widget.source == FollowupSource.today) {
        unawaited(Analytics.todayBlockTapped('loop', 'followup_dismiss'));
      }
      container.invalidate(dueFollowupsProvider);
      if (!mounted) return;
      navigator.pop();
      messenger.showSnackBar(SnackBar(content: Text(l10n.followupDismissed)));
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        _error = describeActionFailure(context, e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final proof = ref.watch(deviceProofStateProvider);
    final Widget content;
    if (_answer != null) {
      content = _answer!.remembered
          ? _Thanks(answer: _answer!)
          : const _NotSaved();
    } else if (_loading) {
      content = proof.phase == ProofPhase.confirming
          ? const ProofConfirmingView()
          : const Padding(
              padding: EdgeInsets.all(32),
              child: Center(child: CircularProgressIndicator()),
            );
    } else if (_loadError != null) {
      content = _LoadFailed(error: _loadError!, onRetry: _load);
    } else if (_followup == null) {
      content = const SizedBox.shrink();
    } else if (!_followup!.isPending) {
      content = _Closed(followup: _followup!);
    } else if (_memoryEnabled == false ||
        ref.watch(memorySettingsProvider).valueOrNull?.enabled == false) {
      // Memory is off: the loop is paused. No answer is offered that memory
      // would then keep — and a push sent before the switch can still land.
      content = _MemoryOff(
        followup: _followup!,
        busy: _sending,
        error: _error,
        onTurnOn: _turnMemoryOn,
      );
    } else {
      content = _Ask(
        followup: _followup!,
        outcome: _outcome,
        note: _note,
        sending: _sending,
        error: _error,
        onOutcome: (o) => setState(() => _outcome = o),
        onSend: _send,
        onDismiss: _dismiss,
      );
    }
    return Padding(
      padding: EdgeInsets.fromLTRB(
          20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(child: content),
    );
  }
}

/// The child's name for a follow-up, and the family for sibling letters.
({String? name, List<FamilyMember> family}) _who(WidgetRef ref, int childId) =>
    (
      name: ref.watch(childNameProvider(childId)),
      family: ref.watch(familyMembersProvider),
    );

class _Ask extends ConsumerWidget {
  const _Ask({
    required this.followup,
    required this.outcome,
    required this.note,
    required this.sending,
    required this.error,
    required this.onOutcome,
    required this.onSend,
    required this.onDismiss,
  });

  final Followup followup;
  final String? outcome;
  final TextEditingController note;
  final bool sending;
  final String? error;
  final ValueChanged<String> onOutcome;
  final VoidCallback onSend;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final who = _who(ref, followup.childId);
    final strategy = renderMemoryText(followup.strategy,
        childName: who.name,
        family: who.family,
        subjectId: followup.childId,
        lang: followup.lang);
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          who.name == null ? l10n.followupTitle : l10n.followupTitleFor(who.name!),
          style: TextStyle(
              color: colors.primary, fontWeight: FontWeight.w700, fontSize: 13),
        ),
        const SizedBox(height: 6),
        Text(
          l10n.followupQuestion(strategy),
          textDirection: ContentDirectionality.resolve(
              text: strategy, fallback: Directionality.of(context)),
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: colors.ink,
                fontWeight: FontWeight.w700,
                height: 1.5,
              ),
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final o in FollowupOutcome.all)
              ChoiceChip(
                label: Text(outcomeLabel(l10n, o)),
                selected: outcome == o,
                onSelected: sending ? null : (_) => onOutcome(o),
              ),
          ],
        ),
        const SizedBox(height: 14),
        TextField(
          controller: note,
          enabled: !sending,
          minLines: 1,
          maxLines: 4,
          maxLength: kFollowupNoteMaxChars,
          decoration: InputDecoration(hintText: l10n.followupNoteHint),
        ),
        if (error != null) ...[
          const SizedBox(height: 4),
          Text(error!,
              style: TextStyle(color: colors.dangerFg, fontSize: 13, height: 1.5)),
        ],
        const SizedBox(height: 8),
        FilledButton(
          onPressed: outcome == null || sending ? null : onSend,
          child: sending
              ? SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: colors.onPrimary),
                )
              : Text(l10n.send),
        ),
        const SizedBox(height: 4),
        TextButton(
          onPressed: sending ? null : onDismiss,
          child: Text(l10n.followupDismiss),
        ),
      ],
    );
  }
}

class _MemoryOff extends ConsumerWidget {
  const _MemoryOff({
    required this.followup,
    required this.busy,
    required this.error,
    required this.onTurnOn,
  });

  final Followup followup;
  final bool busy;
  final String? error;
  final VoidCallback onTurnOn;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final who = _who(ref, followup.childId);
    final strategy = renderMemoryText(followup.strategy,
        childName: who.name,
        family: who.family,
        subjectId: followup.childId,
        lang: followup.lang);
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          strategy,
          textDirection: ContentDirectionality.resolve(
              text: strategy, fallback: Directionality.of(context)),
          style: TextStyle(color: colors.ink, fontSize: 15, height: 1.5),
        ),
        const SizedBox(height: 12),
        Text(l10n.followupMemoryOff,
            style: TextStyle(
                color: colors.textSecondary, fontSize: 13.5, height: 1.6)),
        if (error != null) ...[
          const SizedBox(height: 8),
          Text(error!,
              style: TextStyle(color: colors.dangerFg, fontSize: 13, height: 1.5)),
        ],
        const SizedBox(height: 16),
        FilledButton(
          onPressed: busy ? null : onTurnOn,
          child: busy
              ? SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: colors.onPrimary),
                )
              : Text(l10n.memoryTurnOn),
        ),
        const SizedBox(height: 4),
        TextButton(
          onPressed: busy ? null : () => Navigator.of(context).maybePop(),
          child: Text(l10n.close),
        ),
      ],
    );
  }
}

/// An answer given while memory was off: nothing was kept — not the
/// outcome, not the note — so no thank-you that promises to remember.
class _NotSaved extends StatelessWidget {
  const _NotSaved();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(l10n.followupNotSaved,
            textAlign: TextAlign.center,
            style: TextStyle(color: colors.ink, fontSize: 15, height: 1.6)),
        const SizedBox(height: 16),
        OutlinedButton(
          onPressed: () => Navigator.of(context).maybePop(),
          child: Text(l10n.close),
        ),
      ],
    );
  }
}

class _Thanks extends StatelessWidget {
  const _Thanks({required this.answer});

  final FollowupAnswer answer;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final line = switch (answer.followup.outcome) {
      FollowupOutcome.worked => l10n.followupThanksWorked,
      FollowupOutcome.partly => l10n.followupThanksPartly,
      FollowupOutcome.didntWork => l10n.followupThanksDidntWork,
      _ => l10n.followupThanksDidntTry,
    };
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          l10n.followupThanksTitle,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: colors.ink,
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 10),
        Text(line,
            textAlign: TextAlign.center,
            style: TextStyle(
                color: colors.textSecondary, fontSize: 14, height: 1.6)),
        if (answer.noteDropped) ...[
          const SizedBox(height: 12),
          Text(l10n.followupNoteDropped,
              textAlign: TextAlign.center,
              style: TextStyle(color: colors.inkSoft, fontSize: 12.5, height: 1.5)),
        ],
        const SizedBox(height: 16),
        FilledButton(
          onPressed: () => Navigator.of(context).maybePop(),
          child: Text(l10n.done),
        ),
      ],
    );
  }
}

class _Closed extends ConsumerWidget {
  const _Closed({required this.followup});

  final Followup followup;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final who = _who(ref, followup.childId);
    final strategy = renderMemoryText(followup.strategy,
        childName: who.name,
        family: who.family,
        subjectId: followup.childId,
        lang: followup.lang);
    final result = switch (followup.status) {
      'answered' => l10n.followupAnsweredResult(
          outcomeLabel(l10n, followup.outcome ?? FollowupOutcome.didntTry)),
      'dismissed' => l10n.followupDismissedResult,
      _ => l10n.followupExpiredResult,
    };
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          who.name == null ? l10n.followupTitle : l10n.followupTitleFor(who.name!),
          style: TextStyle(
              color: colors.primary, fontWeight: FontWeight.w700, fontSize: 13),
        ),
        const SizedBox(height: 6),
        Text(
          strategy,
          textDirection: ContentDirectionality.resolve(
              text: strategy, fallback: Directionality.of(context)),
          style: TextStyle(color: colors.ink, fontSize: 15, height: 1.5),
        ),
        const SizedBox(height: 12),
        Text(result,
            style: TextStyle(
                color: colors.textSecondary,
                fontWeight: FontWeight.w600,
                fontSize: 14)),
        if (followup.status == 'answered' && followup.note != null) ...[
          const SizedBox(height: 6),
          Text(followup.note!,
              style: TextStyle(color: colors.inkSoft, fontSize: 13, height: 1.5)),
        ],
        const SizedBox(height: 16),
        OutlinedButton(
          onPressed: () => Navigator.of(context).maybePop(),
          child: Text(l10n.close),
        ),
      ],
    );
  }
}

class _LoadFailed extends StatelessWidget {
  const _LoadFailed({required this.error, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final e = error;
    if (e is TgApiError && e.code == 'device_proof_cooldown') {
      return ProofPausedView(
        until: e.availableAt ?? DateTime.now().toUtc(),
        body: l10n.proofPausedMemoryBody,
      );
    }
    if (isProofError(e)) {
      return ProofFailedView(error: e as TgApiError, onRetry: onRetry);
    }
    final notFound = e is TgApiError &&
        (e.code == 'followup_not_found' || e.isMissingEndpoint);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            notFound ? l10n.followupNotFound : memoryErrorText(l10n, e),
            textAlign: TextAlign.center,
            style: TextStyle(color: colors.textSecondary, fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 12),
          if (!notFound)
            FilledButton(onPressed: onRetry, child: Text(l10n.retry))
          else
            OutlinedButton(
              onPressed: () => Navigator.of(context).maybePop(),
              child: Text(l10n.close),
            ),
        ],
      ),
    );
  }
}
