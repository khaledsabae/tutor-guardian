/// «ما يعرفه المربّي عن <اسم>» — MOBILE_API §9.2, §9.3.
///
/// What the assistant remembers about one child, and every control over it:
/// confirm or reject a suggested health note, edit, reject or delete one
/// fact, add one, delete everything about the child, and the memory switch.
///
/// Privacy is the product here (plan §1.1 — the Muslim Pro scandal of 2020 is
/// what this screen exists to never resemble), so three rules hold on every
/// path:
///   * switching memory OFF always works — no proof, no pause, no error view
///     can hide the switch;
///   * the screen says what is kept, where, until when, and what is never
///     kept, in plain words, before the parent scrolls to anything else;
///   * names are swapped in on the device only (placeholder_names.dart) and
///     never sent back unless the parent changed the words.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/tg_client.dart';
import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/error_retry_view.dart';
import '../../../widgets/ui/empty_state.dart';
import '../data/memory_models.dart';
import '../data/placeholder_names.dart';
import '../device_proof/device_proof_service.dart';
import '../providers/memory_providers.dart';
import '../widgets/memory_errors.dart';
import '../widgets/memory_switch_tile.dart';
import '../widgets/proof_views.dart';

class ChildMemoryScreen extends ConsumerStatefulWidget {
  const ChildMemoryScreen({
    super.key,
    required this.childId,
    required this.childName,
  });

  final int childId;
  final String childName;

  @override
  ConsumerState<ChildMemoryScreen> createState() => _ChildMemoryScreenState();
}

class _ChildMemoryScreenState extends ConsumerState<ChildMemoryScreen> {
  bool _busy = false;

  List<FamilyMember> _family() => ref.watch(familyMembersProvider);

  void _reload() => ref.invalidate(childMemoryProvider(widget.childId));

  /// Runs one change, then reloads. Errors become one calm sentence.
  Future<bool> _change(Future<void> Function() op, {String? done}) async {
    if (_busy) return false;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    // Held before the await: the parent may leave the screen meanwhile.
    final container = ProviderScope.containerOf(context, listen: false);
    try {
      await op();
      if (done != null) {
        messenger.showSnackBar(SnackBar(content: Text(done)));
      }
      container.invalidate(childMemoryProvider(widget.childId));
      return true;
    } catch (e) {
      if (!mounted) return false;
      messenger.showSnackBar(
        SnackBar(content: Text(describeActionFailure(context, e))),
      );
      return false;
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _editFact(
      MemoryFact fact, RenderedMemoryText shown, int maxChars) async {
    final result = await showFactEditSheet(
      context,
      maxChars: maxChars,
      original: shown,
      initialCategory: fact.category,
    );
    if (result == null || !mounted) return;
    // Both in the stored form: the names the app put in are placeholders
    // again (RenderedMemoryText.restore), so an untouched text compares equal
    // and a touched one goes back without the names the app inserted.
    final textChanged = result.text != fact.fact.trim();
    final categoryChanged = result.category != fact.category;
    if (!textChanged && !categoryChanged) return;
    final repo = ref.read(memoryRepositoryProvider);
    await _change(() => repo.updateFact(
          widget.childId,
          fact.id,
          fact: textChanged ? result.text : null,
          category: categoryChanged ? result.category : null,
        ));
  }

  Future<void> _addFact(int maxChars) async {
    final result = await showFactEditSheet(context, maxChars: maxChars);
    if (result == null || !mounted) return;
    final repo = ref.read(memoryRepositoryProvider);
    await _change(() => repo.addFact(widget.childId,
        category: result.category, fact: result.text));
  }

  Future<void> _setStatus(MemoryFact fact, String status) async {
    final l10n = AppLocalizations.of(context);
    final repo = ref.read(memoryRepositoryProvider);
    await _change(
      () => repo.updateFact(widget.childId, fact.id, status: status),
      done: status == 'rejected' ? l10n.memoryRejected : null,
    );
  }

  Future<void> _deleteFact(MemoryFact fact) async {
    final l10n = AppLocalizations.of(context);
    final ok = await _confirm(
      title: l10n.memoryDeleteFactTitle,
      body: l10n.memoryDeleteFactBody,
      action: l10n.delete,
    );
    if (!ok || !mounted) return;
    final repo = ref.read(memoryRepositoryProvider);
    await _change(() => repo.deleteFact(widget.childId, fact.id),
        done: l10n.memoryFactDeleted);
  }

  Future<void> _forgetChild() async {
    final l10n = AppLocalizations.of(context);
    final ok = await _confirm(
      title: l10n.memoryForgetChild(widget.childName),
      body: l10n.memoryForgetChildBody(widget.childName),
      action: l10n.delete,
    );
    if (!ok || !mounted) return;
    final repo = ref.read(memoryRepositoryProvider);
    final container = ProviderScope.containerOf(context, listen: false);
    final done = await _change(() => repo.forgetChild(widget.childId),
        done: l10n.memoryForgotten(widget.childName));
    if (done) {
      container.invalidate(dueFollowupsProvider);
      container.invalidate(weeklyPlanProvider);
    }
  }

  Future<bool> _confirm({
    required String title,
    required String body,
    required String action,
  }) async {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.cancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: colors.dangerFg),
            child: Text(action),
          ),
        ],
      ),
    );
    return ok == true;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final asyncMemory = ref.watch(childMemoryProvider(widget.childId));
    final proof = ref.watch(deviceProofStateProvider);
    final family = _family();

    Widget body = asyncMemory.when(
      loading: () => proof.phase == ProofPhase.confirming
          ? const Center(child: ProofConfirmingView())
          : const Center(child: CircularProgressIndicator()),
      error: (e, _) => _ErrorBody(
        error: e,
        childName: widget.childName,
        onRetry: _reload,
      ),
      data: (memory) => _MemoryList(
        memory: memory,
        childName: widget.childName,
        family: family,
        childId: widget.childId,
        // The live switch first (it changes on this screen), else what came
        // with the list; adding is refused while memory is off (§9.2).
        memoryOn: ref.watch(memorySettingsProvider).valueOrNull?.enabled ??
            memory.settings?.enabled ??
            true,
        onConfirm: (f) => _setStatus(f, 'active'),
        onReject: (f) => _setStatus(f, 'rejected'),
        onEdit: (f, shown) => _editFact(f, shown, memory.maxFactChars),
        onDelete: _deleteFact,
        onAdd: () => _addFact(memory.maxFactChars),
        onForget: _forgetChild,
      ),
    );

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.memoryTitle(widget.childName)),
        bottom: _busy
            ? const PreferredSize(
                preferredSize: Size.fromHeight(2),
                child: LinearProgressIndicator(minHeight: 2),
              )
            : null,
      ),
      body: SafeArea(child: body),
    );
  }
}

