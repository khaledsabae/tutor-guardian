/// Putting the child's name back into memory text — on the device only — and
/// taking exactly those names out again before anything is sent.
///
/// The server never stores a child's name in memory (MOBILE_API §9.0): a fact
/// about the child it belongs to says «طفلي» (Arabic) or "my child"
/// (English), and a sibling mentioned in it is «الطفل أ», «الطفل ب»… by
/// profile order. The app swaps the names in when it renders, so the parent
/// reads «أحمد يخاف من الظلام» rather than «طفلي يخاف من الظلام».
///
/// What goes back must not carry those names (PR #36 review, item 2). The
/// server's redaction is a safety net with known gaps — a name that is also a
/// word («نور», «أمل») is the child only on positive evidence, so «أحمد يضرب
/// نور حين يغضب» would be stored with a sibling's real name and reach every
/// model prompt. So [RenderedMemoryText] remembers exactly where the app put
/// each name, and [RenderedMemoryText.restore] turns those very spans — where
/// they survive the parent's edit — back into the placeholder that was there.
/// Words the parent typed are left to the server; a «آية» that was already
/// in the text (آية الكرسي) is not a name the app inserted and is left alone.
library;

/// The letters the server assigns siblings, in profile order — the same
/// string as `_SIBLING_LETTERS` in backend/app/services/privacy.py.
const String siblingLetters = 'أبجدهوزحطيكلمن';

/// One child of the family as the server orders them for placeholders.
class FamilyMember {
  const FamilyMember({required this.id, required this.name});
  final int id;
  final String name;
}

/// The family in the server's placeholder order: by profile id, skipping
/// names shorter than two characters (the server does not redact those).
List<FamilyMember> placeholderOrder(Iterable<FamilyMember> children) {
  final named = [
    for (final c in children)
      if (c.name.trim().length >= 2) FamilyMember(id: c.id, name: c.name.trim()),
  ]..sort((a, b) => a.id.compareTo(b.id));
  return named;
}

/// One name the app put into a text: where (in the rendered text), and the
/// stored placeholder it stands for.
class NameInsertion {
  const NameInsertion(this.start, this.end, this.placeholder);
  final int start;
  final int end;
  final String placeholder;
}

/// A memory text as shown, with the record of what the app inserted.
class RenderedMemoryText {
  const RenderedMemoryText(this.stored, this.text, this.insertions);

  /// The text as the server stores it (placeholders).
  final String stored;

  /// The text as shown (names).
  final String text;
  final List<NameInsertion> insertions;

  /// What to send after the parent edited [text] into [edited]: every name
  /// the app inserted that is still there, in place, becomes its placeholder
  /// again. Nothing else is touched.
  ///
  /// The two texts are aligned word by word (letter runs, whitespace runs,
  /// single marks), not letter by letter: a name survives an edit only as a
  /// whole word, and a letter-level match could split it across neighbours
  /// («أحيانًا أحمد» shares «أح» twice). A word the parent changed — a letter
  /// glued on, a prefix removed — no longer matches, and is left as typed.
  String restore(String edited) {
    if (insertions.isEmpty) return edited;
    if (edited == text) return stored;
    final a = _tokens(text);
    final b = _tokens(edited);
    final map = _align(a, b);
    final replacements = <(int, int, String)>[];
    for (final ins in insertions) {
      final first = a.indexWhere((t) => t.end > ins.start);
      final last = a.lastIndexWhere((t) => t.start < ins.end);
      if (first < 0 || last < first) continue;
      final bFirst = map[first];
      if (bFirst == null) continue;
      var kept = true;
      for (var k = first; k <= last; k++) {
        if (map[k] != bFirst + (k - first)) {
          kept = false;
          break;
        }
      }
      if (!kept) continue;
      final s = b[bFirst].start + (ins.start - a[first].start);
      replacements.add((s, s + (ins.end - ins.start), ins.placeholder));
    }
    replacements.sort((x, y) => y.$1.compareTo(x.$1));
    var out = edited;
    for (final (s, e, placeholder) in replacements) {
      out = out.replaceRange(s, e, placeholder);
    }
    return out;
  }
}

/// One word, whitespace run or mark of a text, with where it sits.
class _Token {
  const _Token(this.start, this.end, this.value);
  final int start;
  final int end;
  final String value;
}

final RegExp _tokenPattern = RegExp(r'[\p{L}\p{M}]+|\s+|.', unicode: true);

List<_Token> _tokens(String t) => [
      for (final m in _tokenPattern.allMatches(t))
        _Token(m.start, m.end, m.group(0)!),
    ];

