/// When does the narrator say a word? Read off a page manifest's sentence
/// ranges and timings — no forced alignment, no per-language indexes.
///
/// A cue is a list of words that name one thing, Arabic and English in one
/// list (`['فاطم', 'fatimah']`), matched against whatever text the page was
/// recorded from. The Arabic and English recordings split a page into
/// different sentence counts, so nothing here is keyed to a sentence number:
/// a word's moment is its sentence's start plus the sentence's duration in
/// proportion to where the word sits in it. An estimate — speech is not
/// perfectly even — good to a fraction of a second on a story page.
///
/// Matching: lower case, no harakat/tatweel, one alef, ى as ي; Arabic glued
/// prefixes (ال، و، ف، ب، ل، ك، لل) are tried off; a stem may carry one of a
/// closed list of endings («فاطمة», "toys") — so «هر» catches «هراً» and
/// «بالهر» but never «هرب». A word written `=word` matches exactly.
///
/// Missing or broken data means fewer cues, never an error.
library;

import 'story_narration.dart';

/// Target [target] is named [at] seconds into the page recording.
class WordCue {
  const WordCue(this.at, this.target);

  final double at;
  final int target;

  @override
  String toString() => 'WordCue($at, $target)';
}

/// Every moment one of [targets]' words is said in [text], in time order.
/// A target named twice within [minGap] seconds is cued once.
List<WordCue> wordCuesFor(
  List<List<String>> targets,
  String text,
  List<NarrationSentence> sentences, {
  double minGap = 1.2,
}) {
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
    for (final words in targets) [for (final w in words) normalizeCueWord(w)],
  ];
  final cues = <WordCue>[];
  final lastAt = <int, double>{};
  for (final token in _word.allMatches(text)) {
    final candidates = _candidates(normalizeCueWord(token.group(0)!)).toList();
    for (var i = 0; i < stems.length; i++) {
      if (!candidates.any((c) => stems[i].any((s) => _matches(c, s)))) {
        continue;
      }
      final at = _timeOf(token.start, timed);
      if (at == null) continue;
      final last = lastAt[i];
      if (last != null && at - last < minGap) continue;
      lastAt[i] = at;
      cues.add(WordCue(at, i));
    }
  }
  cues.sort((a, b) => a.at.compareTo(b.at));
  return cues;
}

final _word = RegExp(r'[\p{L}\p{M}]+', unicode: true);
final _harakat = RegExp('[\u064B-\u0652\u0670\u0640]');
final _alef = RegExp('[\u0623\u0625\u0622\u0671]');

String normalizeCueWord(String word) => word
    .toLowerCase()
    .replaceAll(_harakat, '')
    .replaceAll(_alef, 'ا')
    .replaceAll('\u0649', '\u064A');

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

const _endings = {
  'ا', 'ه', 'ها', 'ة', 'ات', 'ي', 'ك', 'هم', 'ين', 'ون', 'ته', 'تها', 'تي', //
  's', 'es',
};

bool _matches(String candidate, String stem) => stem.startsWith('=')
    ? candidate == stem.substring(1)
    : candidate == stem ||
          (candidate.startsWith(stem) &&
              _endings.contains(candidate.substring(stem.length)));

double? _timeOf(int c, List<NarrationSentence> sentences) {
  for (final s in sentences) {
    if (c >= s.from && c < s.to) {
      return s.start + (c - s.from) / (s.to - s.from) * (s.end - s.start);
    }
  }
  return null;
}
