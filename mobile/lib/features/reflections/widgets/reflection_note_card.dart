/// Phase 8-C — "ملاحظاتي" surface inside the lesson screen.
///
/// Read mode (default): shows the saved note + edit/delete actions.
/// Edit mode: text field + character counter + save/cancel actions.
/// Empty state: hint + "أضف ملاحظة" button.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../data/reflection_storage.dart';
import '../providers/reflections_providers.dart';

class ReflectionNoteCard extends ConsumerStatefulWidget {
  const ReflectionNoteCard({super.key, required this.lessonId});
  final String lessonId;

  @override
  ConsumerState<ReflectionNoteCard> createState() =>
      _ReflectionNoteCardState();
}

class _ReflectionNoteCardState extends ConsumerState<ReflectionNoteCard> {
  final _controller = TextEditingController();
  final _focus = FocusNode();
  bool _editing = false;

  @override
  void initState() {
    super.initState();
    final existing =
        ref.read(lessonReflectionProvider(widget.lessonId));
    _controller.text = existing?.text ?? '';
  }

  @override
  void didUpdateWidget(covariant ReflectionNoteCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.lessonId != widget.lessonId) {
      // Lesson changed — reset text from new entry.
      final existing = ref.read(lessonReflectionProvider(widget.lessonId));
      _controller.text = existing?.text ?? '';
      _editing = false;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _focus.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final text = _controller.text.trim();
    if (text.isEmpty) {
      // Treat empty save as a delete.
      await ref
          .read(reflectionsMapProvider.notifier)
          .delete(widget.lessonId);
    } else {
      await ref
          .read(reflectionsMapProvider.notifier)
          .save(widget.lessonId, text);
    }
    if (mounted) {
      setState(() => _editing = false);
      _focus.unfocus();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تم حفظ ملاحظتك.')),
      );
    }
  }

  Future<void> _delete() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('حذف الملاحظة؟'),
        content: const Text('سيتم حذف ملاحظتك على هذا الدرس. لا يمكن التراجع.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('إلغاء'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppTheme.dangerFg),
            child: const Text('حذف'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    await ref
        .read(reflectionsMapProvider.notifier)
        .delete(widget.lessonId);
    _controller.clear();
    if (mounted) {
      setState(() => _editing = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تم حذف الملاحظة.')),
      );
    }
  }

  void _startEdit() {
    setState(() => _editing = true);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focus.requestFocus();
    });
  }

  @override
  Widget build(BuildContext context) {
    final entry = ref.watch(lessonReflectionProvider(widget.lessonId));
    final hasNote = entry != null && entry.text.isNotEmpty;
    final theme = Theme.of(context);

    return Card(
      elevation: 0,
      color: AppTheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: Color(0xFFE4E7EC)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceAlt,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.edit_note,
                    size: 18,
                    color: AppTheme.textSecondary,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  'ملاحظاتي',
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                const Spacer(),
                if (hasNote && !_editing)
                  Text(
                    _formatDate(entry.updatedAt),
                    style: const TextStyle(
                      color: AppTheme.textMuted,
                      fontSize: 11,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            if (_editing) ...[
              TextField(
                controller: _controller,
                focusNode: _focus,
                maxLines: 4,
                minLines: 3,
                maxLength: ReflectionStorage.kMaxNoteLength,
                decoration: const InputDecoration(
                  hintText: 'كيف كانت تجربتك مع هذا الدرس؟ ماذا نجحت؟ ماذا ستجربين غداً؟',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () {
                      setState(() {
                        _editing = false;
                        // Restore prior text
                        _controller.text = entry?.text ?? '';
                      });
                      _focus.unfocus();
                    },
                    child: const Text('إلغاء'),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton.icon(
                    onPressed: _save,
                    icon: const Icon(Icons.save_outlined, size: 18),
                    label: const Text('حفظ'),
                  ),
                ],
              ),
            ] else if (hasNote) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceAlt,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  entry.text,
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    height: 1.55,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  TextButton.icon(
                    onPressed: _startEdit,
                    icon: const Icon(Icons.edit_outlined, size: 16),
                    label: const Text('تعديل'),
                  ),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: _delete,
                    icon: const Icon(Icons.delete_outline, size: 16),
                    label: const Text('حذف'),
                    style: TextButton.styleFrom(
                      foregroundColor: AppTheme.dangerFg,
                    ),
                  ),
                ],
              ),
            ] else ...[
              // Empty state
              const Text(
                'احفظ ملاحظة شخصية على هذا الدرس. ستظهر لك هنا وفي صفحة المسار.',
                style: TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 13,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _startEdit,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('أضف ملاحظة'),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(40),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    final y = local.year.toString().padLeft(4, '0');
    final m = local.month.toString().padLeft(2, '0');
    final d = local.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }
}
