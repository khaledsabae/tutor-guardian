/// A failure the parent can act on, instead of the exception's toString().
///
/// Three screens rendered `errorGeneric(e.toString())`, which put
/// "SocketException: Failed host lookup: 'tg-api.alsaba.cloud'" in front of an
/// Arabic-speaking parent — untranslatable, unactionable, and alarming. What
/// they need to know is which of a handful of things happened (no connection,
/// the service is unwell, the thing is gone, the session ended, too many
/// requests, or something else worth a retry); [friendlyError] decides which.
library;

import 'package:flutter/material.dart';

import '../../core/failures.dart';
import '../../l10n/app_localizations.dart';
import 'empty_state.dart';

export '../../core/failures.dart'
    show FailureKind, FriendlyError, describeFailure, friendlyError;

/// [friendlyError] in the current locale.
FriendlyError userFacingError(BuildContext context, Object error) =>
    friendlyError(AppLocalizations.of(context), error);

class ErrorRetryView extends StatelessWidget {
  const ErrorRetryView({super.key, required this.error, this.onRetry});

  final Object error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final f = friendlyError(l10n, error);
    return EmptyState(
      emoji: f.emoji,
      title: f.title,
      subtitle: f.body,
      actionLabel: onRetry == null ? null : l10n.retry,
      onAction: onRetry,
    );
  }
}
