/// A failure the parent can act on, instead of the exception's toString().
///
/// Three screens rendered `errorGeneric(e.toString())`, which put
/// "SocketException: Failed host lookup: 'tg-api.alsaba.cloud'" in front of an
/// Arabic-speaking parent — untranslatable, unactionable, and alarming. What
/// they need to know is only ever one of three things: the connection is down,
/// the service is unwell, or something else went wrong and retrying is worth a
/// try.
library;

import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../api/tg_client.dart';
import '../../l10n/app_localizations.dart';
import 'empty_state.dart';

/// What the reader can do about a failure — not what threw it.
enum FailureKind { offline, server, unknown }

/// Classify [error] into something worth saying out loud.
FailureKind classifyFailure(Object error) {
  if (error is SocketException || error is HttpException) return FailureKind.offline;
  if (error is TimeoutException) return FailureKind.offline;
  if (error is TgApiError) {
    final code = error.statusCode;
    if (code == null) return FailureKind.offline;
    if (code >= 500) return FailureKind.server;
    return FailureKind.unknown;
  }
  return FailureKind.unknown;
}

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
