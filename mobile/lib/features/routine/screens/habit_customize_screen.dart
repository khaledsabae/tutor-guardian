/// Parent screen for customizing a child's habit templates.
///
/// Allows adding new custom habits per category, archiving/unarchiving
/// existing ones, while preserving historical events (soft archive).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/providers/habit_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/theme/design_tokens.dart';

class HabitCustomizeScreen extends ConsumerStatefulWidget {
  const HabitCustomizeScreen({super.key});

  @override
  ConsumerState<HabitCustomizeScreen> createState() => _HabitCustomizeScreenState();
}

class _HabitCustomizeScreenState extends ConsumerState<HabitCustomizeScreen> {
  HabitCategory _selectedCategory = HabitCategory.worship;
  final _nameController = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final childId = ref.watch(activeChildIdProvider);

    return Scaffold(
      appBar: AppBar(title: Text(AppLocalizations.of(context).routineCustomize)),
      body: childId == null
          ? Center(child: Text(AppLocalizations.of(context).routineNoHabits))
          : Column(
              children: [
                _CategorySelector(
                  selected: _selectedCategory,
                  onChanged: (c) => setState(() => _selectedCategory = c),
                ),
                Padding(
                  padding: const EdgeInsets.all(Dt.pad),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _nameController,
                          decoration: InputDecoration(
                            labelText: AppLocalizations.of(context).habitCustomizeNameLabel,
                            hintText: AppLocalizations.of(context).habitCustomizeNameHint,
                          ),
                          maxLength: 60,
                        ),
                      ),
                      const SizedBox(width: 8),
                      FilledButton.icon(
                        onPressed: _saving ? null : () => _addTemplate(childId),
                        icon: _saving
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.add),
                        label: Text(AppLocalizations.of(context).add),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: _TemplateList(
                    childId: childId,
                    category: _selectedCategory,
                  ),
                ),
              ],
            ),
    );
  }

  Future<void> _addTemplate(int childId) async {
    final l10n = AppLocalizations.of(context);
    final name = _nameController.text.trim();
    if (name.isEmpty || name.length < 2 || name.length > 60) {
      _showSnack(l10n.habitCustomizeNameLength);
      return;
    }
    setState(() => _saving = true);
    try {
      await TgClient().createHabitTemplate(
        childId,
        body: {
          'category': _selectedCategory.wireName,
          'custom_name': name,
        },
      );
      _nameController.clear();
      ref.invalidate(habitTemplatesProvider(childId));
      _showSnack(l10n.habitCustomizeAdded);
    } on TgApiError catch (e) {
      _showSnack(l10n.habitCustomizeAddFailed(e.message));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }
}

class _CategorySelector extends StatelessWidget {
  const _CategorySelector({required this.selected, required this.onChanged});

  final HabitCategory selected;
  final ValueChanged<HabitCategory> onChanged;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<HabitCategory>(
      segments: HabitCategory.values
          .map((c) => ButtonSegment(
                value: c,
                label: Text('${c.icon} ${c.label(AppLocalizations.of(context))}'),
              ))
          .toList(),
      selected: {selected},
      onSelectionChanged: (s) => onChanged(s.first),
    );
  }
}

class _TemplateList extends ConsumerWidget {
  const _TemplateList({required this.childId, required this.category});

  final int childId;
  final HabitCategory category;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncTemplates = ref.watch(habitTemplatesProvider(childId));

    return asyncTemplates.when(
      data: (all) {
        final templates = all.where((t) => t.category == category).toList();
        if (templates.isEmpty) {
          return Center(child: Text(AppLocalizations.of(context).routineNoHabits));
        }
        return ListView.builder(
          padding: const EdgeInsets.all(Dt.pad),
          itemCount: templates.length,
          itemBuilder: (context, i) {
            final t = templates[i];
            return _TemplateTile(
              template: t,
              onToggle: () => _toggleActive(context, ref, t),
            );
          },
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text(AppLocalizations.of(context).errorGeneric(e.toString()))),
    );
  }

  Future<void> _toggleActive(
    BuildContext context,
    WidgetRef ref,
    HabitTemplate template,
  ) async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    try {
      await TgClient().updateHabitTemplate(
        template.id,
        body: {'is_active': !template.isActive},
      );
      ref.invalidate(habitTemplatesProvider(template.childId));
    } on TgApiError catch (e) {
      messenger.showSnackBar(
        SnackBar(content: Text(l10n.habitCustomizeUpdateFailed(e.message))),
      );
    }
  }
}

class _TemplateTile extends StatelessWidget {
  const _TemplateTile({required this.template, required this.onToggle});

  final HabitTemplate template;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(
          template.isActive ? Icons.check_circle : Icons.archive_outlined,
          color: template.isActive ? null : Colors.grey,
        ),
        title: Text(
          template.customName,
          style: TextStyle(
            decoration: template.isActive ? null : TextDecoration.lineThrough,
            color: template.isActive ? null : Colors.grey,
          ),
        ),
        subtitle: Text(template.isActive ? AppLocalizations.of(context).habitChildModeDone : AppLocalizations.of(context).habitChildModeMissed),
        trailing: Switch(
          value: template.isActive,
          onChanged: (_) => onToggle(),
        ),
      ),
    );
  }
}