/// Why the facts are not on screen — and the switch, which always is.
class _ErrorBody extends StatelessWidget {
  const _ErrorBody({
    required this.error,
    required this.childName,
    required this.onRetry,
  });

  final Object error;
  final String childName;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final e = error;
    if (e is TgApiError && e.isMissingEndpoint) {
      return EmptyState(emoji: '🌱', title: l10n.memoryUnavailable);
    }
    final Widget top;
    if (e is TgApiError && e.code == 'device_proof_cooldown') {
      top = ProofPausedView(
        until: e.availableAt ?? DateTime.now().toUtc(),
        body: l10n.proofPausedMemoryBody,
      );
    } else if (isProofError(e)) {
      top = ProofFailedView(error: e as TgApiError, onRetry: onRetry);
    } else {
      return ErrorRetryView(error: e, onRetry: onRetry);
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        _IntroCard(childName: childName),
        const SizedBox(height: 16),
        top,
        const SizedBox(height: 16),
        // Off must always be reachable — whatever else could not load.
        const MemorySwitchTile(),
        const SizedBox(height: 24),
        const _NeverKeptFooter(),
      ],
    );
  }
}

class _MemoryList extends StatelessWidget {
  const _MemoryList({
    required this.memory,
    required this.childName,
    required this.family,
    required this.childId,
    required this.memoryOn,
    required this.onConfirm,
    required this.onReject,
    required this.onEdit,
    required this.onDelete,
    required this.onAdd,
    required this.onForget,
  });

  final ChildMemory memory;
  final String childName;
  final List<FamilyMember> family;
  final int childId;
  final bool memoryOn;
  final ValueChanged<MemoryFact> onConfirm;
  final ValueChanged<MemoryFact> onReject;
  final void Function(MemoryFact fact, RenderedMemoryText shown) onEdit;
  final ValueChanged<MemoryFact> onDelete;
  final VoidCallback onAdd;
  final VoidCallback onForget;

