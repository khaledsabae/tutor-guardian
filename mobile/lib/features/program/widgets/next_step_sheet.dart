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
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/ui/bouncy_button.dart';

/// Shows the lesson's concrete action. Returns true when the parent
/// acknowledged it, false when they dismissed the sheet instead.
Future<bool> showNextStepSheet(
  BuildContext context, {
  required String tryThis,
}) async {
  final taken = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    backgroundColor: Dt.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(Dt.rSheet)),
    ),
    builder: (ctx) => _NextStepSheet(tryThis: tryThis),
  );
  return taken ?? false;
}

class _NextStepSheet extends StatelessWidget {
  const _NextStepSheet({required this.tryThis});

  final String tryThis;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l10n.lessonNextStepTitle,
              style: const TextStyle(
                fontSize: 19,
                fontWeight: FontWeight.w800,
                color: Dt.ink,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              l10n.lessonNextStepIntro,
              style: const TextStyle(
                fontSize: 13,
                color: Dt.inkSoft,
                height: 1.4,
              ),
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
                  const Text('💡', style: TextStyle(fontSize: 22)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      tryThis,
                      style: const TextStyle(
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
            BouncyButton(
              label: l10n.lessonNextStepConfirm,
              color: AppTheme.success,
              icon: const Icon(Icons.check_rounded, color: Colors.white),
              onTap: () => Navigator.of(context).pop(true),
            ),
          ],
        ),
      ),
    );
  }
}
