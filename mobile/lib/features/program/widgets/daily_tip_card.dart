/// Daily Tip card — small surface that surfaces the day's parenting
/// tip on top of the chat. Driven by [dailyTipProvider] filtered by
/// the active child's age group (from [activeChildProfileProvider]).
///
/// If the child profile isn't loaded yet (post-onboarding race), the
/// card gracefully hides itself rather than show a loading skeleton
/// that competes with the chat for attention.
library;

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:screenshot/screenshot.dart';
import 'package:share_plus/share_plus.dart';

import '../../../theme/app_theme.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../data/models.dart';
import '../providers/program_providers.dart';
import '../providers/favorites_provider.dart';
import '../widgets/shareable_tip_card.dart';

class DailyTipCard extends ConsumerWidget {
  const DailyTipCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(activeChildProfileProvider);
    if (profile == null) {
      return const SizedBox.shrink();
    }
    final args = DailyTipArgs(ageGroup: profile.ageGroup);
    final asyncTip = ref.watch(dailyTipProvider(args));
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: asyncTip.when(
        data: (tip) => _Card(tip: tip, childName: profile.name),
        loading: () => const SizedBox.shrink(),
        error: (_, __) => const SizedBox.shrink(),
      ),
    );
  }
}

class _Card extends ConsumerStatefulWidget {
  const _Card({required this.tip, required this.childName});
  final DailyTip tip;
  final String childName;

  @override
  ConsumerState<_Card> createState() => _CardState();
}

class _CardState extends ConsumerState<_Card> {
  final ScreenshotController _screenshotController = ScreenshotController();
  bool _isSharing = false;

  @override
  void dispose() {
    super.dispose();
  }

  Future<void> _shareTip() async {
    if (_isSharing) return;
    setState(() => _isSharing = true);

    try {
      // Capture the shareable tip card as PNG
      final shareableCard = ShareableTipCard(
        tip: widget.tip,
        childName: widget.childName,
      );

      final image = await _screenshotController.captureFromWidget(
        shareableCard,
        pixelRatio: 2.0, // High-res capture (2160x2160)
      );

      // Save to temporary file
      final tempDir = await Directory.systemTemp.createTemp('tg_share_');
      final file = File('${tempDir.path}/tip_${widget.tip.id}.png');
      await file.writeAsBytes(image);

      // Share the image
      await Share.shareXFiles(
        [XFile(file.path)],
        text: 'نصيحة اليوم من المربي الذكي: ${widget.tip.text}',
        subject: 'نصيحة اليوم - المربي الذكي',
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('تعذّر مشاركة النصيحة: $e'),
            backgroundColor: AppTheme.dangerFg,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isSharing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isFav = ref.watch(favoritesProvider)['tips']
            ?.contains(widget.tip.id) ?? false;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topRight,
          end: Alignment.bottomLeft,
          colors: [Color(0xFFFFE9C7), Color(0xFFFFD89E)],
        ),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.wb_sunny_outlined,
                color: Color(0xFF8A5A0F), size: 20),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      'نصيحة اليوم لـ ${widget.childName}',
                      style: const TextStyle(
                        color: Color(0xFF8A5A0F),
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                      ),
                    ),
                    const Spacer(),
                    IconButton(
                      onPressed: () {
                        ref
                            .read(favoritesProvider.notifier)
                            .toggleTip(widget.tip.id);
                      },
                      icon: Icon(
                        isFav ? Icons.favorite : Icons.favorite_border,
                        color: isFav ? Colors.redAccent : const Color(0xFF8A5A0F),
                        size: 20,
                      ),
                      tooltip: isFav ? 'إزالة من المفضلة' : 'إضافة للمفضلة',
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                    const SizedBox(width: 4),
                    IconButton(
                      onPressed: _isSharing ? null : _shareTip,
                      icon: _isSharing
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Color(0xFF8A5A0F),
                              ),
                            )
                          : const Icon(
                              Icons.share_outlined,
                              color: Color(0xFF8A5A0F),
                              size: 20,
                            ),
                      tooltip: 'مشاركة النصيحة',
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.4),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        widget.tip.timeOfDayLabel,
                        style: const TextStyle(
                          color: Color(0xFF8A5A0F),
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  widget.tip.text,
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 13,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
