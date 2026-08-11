import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/painting.dart';

/// What to do with an error that reached a global handler.
///
/// There is no `fatal` member on purpose. Anything that arrives at
/// `FlutterError.onError` or `PlatformDispatcher.onError` did **not** kill the
/// app — `PlatformDispatcher.onError` returning `true` is literally the
/// statement "handled". Reporting these as fatal is what produced 18,580
/// `app_exception` events across 1,219 users in 28 days while Play measured a
/// crash-free rate of 99.85%: ~15 "crashes" per affected user, none of which
/// the user ever saw. Genuine process-terminating crashes are caught by the
/// native Crashlytics layer without any Dart wiring.
///
/// Promote to fatal explicitly at the two call sites where the app really
/// cannot continue (boot failure, session establishment), never here.
enum CrashSeverity {
  /// Expected in the field. Recording it buys noise, not signal.
  ignore,

  /// A real defect worth a report, but the app kept running.
  nonFatal,
}

/// Errors that mean "the network is bad", not "the code is wrong".
///
/// Users on patchy mobile data generate these continuously. They drowned the
/// genuine defects in the same bucket.
bool _isConnectivityNoise(Object? error) =>
    error is SocketException ||
    error is TimeoutException ||
    error is HttpException ||
    error is HandshakeException ||
    error is NetworkImageLoadException;

/// Classify a raw error from [PlatformDispatcher.onError].
CrashSeverity severityFor(Object? error) =>
    _isConnectivityNoise(error) ? CrashSeverity.ignore : CrashSeverity.nonFatal;

/// Classify a framework error from [FlutterError.onError].
///
/// Layout overflow is the loudest offender: one mis-sized row on a small
/// screen repeats on every rebuild, so a single cosmetic bug bills thousands
/// of reports. It is a real problem — it just belongs in an analytics event
/// carrying the screen name, not in the crash reporter.
CrashSeverity severityForFlutterError(FlutterErrorDetails details) {
  if (_isConnectivityNoise(details.exception)) return CrashSeverity.ignore;
  if (isLayoutOverflow(details)) return CrashSeverity.ignore;
  return CrashSeverity.nonFatal;
}

/// Whether [details] describes a RenderFlex/RenderBox overflow.
///
/// Matched on the rendering library plus the framework's own wording, because
/// overflow is reported as a plain [FlutterError] with no distinct type.
bool isLayoutOverflow(FlutterErrorDetails details) {
  if (details.library != 'rendering library') return false;
  final text = details.exception.toString();
  return text.contains('overflowed by') || text.contains('OVERFLOWING');
}