/// For each token of [a], the index of the token of [b] it was kept as, or
/// null: a longest common subsequence of whole tokens, which follows any
/// number of separate edits. A paste too long for that falls back to the
/// shared leading and trailing tokens.
List<int?> _align(List<_Token> a, List<_Token> b) {
  final n = a.length, m = b.length;
  final map = List<int?>.filled(n, null);
  if (n * m > 200000) {
    var p = 0;
    while (p < n && p < m && a[p].value == b[p].value) {
      map[p] = p;
      p++;
    }
    var q = 0;
    while (q < n - p && q < m - p && a[n - 1 - q].value == b[m - 1 - q].value) {
      map[n - 1 - q] = m - 1 - q;
      q++;
    }
    return map;
  }
  final dp = List.generate(n + 1, (_) => List<int>.filled(m + 1, 0));
  for (var i = n - 1; i >= 0; i--) {
    for (var j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i].value == b[j].value
          ? dp[i + 1][j + 1] + 1
          : (dp[i + 1][j] >= dp[i][j + 1] ? dp[i + 1][j] : dp[i][j + 1]);
    }
  }
  var i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i].value == b[j].value) {
      map[i] = j;
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      i++;
    } else {
      j++;
    }
  }
  return map;
}

/// [stored] with its placeholders replaced by names, for display — and the
/// record of every replacement, for [RenderedMemoryText.restore].
///
/// [childName] replaces «طفلي» / "my child". [family], when given, resolves
/// «الطفل أ» and friends to the sibling holding that letter. A letter that
/// resolves to the subject child itself ([subjectId]) — the letters are
/// positional, so deleting a sibling shifts them — is shown as «طفل آخر» /
/// "another child", never as the child's own name («عمر يغار من عمر»).
/// Unknown letters and a missing [childName] leave the placeholder as it is:
/// a generic word is better than a wrong name.
RenderedMemoryText renderMemory(
  String stored, {
  String? childName,
  List<FamilyMember> family = const [],
  int? subjectId,
  String lang = 'ar',
}) {
  final found = <(int, int, String)>[];
  if (family.length > 1) {
    final ordered = placeholderOrder(family);
    final english = lang.startsWith('en');
    for (var i = 0; i < ordered.length; i++) {
      // The server's labels: the 14 letters, then 15, 16… (sibling_placeholder).
      final label = RegExp.escape(
          i < siblingLetters.length ? siblingLetters[i] : '${i + 1}');
      final isSubject = subjectId != null && ordered[i].id == subjectId;
      // «الطفل ب» and, should the extraction have inflected it, «الطفلة ب».
      // Attached و/ف/ب/ك stay in the text before the name («ونور»،
      // «بنور»); «للطفل ب» is ل + «الطفل ب» and becomes «لنور».
      for (final feminine in const [false, true]) {
        final word = feminine ? 'طفلة' : 'طفل';
        final other = english
            ? 'another child'
            : (feminine ? 'طفلة أخرى' : 'طفل آخر');
        final name = isSubject ? other : ordered[i].name;
        for (final m in RegExp('لل$word $label(?![ء-ي0-9])').allMatches(stored)) {
          found.add((m.start, m.end, 'ل$name'));
        }
        for (final m in RegExp('ال$word $label(?![ء-ي0-9])').allMatches(stored)) {
          found.add((m.start, m.end, name));
        }
      }
    }
  }
  // «طفل آخر» / «طفلة أخرى» / "another child" — what the server writes for a
  // child no longer in the family (MOBILE_API §9.0) — are plain words: no
  // pattern above or below matches them, so they render exactly as written.
  final name = childName?.trim();
  if (name != null && name.isNotEmpty) {
    for (final m in _arChild.allMatches(stored)) {
      found.add((m.start, m.end, name));
    }
    for (final m in _enChild.allMatches(stored)) {
      found.add((m.start, m.end, name));
    }
  }
  found.sort((x, y) => x.$1.compareTo(y.$1));

  final out = StringBuffer();
  final insertions = <NameInsertion>[];
  var pos = 0;
  for (final (s, e, replacement) in found) {
    if (s < pos) continue; // overlaps one already taken
    out.write(stored.substring(pos, s));
    final start = out.length;
    out.write(replacement);
    insertions.add(NameInsertion(start, out.length, stored.substring(s, e)));
    pos = e;
  }
  out.write(stored.substring(pos));
  return RenderedMemoryText(stored, out.toString(), insertions);
}

final RegExp _arChild = RegExp('طفلي(?![ء-ي])');
final RegExp _enChild = RegExp(r"\b[Mm]y child\b");

/// [renderMemory]'s text alone, where nothing will be edited.
String renderMemoryText(
  String text, {
  String? childName,
  List<FamilyMember> family = const [],
  int? subjectId,
  String lang = 'ar',
}) =>
    renderMemory(text,
            childName: childName,
            family: family,
            subjectId: subjectId,
            lang: lang)
        .text;
