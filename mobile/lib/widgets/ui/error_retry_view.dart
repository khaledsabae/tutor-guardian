/// A failure the parent can act on, instead of the exception's toString().
///
/// Three screens rendered `errorGeneric(e.toString())`, which put
/// "SocketException: Failed host lookup: 'tg-api.alsaba.cloud'" in front of an
/// Arabic-speaking parent — untranslatable, unactionable, and alarming. What
/// they need to know is only ever one of three things: the connection is down,
/// the service is unwell, or something else went wrong and retrying is worth a
/// try.
library;

import 'package:flutter/material.dart';

import '../../core/failures.dart';
import '../../l10n/app_localizations.dart';
import 'empty_state.dart';

class ErrorRetryView extends StatelessWidget {
  const ErrorRetryView({super.key, required this.error, this.onRetry});

  final Object error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final (emoji, title, body) = switch (classifyFailure(error)) {
      FailureKind.offline => ('📡', l10n.errorOfflineTitle, l10n.errorOfflineBody),
      FailureKind.server => ('🛠️', l10n.errorServerTitle, l10n.errorServerBody),
      FailureKind.unknown => ('🤔', l10n.errorUnknownTitle, l10n.errorUnknownBody),
    };

    return EmptyState(
      emoji: emoji,
      title: title,
      subtitle: body,
      actionLabel: onRetry == null ? null : l10n.retry,
      onAction: onRetry,
    );
  }
}
