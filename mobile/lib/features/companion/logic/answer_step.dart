/// «سأجرّبها مع …» — the one step a parent can promise from an answer
/// (NOOR_WAL_QANADIL_PLAN, phase 4, «المساعد»).
///
/// The assistant answers in a fixed shape (llm_service.py, the "rich" and
/// "compact" prompts): a sentence or two that answers the question, then
/// numbered practical steps, sometimes a «متى تراجع متخصصاً» paragraph, and
/// a closing «📚 المصادر» line. The actionable part is the step list, so the
/// promise is the first sentence of its first usable item — the label and
/// the sentence that follows it, the way the parent read them — cut to what
/// the server accepts.
///
/// No list, a list that is only sources or warning signs, or an item that
/// does not read as a step → null, and the chat shows no chip: a promise
/// built from a fragment would be read back to the parent days later.
///
/// Pure Dart on purpose: the extractor is run over real answers outside
/// Flutter, and the widget tests pin the chip, not the parsing.
library;

/// The server's ceiling for a promise's step: `open_promise_followup` refuses
/// a cleaned text longer than 120 characters.
const int kPromiseStepMax = 120;

/// How many list items are tried before the answer is judged to have no step.
const int _maxItemsTried = 3;

// «1. », «١) », «2- » — and «- », «* », «• » bullets.
final RegExp _listItem = RegExp(
  r'^(\s*)(?:(?:\d{1,2}|[٠-٩]{1,2})\s*[.)\-–]|[-*•+])\s+(.+)$',
);

// «**التواصل والتفهم**: …», «**توضيح الأهمية:** …», «__label__ …».
final RegExp _boldLabel = RegExp(r'^(?:\*\*|__)(.+?)(?:\*\*|__)\s*[:：]?\s*(.*)$');

// Citations the answer carries inline: 【2】, [1], [1، 3], (مرجع 2).
final RegExp _citation = RegExp(
  r'【[^】]*】|\[\d+(?:\s*[,،]\s*\d+)*\]|\(\s*(?:ال)?(?:مرجع|مصدر)\s*\d+\s*\)',
);

final RegExp _mdLink = RegExp(r'\[([^\]]+)\]\([^)]*\)');

// «أولًا، » — the ordinal a step sometimes opens with; it means nothing once
// the step stands alone.
final RegExp _ordinal = RegExp(
  r'^(?:أولاً|أولًا|أولا|ثانيًا|ثانياً|ثانيا|ثالثًا|ثالثاً|ثالثا|رابعًا|رابعاً|'
  r'رابعا|خامسًا|خامساً|خامسا|أخيرًا|أخيراً|أخيرا|'
  r'first(?:ly)?|second(?:ly)?|third(?:ly)?|finally)\s*[،,:]\s*',
  caseSensitive: false,
);

// The parts of an answer that are not steps: the sources and the referral.
final RegExp _stopHeading = RegExp(
  r'المصادر|المصدر|المراجع|متى (?:تراجع|تستشير|تطلب)|مراجعة (?:ال)?متخصص|'
  r'sources?\b|references?\b|when to (?:see|seek|consult)',
  caseSensitive: false,
);

// Referrals and talk about the sources — real advice, but not a step to
// try with the child: the server's memory refuses the medical ones anyway.
final RegExp _notAStep = RegExp(
  r'طبيب|أخصائي|اختصاصي|متخصص|استشر|مصدر|مصادر|مرجع|مراجع|'
  r'doctor|pediatrician|paediatrician|specialist|therapist|psycholog|'
  r'\bsources?\b|\breferences?\b',
  caseSensitive: false,
);

// A sentence that opens with a condition: «إذا …، …» / "If …, …".
final RegExp _conditional = RegExp(
  r'^(?:و|ف)?(?:إذا|إن|لو|عندما|حين|حينما|متى|كلما)\s|^(?:if|when|whenever)\b',
  caseSensitive: false,
);

final RegExp _numberLabel = RegExp(
  r'^(?:ال)?خطوة(?:\s+رقم)?\s*[\d٠-٩]+$|^step\s*\d+$',
  caseSensitive: false,
);

