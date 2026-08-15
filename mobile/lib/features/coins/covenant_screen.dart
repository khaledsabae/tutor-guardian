import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../../theme/app_theme.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/ui/bouncy_button.dart';
import '../program/providers/progress_providers.dart';
import 'coins_providers.dart';
import 'covenant_service.dart';

class CovenantScreen extends ConsumerStatefulWidget {
  const CovenantScreen({super.key});

  @override
  ConsumerState<CovenantScreen> createState() => _CovenantScreenState();
}

class _CovenantScreenState extends ConsumerState<CovenantScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  List<Covenant> _covenants = [];
  List<Covenant> _overdue = const [];
  bool _loading = true;

  /// Rewards belong to a child. Child 0 is the fallback for a family that has
  /// not created a profile yet — it keeps its own list rather than sharing one.
  int get _childId => ref.read(activeChildIdProvider) ?? 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadCovenants();
  }

  Future<void> _loadCovenants() async {
    setState(() => _loading = true);
    final data = await CovenantService.instance.load(_childId);
    final overdue = await CovenantService.instance.overdueDeliveries(_childId);
    if (mounted) {
      setState(() {
        _covenants = data;
        _overdue = overdue;
        _loading = false;
      });
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _addReward(String title, int cost) async {
    if (title.trim().isEmpty || cost <= 0) return;
    await CovenantService.instance.add(_childId, title.trim(), cost);
    await _loadCovenants();
  }

  Future<void> _redeem(Covenant cov) async {
    final balance = ref.read(coinsProvider).balance;
    if (balance < cov.cost) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).covenantInsufficient)),
      );
      return;
    }

    final success = await ref.read(coinsProvider.notifier).spendOnCovenant(cov.cost);
    if (success) {
      await CovenantService.instance.redeem(_childId, cov.id);
      await _loadCovenants();
      if (mounted) {
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: Text(AppLocalizations.of(context).covenantSuccess),
            content: Text(AppLocalizations.of(context).covenantSuccessMsg(cov.title, cov.cost)),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: Text(AppLocalizations.of(context).ok),
              ),
            ],
          ),
        );
      }
    }
  }

  Future<void> _deliver(Covenant cov) async {
    await CovenantService.instance.deliver(_childId, cov.id);
    await _loadCovenants();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).covenantDelivered)),
      );
    }
  }

  Future<void> _delete(Covenant cov) async {
    await CovenantService.instance.delete(_childId, cov.id);
    await _loadCovenants();
  }

  @override
  Widget build(BuildContext context) {
    final coins = ref.watch(coinsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context).covenantTitle),
        bottom: TabBar(
          controller: _tabController,
          labelColor: Dt.accentDeep,
          unselectedLabelColor: AppTheme.textMuted,
          indicatorColor: Dt.accent,
          tabs: [
            Tab(text: AppLocalizations.of(context).covenantTabRedeem),
            Tab(text: AppLocalizations.of(context).covenantTabParent),
          ],
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildChildView(coins.balance),
                _buildParentView(),
              ],
            ),
    );
  }

  Widget _buildChildView(int balance) {
    final available = _covenants.where((e) => !e.isRedeemed).toList();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Balance Banner
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: Dt.accentGradient,
            borderRadius: BorderRadius.circular(Dt.rCard),
            boxShadow: Dt.softShadow(Dt.accent),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    AppLocalizations.of(context).covenantBalanceLabel,
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    AppLocalizations.of(context).covenantBalanceHint,
                    style: const TextStyle(color: Colors.white70, fontSize: 11),
                  ),
                ],
              ),
              Row(
                children: [
                  const Text('🪙', style: TextStyle(fontSize: 20)),
                  const SizedBox(width: 6),
                  Text(
                    '$balance',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),

        if (available.isEmpty)
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 40),
              child: Text(
                AppLocalizations.of(context).covenantEmpty,
                textAlign: TextAlign.center,
                style: const TextStyle(fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
              ),
            ),
          )
        else
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: available.length,
            separatorBuilder: (_, _) => const SizedBox(height: 12),
            itemBuilder: (ctx, idx) {
              final cov = available[idx];
              final canAfford = balance >= cov.cost;
              return Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(24),
                  boxShadow: Dt.cardShadow,
                ),
                child: Row(
                  children: [
                    const Text('🎁', style: TextStyle(fontSize: 32)),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            cov.title,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            AppLocalizations.of(context).covenantCost(cov.cost),
                            style: const TextStyle(
                              color: Dt.accentDeep,
                              fontWeight: FontWeight.bold,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 10),
                    ElevatedButton(
                      onPressed: canAfford ? () => _redeem(cov) : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Dt.accent,
                        foregroundColor: Colors.white,
                        disabledBackgroundColor: Colors.grey.shade200,
                        disabledForegroundColor: Colors.grey.shade500,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      child: Text(
                        canAfford ? AppLocalizations.of(context).covenantRedeem : AppLocalizations.of(context).covenantRemaining(cov.cost - balance),
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              ).animate().fadeIn(delay: (idx * 60).ms).slideX(begin: 0.1, end: 0);
            },
          ),
      ],
    );
  }

  Widget _buildParentView() {
    final pending = _covenants.where((e) => e.isRedeemed && !e.isDelivered).toList();
    final delivered = _covenants.where((e) => e.isDelivered).toList();
    final customRewards = _covenants.where((e) => !e.isRedeemed).toList();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // The child already paid. Surfacing this first is the whole reason
        // delivery is tracked separately from redemption.
        if (_overdue.isNotEmpty) ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.amber.shade50,
              borderRadius: BorderRadius.circular(Dt.rCard),
              border: Border.all(color: Colors.amber.shade200),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  AppLocalizations.of(context).covenantOverdueTitle,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 6),
                Text(
                  AppLocalizations.of(context).covenantOverdueBody(_overdue.length),
                  style: const TextStyle(height: 1.5),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
        ],
        // Parent welcome box
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.deepPurple.shade50,
            borderRadius: BorderRadius.circular(Dt.rCard),
            border: Border.all(color: Colors.deepPurple.shade100),
          ),
          child: Row(
            children: [
              const Text('🔑', style: TextStyle(fontSize: 24)),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  AppLocalizations.of(context).covenantParentWelcome,
                  style: const TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: Colors.deepPurple,
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),

        // Action: Add new custom reward
        BouncyButton(
          label: AppLocalizations.of(context).covenantAddNew,
          color: Colors.deepPurple,
          onTap: _showAddRewardDialog,
        ),
        const SizedBox(height: 24),

        // Section: Pending Deliveries
        Text(
          AppLocalizations.of(context).covenantPending,
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Colors.amber),
        ),
        const SizedBox(height: 10),
        if (pending.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Text(AppLocalizations.of(context).covenantPendingEmpty, style: const TextStyle(color: AppTheme.textMuted)),
          )
        else
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: pending.length,
            separatorBuilder: (_, _) => const SizedBox(height: 10),
            itemBuilder: (ctx, idx) {
              final cov = pending[idx];
              return Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.amber.shade50,
                  border: Border.all(color: Colors.amber.shade200),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(cov.title, style: const TextStyle(fontWeight: FontWeight.w800)),
                          const SizedBox(height: 4),
                          Text(AppLocalizations.of(context).covenantPendingRedeemed(cov.cost), style: const TextStyle(fontSize: 12)),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    FilledButton(
                      onPressed: () => _deliver(cov),
                      style: FilledButton.styleFrom(backgroundColor: AppTheme.success),
                      child: Text(AppLocalizations.of(context).covenantDeliver, style: const TextStyle(fontWeight: FontWeight.bold)),
                    ),
                  ],
                ),
              );
            },
          ),
        const SizedBox(height: 24),

        // Section: Custom rewards manager list
        Text(
          AppLocalizations.of(context).covenantManage,
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 10),
        if (customRewards.isEmpty)
          Text(AppLocalizations.of(context).covenantManageEmpty, style: const TextStyle(color: AppTheme.textMuted))
        else
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: customRewards.length,
            separatorBuilder: (_, _) => const SizedBox(height: 8),
            itemBuilder: (ctx, idx) {
              final cov = customRewards[idx];
              return Card(
                elevation: 0,
                color: AppTheme.surface,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: BorderSide(color: Colors.grey.shade200),
                ),
                child: ListTile(
                  leading: const Text('🎁', style: TextStyle(fontSize: 22)),
                  title: Text(cov.title, style: const TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: Text(AppLocalizations.of(context).covenantCost(cov.cost)),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline, color: Colors.red),
                    onPressed: () => _delete(cov),
                  ),
                ),
              );
            },
          ),
        const SizedBox(height: 24),
        // Section: Delivered History
        Text(
          AppLocalizations.of(context).covenantHistory,
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.success),
        ),
        const SizedBox(height: 10),
        if (delivered.isEmpty)
          Text(AppLocalizations.of(context).covenantHistoryEmpty, style: const TextStyle(color: AppTheme.textMuted))
        else
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: delivered.length,
            separatorBuilder: (_, _) => const SizedBox(height: 8),
            itemBuilder: (ctx, idx) {
              final cov = delivered[idx];
              return Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.grey.shade300),
                ),
                child: Row(
                  children: [
                    const Text('🎉', style: TextStyle(fontSize: 20)),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            cov.title,
                            style: TextStyle(
                              decoration: TextDecoration.lineThrough,
                              color: Colors.grey.shade600,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            AppLocalizations.of(context).covenantHistoryRedeemed(cov.cost),
                            style: TextStyle(color: Colors.grey.shade500, fontSize: 11),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
      ],
    );
  }

  void _showAddRewardDialog() {
    final titleController = TextEditingController();
    final costController = TextEditingController(text: '30');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(AppLocalizations.of(context).covenantAddTitle),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: titleController,
              decoration: InputDecoration(
                labelText: AppLocalizations.of(context).covenantAddNameLabel,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: costController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: AppLocalizations.of(context).covenantAddCostLabel,
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(AppLocalizations.of(context).cancel),
          ),
          ElevatedButton(
            onPressed: () {
              final cost = int.tryParse(costController.text) ?? 0;
              _addReward(titleController.text, cost);
              Navigator.of(ctx).pop();
            },
            child: Text(AppLocalizations.of(context).add),
          ),
        ],
      ),
    );
  }
}
