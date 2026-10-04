/// Putting the child's name back into memory text — on the device only.
///
/// The server never stores a child's name in memory (MOBILE_API §9.0): a fact
/// about the child it belongs to says «طفلي» (Arabic) or "my child"
/// (English), and a sibling mentioned in it is «الطفل أ», «الطفل ب»… by
/// profile order. The app may swap the names back in when it renders, so the
/// parent reads «أحمد يخاف من الظلام» rather than «طفلي يخاف من الظلام».
///
/// The swapped text is for display only. It must never be sent back as if the
/// parent had typed it — the edit sheet sends `fact` only when the parent
/// actually changed the words.
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

final RegExp _arChild = RegExp('طفلي(?![ء-ي])');
final RegExp _enChild = RegExp(r"\b[Mm]y child\b");

/// [text] with its placeholders replaced by names, for display.
///
/// [childName] replaces «طفلي» / "my child". [family], when given, resolves
/// «الطفل أ» and friends to the sibling holding that letter. Unknown letters
/// and a missing [childName] leave the placeholder as it is — a generic word
/// is better than a wrong name.
String renderMemoryText(
  String text, {
  String? childName,
  List<FamilyMember> family = const [],
}) {
  var out = text;
  if (family.length > 1) {
    final ordered = placeholderOrder(family);
    for (var i = 0; i < ordered.length && i < siblingLetters.length; i++) {
      final letter = siblingLetters[i];
      final name = ordered[i].name;
      // «للطفل ب» is ل + «الطفل ب» (the server writes it that way).
      out = out
          .replaceAll(RegExp('للطفل $letter(?![ء-ي])'), 'ل$name')
          .replaceAll(RegExp('الطفل $letter(?![ء-ي])'), name);
    }
  }
  final name = childName?.trim();
  if (name != null && name.isNotEmpty) {
    out = out.replaceAll(_arChild, name).replaceAll(_enChild, name);
  }
  return out;
}
