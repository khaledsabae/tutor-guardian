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

import '../../api/tg_client.dart';
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

/// One sentence a parent can act on, for places too small for [ErrorRetryView]
/// — a SnackBar, an inline hint.
///
/// Eight SnackBars interpolated `e.toString()`, which printed
/// "TgApiError(500): …" or "SocketException: Failed host lookup" into an
/// Arabic sentence. A 4xx from our own API carries a server-written message
/// meant for the reader, so that one is passed through; everything else maps
/// to the same three explanations [ErrorRetryView] uses.
String describeFailure(AppLocalizations l10n, Object error) {
  final kind = classifyFailure(error);
  if (kind == FailureKind.unknown &&
      error is TgApiError &&
      error.statusCode != null &&
      error.message.trim().isNotEmpty) {
    return error.message;
  }
  return switch (kind) {
    FailureKind.offline => l10n.errorOfflineBody,
    FailureKind.server => l10n.errorServerBody,
    FailureKind.unknown => l10n.errorUnknownBody,
  };
}
