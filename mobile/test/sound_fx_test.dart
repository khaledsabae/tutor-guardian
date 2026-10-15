// Soft interface sounds («أصوات ناعمة بلا موسيقى»): who may hear them, which
// haptic carries which sound, what the files are, and that a broken player
// never reaches the person holding the phone. No test here needs a speaker.

import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/core/haptics.dart';
import 'package:almorabbi/core/sound_fx.dart';

class _FakeBackend implements SfxBackend {
  _FakeBackend({
    this.failPreload = false,
    this.failPlay = false,
    this.failPlaySync = false,
  });

  final bool failPreload;
  final bool failPlay;
  final bool failPlaySync;
  final played = <Sfx>[];
  List<Sfx>? preloaded;

  @override
  Future<void> preload(List<Sfx> sounds) async {
    if (failPreload) throw StateError('decoder exploded');
    preloaded = sounds;
  }

  @override
  Future<void> play(Sfx sound) {
    if (failPlaySync) throw StateError('player gone');
    played.add(sound);
    if (failPlay) return Future.error(PlatformException(code: 'boom'));
    return Future.value();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  final pulses = <String>[];

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
  });

  tearDown(() async {
    SoundFx.debugReset();
    await Haptics.setEnabled(true);
  });

  group('SoundPolicy', () {
    test('plays only with the switch on, outside child mode and screen-off',
        () {
      for (final switchOn in [true, false]) {
        for (final childMode in [true, false]) {
          for (final screenOff in [true, false]) {
            expect(
              SoundPolicy.allows(
                switchOn: switchOn,
                childMode: childMode,
                screenOff: screenOff,
              ),
              switchOn && !childMode && !screenOff,
              reason: 'switchOn=$switchOn childMode=$childMode '
                  'screenOff=$screenOff',
            );
          }
        }
      }
    });

    test('switch off → silent', () {
      expect(
        SoundPolicy.allows(switchOn: false, childMode: false, screenOff: false),
        isFalse,
      );
    });

    test('child mode → silent', () {
      expect(
        SoundPolicy.allows(switchOn: true, childMode: true, screenOff: false),
        isFalse,
      );
    });

    test('normal → plays', () {
      expect(
        SoundPolicy.allows(switchOn: true, childMode: false, screenOff: false),
        isTrue,
      );
    });
  });

  group('Haptics carries the sound', () {
    test('before init nothing plays, and the pulse still does', () async {
      await Haptics.selection();
      await Haptics.success();
      expect(pulses, hasLength(2));
    });

    test('init preloads all five, once', () async {
      final fake = _FakeBackend();
      await SoundFx.init(backend: fake);
      await SoundFx.init(backend: _FakeBackend()); // a second call is a no-op
      expect(fake.preloaded, Sfx.values);
    });

    test('selection → tick, success → water drop; warning and strong silent',
        () async {
      final fake = _FakeBackend();
      await SoundFx.init(backend: fake);

      await Haptics.selection();
      await Haptics.success();
      await Haptics.warning();
      await Haptics.strong();

      expect(fake.played, [Sfx.select, Sfx.success]);
      expect(pulses, hasLength(4), reason: 'every pulse still fires');
    });

    test('the tasbeeh keeps its vibration and stays quiet', () async {
      final fake = _FakeBackend();
      await SoundFx.init(backend: fake);
      await Haptics.selection(sound: false);
      expect(fake.played, isEmpty);
      expect(pulses, hasLength(1));
    });

    test('success(sound: false) keeps the pulse and drops the drop', () async {
      final fake = _FakeBackend();
      await SoundFx.init(backend: fake);

      await Haptics.success(sound: false);

      expect(fake.played, isEmpty);
      expect(pulses, hasLength(1));
    });

    test('the direct sounds play what they name', () async {
      final fake = _FakeBackend();
      await SoundFx.init(backend: fake);

      await SoundFx.tap();
      await SoundFx.lantern();
      await SoundFx.page();

      expect(fake.played, [Sfx.tap, Sfx.lantern, Sfx.page]);
    });
  });

  group('one switch', () {
    test('off silences sound and vibration together', () async {
      final fake = _FakeBackend();
      await SoundFx.init(backend: fake);

      await Haptics.setEnabled(false);
      await Haptics.selection();
      await Haptics.success();
      await SoundFx.tap(); // a direct call obeys the same switch

      expect(fake.played, isEmpty);
      expect(pulses, isEmpty);
    });

    test('an existing "haptics off" choice silences sound too', () async {
      // Same key as when the switch was vibration only.
      SharedPreferences.setMockInitialValues({'haptics_enabled': false});
      final fake = _FakeBackend();
      await SoundFx.init(backend: fake);

      await Haptics.load();
      expect(SoundFx.switchOn, isFalse);
      await Haptics.success();
      expect(fake.played, isEmpty);

      await Haptics.setEnabled(true);
      await Haptics.success();
      expect(fake.played, [Sfx.success]);
    });
  });

  group('muted contexts', () {
    test('child mode → silent, the vibration stays', () async {
      final fake = _FakeBackend();
      await SoundFx.init(backend: fake);

      SoundFx.childMode = true;
      await Haptics.success();
      await Haptics.selection();
      expect(fake.played, isEmpty);
      expect(pulses, hasLength(2));

      SoundFx.childMode = false;
      await Haptics.success();
      expect(fake.played, [Sfx.success]);
    });

    test('screen-off → silent until the last player closes', () async {
      final fake = _FakeBackend();
      await SoundFx.init(backend: fake);

      SoundFx.screenOffBegan();
      SoundFx.screenOffBegan();
      SoundFx.screenOffEnded();
      await SoundFx.success();
      expect(fake.played, isEmpty, reason: 'one player is still open');

      SoundFx.screenOffEnded();
      SoundFx.screenOffEnded(); // an extra close does not go below zero
      await SoundFx.success();
      expect(fake.played, [Sfx.success]);

      SoundFx.screenOffBegan();
      await SoundFx.success();
      expect(fake.played, [Sfx.success]);
    });
  });

  group('a failing player never surfaces', () {
    test('preload fails → init completes, every call is a no-op', () async {
      final fake = _FakeBackend(failPreload: true);
      await expectLater(SoundFx.init(backend: fake), completes);

      await expectLater(SoundFx.success(), completes);
      await expectLater(Haptics.selection(), completes);
      expect(fake.played, isEmpty);
      expect(pulses, hasLength(1), reason: 'the vibration is unaffected');
    });

    test('play fails asynchronously → no throw', () async {
      final fake = _FakeBackend(failPlay: true);
      await SoundFx.init(backend: fake);

      await expectLater(SoundFx.success(), completes);
      await expectLater(Haptics.success(), completes);
      expect(fake.played, [Sfx.success, Sfx.success]);
    });

    test('play throws synchronously → no throw', () async {
      await SoundFx.init(backend: _FakeBackend(failPlaySync: true));

      await expectLater(SoundFx.tap(), completes);
      await expectLater(Haptics.selection(), completes);
    });

    test('the real backend with a broken plugin: no throw, and no focus asked',
        () async {
      const methods = MethodChannel('xyz.luan/audioplayers');
      const global = MethodChannel('xyz.luan/audioplayers.global');
      final contexts = <Map<Object?, Object?>>[];
      final modes = <Object?>[];
      final resumed = <Object?>[];
      messenger.setMockMethodCallHandler(global, (call) async => null);
      messenger.setMockStreamHandler(
        const EventChannel('xyz.luan/audioplayers.global/events'),
        MockStreamHandler.inline(onListen: (_, _) {}),
      );
      for (final s in Sfx.values) {
        messenger.setMockStreamHandler(
          EventChannel('xyz.luan/audioplayers/events/sfx_${s.name}'),
          MockStreamHandler.inline(onListen: (_, _) {}),
        );
      }
      messenger.setMockMethodCallHandler(methods, (call) async {
        final args = call.arguments as Map<Object?, Object?>;
        switch (call.method) {
          case 'setAudioContext':
            contexts.add(args);
          case 'setPlayerMode':
            modes.add(args['playerMode']);
          case 'resume':
            resumed.add(args['playerId']);
          case 'setSourceUrl':
            throw PlatformException(code: 'AndroidAudioError');
        }
        return null;
      });
      addTearDown(() {
        messenger.setMockMethodCallHandler(methods, null);
        messenger.setMockMethodCallHandler(global, null);
      });

      await expectLater(
        SoundFx.init(backend: AudioplayersSfxBackend()),
        completes,
      );
      await expectLater(SoundFx.success(), completes);
      expect(resumed, isEmpty, reason: 'nothing loaded, nothing played');

      // What reached the platform for each player: no focus request, a
      // sonification stream, low-latency mode.
      expect(contexts, hasLength(Sfx.values.length));
      for (final c in contexts) {
        expect(c['audioFocus'], AndroidAudioFocus.none.value);
        expect(c['usageType'], AndroidUsageType.assistanceSonification.value);
        expect(c['contentType'], AndroidContentType.sonification.value);
      }
      expect(modes, everyElement(PlayerMode.lowLatency.toString()));
    });
  });

  group('the audio context', () {
    test('asks for no focus and is UI sonification, not media', () {
      final android = AudioplayersSfxBackend.audioContext.android;
      expect(android.audioFocus, AndroidAudioFocus.none);
      expect(android.usageType, AndroidUsageType.assistanceSonification);
      expect(android.contentType, AndroidContentType.sonification);
      expect(android.stayAwake, isFalse);
    });

    test('sound effects never go through just_audio', () {
      final src = File('lib/core/sound_fx.dart').readAsStringSync();
      expect(src.contains("import 'package:just_audio"), isFalse,
          reason: 'just_audio owns audio focus for recitation');
    });
  });

  group('the files', () {
    // ops/tools/gen_sfx.py writes them; these are the limits it promises.
    const maxBytes = 30 * 1024;
    const maxMs = 400;
    final maxPeak = (32767 * math.pow(10, -12 / 20)).floor(); // −12 dBFS

    for (final s in Sfx.values) {
      test('${s.name}.wav: exists, ≤ 30 KB, mono 22.05 kHz, ≤ 400 ms, '
          '≤ −12 dBFS, silent at both ends', () {
        final file = File('assets/${s.asset}');
        expect(file.existsSync(), isTrue, reason: file.path);
        final bytes = file.readAsBytesSync();
        expect(bytes.length, lessThanOrEqualTo(maxBytes));

        final wav = _Wav.parse(bytes);
        expect(wav.format, 1, reason: 'PCM');
        expect(wav.channels, 1);
        expect(wav.sampleRate, 22050);
        expect(wav.bitsPerSample, 16);
        expect(wav.samples.length * 1000 / wav.sampleRate,
            lessThanOrEqualTo(maxMs));
        final peak = wav.samples.fold<int>(0, (m, v) => math.max(m, v.abs()));
        expect(peak, lessThanOrEqualTo(maxPeak));
        expect(wav.samples.first, 0, reason: 'fade-in: no click');
        expect(wav.samples.last, 0, reason: 'fade-out: no click');
      });
    }

    test('all five are in the app bundle (pubspec lists assets/audio/sfx/)',
        () async {
      for (final s in Sfx.values) {
        final data = await rootBundle.load('assets/${s.asset}');
        expect(data.lengthInBytes, greaterThan(44), reason: s.name);
      }
    });
  });
}

