/// Daily routine tab — «حِساب اليوم».
///
/// Lists today's sleep/feed/diaper events and lets the parent add new ones.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../../core/analytics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/features/program/providers/progress_providers.dart';
import 'package:almorabbi/theme/app_theme.dart';
import 'package:almorabbi/theme/design_tokens.dart';
import 'package:almorabbi/features/routine/models/routine_models.dart';
import 'package:almorabbi/features/routine/providers/routine_providers.dart';
import 'package:almorabbi/features/routine/models/habit_models.dart';
import 'package:almorabbi/features/routine/providers/habit_providers.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/features/routine/screens/child_mode_lock_screen.dart';
import 'package:almorabbi/features/routine/screens/habit_customize_screen.dart';

bool routineAgeAllowed(String ageGroup) {
  // Daily routine (sleep/feed/diaper) is for babies/toddlers 0–6 years.
  return const {'prenatal-1', '0-3', '2-3', '4-6'}.contains(ageGroup);
}

bool habitAgeAllowed(String ageGroup) {
  // Habit balance (ميزان العادات) is for children 7–18 years.
  return const {'7-9', '10-12', '13-15', '16-18'}.contains(ageGroup);
}

String habitTabLabel(String ageGroup) {
  // Dynamic bottom nav label for the 4th tab based on active child's age.
  if (habitAgeAllowed(ageGroup)) return 'ميزان العادات';
  return 'حِساب اليوم';
}

String habitScreenTitle(String ageGroup) {
  if (habitAgeAllowed(ageGroup)) return 'ميزان العادات ⚖️';
  return 'حِساب اليوم 🍼';
}

List<RoutineEventType> allowedRoutineTypes(String ageGroup) {
  return switch (ageGroup) {
    // 0–3 years: breast/bottle feeding, diapers and sleep are all normal.
    'prenatal-1' || '0-3' || '2-3' => RoutineEventType.values,
    // 4–6 years: diapers may still happen; feeding is no longer tracked.
    '4-6' => const [RoutineEventType.sleep, RoutineEventType.diaper],
    // 7–9 years: only sleep tracking remains age-appropriate.
    '7-9' => const [RoutineEventType.sleep],
    _ => const [],
  };
}

class DailyRoutineScreen extends ConsumerWidget {
  const DailyRoutineScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final childId = ref.watch(activeChildIdProvider);
    final profile = ref.watch(activeChildProfileProvider);

    // Age-dynamic switch: habit tracking for 7–18, routine for 0–6.
    final isHabitAge = profile != null && habitAgeAllowed(profile.ageGroup);

    if (isHabitAge) {
      return Scaffold(
        appBar: AppBar(
          title: Text(habitScreenTitle(profile.ageGroup)),
          actions: const [
            Padding(
              padding: EdgeInsets.symmetric(horizontal: 12),
              child: Center(child: _ActiveChildChip()),
            ),
          ],
        ),
        body: childId == null
            ? const _NoChildState()
            : _HabitBalanceBody(ageGroup: profile.ageGroup),
      );
    }

    if (profile != null && !routineAgeAllowed(profile.ageGroup)) {
      return Scaffold(
        appBar: AppBar(title: Text(habitScreenTitle(profile.ageGroup))),
        body: _RoutineAgeGate(profile: profile),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(habitScreenTitle(profile?.ageGroup ?? '')),
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
      data: (s) => Card(
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

// ── Habit Balance (ميزان العادات) ────────────────────────────────────────

class _HabitBalanceBody extends ConsumerStatefulWidget {
  const _HabitBalanceBody({required this.ageGroup});

  final String ageGroup;

  @override
  ConsumerState<_HabitBalanceBody> createState() => _HabitBalanceBodyState();
}

class _HabitBalanceBodyState extends ConsumerState<_HabitBalanceBody>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController =
      TabController(length: 3, vsync: this);
  int _selectedTab = 0;

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _openCustomizeScreen(int childId) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const HabitCustomizeScreen(),
      ),
    );
  }

  Future<void> _showWebShareDialog(int childId, String childName) async {
    final client = ref.read(tgClientProvider);

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => const AlertDialog(
        content: SizedBox(
          width: 80,
          height: 80,
          child: Center(child: CircularProgressIndicator()),
        ),
      ),
    );

