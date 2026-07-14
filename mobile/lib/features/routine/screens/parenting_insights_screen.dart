import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state/chat_notifier.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../../program/providers/progress_providers.dart';

class ParentingInsightsScreen extends ConsumerStatefulWidget {
  const ParentingInsightsScreen({super.key});

  @override
  ConsumerState<ParentingInsightsScreen> createState() => _ParentingInsightsScreenState();
}

class _ParentingInsightsScreenState extends ConsumerState<ParentingInsightsScreen> {
  bool _loading = true;
  String? _error;

  int _sleepMinutes = 0;
  int _feedCount = 0;
  int _feedAmount = 0;
  int _diaperCount = 0;
  List<dynamic> _insights = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final childId = ref.read(activeChildIdProvider);
    if (childId == null) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'يرجى اختيار طفل أولاً.';
        });
      }
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final client = ref.read(tgClientProvider);
      
      // Load both stats summary and AI insights concurrently
      final results = await Future.wait<Map<String, dynamic>>([
        client.fetchRoutineSummary(childId, days: 7),
        client.fetchParentingInsights(childId),
      ]);

      final summary = results[0];
      final insightsData = results[1];

      if (mounted) {
        setState(() {
          _sleepMinutes = summary['total_sleep_minutes'] as int? ?? 0;
          _feedCount = summary['total_feed_count'] as int? ?? 0;
          _feedAmount = summary['total_feed_amount_ml'] as int? ?? 0;
          _diaperCount = summary['diaper_count'] as int? ?? 0;
          _insights = insightsData['insights'] as List<dynamic>? ?? [];
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'فشل تحميل البيانات. يرجى التحقق من اتصال الإنترنت.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final activeChild = ref.watch(activeChildProfileProvider);
    final childName = activeChild?.name ?? 'طفلك';

    return Scaffold(
      appBar: AppBar(
        title: const Text('تحليلات وتوصيات المربّي 🧠'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
          ),
        ],
      ),
      body: _loading
          ? _buildLoadingState()
          : _error != null
              ? _buildErrorState()
              : _buildContent(childName),
    );
  }

  Widget _buildLoadingState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation(Dt.accent),
          ),
          SizedBox(height: 20),
          Text(
            'جاري تحليل نشاط طفلك وتوليد التوصيات...',
            style: TextStyle(
              fontSize: 16,
              color: AppTheme.textSecondary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              '⚠️',
              style: TextStyle(fontSize: 48),
            ),
            const SizedBox(height: 16),
            Text(
              _error ?? 'حدث خطأ غير متوقع',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _loadData,
              icon: const Icon(Icons.refresh),
              label: const Text('إعادة المحاولة'),
              style: FilledButton.styleFrom(
                backgroundColor: Dt.accent,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(String childName) {
    final sleepHours = _sleepMinutes ~/ 60;
    final sleepMins = _sleepMinutes % 60;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Welcome and intro card
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Dt.accent.withValues(alpha: .08),
            borderRadius: BorderRadius.circular(Dt.rCard),
            border: Border.all(color: Dt.accent.withValues(alpha: .15)),
          ),
          child: Row(
            children: [
              const Text('✨', style: TextStyle(fontSize: 28)),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  'أهلاً بك في التحليلات التربوية! نقوم بتحليل الروتين الأسبوعي ورسائل المحادثات لتقديم إرشادات مخصصة لرحلة تربية $childName.',
                  style: const TextStyle(
                    fontSize: 14,
                    height: 1.5,
                    fontWeight: FontWeight.w600,
                    color: Dt.accentDeep,
                  ),
                ),
              ),
            ],
          ),
        ).animate().fadeIn(duration: 400.ms).slideY(begin: 0.1, end: 0),
        const SizedBox(height: 20),

        // Section: stats summary
        const Text(
          'النشاط الأسبوعي الأخير 📊',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 12),

        // Stats grid
        Row(
          children: [
            Expanded(
              child: _buildMetricTile(
                title: 'نوم',
                value: sleepHours > 0 ? '$sleepHours س $sleepMins د' : '$sleepMins دقيقة',
                icon: '🌙',
                color: Colors.indigo.shade50,
                textColor: Colors.indigo.shade900,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildMetricTile(
                title: 'رضاعة وتغذية',
                value: '$_feedCount مرات\n($_feedAmount مل)',
                icon: '🍼',
                color: Colors.teal.shade50,
                textColor: Colors.teal.shade900,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildMetricTile(
                title: 'تغيير حفاظ',
                value: '$_diaperCount مرات',
                icon: '👶',
                color: Colors.amber.shade50,
                textColor: Colors.amber.shade900,
              ),
            ),
          ],
        ).animate().fadeIn(delay: 150.ms, duration: 400.ms).slideY(begin: 0.1, end: 0),
        const SizedBox(height: 24),

        // Section: AI recommendations
        const Text(
          'توصيات المربّي الذكي ✨',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 12),

        if (_insights.isEmpty)
          const Center(
            child: Padding(
              padding: EdgeInsets.symmetric(vertical: 32.0),
              child: Text(
                'لا توجد توصيات كافية حالياً. استمر في تسجيل الروتين والمحادثات مع المساعد للحصول على توصيات مخصصة.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: AppTheme.textSecondary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          )
        else
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _insights.length,
            separatorBuilder: (_, __) => const SizedBox(height: 14),
            itemBuilder: (context, idx) {
              final insight = _insights[idx] as Map<String, dynamic>;
              return _buildInsightCard(insight)
                  .animate()
                  .fadeIn(delay: (200 + idx * 100).ms, duration: 450.ms)
                  .slideY(begin: 0.15, end: 0);
            },
          ),
      ],
    );
  }

  Widget _buildMetricTile({
    required String title,
    required String value,
    required String icon,
    required Color color,
    required Color textColor,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        children: [
          Text(icon, style: const TextStyle(fontSize: 28)),
          const SizedBox(height: 8),
          Text(
            title,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: textColor.withValues(alpha: 0.7),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w900,
              color: textColor,
              height: 1.3,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInsightCard(Map<String, dynamic> insight) {
    final type = insight['type'] as String? ?? 'tip';
    final title = insight['title'] as String? ?? '';
    final desc = insight['description'] as String? ?? '';
    final category = insight['category'] as String? ?? 'أخرى';

    Color cardBg;
    Color borderCol;
    Color accentColor;
    String badgeText;

    if (type == 'positive') {
      cardBg = const Color(0xFFE8F5E9).withValues(alpha: 0.6);
      borderCol = const Color(0xFFC8E6C9);
      accentColor = const Color(0xFF2E7D32);
      badgeText = '✅ إيجابي';
    } else if (type == 'warning') {
      cardBg = const Color(0xFFFFF3E0).withValues(alpha: 0.6);
      borderCol = const Color(0xFFFFE0B2);
      accentColor = const Color(0xFFE65100);
      badgeText = '⚠️ تنبيه';
    } else {
      cardBg = const Color(0xFFE0F2F1).withValues(alpha: 0.6);
      borderCol = const Color(0xFFB2DFDB);
      accentColor = const Color(0xFF00796B);
      badgeText = '💡 نصيحة';
    }

    String catEmoji = '💡';
    if (category.contains('نوم')) catEmoji = '🌙';
    if (category.contains('غذ')) catEmoji = '🍼';
    if (category.contains('سلو')) catEmoji = '🧩';

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: borderCol, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '$catEmoji $title',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: accentColor,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: accentColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  badgeText,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: accentColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Directionality(
            textDirection: TextDirection.rtl,
            child: Text(
              desc,
              style: const TextStyle(
                fontSize: 14,
                height: 1.6,
                fontWeight: FontWeight.w600,
                color: Color(0xFF2E2E2E),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
