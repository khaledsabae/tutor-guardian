/// The scene listens to the narrator: when the voice reaches a word a piece
/// stands for — «الهر», "the cat" — that piece hops, or walks in, and the
/// picture leans a little towards it at each new sentence.
///
/// The cue data is one list of words per piece, in every language at once
/// (`['هر', 'قط', 'cat', 'kitten']`), matched against whatever text the page
/// was recorded from. Nothing is keyed to a sentence number: the Arabic and
/// English recordings of a page split into different sentence counts (2 and
/// 3 on the same page is common), and a re-recorded page may split again.
/// What a manifest does guarantee is each sentence's character range and its
/// start and end in the audio; a word's moment is read off that, in
/// proportion to where the word sits in its sentence. That is an estimate —
/// speech is not perfectly even — good to a fraction of a second on a page
/// of story, which is what a hop needs.
///
/// Anything missing degrades to less motion, never to a broken page: no
/// recording, a page whose words a piece's list does not contain, a
/// malformed range → that piece simply has no cue.
library;

import 'package:flutter/foundation.dart';

import '../narration/story_narration.dart';
import 'story_scene.dart';

enum SceneBeatKind {
  /// The piece hops and swells — "this is the one being talked about".
  pop,

  /// The piece walks in: hidden until the narrator names it, while the
  /// narrator is reading. Only for a piece the story brings in (a visitor at
  /// the door, a mother coming closer).
  enter,

  /// The picture leans towards [SceneBeat.focus] — once per sentence.
  camera,
}

@immutable
class SceneBeat {
  const SceneBeat(this.at, this.kind, {this.layer = -1, this.focus = .5});

  /// Seconds into the page's recording.
  final double at;
  final SceneBeatKind kind;

  /// Index into the scene's layers (−1 for a camera beat).
  final int layer;

  /// For a camera beat: where to lean, 0 (left) … 1 (right).
  final double focus;

  @override
  String toString() => 'SceneBeat($at, $kind, layer: $layer, focus: $focus)';
}

/// What a scene needs to follow a narrator: its beats, and the clock they
/// are read against (the page recording's position).
@immutable
class SceneCues {
  const SceneCues({required this.beats, required this.clock});

  final List<SceneBeat> beats;
  final ValueListenable<Duration> clock;
}

/// A piece's cue words found in [text], timed against [sentences].
///
/// Beats come out sorted by time. A piece named twice in a breath hops once;
/// a piece marked [SceneLayer.entersOnCue] enters at its first mention and
/// hops at the later ones.
List<SceneBeat> beatsFor(
  StoryScene scene,
  String text,
  List<NarrationSentence> sentences,
) {
  final timed = [
    for (final s in sentences)
      if (s.from >= 0 &&
          s.to <= text.length &&
          s.from < s.to &&
          s.end > s.start)
        s,
  ];
  if (timed.isEmpty) return const [];

  final stems = [
    for (final layer in scene.layers)
      [for (final w in layer.cue) normalizeCueWord(w)],
  ];
  final beats = <SceneBeat>[];
  final lastAt = <int, double>{};
  for (final token in _word.allMatches(text)) {
    final candidates = _candidates(normalizeCueWord(token.group(0)!));
    for (var i = 0; i < stems.length; i++) {
      if (stems[i].isEmpty) continue;
      if (!candidates.any((c) => stems[i].any((s) => _matches(c, s)))) continue;
      final at = _timeOf(token.start, timed);
      if (at == null) continue;
      final last = lastAt[i];
      if (last != null && at - last < 1.2) continue;
      final first = last == null;
      lastAt[i] = at;
      beats.add(
        SceneBeat(
          at,
          first && scene.layers[i].entersOnCue
              ? SceneBeatKind.enter
              : SceneBeatKind.pop,
          layer: i,
        ),
      );
    }
  }

  // One gentle lean per sentence, towards the first piece it names — or,
  // when it names none, a small sway from side to side so the page still
  // breathes with the voice.
  for (var k = 0; k < timed.length; k++) {
    final s = timed[k];
    SceneBeat? named;
    for (final b in beats) {
      if (b.at >= s.start && b.at < s.end) {
        named = b;
        break;
      }
    }
    final focus = named == null
        ? (k.isEven ? .42 : .58)
        : scene.layers[named.layer].x.clamp(.2, .8).toDouble();
    beats.add(SceneBeat(s.start, SceneBeatKind.camera, focus: focus));
  }
  beats.sort((a, b) => a.at.compareTo(b.at));
  return beats;
}

final _word = RegExp(r'[\p{L}\p{M}]+', unicode: true);
final _harakat = RegExp('[\u064B-\u0652\u0670\u0640]');
final _alef = RegExp('[\u0623\u0625\u0622\u0671]');

/// Lower case, no harakat or tatweel, one alef, ى as ي — so «هِرّاً» and
/// «هرا» are one word, and «إخفاء» and «اخفاء».
String normalizeCueWord(String word) => word
    .toLowerCase()
    .replaceAll(_harakat, '')
    .replaceAll(_alef, 'ا')
    .replaceAll('\u0649', '\u064A');

/// The word, and the word without the prefixes Arabic glues on: «والهر»,
/// «بالهر», «للهر», «فأخفتها» all reach their stem.
Iterable<String> _candidates(String w) sync* {
  yield w;
  String? strip(String s, String p) =>
      s.startsWith(p) && s.length - p.length >= 2
      ? s.substring(p.length)
      : null;
  final noAl = strip(w, 'ال') ?? strip(w, 'لل');
  if (noAl != null) yield noAl;
  for (final p in const ['و', 'ف', 'ب', 'ل', 'ك']) {
    final r = strip(w, p);
    if (r == null) continue;
    yield r;
    final r2 = strip(r, 'ال');
    if (r2 != null) yield r2;
  }
}

/// Endings a cue stem may carry and still be the same thing: «هرا», «قطة»,
/// «مكعبات», «مدرسته», "cats", "boxes". A closed list on purpose — a prefix
/// match would let «هر» catch «هرب».
const _endings = {
  'ا', 'ه', 'ها', 'ة', 'ات', 'ي', 'ك', 'هم', 'ين', 'ون', 'ته', 'تها', 'تي', //
  's', 'es',
};

bool _matches(String candidate, String stem) =>
    candidate == stem ||
    (candidate.startsWith(stem) &&
        _endings.contains(candidate.substring(stem.length)));

/// When the voice reaches character [c]: its sentence's start, plus the
/// sentence's duration in proportion to how far into it [c] is.
double? _timeOf(int c, List<NarrationSentence> sentences) {
  for (final s in sentences) {
    if (c >= s.from && c < s.to) {
      final f = (c - s.from) / (s.to - s.from);
      return s.start + f * (s.end - s.start);
    }
  }
  return null;
}