    Map<String, dynamic>? data;
    try {
      data = await client.createChildWebClaim(childId);
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context, rootNavigator: true).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('تعذر إنشاء رمز QR: $e')),
      );
      return;
    }

    if (!mounted) return;
    Navigator.of(context, rootNavigator: true).pop();

    final claimUrl = data['claim_url'] as String? ?? '';

    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
          title: const Text('شارك الميزان مع المراهق'),
          content: SizedBox(
            width: double.maxFinite,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                if (claimUrl.isNotEmpty) ...[
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: QrImageView(
                      data: claimUrl,
                      version: QrVersions.auto,
                      size: 220,
                      backgroundColor: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
                const Text(
                  'امسح الرمز من هاتف الابن، أو انسخ الرابط وأرسله عبر واتساب.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                if (claimUrl.isNotEmpty)
                  SelectableText(
                    claimUrl,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 12),
                  ),
              ],
            ),
          ),
        ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('إغلاق'),
            ),
            if (claimUrl.isNotEmpty)
              FilledButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: claimUrl));
                  if (ctx.mounted) Navigator.of(ctx).pop();
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('تم نسخ الرابط')),
                    );
                  }
                },
                icon: const Icon(Icons.copy),
                label: const Text('نسخ الرابط'),
              ),
          ],
        ),
      );
  }

  Future<void> _enterChildMode(int childId, String childName) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChildModeLockScreen(
          childId: childId,
          childName: childName,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final childId = ref.watch(activeChildIdProvider);
    if (childId == null) return const SizedBox.shrink();

    final habitsAsync = ref.watch(todayHabitsProvider(childId));
    final categories = HabitCategory.values;

    return Column(
      children: [
        TabBar(
          controller: _tabController,
          tabs: categories
              .map((c) => Tab(text: '${c.icon} ${c.label}'))
              .toList(),
          onTap: (i) => setState(() => _selectedTab = i),
        ),
        Expanded(
          child: habitsAsync.when(
            data: (day) => Column(
              children: [
                _HabitSummaryCard(
                  points: day.points,
                  totalHabits: day.habits.length,
                ),
                Expanded(
                  child: _HabitCategoryList(
                    category: categories[_selectedTab],
                    day: day,
                    childId: childId,
                    onRefresh: () => ref.refresh(todayHabitsProvider(childId)),
                  ),
                ),
              ],
            ),
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('خطأ: $e')),
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: Dt.pad, vertical: 8),
            child: Column(
              children: [
                OutlinedButton.icon(
                  onPressed: () => _openCustomizeScreen(childId),
                  icon: const Icon(Icons.edit_note_outlined),
                  label: const Text('تخصيص العادات'),
                ),
                const SizedBox(height: 8),
                if (widget.ageGroup == '13-15' || widget.ageGroup == '16-18')
                  OutlinedButton.icon(
                    onPressed: () async {
                      final profile = ref.read(activeChildProfileProvider);
                      await _showWebShareDialog(childId, profile?.name ?? 'الطفل');
                    },
                    icon: const Icon(Icons.qr_code_2),
                    label: const Text('مشاركة الميزان عبر الويب 🔗'),
                  ),
                if (widget.ageGroup == '13-15' || widget.ageGroup == '16-18')
                  const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: () {
                    final profile = ref.read(activeChildProfileProvider);
                    _enterChildMode(childId, profile?.name ?? 'الطفل');
                  },
                  icon: const Icon(Icons.child_care),
                  label: const Text('تسليم الجهاز للطفل (وضع الطفل)'),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _HabitSummaryCard extends StatelessWidget {
  const _HabitSummaryCard({required this.points, required this.totalHabits});

  final double points;
  final int totalHabits;

  @override
  Widget build(BuildContext context) {
    final maxPoints = totalHabits.toDouble();
    return Card(
      margin: const EdgeInsets.all(Dt.pad).copyWith(bottom: 0),
      color: Dt.primary.withValues(alpha: .08),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: Dt.pad, vertical: 12),
        child: Row(
          children: [
            const Icon(Icons.emoji_events_outlined, color: Dt.primary),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'نقاط اليوم',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
            Text(
              '${points.toStringAsFixed(1)} / ${maxPoints.toStringAsFixed(0)}',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Dt.primary,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HabitCategoryList extends ConsumerWidget {
  const _HabitCategoryList({
    required this.category,
    required this.day,
    required this.childId,
    required this.onRefresh,
  });

  final HabitCategory category;
  final HabitDay day;
  final int childId;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final items = day.habits.where((h) => h.category == category).toList();
    if (items.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('🌱', style: TextStyle(fontSize: 48)),
            const SizedBox(height: 12),
            Text(
              'لا توجد عادات في هذا القسم',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(Dt.pad),
      itemCount: items.length,
      itemBuilder: (context, i) {
        final item = items[i];
        return _HabitCard(
          habitName: item.habitName,
          category: category,
          childId: childId,
          existingEvent: item.status == null
              ? null
              : HabitEvent(
                  id: item.eventId,
                  childId: childId,
                  category: category,
                  habitName: item.habitName,
                  status: item.status!,
                  createdAt: '',
                ),
          onRecorded: onRefresh,
        );
      },
    );
  }
}

class _HabitCard extends StatefulWidget {
  const _HabitCard({
    required this.habitName,
    required this.category,
    required this.childId,
    required this.existingEvent,
    required this.onRecorded,
  });

  final String habitName;
  final HabitCategory category;
  final int childId;
  final HabitEvent? existingEvent;
  final VoidCallback onRecorded;

  @override
  State<_HabitCard> createState() => _HabitCardState();
}

class _HabitCardState extends State<_HabitCard> {
  bool _saving = false;

  Future<void> _record(HabitStatus status) async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await TgClient().createHabitEvent(
        widget.childId,
        body: {
          'category': widget.category.wireName,
          'habit_name': widget.habitName,
          'status': status.wireName,
        },
      );
      unawaited(Analytics.habitCheckIn(status.wireName));
      widget.onRecorded();
    } on TgApiError catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('فشل التسجيل: ${e.message}')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = widget.existingEvent?.status;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(Dt.pad),
        child: Row(
          children: [
            Expanded(
              child: Text(
                widget.habitName,
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            if (_saving)
              const SizedBox(
                height: 20,
                width: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Row(
                mainAxisSize: MainAxisSize.min,
                children: HabitStatus.values.map((s) {
                  final isSelected = current == s;
                  return IconButton(
                    icon: Text(s.icon, style: const TextStyle(fontSize: 24)),
                    tooltip: s.label,
                    style: isSelected
                        ? IconButton.styleFrom(
                            backgroundColor: Dt.primary.withValues(alpha: .15),
                          )
                        : null,
                    onPressed: () => _record(s),
                  );
                }).toList(),
              ),
          ],
        ),
      ),
    );
  }
}
