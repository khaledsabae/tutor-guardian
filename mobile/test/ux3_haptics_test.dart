// E5: one switch silences every haptic; the preference survives restarts.

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/core/haptics.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final calls = <String>[];

  setUp(() {
    calls.clear();
    SharedPreferences.setMockInitialValues({});
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'HapticFeedback.vibrate') calls.add('${call.arguments}');
      return null;
    });
  });

  test('on by default, off silences every kind, and it is remembered',
      () async {
    await Haptics.load();
    expect(Haptics.enabled, isTrue);
    await Haptics.success();
    expect(calls, hasLength(1));

    await Haptics.setEnabled(false);
    await Haptics.selection();
    await Haptics.success();
    await Haptics.warning();
    await Haptics.strong();
    expect(calls, hasLength(1));

    await Haptics.load(); // a restart reads the saved choice
    expect(Haptics.enabled, isFalse);
    await Haptics.setEnabled(true);
  });
}
