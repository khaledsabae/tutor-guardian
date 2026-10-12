/// «هدية اليوم» as a moment, not a line (جولة الحرفة, item 2).
///
/// The child's login reward used to appear as a muted sentence — a coin
/// flow the parent never *felt*. Once per day, on the first «اليوم» visit
/// that sees a claimed gift, it now lands: the drawn gift glyph bounces
/// in, the number counts up, and one success haptic ticks. On every later
/// visit of the same day — and always under reduced motion, where the
/// moment would be a snap instead of a landing — it falls back to the
/// quiet line, so the information never disappears, only the fanfare.
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/haptics.dart';
import '../../../core/motion.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/brand_glyph.dart';
import '../../../widgets/ui/count_up_text.dart';

/// What this visit gets: the day's landing, or the quiet line.
enum _GiftMomentPhase { deciding, moment, quiet }

class DailyGiftMoment extends StatefulWidget {
  const DailyGiftMoment({super.key, required this.gift});

  /// The coins claimed by the child's login today; 0 hides the row.
  final int gift;

  @override
  State<DailyGiftMoment> createState() => _DailyGiftMomentState();
}

class _DailyGiftMomentState extends State<DailyGiftMoment>
    with SingleTickerProviderStateMixin {
  _GiftMomentPhase _phase = _GiftMomentPhase.deciding;
  late final AnimationController _bounceController;
  late final Animation<double> _bounceAnimation;

  static const _shownKey = 'home.gift_moment_day';

  @override
  void initState() {
    super.initState();
    _bounceController = AnimationController(
      vsync: this,
      duration: Dt.slow,
    );
    _bounceAnimation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(
        parent: _bounceController,
        curve: Curves.easeOutBack,
      ),
    );
    _decide();
  }

  @override
  void dispose() {
    _bounceController.dispose();
    super.dispose();
  }

  /// The moment plays only on the day's first visit that sees the gift.
  /// The claim itself is already once-per-day server-side; this only stops
  /// a re-entry (tab switch, app resume) from re-celebrating.
  Future<void> _decide() async {
    final prefs = await SharedPreferences.getInstance();
    final today = DateTime.now().toIso8601String().substring(
      0,
      10,
    ); // yyyy-MM-dd
    if (!mounted || widget.gift <= 0) return;
    if (prefs.getString(_shownKey) == today) {
      setState(() => _phase = _GiftMomentPhase.quiet);
      return;
    }
    await prefs.setString(_shownKey, today);
    if (!mounted) return;
    // One haptic with the landing, never with the quiet line.
    Haptics.success();
    setState(() => _phase = _GiftMomentPhase.moment);
    if (!reduceMotion(context)) {
      _bounceController.forward(from: 0);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.gift <= 0) return const SizedBox.shrink();
    final colors = context.colors;
    final l10n = AppLocalizations.of(context);

    // The quiet form: same place in the page, no motion — what repeat
    // visits and reduced motion see. Also the safe default while the
    // day's decision loads.
    final quiet = Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          BrandGlyph(BrandIcon.gift, size: 15, color: colors.accent),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              l10n.dailyGiftLine(widget.gift),
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: colors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );

    // The landing: a one-shot entrance (collapses to a frame on its own
    // under remove-animations) and a count that arrives.
    if (_phase == _GiftMomentPhase.moment && !reduceMotion(context)) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            ScaleTransition(
              scale: _bounceAnimation,
              child: BrandGlyph(
                BrandIcon.gift,
                size: 20,
                color: colors.accent,
              ),
            ),
            const SizedBox(width: 7),
            Flexible(
              child: Text(
                l10n.dailyGiftLabel,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: colors.textSecondary,
                ),
              ),
            ),
            const SizedBox(width: 6),
            CountUpText(
              widget.gift,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w800,
                color: colors.accent,
              ),
              duration: const Duration(milliseconds: 900),
            ),
            const SizedBox(width: 4),
            BrandGlyph(BrandIcon.coin, size: 15, color: colors.accent),
          ],
        ),
      );
    }
    return quiet;
  }
}