  RenderedMemoryText _shown(MemoryFact f) => renderMemory(f.fact,
      childName: childName, family: family, subjectId: childId, lang: f.lang);

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final pending = memory.pending;
    final groups = memory.activeByCategory;
    final hasAny = pending.isNotEmpty || groups.isNotEmpty;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        _IntroCard(childName: childName),
        const SizedBox(height: 16),
        MemorySwitchTile(fallback: memory.settings),
        const SizedBox(height: 20),
        if (pending.isNotEmpty) ...[
          _SectionTitle(text: l10n.memoryPendingTitle),
          Padding(
            padding: const EdgeInsetsDirectional.only(start: 4, bottom: 8),
            child: Text(l10n.memoryPendingBody,
                style: TextStyle(color: colors.textSecondary, fontSize: 12)),
          ),
          for (final f in pending)
            _PendingFactCard(
              text: _shown(f).text,
              lang: f.lang,
              onConfirm: () => onConfirm(f),
              onReject: () => onReject(f),
            ),
          const SizedBox(height: 12),
        ],
        if (!hasAny)
          _EmptyMemory(childName: childName)
        else
          for (final entry in groups.entries) ...[
            _SectionTitle(text: categoryTitle(l10n, entry.key)),
            for (final f in entry.value)
              _FactTile(
                fact: f,
                shown: _shown(f).text,
                onEdit: () => onEdit(f, _shown(f)),
                onReject: () => onReject(f),
                onDelete: () => onDelete(f),
              ),
            const SizedBox(height: 8),
          ],
        const SizedBox(height: 8),
        Align(
          alignment: AlignmentDirectional.centerStart,
          child: OutlinedButton.icon(
            // Memory off: nothing new goes into memory by any route (§9.2).
            // Editing, confirming and deleting stay open.
            onPressed: memoryOn ? onAdd : null,
            icon: const Icon(Icons.add_rounded),
            label: Text(l10n.memoryAddFact),
          ),
        ),
        if (!memoryOn)
          Padding(
            padding: const EdgeInsetsDirectional.only(start: 4, top: 6),
            child: Text(l10n.memoryOffCannotAdd,
                style: TextStyle(
                    color: colors.textSecondary, fontSize: 12.5, height: 1.5)),
          ),
        if (hasAny) ...[
          const SizedBox(height: 12),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton.icon(
              onPressed: onForget,
              style: TextButton.styleFrom(foregroundColor: colors.dangerFg),
              icon: const Icon(Icons.delete_sweep_outlined),
              label: Text(l10n.memoryForgetChild(childName)),
            ),
          ),
        ],
        const SizedBox(height: 24),
        const _NeverKeptFooter(),
      ],
    );
  }
}

/// The category's heading on this screen (and its label in the edit sheet).
String categoryTitle(AppLocalizations l10n, String category) =>
    switch (category) {
      FactCategory.temperament => l10n.memoryCatTemperament,
      FactCategory.challenge => l10n.memoryCatChallenge,
      FactCategory.goal => l10n.memoryCatGoal,
      FactCategory.triedStrategy => l10n.memoryCatTried,
      FactCategory.outcome => l10n.memoryCatOutcome,
      FactCategory.healthNote => l10n.memoryCatHealth,
      FactCategory.school => l10n.memoryCatSchool,
      FactCategory.worship => l10n.memoryCatWorship,
      _ => l10n.memoryCatOther,
    };

class _IntroCard extends StatelessWidget {
  const _IntroCard({required this.childName});

  final String childName;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: colors.primary.withValues(alpha: colors.isDark ? .16 : .07),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.favorite_border_rounded, color: colors.primary, size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              l10n.memoryIntro(childName),
              style: TextStyle(color: colors.ink, fontSize: 13.5, height: 1.6),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.fromSTEB(4, 4, 4, 6),
      child: Semantics(
        header: true,
        child: Text(
          text,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: context.colors.ink,
                fontWeight: FontWeight.w800,
              ),
        ),
      ),
    );
  }
}

class _EmptyMemory extends StatelessWidget {
  const _EmptyMemory({required this.childName});

  final String childName;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.memoryEmptyTitle(childName),
              style: TextStyle(
                  color: colors.ink, fontWeight: FontWeight.w700, fontSize: 15)),
          const SizedBox(height: 6),
          Text(l10n.memoryEmptyBody,
              style: TextStyle(
                  color: colors.textSecondary, fontSize: 13, height: 1.6)),
        ],
      ),
    );
  }
}

class _PendingFactCard extends StatelessWidget {
  const _PendingFactCard({
    required this.text,
    required this.lang,
    required this.onConfirm,
    required this.onReject,
  });

