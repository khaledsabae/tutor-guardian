// The CI rehearsal's key probe (core/e2e_probes.dart): absent from every
// build that is not the rehearsal APK, and — where a test installs it — one
// F12 is exactly one interface tick through the path a tab tap takes.

import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/core/e2e_probes.dart';
import 'package:almorabbi/core/haptics.dart';
import 'package:almorabbi/core/sound_fx.dart';

class _Backend implements SfxBackend {
  final played = <Sfx>[];

  @override
  Future<void> preload(List<Sfx> sounds) async {}

  @override
  Future<void> play(Sfx sound) async => played.add(sound);
}

Future<void> _press(WidgetTester tester, LogicalKeyboardKey key) async {
  await simulateKeyDownEvent(key);
  await simulateKeyUpEvent(key);
  await tester.pump();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  final pulses = <String>[];
  late _Backend backend;

  setUp(() async {
    pulses.clear();
    SoundFx.debugReset();
    SharedPreferences.setMockInitialValues({});
    messenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'HapticFeedback.vibrate') {
        pulses.add('${call.arguments}');
      }
      return null;
    });
    await Haptics.setEnabled(true);
    backend = _Backend();
    await SoundFx.init(backend: backend);
  });

  tearDown(() async {
    E2eProbes.uninstall();
    SoundFx.debugReset();
    await Haptics.setEnabled(true);
  });

  test('a build made without --dart-define=E2E_PROBES=true has no probe', () {
    // `flutter test` passes no define, exactly like the Play build.
    expect(kE2eProbes, isFalse);
    E2eProbes.installIfEnabled();
    expect(E2eProbes.installed, isFalse);
  });

  testWidgets('without the probe, F12 is just a key', (tester) async {
    E2eProbes.installIfEnabled();
    await tester.pumpWidget(const SizedBox());
    await _press(tester, LogicalKeyboardKey.f12);
    expect(backend.played, isEmpty);
    expect(pulses, isEmpty);
  });

  testWidgets('installed, F12 is one tick on the tap path', (tester) async {
    E2eProbes.install();
    await tester.pumpWidget(const SizedBox());
    await _press(tester, LogicalKeyboardKey.f12);
    expect(backend.played, [Sfx.select]);
    expect(pulses, ['HapticFeedbackType.selectionClick']);
  });

  testWidgets('installed, a system light/dark change is one tick',
      (tester) async {
    E2eProbes.install();
    await tester.pumpWidget(const SizedBox());
    tester.platformDispatcher.platformBrightnessTestValue = Brightness.dark;
    await tester.pump();
    tester.platformDispatcher.clearPlatformBrightnessTestValue();
    await tester.pump();
    expect(backend.played, [Sfx.select, Sfx.select]);
  });

  testWidgets('without the probe, a light/dark change is silent',
      (tester) async {
    E2eProbes.installIfEnabled();
    await tester.pumpWidget(const SizedBox());
    tester.platformDispatcher.platformBrightnessTestValue = Brightness.dark;
    await tester.pump();
    tester.platformDispatcher.clearPlatformBrightnessTestValue();
    expect(backend.played, isEmpty);
  });

  testWidgets('installed, every other key passes through', (tester) async {
    E2eProbes.install();
    await tester.pumpWidget(const SizedBox());
    await _press(tester, LogicalKeyboardKey.f11);
    await _press(tester, LogicalKeyboardKey.enter);
    expect(backend.played, isEmpty);
  });

  testWidgets('the probe obeys the same rules as a tap', (tester) async {
    E2eProbes.install();
    await tester.pumpWidget(const SizedBox());
    await Haptics.setEnabled(false);
    await _press(tester, LogicalKeyboardKey.f12);
    await Haptics.setEnabled(true);
    SoundFx.childMode = true;
    await _press(tester, LogicalKeyboardKey.f12);
    expect(backend.played, isEmpty);
  });

  test('main.dart reaches the probe only behind the constant', () {
    final main = File('lib/main.dart').readAsStringSync();
    expect('E2eProbes.'.allMatches(main).length, 1);
    expect(main, contains('if (kE2eProbes) E2eProbes.installIfEnabled();'));
    final others = Directory('lib')
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))
        .where((f) => !f.path.endsWith('main.dart') &&
            !f.path.endsWith('e2e_probes.dart'))
        .where((f) => f.readAsStringSync().contains('e2e_probes.dart'))
        .map((f) => f.path)
        .toList();
    expect(others, isEmpty, reason: 'nothing else may import the probe');
  });

  test('no release workflow builds with the probe', () {
    for (final name in const [
      'release-play.yml',
      'build-release-unsigned.yml',
      'flutter.yml',
    ]) {
      final f = File('../.github/workflows/$name');
      expect(f.existsSync(), isTrue, reason: name);
      expect(f.readAsStringSync(), isNot(contains('E2E_PROBES')),
          reason: name);
    }
  });
}
