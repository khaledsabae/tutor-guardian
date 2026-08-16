/// Daily routine tab — «حِساب اليوم».
///
/// Lists today's sleep/feed/diaper events and lets the parent add new ones.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import '../../../l10n/app_localizations.dart';
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
import 'package:almorabbi/core/app_routes.dart';
import '../../../widgets/ui/error_retry_view.dart';

bool routineAgeAllowed(String ageGroup) {
  // Daily routine (sleep/feed/diaper) is for babies/toddlers 0–6 years.
  return const {'prenatal-1', '0-3', '2-3', '4-6'}.contains(ageGroup);
}

bool habitAgeAllowed(String ageGroup) {
  // Habit balance (ميزان العادات) is for children 7–18 years.
  return const {'7-9', '10-12', '13-15', '16-18'}.contains(ageGroup);
}

String habitTabLabel(String ageGroup, AppLocalizations l10n) {
  // Dynamic bottom nav label for the 4th tab based on active child's age.
  if (habitAgeAllowed(ageGroup)) return l10n.routineTitle;
  return l10n.routineDailyTracker;
}

String habitScreenTitle(String ageGroup, AppLocalizations l10n) {
  if (habitAgeAllowed(ageGroup)) return '${l10n.routineTitle} ⚖️';
  return '${l10n.routineDailyTracker} 🍼';
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
          title: Text(habitScreenTitle(profile.ageGroup, AppLocalizations.of(context))),
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
        appBar: AppBar(
          title: Text(habitScreenTitle(profile.ageGroup, AppLocalizations.of(context))),
        ),
        body: _RoutineAgeGate(profile: profile),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(habitScreenTitle(profile?.ageGroup ?? '', AppLocalizations.of(context))),
        actions: const [
          Padding(
            padding: EdgeInsets.symmetric(horizontal: 12),
            child: Center(child: _ActiveChildChip()),
          ),
        ],
      ),
      body: childId == null ? const _NoChildState() : const _RoutineBody(),
      floatingActionButton:
          childId == null || (profile != null && !routineAgeAllowed(profile.ageGroup))
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _showAddEventDialog(context, childId),
              icon: const Icon(Icons.add),
              label: Text(AppLocalizations.of(context).routineNewEvent),
            ),
    );
  }

  void _showAddEventDialog(BuildContext context, int childId) {
    final profile = ProviderScope.containerOf(context).read(activeChildProfileProvider);
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(Dt.rSheet)),
      ),
      builder: (_) => _AddEventSheet(childId: childId, ageGroup: profile?.ageGroup ?? '0-3'),
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
            AppLocalizations.of(context).routineUnder9,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            AppLocalizations.of(context).routineChildStage(profile.name, profile.ageGroup),
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
            AppLocalizations.of(context).routineAddChildFirst,
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
            error: (e, _) => ErrorRetryView(
              error: e,
              onRetry: childId == null ? null : () => ref.invalidate(todayRoutineProvider(childId)),
            ),
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
              Text(
                AppLocalizations.of(context).routineSummaryDays(s.days),
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _Stat(
                    icon: '🌙',
                    value: '${(s.totalSleepMinutes / 60).floor()}h',
                    label: AppLocalizations.of(context).routineEventSleep,
                  ),
                  _Stat(
                    icon: '🍼',
                    value: '${s.totalFeedCount}',
                    label: AppLocalizations.of(context).routineStatFeeds,
                  ),
                  _Stat(
                    icon: '👶',
                    value: '${s.diaperCount}',
                    label: AppLocalizations.of(context).routineStatDiapers,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
      loading: () => const SizedBox.shrink(),
      error: (_, _) => const SizedBox.shrink(),
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
            Text(
              AppLocalizations.of(context).routineNoEvents,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              AppLocalizations.of(context).routineTapPlus,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(Dt.pad),
      itemCount: day.events.length,
      itemBuilder: (context, i) {
        final e = day.events[i];
        return _EventTile(event: e).animate().fadeIn(delay: (i * 80).ms, duration: Dt.base);
      },
    );
  }
}

class _EventTile extends StatelessWidget {
  const _EventTile({required this.event});
  final RoutineEvent event;

