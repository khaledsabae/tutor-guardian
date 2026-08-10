/// What a failure means to the reader — not what threw it.
///
/// Both the UI (which message to show) and the data layer (whether a cached
/// copy is a better answer than an error) need this distinction, so it lives
/// here rather than beside either one.
library;

import 'dart:async';
import 'dart:io';

import '../api/tg_client.dart';

enum FailureKind {
  /// The request never reached a healthy server.
  offline,

  /// It reached the server and the server is unwell.
  server,

  /// Something else — a 4xx, a parse error, a bug.
  unknown,
}

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

/// True when a stale local copy is a better answer than this error.
///
/// A 404 means the thing is gone and showing a cached version would be a lie;
/// a dropped connection or a 5xx says nothing about the content itself.
bool staleDataBeatsError(Object error) {
  final kind = classifyFailure(error);
  return kind == FailureKind.offline || kind == FailureKind.server;
}