  final String text;
  final String lang;
  final VoidCallback onConfirm;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colors.warningBg,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            text,
            textDirection: ContentDirectionality.resolve(
                languageCode: lang, text: text),
            style: TextStyle(color: colors.warningFg, fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            alignment: WrapAlignment.end,
            children: [
              TextButton(
                onPressed: onReject,
                style: TextButton.styleFrom(foregroundColor: colors.warningFg),
                child: Text(l10n.memoryRejectFact),
              ),
              FilledButton(
                onPressed: onConfirm,
                child: Text(l10n.memoryConfirmFact),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

enum _FactAction { edit, reject, delete }

class _FactTile extends StatelessWidget {
  const _FactTile({
    required this.fact,
    required this.shown,
    required this.onEdit,
    required this.onReject,
    required this.onDelete,
  });

  final MemoryFact fact;
  final String shown;
  final VoidCallback onEdit;
  final VoidCallback onReject;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final source = switch (fact.source) {
      'followup' => l10n.memorySourceFollowup,
      'parent_manual' => l10n.memorySourceManual,
      _ => l10n.memorySourceChat,
    };
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsetsDirectional.fromSTEB(14, 10, 4, 10),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: colors.track),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  shown,
                  textDirection: ContentDirectionality.resolve(
                      languageCode: fact.lang, text: shown),
                  style: TextStyle(color: colors.ink, fontSize: 14, height: 1.5),
                ),
                const SizedBox(height: 4),
                Text(source,
                    style: TextStyle(color: colors.inkSoft, fontSize: 11.5)),
              ],
            ),
          ),
          PopupMenuButton<_FactAction>(
            tooltip: l10n.memoryFactOptions,
            icon: Icon(Icons.more_vert_rounded, color: colors.inkSoft),
            onSelected: (a) => switch (a) {
              _FactAction.edit => onEdit(),
              _FactAction.reject => onReject(),
              _FactAction.delete => onDelete(),
            },
            itemBuilder: (_) => [
              PopupMenuItem(value: _FactAction.edit, child: Text(l10n.edit)),
              PopupMenuItem(
                  value: _FactAction.reject, child: Text(l10n.memoryRejectFact)),
              PopupMenuItem(value: _FactAction.delete, child: Text(l10n.delete)),
            ],
          ),
        ],
      ),
    );
  }
}

class _NeverKeptFooter extends StatelessWidget {
  const _NeverKeptFooter();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: colors.surfaceAlt,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.shield_outlined, size: 18, color: colors.primary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(l10n.memoryNeverTitle,
                    style: TextStyle(
                        color: colors.ink,
                        fontWeight: FontWeight.w700,
                        fontSize: 14)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(l10n.memoryNeverBody,
              style: TextStyle(
                  color: colors.textSecondary, fontSize: 12.5, height: 1.6)),
          const SizedBox(height: 8),
          Text(l10n.memoryWhereKept,
              style: TextStyle(
                  color: colors.textSecondary, fontSize: 12.5, height: 1.6)),
        ],
      ),
    );
  }
}

/// The add/edit sheet. Resolves to the text — in the STORED form, with the
/// names the app put in turned back into their placeholders — and the
/// category; or null.
Future<({String text, String category})?> showFactEditSheet(
  BuildContext context, {
  required int maxChars,
  RenderedMemoryText? original,
  String? initialCategory,
}) {
  return showModalBottomSheet<({String text, String category})>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _FactEditSheet(
      maxChars: maxChars,
      original: original,
      initialCategory: initialCategory,
    ),
  );
}

class _FactEditSheet extends StatefulWidget {
  const _FactEditSheet({
    required this.maxChars,
    this.original,
    this.initialCategory,
  });

  final int maxChars;

  /// The fact being edited, as shown (null: adding a new one).
  final RenderedMemoryText? original;
  final String? initialCategory;

  @override
  State<_FactEditSheet> createState() => _FactEditSheetState();
}

class _FactEditSheetState extends State<_FactEditSheet> {
  late final TextEditingController _text =
      TextEditingController(text: widget.original?.text ?? '');

  /// What would be stored: the limit is the server's, on the stored form —
  /// «طفلي» is four characters whatever the child's name is.
  String get _stored =>
      (widget.original?.restore(_text.text) ?? _text.text).trim();
  late String _category = widget.initialCategory ?? FactCategory.other;

  @override
  void initState() {
    super.initState();
    _text.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final editing = widget.original != null;
    final stored = _stored;
    final canSave = stored.isNotEmpty && stored.length <= widget.maxChars;
    return Padding(
      padding: EdgeInsets.fromLTRB(
          20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              editing ? l10n.memoryEditTitle : l10n.memoryAddTitle,
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _category,
              isExpanded: true,
              decoration: InputDecoration(labelText: l10n.memoryCategoryLabel),
              items: [
                for (final c in FactCategory.all)
                  DropdownMenuItem(
                      value: c, child: Text(categoryTitle(l10n, c))),
              ],
              onChanged: (v) => setState(() => _category = v ?? _category),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _text,
              autofocus: !editing,
              minLines: 2,
              maxLines: 4,
              // A generous cap on the field; the real limit is on what is
              // stored, and the counter shows that.
              inputFormatters: [
                LengthLimitingTextInputFormatter(widget.maxChars * 2),
              ],
              textInputAction: TextInputAction.done,
              decoration: InputDecoration(
                hintText: l10n.memoryFactHint,
                counterText: '${stored.length}/${widget.maxChars}',
                errorText: stored.length > widget.maxChars
                    ? l10n.memoryFactTooLong(widget.maxChars)
                    : null,
              ),
            ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: canSave
                  ? () => Navigator.of(context)
                      .pop((text: stored, category: _category))
                  : null,
              child: Text(l10n.save),
            ),
          ],
        ),
      ),
    );
  }
}