/// Just enough RIFF/WAVE to check what gen_sfx.py promises.
class _Wav {
  _Wav(this.format, this.channels, this.sampleRate, this.bitsPerSample,
      this.samples);

  final int format;
  final int channels;
  final int sampleRate;
  final int bitsPerSample;
  final Int16List samples;

  static _Wav parse(Uint8List bytes) {
    final data = ByteData.sublistView(bytes);
    String tag(int at) => String.fromCharCodes(bytes.sublist(at, at + 4));
    if (tag(0) != 'RIFF' || tag(8) != 'WAVE') {
      throw const FormatException('not a RIFF/WAVE file');
    }
    int? format, channels, rate, bits;
    Int16List? samples;
    var at = 12;
    while (at + 8 <= bytes.length) {
      final id = tag(at);
      final size = data.getUint32(at + 4, Endian.little);
      final body = at + 8;
      if (id == 'fmt ') {
        format = data.getUint16(body, Endian.little);
        channels = data.getUint16(body + 2, Endian.little);
        rate = data.getUint32(body + 4, Endian.little);
        bits = data.getUint16(body + 14, Endian.little);
      } else if (id == 'data') {
        samples = Int16List(size ~/ 2);
        for (var i = 0; i < samples.length; i++) {
          samples[i] = data.getInt16(body + 2 * i, Endian.little);
        }
      }
      at = body + size + (size.isOdd ? 1 : 0);
    }
    if (format == null || samples == null) {
      throw const FormatException('missing fmt or data chunk');
    }
    return _Wav(format, channels!, rate!, bits!, samples);
  }
}
