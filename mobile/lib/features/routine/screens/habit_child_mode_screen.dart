import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../models/habit_models.dart';
import '../../agreement/child_agreement_screen.dart';
import '../providers/child_mode_providers.dart';

/// The child-facing self-reporting screen.
/// Very simple, large buttons, confirmation dialogs, no edit/delete.
class HabitChildModeScreen extends ConsumerWidget {
  const HabitChildModeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(childModeProvider);

    if (!state.active || state.day == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    // Expired UX Guard: if the child session died and the notifier surfaced
    // an explicit expiry message, take the child back to the lock screen so
    // the parent can re-issue a token. This avoids leaving the child in a
    // hung screen or showing a raw HTTP error.
    if (state.error == kChildModeErrorSessionExpired) {
      return _ExpiredGuard(childId: state.childId);
    }

    // The server refuses every other surface until the family agreement is
    // signed, and it names the agreement as the way through. Sending the
    // child straight there is what makes that refusal an instruction rather
    // than a dead end — the gate is only a gate if its exit is reachable.
    if (state.error == kChildModeAgreementRequired) {
      return const ChildAgreementScreen();
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context).habitChildModeTitle),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: AppLocalizations.of(context).habitChildModeExit,
            onPressed: () => _askExit(context, ref),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: state.day!.habits.length,
          itemBuilder: (context, index) {
            final item = state.day!.habits[index];
            return _HabitChildCard(
              item: HabitItem(
                category: item.category,
                habitName: item.habitName,
              ),
              submitted: state.isSubmitted(item.habitName),
            );
          },
        ),
      ),
    );
  }

  Future<void> _askExit(BuildContext context, WidgetRef ref) async {
    final state = ref.read(childModeProvider);
    final childId = state.childId;
    if (childId == null) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(AppLocalizations.of(context).habitChildModeExitTitle),
        content: Text(AppLocalizations.of(context).habitChildModeExitConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(AppLocalizations.of(context).cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(AppLocalizations.of(context).habitChildModeExit),
          ),
        ],
      ),
    );
    if (ok != true && context.mounted) return;
    if (!context.mounted) return;
    await Navigator.of(context).push(
      AppRoutes.childModeLock<void>(
        childId: childId,
        childName: AppLocalizations.of(context).childFallbackName,
        isExit: true,
      ),
    );
  }
}

class _ExpiredGuard extends StatefulWidget {
  final int? childId;
  const _ExpiredGuard({this.childId});

  @override
  State<_ExpiredGuard> createState() => _ExpiredGuardState();
}

class _ExpiredGuardState extends State<_ExpiredGuard> {
  @override
  void initState() {
    super.initState();
    // Let the frame settle, then push the lock screen as a modal replacement.
    WidgetsBinding.instance.addPostFrameCallback((_) => _redirect());
  }

  Future<void> _redirect() async {
    if (!mounted) return;
    final childId = widget.childId;
    final l10n = AppLocalizations.of(context);
    // Two genuinely different destinations, so they get two named routes
    // rather than one route that switches its own body — otherwise both
    // report as the same screen in analytics.
    await Navigator.of(context).pushReplacement(
      childId == null
          ? AppRoutes.childModeExpired<void>(l10n.habitChildModeExpired)
          : AppRoutes.childModeLock<void>(
              childId: childId,
              childName: l10n.childFallbackName,
              isExit: false,
            ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}

class _HabitChildCard extends ConsumerStatefulWidget {
  const _HabitChildCard({required this.item, required this.submitted});

  final HabitItem item;
  final bool submitted;

  @override
  ConsumerState<_HabitChildCard> createState() => _HabitChildCardState();
}

class _HabitChildCardState extends ConsumerState<_HabitChildCard> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = switch (widget.item.category) {
      HabitCategory.worship => theme.colorScheme.primary,
      HabitCategory.selfBuilding => theme.colorScheme.secondary,
      HabitCategory.study => theme.colorScheme.tertiary,
    };

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(_categoryIcon(widget.item.category), color: color),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    habitDisplayName(widget.item.habitName, AppLocalizations.of(context)),
                    style: theme.textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (widget.submitted)
              Center(
                child: Chip(
                  avatar: const Icon(Icons.check_circle, color: Colors.white),
                  label: Text(AppLocalizations.of(context).habitChildModeLogged),
                  backgroundColor: theme.colorScheme.primary,
                  labelStyle: const TextStyle(color: Colors.white),
                ),
              )
            else
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _ActionButton(
                    label: AppLocalizations.of(context).habitChildModeDone,
                    icon: Icons.check,
                    color: Colors.green,
                    onPressed: _busy ? null : () => _submit('completed', AppLocalizations.of(context).habitChildModeDone),
                  ),
                  _ActionButton(
                    label: AppLocalizations.of(context).habitChildModePartial,
                    icon: Icons.remove_circle_outline,
                    color: Colors.orange,
                    onPressed: _busy ? null : () => _submit('partially', AppLocalizations.of(context).habitChildModePartial),
                  ),
                  _ActionButton(
                    label: AppLocalizations.of(context).habitChildModeMissed,
                    icon: Icons.close,
                    color: Colors.red,
                    onPressed: _busy ? null : () => _submit('missed', AppLocalizations.of(context).habitChildModeMissed),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  IconData _categoryIcon(HabitCategory c) => switch (c) {
    HabitCategory.worship => Icons.mosque,
    HabitCategory.selfBuilding => Icons.self_improvement,
    HabitCategory.study => Icons.menu_book,
  };

  Future<void> _submit(String status, String label) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(AppLocalizations.of(context).habitChildModeConfirmTitle),
        content: Text(
          AppLocalizations.of(context).habitChildModeConfirmMsg(
              habitDisplayName(widget.item.habitName, AppLocalizations.of(context)), label),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(AppLocalizations.of(context).cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(AppLocalizations.of(context).confirm),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _busy = true);
    final ok = await ref
        .read(childModeProvider.notifier)
        .submit(widget.item, status);
    if (mounted) {
      setState(() => _busy = false);
      if (!ok) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppLocalizations.of(context).habitChildModeFailed)),
        );
      }
    }
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.label,
    required this.icon,
    required this.color,
    this.onPressed,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton.icon(
      onPressed: onPressed,
      icon: Icon(icon, color: Colors.white),
      label: Text(label),
      style: ElevatedButton.styleFrom(
        backgroundColor: color,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
    );
  }
}
