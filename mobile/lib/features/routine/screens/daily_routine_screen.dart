/// Daily routine tab — «حِساب اليوم».
///
/// Lists today's sleep/feed/diaper events and lets the parent add new ones.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/theme/app_theme.dart';
import 'package:almorabbi/theme/design_tokens.dart';
import 'package:almorabbi/features/routine/models/routine_models.dart';
import 'package:almorabbi/features/routine/providers/routine_providers.dart';

bool routineAgeAllowed(String ageGroup) {
  return const {'prenatal-1', '0-3', '4-6', '7-9'}.contains(ageGroup);
}

List<RoutineEventType> allowedRoutineTypes(String ageGroup) {
  return switch (ageGroup) {
    'prenatal-1' || '0-3' || '4-6' => RoutineEventType.values,
    '7-9' => const [RoutineEventType.sleep, RoutineEventType.feed],
    _ => const [],
  };
}

class DailyRoutineScreen extends ConsumerWidget {
  const DailyRoutineScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final childId = ref.watch(activeChildIdProvider);
    final profile = ref.watch(activeChildProfileProvider);

    if (profile != null && !routineAgeAllowed(profile.ageGroup)) {
      return Scaffold(
        appBar: AppBar(title: const Text('حِساب اليوم 🍼')),
        body: _RoutineAgeGate(profile: profile),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('حِساب اليوم 🍼'),
        actions: const [
          Padding(
            padding: EdgeInsets.symmetric(horizontal: 12),
            child: Center(child: _ActiveChildChip()),
          ),
        ],
      ),
      body: childId == null
          ? const _NoChildState()
          : const _RoutineBody(),
      floatingActionButton: childId == null || (profile != null && !routineAgeAllowed(profile.ageGroup))
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _showAddEventDialog(context, childId),
              icon: const Icon(Icons.add),
              label: const Text('حدث جديد'),
            ),
    );
  }

  void _showAddEventDialog(BuildContext context, int childId) {
    final profile = ProviderScope.containerOf(context)
        .read(activeChildProfileProvider);
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(Dt.rSheet)),
      ),
      builder: (_) => _AddEventSheet(
        childId: childId,
        ageGroup: profile?.ageGroup ?? '0-3',
      ),
    );
  }
}

class _RoutineAgeGate extends StatelessWidget {
  final ActiveChildProfile profile;
  const _RoutineAgeGate({required this.profile});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('🍼', style: TextStyle(fontSize: 56)),
          const SizedBox(height: 12),
          Text(
            'التتبع اليومي متاح للأطفال حتى 9 سنوات',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'الطفل ${profile.name} في مرحلة ${profile.ageGroup}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _ActiveChildChip extends ConsumerWidget {
  const _ActiveChildChip();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(activeChildProfileProvider);
    if (profile == null) return const SizedBox.shrink();
    return Chip(
      avatar: Text(profile.avatarEmoji ?? '👶'),
      label: Text(profile.name, style: const TextStyle(fontSize: 12)),
      backgroundColor: Dt.primary.withValues(alpha: .12),
    );
  }
}

class _NoChildState extends StatelessWidget {
  const _NoChildState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('👶', style: TextStyle(fontSize: 56)),
          const SizedBox(height: 12),
          Text(
            'أضف طفلك أولاً من شاشة اليوم',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ],
      ),
    );
  }
}

class _RoutineBody extends ConsumerWidget {
  const _RoutineBody();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final childId = ref.watch(activeChildIdProvider);
    final routineAsync = childId == null
        ? const AsyncData(RoutineDay(routineId: 0, childId: 0, routineDate: '', events: []))
        : ref.watch(todayRoutineProvider(childId));

    return Column(
      children: [
        const _SummaryCard(),
        Expanded(
          child: routineAsync.when(
            data: (day) => _EventsList(day: day),
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('خطأ: ${e.toString()}')),
          ),
        ),
      ],
    );
  }
}

class _SummaryCard extends ConsumerWidget {
  const _SummaryCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final childId = ref.watch(activeChildIdProvider);
    if (childId == null) return const SizedBox.shrink();
    final summaryAsync = ref.watch(routineSummaryProvider(childId));

