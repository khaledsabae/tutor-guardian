/// What a failure means to the reader — not what threw it.
///
/// Both the UI (which message to show) and the data layer (whether a cached
/// copy is a better answer than an error) need this distinction, so it lives
/// here rather than beside either one.
///
/// [friendlyError] is the one place an error becomes words on a screen. The
/// lesson screen once printed '$err' under «تعذّر تحميل الدرس», which put
/// "TgApiError(502): The origin web server returned an invalid or incomplete
/// response to Cloudflare…" in front of Arabic-speaking parents. The raw error
/// is logged for diagnostics and never shown.
library;

import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../api/tg_client.dart';
import '../l10n/app_localizations.dart';

enum FailureKind {
  /// The request never reached a healthy server (no connection, timeout).
  offline,

  /// It reached the server and the server is unwell — any 5xx, Cloudflare's
  /// 52x included.
  server,

  /// 404: the thing asked for is not there.
  notFound,

  /// 401/403: the session ended or is not allowed. The client already drops an
  /// expired session, so the next attempt mints a new one — retrying is the
  /// re-auth flow.
  unauthorized,

  /// 429: too many requests; waiting is the fix.
  rateLimited,

  /// Something else — another 4xx, a parse error, a bug.
  unknown,
}

FailureKind classifyFailure(Object error) {
  if (error is SocketException ||
      error is HttpException ||
      error is http.ClientException) {
    return FailureKind.offline;
  }
  if (error is TimeoutException) return FailureKind.offline;
  if (error is TgApiError) {
    final code = error.statusCode;
    if (code == null) return FailureKind.offline;
    if (code >= 500) return FailureKind.server;
    if (code == 404) return FailureKind.notFound;
    if (code == 401 || code == 403) return FailureKind.unauthorized;
    if (code == 429) return FailureKind.rateLimited;
    return FailureKind.unknown;
  }
  return FailureKind.unknown;
}

/// True when a stale local copy is a better answer than this error.
///
/// A 404 means the thing is gone and showing a cached version would be a lie;
/// a dropped connection or a 5xx says nothing about the content itself.
bool staleDataBeatsError(Object error) {
  final kind = classifyFailure(error);
  return kind == FailureKind.offline || kind == FailureKind.server;
}

/// An error as the reader should see it.
@immutable
class FriendlyError {
  const FriendlyError({
    required this.kind,
    required this.emoji,
    required this.title,
    required this.body,
  });

  final FailureKind kind;
  final String emoji;
  final String title;

  /// One sentence the reader can act on. Usually the category's own line; for
  /// a 4xx whose message our server wrote for the reader, in their language,
  /// that message.
  final String body;
}

/// The one mapper from an error to words on a screen.
///
/// Never returns any part of [error]'s toString(). A [TgApiError]'s message is
/// passed through only when it is a 4xx other than 401/403 (a 5xx detail is
/// whatever the failing layer wrote — Python, nginx, Cloudflare), and only
/// when it reads as a sentence for this reader: in their script, with no
/// markup or stock HTTP phrase in it.
FriendlyError friendlyError(AppLocalizations l10n, Object error) {
  // Diagnostics only — this is the copy nobody on the screen sees.
  debugPrint('[friendlyError] $error');
  final kind = classifyFailure(error);
  final (emoji, title, body) = switch (kind) {
    FailureKind.offline => ('📡', l10n.errorOfflineTitle, l10n.errorOfflineBody),
    FailureKind.server => ('🛠️', l10n.errorServerTitle, l10n.errorServerBody),
    FailureKind.notFound => ('🔎', l10n.errorNotFoundTitle, l10n.errorNotFoundBody),
    FailureKind.unauthorized => ('🔑', l10n.errorSessionTitle, l10n.errorSessionBody),
    FailureKind.rateLimited => ('⏳', l10n.errorRateLimitedTitle, l10n.errorRateLimitedBody),
    FailureKind.unknown => ('🤔', l10n.errorUnknownTitle, l10n.errorUnknownBody),
  };
  final passed = _serverWrittenMessage(l10n, error, kind);
  return FriendlyError(
      kind: kind, emoji: emoji, title: title, body: passed ?? body);
}

/// One sentence a parent can act on, for places too small for a full error
/// view — a SnackBar, an inline hint, the tail of «تعذّر …: {error}».
String describeFailure(AppLocalizations l10n, Object error) =>
    friendlyError(l10n, error).body;

final RegExp _arabic = RegExp(r'[؀-ۿ]');

/// Markup, stack traces, and the stock phrases of FastAPI, nginx, Cloudflare
/// and our own generic «خطأ HTTP n» — true, but nothing a parent can act on.
final RegExp _plumbing = RegExp(
  r'<[a-z!/]|cloudflare|origin web server|exception|traceback|error\(|'
  r'\bhttp\s?\d{3}\b|^\s*(not found|method not allowed|unauthorized|forbidden|'
  r'too many requests|bad request|bad gateway|service unavailable|'
  r'gateway time-?out|internal server error)\s*\.?\s*$',
  caseSensitive: false,
);

String? _serverWrittenMessage(
    AppLocalizations l10n, Object error, FailureKind kind) {
  if (error is! TgApiError) return null;
  final status = error.statusCode;
  if (status == null || status < 400 || status >= 500) return null;
  if (kind == FailureKind.unauthorized) return null;
  final message = error.message.trim();
  if (message.isEmpty || message.length > 240) return null;
  if (_plumbing.hasMatch(message)) return null;
  if (message == l10n.apiHttpError('$status')) return null;
  final readerIsArabic = l10n.localeName.startsWith('ar');
  if (_arabic.hasMatch(message) != readerIsArabic) return null;
  return message;
}
