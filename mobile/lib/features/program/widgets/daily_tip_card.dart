/// Daily Tip card — small surface that surfaces the day's parenting
/// tip on top of the chat. Driven by [dailyTipProvider] filtered by
/// the active child's age group (from [activeChildProfileProvider]).
///
/// If the child profile isn't loaded yet (post-onboarding race), the
/// card gracefully hides itself rather than show a loading skeleton
/// that competes with the chat for attention.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../../onboarding/providers/onboarding_providers.dart';
import '../data/models.dart';
import '../providers/program_providers.dart';
import '../providers/favorites_provider.dart';
import '../widgets/shareable_tip_card.dart';
import '../../share/share_service.dart';
import '../../../theme/app_palette.dart';

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
        error: (_, _) => const SizedBox.shrink(),
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
  bool _isSharing = false;

  @override
  void dispose() {
    super.dispose();
  }

  Future<void> _shareTip() async {
    if (_isSharing) return;
    setState(() => _isSharing = true);

    try {
      // Route through ShareService so the tip carries the install link and
      // this device's referral code. Sharing the text alone gave whoever
      // received it no way to reach the app — on the one screen most likely
      // to be shared.
      await ShareService.shareMomentCard(
        fileTag: 'tip_${widget.tip.id}',
        message: 'نصيحة اليوم من المربي الذكي: ${widget.tip.text}',
        card: ShareableTipCard(
          tip: widget.tip,
          childName: widget.childName,
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppLocalizations.of(context).dailyTipShareError(e)),
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
        gradient: LinearGradient(
          begin: Alignment.topRight,
          end: Alignment.bottomLeft,
          colors: AppPalette.current.tipGradient,
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
              color: AppPalette.current.surface.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(Icons.wb_sunny_outlined,
                color: AppPalette.current.tipInk, size: 20),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      AppLocalizations.of(context).insightsTitle,
                      style: TextStyle(
                        color: AppPalette.current.tipInk,
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
                        color: isFav ? Colors.redAccent : AppPalette.current.tipInk,
                        size: 20,
                      ),
                      tooltip: isFav ? AppLocalizations.of(context).lessonFavRemove : AppLocalizations.of(context).lessonFavAdd,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                    const SizedBox(width: 4),
                    IconButton(
                      onPressed: _isSharing ? null : _shareTip,
                      icon: _isSharing
                          ? SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: AppPalette.current.tipInk,
                              ),
                            )
                          : Icon(
                              Icons.share_outlined,
                              color: AppPalette.current.tipInk,
                              size: 20,
                            ),
                      tooltip: AppLocalizations.of(context).share,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: AppPalette.current.surface.withValues(alpha: 0.4),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        widget.tip.timeOfDayLabel(AppLocalizations.of(context)),
                        style: TextStyle(
                          color: AppPalette.current.tipInk,
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
                  style: TextStyle(
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