final RegExp _url = RegExp(r'https?://|www\.|\S+@\S+\.\w+', caseSensitive: false);
final RegExp _phone = RegExp(r'\d[\d\s\-]{6,}\d');
final RegExp _letter = RegExp(r'\p{L}', unicode: true);
final RegExp _leadingNoise = RegExp(r'^[^\p{L}\p{N}«"“(]+', unicode: true);

/// The first sentence of the answer's first usable step, at most
/// [kPromiseStepMax] characters — or null when there is none.
String? promiseStepFromAnswer(String answer) {
  final lines = answer.replaceAll('\r', '').split('\n');
  var tried = 0;
  for (var i = 0; i < lines.length; i++) {
    final line = lines[i];
    if (line.trim().isEmpty) continue;
    if (line.replaceFirst(RegExp(r'^[\s>*_#\-]+'), '').startsWith('📚')) break;
    final plain = _unmark(line);
    if (_isHeading(line) && _stopHeading.hasMatch(plain)) break;
    final item = _listItem.firstMatch(line);
    // The direct answer, a heading, prose — unless the prose is itself a
    // list in words («أولًا، …»), which older answers write.
    final content = item?.group(2)!.trim() ??
        (_ordinal.hasMatch(plain) ? plain : null);
    if (content == null) continue;
    if (++tried > _maxItemsTried) break;

    var label = '';
    var body = content;
    final bold = _boldLabel.firstMatch(content);
    if (bold != null) {
      label = _unmark(bold.group(1)!).replaceAll(RegExp(r'[:：]\s*$'), '').trim();
      body = bold.group(2)!.trim();
      // «**الخطوة 1:**» numbers the step; it says nothing on its own.
      if (_numberLabel.hasMatch(label)) label = '';
    }
    if (body.isEmpty) {
      // A label with its detail underneath: the detail is the step. A
      // sub-item is reached by this loop; a plain continuation is taken here.
      final next = _nextNonEmpty(lines, i + 1);
      if (next != null && _listItem.hasMatch(lines[next])) {
        tried--; // the label was not a try; its first sub-item is
        continue;
      }
      if (next != null && !_isHeading(lines[next])) {
        body = lines[next].trim();
      }
    }
    body = _firstSentence(_unmark(body).replaceFirst(_ordinal, ''))
        .replaceFirst(RegExp(r'[.。\s]+$'), '');
    final whole = label.isEmpty
        ? body
        : (body.isEmpty ? label : '$label: $body');
    // The label and its first sentence, as the parent read them; the
    // sentence alone when both do not fit; cut only when neither does.
    final String sentence;
    if (whole.length <= kPromiseStepMax) {
      sentence = whole;
    } else if (label.isNotEmpty && body.length <= kPromiseStepMax) {
      sentence = body;
    } else if (_conditional.hasMatch(body.isEmpty ? label : body)) {
      // A condition cut away from what to do about it reads as a warning
      // sign («إذا لاحظت نوبات غضب متكررة») — skip rather than promise it.
      continue;
    } else {
      sentence = trimStep(whole);
    }
    // «راجع الطبيب …» and «حسب المصدر الأول …» are real advice, but not
    // something to try with a child tonight; the next item may be.
    if (_notAStep.hasMatch(sentence)) continue;
    final step = _usable(trimStep(sentence));
    if (step != null) return step;
  }
  return null;
}

