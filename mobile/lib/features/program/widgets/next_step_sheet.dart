/// The one concrete thing to do with the child tonight.
///
/// «كيفية تنفيذ القيمة» — a parent on Facebook, 17 Aug 2026, listing what he
/// could not work out from the app. The lesson already answers him: every
/// lesson carries a `try_this` field written as a single doable action («هذا
/// الأسبوع: حين يصدق طفلك في أمرٍ صعب، امدح صدقه أولاً قبل معالجة الخطأ»). It
/// was rendered as section 4 of 7, mid-scroll, between the summary and the
/// reflection prompts, and then the lesson ended: confetti, a store-review
/// ask, and a pop back to the list. The strongest moment in the app spent its
/// momentum on everything except the next step.
///
/// This sheet is that field, promoted to the moment it is useful.
library;

import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';
import '../../../widgets/ui/brand_glyph.dart';
import '../../companion/data/companion_store.dart';

/// Shows the lesson's concrete action and asks when the parent will try it
/// («نور يتذكّر», حلقة الوعد). Returns the slot picked, or null when the
/// sheet was dismissed instead. Noor asks back on the slot's due day.
///
/// [title] and [intro] replace the lesson's copy when the step comes from
/// somewhere else — an assistant answer's «سأجرّبها مع …» (phase 4).
Future<PromiseSlot?> showNextStepSheet(
  BuildContext context, {
  required String tryThis,
  required String childName,
  String? title,
  String? intro,
}) async {
  return showModalBottomSheet<PromiseSlot>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    backgroundColor: Dt.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(Dt.rSheet)),
    ),
    builder: (ctx) => _NextStepSheet(
      tryThis: tryThis,
      childName: childName,
      title: title,
      intro: intro,
    ),
  );
}

class _NextStepSheet extends StatelessWidget {
  const _NextStepSheet({
    required this.tryThis,
    required this.childName,
    this.title,
    this.intro,
  });

  final String tryThis;
  final String? title;
  final String? intro;

  /// The child's name, or «طفلك» when it is still the default.
  final String childName;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    // Scrolls when it must: at 200% text the step, the question and three
    // full-width slots are taller than a 360dp phone.
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title ?? l10n.lessonNextStepTitle,
              style: TextStyle(
                fontSize: 19,
                fontWeight: FontWeight.w800,
                color: Dt.ink,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              intro ?? l10n.lessonNextStepIntro,
              style: TextStyle(fontSize: 13, color: Dt.inkSoft, height: 1.4),
            ),
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Dt.accent.withValues(alpha: .10),
                borderRadius: BorderRadius.circular(Dt.rButton),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // The lit lantern is the drawn successor of the 💡 this
                  // card carried (جولة الحرفة) — gold, like the tint behind.
                  BrandGlyph(
                    BrandIcon.lantern,
                    size: 26,
                    color: context.colors.accent,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      tryThis,
                      style: TextStyle(
                        fontSize: 15,
                        height: 1.6,
                        color: Dt.ink,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            Text(
              l10n.promiseWhenTitle(childName),
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: Dt.ink,
              ),
            ),
            const SizedBox(height: 10),
            // Three slots, not one «تمام»: the slot is the promise, and the
            // promise is what Noor asks back about (plan §2, حلقة الوعد).
            // Stacked full-width, not side by side: three in a row cut
            // «Tomorrow» to «Tomorro…» on a 360dp phone in English (CI
            // gallery, 2026-10-15), and longer languages and 200% text only
            // make that worse.
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final (i, slot) in PromiseSlot.values.indexed) ...[
                  if (i > 0) const SizedBox(height: 8),
                  BouncyButton(
                    label: switch (slot) {
                      PromiseSlot.tonight => l10n.promiseTonight,
                      PromiseSlot.tomorrow => l10n.promiseTomorrow,
                      PromiseSlot.week => l10n.promiseThisWeek,
                    },
                    color: i == 0 ? AppTheme.success : context.colors.primary,
                    onTap: () => Navigator.of(context).pop(slot),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}
