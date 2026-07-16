/// Safety banner rendered above (or inline with) an assistant message.
///
/// Driven ONLY by the structured `AssistantReply` fields — never by parsing
/// the reply prose. See MOBILE_API.md §4.
library;

import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';
import '../models/api_models.dart';
import '../models/enums.dart';
import '../theme/app_theme.dart';

class SafetyBanner extends StatelessWidget {
  final AssistantReply? reply;

  const SafetyBanner({super.key, required this.reply});

  @override
  Widget build(BuildContext context) {
    final r = reply;
    if (r == null) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);

    // Priority: emergency > needs_human_review > banned notice.
    if (r.isEmergency) {
      return _Banner(
        color: AppTheme.dangerBg,
        textColor: AppTheme.dangerFg,
        icon: Icons.warning_amber_rounded,
        text: l10n.safetyEmergencyText,
        cta: l10n.safetyEmergencyCta,
        ctaUri: 'tel:112',
      );
    }
    if (r.mode == ReplyMode.banned) {
      return _Banner(
        color: AppTheme.warningBg,
        textColor: AppTheme.warningFg,
        icon: Icons.info_outline,
        text: l10n.safetyBannedText,
      );
    }
    if (r.needsHumanReview) {
      final hint = r.escalationTarget == EscalationTarget.pediatrician
          ? l10n.safetyConsultPediatrician
          : r.escalationTarget == EscalationTarget.cybersecuritySpecialist
              ? l10n.safetyConsultCyberSpecialist
              : l10n.safetyConsultHuman;
      return _Banner(
        color: AppTheme.warningBg,
        textColor: AppTheme.warningFg,
        icon: Icons.medical_services_outlined,
        text: l10n.safetyGeneralGuidance(hint),
      );
    }
    return const SizedBox.shrink();
  }
}

class _Banner extends StatelessWidget {
  final Color color;
  final Color textColor;
  final IconData icon;
  final String text;
  final String? cta;
  final String? ctaUri;

  const _Banner({
    required this.color,
    required this.textColor,
    required this.icon,
    required this.text,
    this.cta,
    this.ctaUri,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: textColor.withValues(alpha: 0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: textColor, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(color: textColor, fontSize: 13, height: 1.4),
            ),
          ),
          if (cta != null && ctaUri != null) ...[
            const SizedBox(width: 8),
            TextButton(
              onPressed: () {
                // In a real release this should use url_launcher.
                // For now we just log — the banner is the primary signal.
              },
              style: TextButton.styleFrom(foregroundColor: textColor),
              child: Text(cta!),
            ),
          ],
        ],
      ),
    );
  }
}