    return summaryAsync.when(
      data: (s) => s == null
          ? const SizedBox.shrink()
          : Card(
              margin: const EdgeInsets.all(Dt.pad),
              child: Padding(
                padding: const EdgeInsets.all(Dt.pad),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('ملخّص ${s.days} أيام', style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _Stat(icon: '🌙', value: '${(s.totalSleepMinutes / 60).floor()}h', label: 'نوم'),
                        _Stat(icon: '🍼', value: '${s.totalFeedCount}', label: 'رضاعات'),
                        _Stat(icon: '👶', value: '${s.diaperCount}', label: 'حفاظات'),
                      ],
                    ),
                  ],
                ),
              ),
            ),
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.icon, required this.value, required this.label});
  final String icon;
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(icon, style: const TextStyle(fontSize: 22)),
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
        Text(label, style: const TextStyle(fontSize: 12)),
      ],
    );
  }
}

class _EventsList extends StatelessWidget {
  const _EventsList({required this.day});
  final RoutineDay day;

  @override
  Widget build(BuildContext context) {
    if (day.events.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('✍️', style: TextStyle(fontSize: 48)),
            const SizedBox(height: 12),
            Text('لا توجد أحداث اليوم', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('اضغط + لإضافة أول حدث', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(Dt.pad),
      itemCount: day.events.length,
      itemBuilder: (context, i) {
        final e = day.events[i];
        return _EventTile(event: e)
            .animate()
            .fadeIn(delay: (i * 80).ms, duration: Dt.base);
      },
    );
  }
}

class _EventTile extends StatelessWidget {
  const _EventTile({required this.event});
  final RoutineEvent event;

  String _subtitle() {
    final parts = <String>[];
    if (event.feedType != null) parts.add('نوع: ${event.feedType}');
    if (event.amountMl != null) parts.add('${event.amountMl} ml');
    if (event.side != null) parts.add('جانب: ${event.side}');
    if (event.diaperType != null) parts.add('${event.diaperType}');
    if (event.endedAt != null && event.eventType == RoutineEventType.sleep) {
      final mins = event.endedAt!.difference(event.startedAt).inMinutes;
      parts.add('مدة: ${mins ~/ 60}h ${mins % 60}m');
    }
    return parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Text(event.eventType.icon, style: const TextStyle(fontSize: 28)),
        title: Text(event.eventType.label),
        subtitle: Text(
          '${_formatTime(event.startedAt)}${_subtitle().isEmpty ? '' : '\n${_subtitle()}'}',
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete_outline, color: AppTheme.dangerFg),
          onPressed: () => _delete(context, event.id),
        ),
      ),
    );
  }

  String _formatTime(DateTime dt) =>
      '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';

  void _delete(BuildContext context, int? eventId) {
    if (eventId == null) return;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('حذف الحدث؟'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('إلغاء')),
          TextButton(
            onPressed: () async {
              Navigator.of(ctx).pop();
              try {
                await TgClient().deleteRoutineEvent(eventId);
              } on TgApiError catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('فشل الحذف: ${e.message}')),
                );
              }
            },
            child: const Text('حذف', style: TextStyle(color: AppTheme.dangerFg)),
          ),
        ],
      ),
    );
  }
}

// ── Add-event sheet ───────────────────────────────────────────────────────

class _AddEventSheet extends StatefulWidget {
  const _AddEventSheet({required this.childId, required this.ageGroup});
  final int childId;
  final String ageGroup;

  @override
  State<_AddEventSheet> createState() => _AddEventSheetState();
}

class _AddEventSheetState extends State<_AddEventSheet> {
  late RoutineEventType _type = allowedRoutineTypes(widget.ageGroup).first;
  late final List<RoutineEventType> _allowedTypes = allowedRoutineTypes(widget.ageGroup);
  DateTime _startedAt = DateTime.now();
  DateTime? _endedAt;
  String? _feedType;
  int? _amountMl;
  String? _side;
  String? _diaperType;
  final _notesController = TextEditingController();
  bool _saving = false;

