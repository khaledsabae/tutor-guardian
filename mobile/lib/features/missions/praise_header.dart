/// «كلمة طيبة» — the note a parent sends with the evening confirmation,
/// shown to the child the next time they hold the phone.
///
/// Three rules from the plan shape this file:
///  * **Once, briefly.** The header appears for at most three seconds and
///    never twice for the same note ([PraiseMemory] keys on the mission row
///    the praise settled, which is unique across the device's children).
///  * **By band.** 4–6 read a sticker and nothing else — the warmth arrives
///    without a sentence they must decode; 7–12 get the sticker and the text;
///    13–18 get one text line, because a teenager knows what a star sticker
///    means and would rather not say. Prenatal–3 are unaffected (no mission
///    bank, no praise to show).
///  * **Never in the way.** It is a quiet header above the card, not a dialog
///    and not an animation loop; the child's main action stays reachable and
///    the only motion is a one-shot entrance that stops by itself.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../l10n/app_localizations.dart';
import '../../theme/app_colors.dart';

/// How a band sees the praise. [none] for prenatal–3 and anything unreadable.
enum PraiseDisplay { none, sticker, stickerAndText, textOnly }

/// The display form for a child-surface band ("under-2" … "16-18").
PraiseDisplay praiseDisplayFor(String? band) {
  switch (band) {
    case '4-6':
      return PraiseDisplay.sticker;
    case '7-9':
    case '10-12':
      return PraiseDisplay.stickerAndText;
    case '13-15':
    case '16-18':
      return PraiseDisplay.textOnly;
    default:
      return PraiseDisplay.none;
  }
}

/// Which notes this device has already shown. SharedPreferences, not secure
/// storage: a mission row id is not a secret, and the child surface must be
/// able to read it without the parent's storage.
abstract final class PraiseMemory {
  static const _key = 'missions.praise_shown';

  /// Enough history for a nightly-praising family to never see a repeat,
  /// small enough that the list never grows without end.
  static const _keep = 20;

  static Future<bool> alreadyShown(SharedPreferences prefs, int missionId) async =>
      prefs.getStringList(_key)?.contains('$missionId') ?? false;

  static Future<void> markShown(SharedPreferences prefs, int missionId) async {
    final ids = prefs.getStringList(_key) ?? <String>[];
    ids.add('$missionId');
    await prefs.setStringList(
        _key, ids.length > _keep ? ids.sublist(ids.length - _keep) : ids);
  }
}

/// The header itself: [note] in the form [display] picks, gone in three
/// seconds via [onGone]. It never blocks the child's main action — the caller
/// places it above the card and removes it when it says so.
class PraiseHeader extends StatefulWidget {
  const PraiseHeader({
    super.key,
    required this.note,
    required this.display,
    this.onGone,
  });

  final String note;
  final PraiseDisplay display;
  final VoidCallback? onGone;

  @override
  State<PraiseHeader> createState() => _PraiseHeaderState();
}

class _PraiseHeaderState extends State<PraiseHeader> {
  Timer? _expiry;

  @override
  void initState() {
    super.initState();
    _expiry = Timer(const Duration(seconds: 3), _gone);
  }

  @override
  void dispose() {
    _expiry?.cancel();
    super.dispose();
  }

  void _gone() {
    if (mounted) widget.onGone?.call();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final showSticker = widget.display == PraiseDisplay.sticker ||
        widget.display == PraiseDisplay.stickerAndText;
    final showText = widget.display == PraiseDisplay.stickerAndText ||
        widget.display == PraiseDisplay.textOnly;

    final content = Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (showSticker)
          // One-shot entrance: it scales in once and stops. Nothing here
          // loops, so a CI journey with animations disabled loses nothing.
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.6, end: 1),
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOutBack,
            builder: (context, scale, child) =>
                Transform.scale(scale: scale, child: child),
            child: const Text('🌟', style: TextStyle(fontSize: 40)),
          ),
        if (showSticker && showText) const SizedBox(height: 4),
        if (showText) ...[
          Text(
            l10n.praiseFromFamily,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: colors.textSecondary),
          ),
          const SizedBox(height: 2),
          Text(
            widget.note,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(color: colors.primary, fontWeight: FontWeight.w700),
          ),
        ],
      ],
    );

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: colors.surfaceAlt,
        borderRadius: BorderRadius.circular(16),
      ),
      child: content,
    );
  }
}
