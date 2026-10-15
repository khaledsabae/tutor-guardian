/// «اسمعها من نور» — a story read aloud, one recording per page, with the
/// sentence being read lit up on the page.
///
/// The recordings live next to the story art on the server:
///
///   `docs/stories/narration/{lang}/{story_id}.json` — the manifest
///   `docs/stories/narration/{lang}/{story_id}_p{N}.m4a` — one per page
///
/// written by tool/gen_story_narration.py. Every manifest page carries the
/// exact text it was recorded from, and the reader plays a page only when
/// that text is still the page's text: a story corrected after it was
/// recorded must fall silent on the corrected page rather than read the old
/// words over the new ones. Sentence highlighting uses the manifest's
/// character ranges, so the app never needs to split Arabic sentences itself.
///
/// No manifest (the default today — the voice is still Khaled's decision),
/// a network error, or a malformed file → `null`, and the reader simply has
/// no listen button. Narration is an addition to a story, never a condition.
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:just_audio/just_audio.dart';

import '../../../config/app_config.dart';

/// One sentence of a page: where it is in the text, and when it is heard.
class NarrationSentence {
  const NarrationSentence({
    required this.from,
    required this.to,
    required this.start,
    required this.end,
  });

  /// Character range in the page text, [from, to).
  final int from;
  final int to;

  /// Seconds into the page recording.
  final double start;
  final double end;
}

class NarrationPage {
  const NarrationPage({
    required this.audio,
    required this.text,
    required this.sentences,
  });

  /// Server path (`docs/…`) or absolute URL of the recording.
  final String audio;

  /// The text this recording reads, verbatim.
  final String text;
  final List<NarrationSentence> sentences;

  Uri get uri => audio.startsWith('http')
      ? Uri.parse(audio)
      : Uri.parse('${AppConfig.apiBaseUrl}/$audio');

  /// The sentence being heard at [position], or null between sentences.
  int? sentenceAt(Duration position) {
    final s = position.inMilliseconds / 1000;
    for (var i = 0; i < sentences.length; i++) {
      if (s >= sentences[i].start && s < sentences[i].end) return i;
    }
    return null;
  }
}

class StoryNarration {
  const StoryNarration({required this.pages, this.voice});

  final List<NarrationPage> pages;
  final String? voice;

  /// The recording for page [index] — only if it reads [text] exactly.
  NarrationPage? pageFor(int index, String text) {
    if (index < 0 || index >= pages.length) return null;
    final page = pages[index];
    return page.text == text ? page : null;
  }

  /// Whether at least one page of [pageTexts] can be heard.
  bool covers(List<String> pageTexts) {
    for (var i = 0; i < pageTexts.length; i++) {
      if (pageFor(i, pageTexts[i]) != null) return true;
    }
    return false;
  }

  static StoryNarration? tryParse(Object? json) {
    if (json is! Map || json['pages'] is! List) return null;
    final pages = <NarrationPage>[];
    for (final p in json['pages'] as List) {
      if (p is! Map || p['audio'] is! String || p['text'] is! String) {
        return null;
      }
      final text = p['text'] as String;
      final sentences = <NarrationSentence>[];
      for (final s in (p['sentences'] as List?) ?? const []) {
        if (s is! Map) return null;
        final from = s['from'],
            to = s['to'],
            start = s['start'],
            end = s['end'];
        if (from is! int || to is! int || start is! num || end is! num) {
          return null;
        }
        if (from < 0 || to > text.length || from >= to) return null;
        sentences.add(
          NarrationSentence(
            from: from,
            to: to,
            start: start.toDouble(),
            end: end.toDouble(),
          ),
        );
      }
      pages.add(
        NarrationPage(
          audio: p['audio'] as String,
          text: text,
          sentences: sentences,
        ),
      );
    }
    return StoryNarration(pages: pages, voice: json['voice'] as String?);
  }
}

/// Fetches a story's manifest. Injected into the reader so tests need no
/// network.
typedef NarrationLoader =
    Future<StoryNarration?> Function(String storyId, String language);

Future<StoryNarration?> loadNarration(
  String storyId,
  String language, {
  http.Client? client,
}) async {
  final uri = Uri.parse(
    '${AppConfig.apiBaseUrl}/docs/stories/narration/$language/$storyId.json',
  );
  try {
    final get = client?.get ?? http.get;
    final response = await get(uri).timeout(const Duration(seconds: 5));
    if (response.statusCode != 200) return null;
    return StoryNarration.tryParse(jsonDecode(utf8.decode(response.bodyBytes)));
  } catch (_) {
    return null;
  }
}

/// The few things the reader asks of an audio player.
abstract class NarrationPlayer {
  Stream<Duration> get position;

  /// Fires once each time a page recording plays to its end.
  Stream<void> get completed;

  Future<void> load(Uri uri);
  Future<void> play();
  Future<void> pause();
  Future<void> stop();
  Future<void> dispose();
}

typedef NarrationPlayerFactory = NarrationPlayer Function();

class JustAudioNarrationPlayer implements NarrationPlayer {
  final AudioPlayer _player = AudioPlayer();
  late final Stream<void> _completed = _player.processingStateStream
      .where((s) => s == ProcessingState.completed)
      .map((_) {})
      .asBroadcastStream();

  @override
  Stream<Duration> get position => _player.positionStream;

  @override
  Stream<void> get completed => _completed;

  @override
  Future<void> load(Uri uri) async {
    await _player.setAudioSource(AudioSource.uri(uri));
  }

  @override
  Future<void> play() async {
    unawaited(_player.play());
  }

  @override
  Future<void> pause() => _player.pause();

  @override
  Future<void> stop() => _player.stop();

  @override
  Future<void> dispose() => _player.dispose();
}