  static final _medicalTerms = RegExp(
    r'(جرعة|دواء|أدوية|علاج|مرض|تشخيص|سكر|ضغط|حمة|حمى|إسهال|قيء|طفح|عدوى|'
    r'infection|diagnosis|medication|dosage|dose|medicine|fever|rash|vomit|diarrhea)',
    caseSensitive: false,
  );

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        top: Dt.pad,
        left: Dt.pad,
        right: Dt.pad,
        bottom: MediaQuery.of(context).viewInsets.bottom + Dt.pad,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'إضافة حدث ${_type.label}',
            style: Theme.of(context).textTheme.titleMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),
          SegmentedButton<RoutineEventType>(
            segments: _allowedTypes
                .map((t) => ButtonSegment(
                      value: t,
                      label: Text('${t.icon} ${t.label}'),
                    ))
                .toList(),
            selected: {_type},
            onSelectionChanged: (s) => setState(() {
              _type = s.first;
              _clearTypeSpecific();
            }),
          ),
          const SizedBox(height: 16),
          _typeFields(),
          const SizedBox(height: 12),
          TextField(
            controller: _notesController,
            decoration: const InputDecoration(
              labelText: 'ملاحظة (اختياري)',
              helperText: 'لا تكتب أدوية أو أعراض طبية',
            ),
            maxLength: 500,
            maxLines: 2,
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _saving ? null : _submit,
            child: _saving
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('حفظ'),
          ),
        ],
      ),
    );
  }

  Widget _typeFields() {
    return switch (_type) {
      RoutineEventType.feed => Column(
          children: [
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'breast', label: Text('ثدي')),
                ButtonSegment(value: 'bottle', label: Text('رضّاعة')),
                ButtonSegment(value: 'solid', label: Text('طعام صلب')),
              ],
              selected: {_feedType ?? 'breast'},
              onSelectionChanged: (s) => setState(() => _feedType = s.first),
            ),
            const SizedBox(height: 8),
            if ((_feedType ?? 'breast') == 'breast')
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'left', label: Text('يسار')),
                  ButtonSegment(value: 'right', label: Text('يمين')),
                  ButtonSegment(value: 'both', label: Text('كلاهما')),
                ],
                selected: {_side ?? 'left'},
                onSelectionChanged: (s) => setState(() => _side = s.first),
              ),
            if ((_feedType ?? 'breast') != 'breast')
              TextField(
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'الكمية تقريباً (ml)',
                ),
                onChanged: (v) => _amountMl = int.tryParse(v),
              ),
          ],
        ),
      RoutineEventType.diaper => SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'wet', label: Text('بلل')),
            ButtonSegment(value: 'dirty', label: Text('براز')),
            ButtonSegment(value: 'both', label: Text('كلاهما')),
          ],
          selected: {_diaperType ?? 'wet'},
          onSelectionChanged: (s) => setState(() => _diaperType = s.first),
        ),
      RoutineEventType.sleep => Row(
          children: [
            const Text('النهاية:'),
            const SizedBox(width: 8),
            Expanded(
              child: TextButton(
                onPressed: _pickEndTime,
                child: Text(
                  _endedAt == null
                      ? 'اختر وقت الاستيقاظ'
                      : '${_endedAt!.hour.toString().padLeft(2, '0')}:${_endedAt!.minute.toString().padLeft(2, '0')}',
                ),
              ),
            ),
          ],
        ),
    };
  }

  void _clearTypeSpecific() {
    _feedType = null;
    _amountMl = null;
    _side = null;
    _diaperType = null;
    _endedAt = null;
  }

  Future<void> _pickEndTime() async {
    final now = DateTime.now();
    final t = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(now),
    );
    if (t != null) {
      setState(() {
        _endedAt = DateTime(now.year, now.month, now.day, t.hour, t.minute);
      });
    }
  }

  void _submit() {
    final notes = _notesController.text.trim();
    if (notes.isNotEmpty && _medicalTerms.hasMatch(notes)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('الملاحظة تحتوي على مصطلح طبي/دواء. رجاءً اكتب ملاحظة روتينية فقط.'),
        ),
      );
      return;
    }

    final event = RoutineEvent(
      eventType: _type,
      startedAt: _startedAt,
      endedAt: _endedAt,
      feedType: _type == RoutineEventType.feed ? (_feedType ?? 'breast') : null,
      amountMl: _type == RoutineEventType.feed && (_feedType ?? 'breast') != 'breast'
          ? _amountMl
          : null,
      side: _type == RoutineEventType.feed && (_feedType ?? 'breast') == 'breast'
          ? (_side ?? 'left')
          : null,
      diaperType: _type == RoutineEventType.diaper ? (_diaperType ?? 'wet') : null,
      notes: notes.isEmpty ? null : notes,
    );

    setState(() => _saving = true);
    TgClient()
        .createRoutineEvent(widget.childId, body: event.toJson())
        .then((_) {
      Navigator.of(context).pop();
    }).catchError((e) {
      setState(() => _saving = false);
      final msg = e is TgApiError ? e.message : 'حدث خطأ';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    });
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }
}
