/// One calm, translated sentence for a failed memory or protected action.
library;

import 'package:flutter/widgets.dart';

import '../../../api/tg_client.dart';
import '../../../l10n/app_localizations.dart';
import '../../../widgets/ui/error_retry_view.dart';
import 'proof_views.dart';

/// The branchable codes (MOBILE_API §9.3–§9.4) get their own words; a
/// proof failure keeps the server's message, which names the support
/// address; anything else is the app's usual three-way explanation.
String memoryErrorText(AppLocalizations l10n, Object e, {int maxChars = 160}) {
  if (e is TgApiError) {
    switch (e.code) {
      case 'fact_too_long':
        return l10n.memoryFactTooLong(maxChars);
      case 'fact':
      case 'empty_patch':
        return l10n.memoryFactInvalid;
      case 'sensitive':
        return l10n.memorySensitive;
      case 'followup_closed':
        return l10n.followupClosed;
      case 'followup_not_found':
        return l10n.followupNotFound;
    }
    if (isProofError(e) && e.message.trim().isNotEmpty) return e.message;
  }
  return describeFailure(l10n, e);
}

/// [memoryErrorText], plus the one thing that needs a [BuildContext]: a
/// pause says WHEN it ends, on the parent's own clock (MOBILE_API §9.0.1 —
/// "show the message with the time"). For the protected actions outside the
/// memory screens too: deleting a child, resetting progress.
String describeActionFailure(BuildContext context, Object e,
    {int maxChars = 160}) {
  final l10n = AppLocalizations.of(context);
  if (e is TgApiError && e.code == 'device_proof_cooldown') {
    final until = e.availableAt;
    final message = e.message.trim();
    return [
      if (until != null)
        l10n.proofPausedTitle(formatLocalDateTime(context, until)),
      if (message.isNotEmpty) message,
    ].join(' — ');
  }
  return memoryErrorText(l10n, e, maxChars: maxChars);
}
