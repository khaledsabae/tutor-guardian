import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/painting.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:almorabbi/core/crash_triage.dart';

/// Builds a details object shaped like the framework's own overflow report.
FlutterErrorDetails _renderingError(String message) => FlutterErrorDetails(
      exception: FlutterError(message),
      library: 'rendering library',
    );

void main() {
  group('severityFor — raw async errors', () {
    test('connectivity failures are dropped, not reported', () {
      for (final e in <Object>[
        const SocketException('no route to host'),
        TimeoutException('slow'),
        const HttpException('502'),
        const HandshakeException('bad cert'),
        NetworkImageLoadException(
          statusCode: 404,
          uri: Uri.parse('https://example.test/a.png'),
        ),
      ]) {
        expect(severityFor(e), CrashSeverity.ignore,
            reason: '${e.runtimeType} is a network condition, not a defect');
      }
    });

    test('a genuine bug is still recorded', () {
      expect(severityFor(StateError('bad state')), CrashSeverity.nonFatal);
      expect(severityFor(ArgumentError('nope')), CrashSeverity.nonFatal);
    });

    test('null does not crash the classifier', () {
      expect(severityFor(null), CrashSeverity.nonFatal);
    });
  });

  group('severityForFlutterError — framework errors', () {
    test('layout overflow is dropped', () {
      expect(
        severityForFlutterError(
          _renderingError('A RenderFlex overflowed by 42 pixels on the right.'),
        ),
        CrashSeverity.ignore,
      );
    });

    test('other rendering errors are still recorded', () {
      expect(
        severityForFlutterError(
          _renderingError('RenderBox was not laid out'),
        ),
        CrashSeverity.nonFatal,
      );
    });

    test('overflow wording outside the rendering library is not swallowed', () {
      // Guards against a message that merely mentions overflow — e.g. one our
      // own code throws — being silently dropped.
      expect(
        severityForFlutterError(FlutterErrorDetails(
          exception: FlutterError('the queue overflowed by design'),
          library: 'tutor guardian',
        )),
        CrashSeverity.nonFatal,
      );
    });

    test('connectivity wrapped in FlutterErrorDetails is dropped', () {
      expect(
        severityForFlutterError(FlutterErrorDetails(
          exception: const SocketException('offline'),
          library: 'services',
        )),
        CrashSeverity.ignore,
      );
    });
  });

  group('isLayoutOverflow', () {
    test('matches both wordings the framework uses', () {
      expect(isLayoutOverflow(_renderingError('overflowed by 3.0 pixels')),
          isTrue);
      expect(isLayoutOverflow(_renderingError('A RenderFlex OVERFLOWING')),
          isTrue);
    });

    test('does not match an unrelated rendering failure', () {
      expect(isLayoutOverflow(_renderingError('cannot hit test')), isFalse);
    });
  });
}