/// [s] cut to [max] characters where it still reads whole: at the last
/// clause break past the first third, else at a word with «…». A clause
/// break that would leave a condition without its consequence («هذا
/// الأسبوع: حين يصدق طفلك في أمرٍ صعب») is not whole: the word cut and its
/// «…» say that something follows.
String trimStep(String s, {int max = kPromiseStepMax}) {
  var out = s.trim();
  if (out.length > max) {
    final head = out.substring(0, max);
    var cut = -1;
    for (final sep in const ['،', ',', '؛', ';', ' — ', ' - ', ':']) {
      final at = head.lastIndexOf(sep);
      if (at > cut) cut = at;
    }
    final kept = cut < 0 ? '' : out.substring(0, cut);
    final lastClause = kept.split(RegExp(r'[:،,؛;—]')).last.trim();
    if (cut >= max ~/ 3 && !_conditional.hasMatch(lastClause)) {
      out = kept.trimRight();
    } else {
      final space = out.lastIndexOf(' ', max - 1);
      out = space >= max ~/ 3
          ? '${out.substring(0, space).trimRight()}…'
          : '${out.substring(0, max - 1).trimRight()}…';
    }
  }
  // A quotation the cut left open reads as a mistake: drop the marks.
  if (_unbalanced(out)) out = out.replaceAll(RegExp('[«»“”"]'), '');
  return out;
}

String? _usable(String s) {
  var t = s.trim().replaceFirst(RegExp(r'[.。\s]+$'), '');
  if (t.endsWith(':') || t.endsWith('：')) return null; // a lead-in, not a step
  if (t.startsWith('هل ') || t.toLowerCase().startsWith('is ')) {
    return null; // a question to ask oneself — a warning sign, not a step
  }
  if (t.length < 10 || t.split(RegExp(r'\s+')).length < 3) return null;
  if (!_letter.hasMatch(t)) return null;
  if (_url.hasMatch(t) || _phone.hasMatch(t)) return null; // refused anyway
  t = t.trim();
  return t.length <= kPromiseStepMax ? t : null;
}

/// Up to and including the first sentence end that is not inside quotes.
String _firstSentence(String text) {
  var guillemets = 0, curly = 0;
  var straight = false;
  for (var i = 0; i < text.length; i++) {
    final c = text[i];
    switch (c) {
      case '«':
        guillemets++;
      case '»':
        if (guillemets > 0) guillemets--;
      case '“':
        curly++;
      case '”':
        if (curly > 0) curly--;
      case '"':
        straight = !straight;
      case '.' || '!' || '؟' || '?' || '…':
        final quoted = guillemets > 0 || curly > 0 || straight;
        final atEnd = i + 1 >= text.length || RegExp(r'\s').hasMatch(text[i + 1]);
        if (!quoted && atEnd) return text.substring(0, i + 1).trim();
    }
  }
  return text.trim();
}

bool _unbalanced(String s) {
  int count(String c) => c.allMatches(s).length;
  return count('«') != count('»') ||
      count('“') != count('”') ||
      count('"').isOdd;
}

bool _isHeading(String line) {
  final t = line.trim();
  if (t.startsWith('#')) return true;
  // A line that is bold from end to end: «**خطوات عملية:**».
  if (RegExp(r'^(\*\*|__)[^*_]+(\*\*|__)\s*[:：]?$').hasMatch(t)) return true;
  // A short line that introduces what follows: «المصادر:».
  return !_listItem.hasMatch(line) &&
      RegExp(r'[:：]$').hasMatch(t) &&
      t.split(RegExp(r'\s+')).length <= 5;
}

int? _nextNonEmpty(List<String> lines, int from) {
  for (var j = from; j < lines.length; j++) {
    if (lines[j].trim().isNotEmpty) return j;
  }
  return null;
}

/// Markdown and citation marks out, one line, single spaces.
String _unmark(String s) {
  var t = s
      .replaceAllMapped(_mdLink, (m) => m.group(1)!)
      .replaceAll(_citation, '')
      .replaceAll(RegExp(r'\*\*|__|`|\*'), '')
      .replaceFirst(RegExp(r'^\s*#+\s*'), '')
      .replaceFirst(RegExp(r'^\s*>\s*'), '');
  t = t.replaceAll(RegExp(r'\s+'), ' ').trim();
  t = t.replaceFirst(_leadingNoise, '');
  // A citation removed before a mark leaves «كلمة .» — close the gap.
  return t.replaceAllMapped(RegExp(r'\s+([.،,؛;:!؟?])'), (m) => m.group(1)!);
}