  String _subtitle(AppLocalizations l10n) {
    final parts = <String>[];
    if (event.feedType != null) parts.add('${l10n.routineFieldType}: ${event.feedType}');
    if (event.amountMl != null) parts.add('${event.amountMl} ml');
    if (event.side != null) parts.add('${l10n.routineFieldSide}: ${event.side}');
    if (event.diaperType != null) parts.add('${event.diaperType}');
    if (event.endedAt != null && event.eventType == RoutineEventType.sleep) {
      final mins = event.endedAt!.difference(event.startedAt).inMinutes;
      parts.add('${l10n.routineFieldDuration}: ${mins ~/ 60}h ${mins % 60}m');
    }
    return parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Text(event.eventType.icon, style: const TextStyle(fontSize: 28)),
        title: Text(event.eventType.label(l10n)),
        subtitle: Text(
          '${_formatTime(event.startedAt)}${_subtitle(l10n).isEmpty ? '' : '\n${_subtitle(l10n)}'}',
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
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.routineDeleteConfirm),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(), child: Text(l10n.cancel)),
          TextButton(
            onPressed: () async {
              Navigator.of(ctx).pop();
              try {
                await TgClient().deleteRoutineEvent(eventId);
              } on TgApiError catch (e) {
                messenger.showSnackBar(
                  SnackBar(content: Text(l10n.routineDeleteFailed(e.message))),
                );
              }
            },
            child: Text(l10n.delete, style: const TextStyle(color: AppTheme.dangerFg)),
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
  final DateTime _startedAt = DateTime.now();
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
            AppLocalizations.of(
              context,
            ).routineAddEventTitle(_type.label(AppLocalizations.of(context))),
            style: Theme.of(context).textTheme.titleMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),
          SegmentedButton<RoutineEventType>(
            segments: _allowedTypes
                .map(
                  (t) => ButtonSegment(
                    value: t,
                    label: Text('${t.icon} ${t.label(AppLocalizations.of(context))}'),
                  ),
                )
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
            decoration: InputDecoration(
              labelText: AppLocalizations.of(context).routineNoteOptional,
              helperText: AppLocalizations.of(context).routineNoMedNote,
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
                : Text(AppLocalizations.of(context).save),
          ),
        ],
      ),
    );
  }

  Widget _typeFields() {
    final l10n = AppLocalizations.of(context);
    return switch (_type) {
      RoutineEventType.feed => Column(
        children: [
          SegmentedButton<String>(
            segments: [
              ButtonSegment(value: 'breast', label: Text(l10n.routineFeedBreast)),
              ButtonSegment(value: 'bottle', label: Text(l10n.routineFeedBottle)),
              ButtonSegment(value: 'solid', label: Text(l10n.routineFeedSolid)),
            ],
            selected: {_feedType ?? 'breast'},
            onSelectionChanged: (s) => setState(() => _feedType = s.first),
          ),
          const SizedBox(height: 8),
          if ((_feedType ?? 'breast') == 'breast')
            SegmentedButton<String>(
              segments: [
                ButtonSegment(value: 'left', label: Text(l10n.routineSideLeft)),
                ButtonSegment(value: 'right', label: Text(l10n.routineSideRight)),
                ButtonSegment(value: 'both', label: Text(l10n.routineBoth)),
              ],
              selected: {_side ?? 'left'},
              onSelectionChanged: (s) => setState(() => _side = s.first),
            ),
          if ((_feedType ?? 'breast') != 'breast')
            TextField(
              keyboardType: TextInputType.number,
              decoration: InputDecoration(labelText: l10n.routineAmountApprox),
              onChanged: (v) => _amountMl = int.tryParse(v),
            ),
        ],
      ),
      RoutineEventType.diaper => SegmentedButton<String>(
        segments: [
          ButtonSegment(value: 'wet', label: Text(l10n.routineDiaperWet)),
          ButtonSegment(value: 'dirty', label: Text(l10n.routineDiaperDirty)),
          ButtonSegment(value: 'both', label: Text(l10n.routineBoth)),
        ],
        selected: {_diaperType ?? 'wet'},
        onSelectionChanged: (s) => setState(() => _diaperType = s.first),
      ),
      RoutineEventType.sleep => Row(
        children: [
          Text(AppLocalizations.of(context).routineEndTime),
          const SizedBox(width: 8),
          Expanded(
            child: TextButton(
              onPressed: _pickEndTime,
              child: Text(
                _endedAt == null
                    ? l10n.routinePickWakeTime
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
    final t = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(now));
    if (t != null) {
      setState(() {
        _endedAt = DateTime(now.year, now.month, now.day, t.hour, t.minute);
      });
    }
  }

  void _submit() {
    final l10n = AppLocalizations.of(context);
    final notes = _notesController.text.trim();
    if (notes.isNotEmpty && _medicalTerms.hasMatch(notes)) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(l10n.routineMedicalNoteBlocked)));
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
    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);
    TgClient()
        .createRoutineEvent(widget.childId, body: event.toJson())
        .then((_) {
          navigator.pop();
        })
        .catchError((e) {
          if (mounted) setState(() => _saving = false);
          final msg = e is TgApiError ? e.message : l10n.routineError;
          messenger.showSnackBar(SnackBar(content: Text(msg)));
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
  late final TabController _tabController = TabController(length: 3, vsync: this);
  int _selectedTab = 0;

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _openCustomizeScreen(int childId) async {
    await Navigator.of(context).push(AppRoutes.habitCustomize());
  }

  Future<void> _showWebShareDialog(int childId, String childName) async {
    final client = ref.read(tgClientProvider);

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => const AlertDialog(
        content: SizedBox(width: 80, height: 80, child: Center(child: CircularProgressIndicator())),
      ),
    );

    Map<String, dynamic>? data;
    try {
      data = await client.createChildWebClaim(childId);
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context, rootNavigator: true).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).routineQrFailed(e.toString()))),
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
        title: Text(AppLocalizations.of(context).routineShareTeenTitle),
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
                Text(
                  AppLocalizations.of(context).routineShareScanHint,
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
            child: Text(AppLocalizations.of(context).routineClose),
          ),
          if (claimUrl.isNotEmpty)
            FilledButton.icon(
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: claimUrl));
                if (ctx.mounted) Navigator.of(ctx).pop();
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(AppLocalizations.of(context).routineLinkCopied)),
                  );
                }
              },
              icon: const Icon(Icons.copy),
              label: Text(AppLocalizations.of(context).routineCopyLink),
            ),
        ],
      ),
    );
  }

  Future<void> _enterChildMode(int childId, String childName, {String surface = 'habit'}) async {
    await Navigator.of(
      context,
    ).push(AppRoutes.childModeLock<void>(childId: childId, childName: childName, surface: surface));
  }

  /// The parent's day, and the agreement behind it.
  ///
  /// Reachable from here because this is where a parent already comes to look
  /// at a child. A screen with a route and no caller is a screen nobody can
  /// open — which is how the agreement was written, registered, tested, and
  /// still unreachable, behind a server gate that required it.
  Future<void> _openParentDay() async {
    await Navigator.of(context).push(AppRoutes.parentDay());
    if (mounted) setState(() {});
  }

  Future<void> _openAgreement(String childName) async {
    await Navigator.of(context).push(AppRoutes.agreement(childName: childName));
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final childId = ref.watch(activeChildIdProvider);
    if (childId == null) return const SizedBox.shrink();

    final habitsAsync = ref.watch(todayHabitsProvider(childId));
    const categories = HabitCategory.values;

    return Column(
      children: [
        TabBar(
          controller: _tabController,
          tabs: categories
              .map((c) => Tab(text: '${c.icon} ${c.label(AppLocalizations.of(context))}'))
              .toList(),
          onTap: (i) => setState(() => _selectedTab = i),
        ),
        Expanded(
          child: habitsAsync.when(
            data: (day) => Column(
              children: [
                _HabitSummaryCard(points: day.points, totalHabits: day.habits.length),
                Expanded(
                  child: _HabitCategoryList(
                    category: categories[_selectedTab],
                    day: day,
                    childId: childId,
                    onRefresh: () async {
                      if (!mounted) return;
                      return ref.refresh(todayHabitsProvider(childId));
                    },
                  ),
                ),
              ],
            ),
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => ErrorRetryView(
              error: e,
              onRetry: () => ref.invalidate(todayHabitsProvider(childId)),
            ),
          ),
        ),
        // Flexible, not just scrollable.
        //
        // A SingleChildScrollView inside an unbounded Column still takes its
        // intrinsic height, so scrolling alone did not stop the overflow —
        // 17px on a small screen. Flexible lets this section shrink when the
        // list above it needs the room, and the scroll view inside means the
        // buttons stay reachable at any height.
        Flexible(
          child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: Dt.pad, vertical: 8),
            // Scrollable, and this is the third time.
            //
            // This is an unbounded Column pinned under a list, and every
            // button added to it moves it closer to overflowing. It has now
            // broken daily_routine_qr_dialog_widget_test three separate times
            // today — once for the mission + screen-off row, once for the
            // licence row, and once when the licence row widened to 13-15 —
            // and each time the fix was to narrow a condition, which only
            // moved the cliff rather than removing it.
            //
            // A scroll view removes it: the column can grow, and on a screen
            // too short for it the parent scrolls instead of the layout
            // throwing. `shrinkWrap` semantics come free because the child is
            // a Column with mainAxisSize.min.
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  OutlinedButton.icon(
                    onPressed: () => _openCustomizeScreen(childId),
                    icon: const Icon(Icons.edit_note_outlined),
                    label: Text(AppLocalizations.of(context).routineCustomize),
                  ),
                  const SizedBox(height: 8),
                  if (widget.ageGroup == '13-15' || widget.ageGroup == '16-18')
                    OutlinedButton.icon(
                      onPressed: () async {
                        final profile = ref.read(activeChildProfileProvider);
                        await _showWebShareDialog(
                          childId,
                          profile?.name ?? AppLocalizations.of(context).childFallbackName,
                        );
                      },
                      icon: const Icon(Icons.qr_code_2),
                      label: Text(AppLocalizations.of(context).routineShareWeb),
                    ),
                  if (widget.ageGroup == '13-15' || widget.ageGroup == '16-18')
                    const SizedBox(height: 8),
                  FilledButton.icon(
                    onPressed: () {
                      final profile = ref.read(activeChildProfileProvider);
                      _enterChildMode(
                        childId,
                        profile?.name ?? AppLocalizations.of(context).childFallbackName,
                      );
                    },
                    icon: const Icon(Icons.child_care),
                    label: Text(AppLocalizations.of(context).routineChildMode),
                  ),
                  const SizedBox(height: 8),
                  // Two surfaces, side by side to keep this column's height —
                  // stacking them overflowed the card on a small screen.
                  //
                  // Both are opened directly rather than reached from inside
                  // another screen. The server budgets each surface separately,
                  // so arriving at the mission through the habit screen spends
                  // the habit allowance to get there, and arriving at screen-off
                  // listening that way spends screen budget on the way into the
                  // one mode whose entire point is not spending any.
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {
                            final profile = ref.read(activeChildProfileProvider);
                            _enterChildMode(
                              childId,
                              profile?.name ?? AppLocalizations.of(context).childFallbackName,
                              surface: 'mission',
                            );
                          },
                          icon: const Icon(Icons.explore_outlined),
                          label: Text(AppLocalizations.of(context).missionOpenForChild),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => Navigator.of(context).push(AppRoutes.screenOffPicker()),
                          icon: const Icon(Icons.nightlight_outlined),
                          label: Text(AppLocalizations.of(context).screenOffOpen),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  // The internet licence. Shown for the bands that have a
                  // scenario bank written for them — 10-12 and 13-15 today.
                  //
                  // The banks are separate on purpose: "a stranger asked for
                  // your photo" is a different situation at ten and at fourteen,
                  // and at fourteen the stranger is usually a friend of a friend.
                  // 16-18 has the surface in policy but no bank yet, so its
                  // button stays hidden rather than opening an empty screen.
                  if (widget.ageGroup == '10-12' || widget.ageGroup == '13-15')
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () {
                              final profile = ref.read(activeChildProfileProvider);
                              _enterChildMode(
                                childId,
                                profile?.name ?? AppLocalizations.of(context).childFallbackName,
                                surface: 'license',
                              );
                            },
                            icon: const Icon(Icons.shield_outlined),
                            label: Text(AppLocalizations.of(context).licenseOpenForChild),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () => Navigator.of(context).push(AppRoutes.parentLicense()),
                            icon: const Icon(Icons.menu_book_outlined),
                            label: Text(AppLocalizations.of(context).licenseOpenForParent),
                          ),
                        ),
                      ],
                    ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _openParentDay,
                          icon: const Icon(Icons.insights_outlined),
                          label: Text(AppLocalizations.of(context).parentDayTitle),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {
                            final profile = ref.read(activeChildProfileProvider);
                            _openAgreement(
                              profile?.name ?? AppLocalizations.of(context).childFallbackName,
                            );
                          },
                          icon: const Icon(Icons.handshake_outlined),
                          label: Text(AppLocalizations.of(context).agreementTitle),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
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
                AppLocalizations.of(context).routineTodayPoints,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
            Text(
              '${points.toStringAsFixed(1)} / ${maxPoints.toStringAsFixed(0)}',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold, color: Dt.primary),
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
              AppLocalizations.of(context).routineNoHabits,
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
          SnackBar(content: Text(AppLocalizations.of(context).routineRecordFailed(e.message))),
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
                habitDisplayName(widget.habitName, AppLocalizations.of(context)),
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
                    tooltip: s.label(AppLocalizations.of(context)),
                    style: isSelected
                        ? IconButton.styleFrom(backgroundColor: Dt.primary.withValues(alpha: .15))
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
