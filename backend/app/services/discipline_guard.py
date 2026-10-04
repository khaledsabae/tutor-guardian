"""Physical discipline — «المربّي» never instructs it. High precision, by design.

Until 2026-10-04 a parent asking «هل أضرب ابني لأنه لا يصلي؟» reached the model,
and two knowledge units retrieval could hand it said «يمكن ضرب الأطفال على ترك
الصلاة بعد سن العاشرة». The units are fixed; this guard answers only the
clearest cases with a fixed, reviewed reply. It is deliberately NARROW: real
volume is low (12 hits in 4,295 real questions) and a wrong canned reply does
real harm — a mother asking about her son hitting his sister must not be told
"we never recommend hitting". Everything this guard does not claim goes to the
model, whose system prompt carries the same no-hitting policy (llm_service.py).

What it claims (backend/tests/test_discipline_guard.py pins all of it, including
the 95-row review table):

* ``question`` — an explicit permission or ruling question with the PARENT as
  subject and the CHILD as object («هل أضرب ابني…»، «ينفع أضرب ولادي؟»،
  «أعاقبه بالضرب؟», "can I spank my son"), or a noun-only ruling question about
  hitting children («ما حكم ضرب الأولاد…»، «هل الضرب حلال في التربية»). The
  ruling goes to trusted scholars; the app's non-physical alternatives follow.
* ``regret`` — an explicit first-person confession: «ضربت ابني…» with no subject
  noun before it, «بضرب ابني», «أول مرة أضرب ابني», "I slapped my son". Repair.
* ``abuse`` — an ADULT subject (gender-matched verb), a CHILD object, AND a
  severity tied to the body or an instrument: belt, stick, blood, injury, marks
  on the body, the head or face, fainting. Only this shows the emergency
  escalation. «كل يوم»، «جامد»، «كسر الكوباية»، «علامات وحشة» are not severity.
* ``self_worry`` — a parent afraid of hurting their child («أخاف أؤذي طفلي لما
  أضربه»): support. The router checks this before the banned-intent pairs,
  which would otherwise answer it with a refusal.

What it never claims: a child hitting anyone (sibling, classmate, parent);
«ضرب الطفل لأخيه»، «ضرب الأطفال لبعضهم» and the app's own challenge label «ضرب
الطفل»; «أضرب لابني مثلًا»; a child hit by someone else without bodily
severity; times tables, sunstroke, heartbeats; English idioms ("beat myself
up", "hit the roof", "hit snooze", "beat traffic", "hit pause"); French — the
model answers the parent in their own language.
"""
from __future__ import annotations

import re

# ── Arabic normalisation (ة is kept: «ضربة شمس» must not read as «ضربه») ────
_MARKS = re.compile(r"[ً-ٰٟـ]")
_CLAUSE = re.compile(r"[.!?؟،,;:\n…]+")
_PUNCT = re.compile(r"[«»\"'“”()\[\]{}<>!?؟.,،;:…\-–—]")


def _norm(text: str) -> str:
    t = _MARKS.sub("", text or "")
    for a in ("آ", "أ", "إ", "ٱ"):
        t = t.replace(a, "ا")
    return t.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")


def _clauses(text: str) -> list[list[str]]:
    out = []
    for c in _CLAUSE.split(_norm(text)):
        toks = [t for t in (_PUNCT.sub("", w) for w in c.split()) if t]
        if toks:
            out.append(toks)
    return out


def _w(tok: str) -> str:
    """The token without a leading conjunction و/ف."""
    return tok[1:] if len(tok) > 3 and tok[0] in "وف" else tok


def _in(tok: str, words: set) -> bool:
    """Set membership for the token as written or without a leading و/ف — «ولادي» is
    a word of its own, «وابني» is و + ابني; both must be recognised."""
    return tok in words or _w(tok) in words


def _m(pattern: "re.Pattern[str]", tok: str):
    return pattern.match(tok) or pattern.match(_w(tok))


# The child, as a whole word — «لابني» ("to my son") is not this.
_CHILD = {
    "ابني", "ابنتي", "بنتي", "ولدي", "طفلي", "طفلتي", "اولادي", "ولادي", "اطفالي", "عيالي", "ابنائي",
    "بناتي", "الطفل", "الطفلة", "الاطفال", "الولد", "الولاد", "الواد", "البنت", "البنات", "الابن", "الابناء",
    "الاولاد", "الصغار", "العيال", "ابنه", "ابنها", "ابنهم", "طفله", "طفلها", "الصبي", "الصبيان", "اطفالنا",
    "اولادنا", "ابنائنا", "ولادنا", "عيالنا", "ابننا", "بنتنا", "طفلنا", "صغيري", "صغيرتي", "ولاده",
    "ولادها", "اولاده", "اولادها",
}


def _is_child(tok: str) -> bool:
    return _in(tok, _CHILD)


_FILLERS = {"انا", "اليوم", "النهارده", "النهاردة", "انهارده", "امبارح", "امس", "للاسف", "والله", "بصراحه",
            "بصراحة", "قبل", "شويه", "شوية", "من", "مره", "مرة", "اول", "لاول", "اخر", "الصبح", "بالليل",
            "وبعدين", "بعدين", "فجاه", "فجأة", "غصب", "عني"}
_NEG = {"مش", "ما", "لا", "لم", "لن", "عمري", "ابدا", "مبقتش", "مابقتش", "بلاش", "ميصحش", "مايصحش"}
_FEM_SUBJECT = {"بنتي", "ابنتي", "البنت", "طفلتي", "الطفلة", "مراتي", "زوجتي", "امي", "امه", "امها", "المعلمة",
                "المعلمه", "الدادة", "الداده", "اختي", "اخته", "اختها", "حماتي", "جدته", "جدتها", "الخادمة",
                "الخادمه", "المربية", "المربيه", "هي"}

# «ضرب المثل»، «جدول الضرب»، «ضرب الأرقام»… — not hitting at all.
_NOT_AFTER = {"مثل", "مثلا", "مثال", "امثال", "امثله", "امثلة", "الامثال", "المثل", "موعد", "موعدا", "شمس",
              "عرض", "اخماس", "الارقام", "الاعداد", "ارقام", "اعداد"}
_NOT_BEFORE = {"جدول", "عمليه", "عملية"}

_P1_IMPF = re.compile(r"^(?:اضرب|بضرب|هضرب|حضرب|ساضرب|نضرب|بنضرب|هنضرب|سنضرب)(?:هما|هم|ها|ه)?$")
_P1_PAST = re.compile(r"^ضربت(?:هما|هم|ها|ه|و)?$")
_M3 = re.compile(r"^(?:يضرب|بيضرب|هيضرب|ضرب)(?:هما|هم|ها|ه)?$")
_F3 = re.compile(r"^(?:تضرب|بتضرب|هتضرب|ضربت)(?:هما|هم|ها|ه)?$")
_AUX = {"كان", "كانت", "دايما", "دائما", "بقي", "بقت", "قعد", "قعدت", "عمال", "عماله"}
_NOUN = re.compile(r"^(?:ال|بال|ب|لل)?ضرب(?:ه|ها|هم)?$")
_PASSIVE = re.compile(r"^(?:اتضرب|بيتضرب|انضرب|اتضربت|بتتضرب|انضربت)$")
_PUNISH = re.compile(r"^(?:اعاقب|نعاقب|اادب|نادب|اربي)(?:هما|هم|ها|ه)?$")
_OBJ = re.compile(r"(?:ضرب|ضربت|عاقب|ادب|ربي)(?:هما|هم|ها|ه|و)$")
_AGENT = re.compile(r"^ل(?:ل)?(?:اخ|اخو|اخي|اخت|بعض|اخرين|زميل|زملا|زماي|اصحاب|اصدقا|صحاب|صاحب|غير|ولاد|اولاد|"
                    r"اطفال|طفل|عيال|بنات|كبار|صغار|ناس|الناس)")

_ADULT_M = {"زوجي", "جوزي", "ابوه", "ابوها", "ابوهم", "والده", "والدها", "والدهم", "جده", "جدها", "جدهم", "ابويا",
            "ابي", "المدرس", "المعلم", "الاستاذ", "الشيخ", "المحفظ", "المدير", "خاله", "خالها", "عمه", "عمها",
            "الحارس", "المدرب", "السواق"}
_ADULT_F = {"زوجتي", "مراتي", "امه", "امها", "امهم", "والدته", "والدتها", "جدته", "جدتها", "امي", "المعلمة",
            "المعلمه", "الاستاذة", "الاستاذه", "الدادة", "الداده", "الدادا", "المربية", "المربيه", "الخادمة",
            "الخادمه", "الشغالة", "الشغاله", "خالته", "عمته", "المدربة", "المدربه"}

_ASK = {"هل", "ينفع", "يجوز", "يصح", "ممكن", "مسموح", "اقدر", "استطيع", "لازم", "المفروض", "متي", "امتي",
        "حرام", "حلال", "صح", "الصح", "رايك", "حكم", "مباح"}
_RULING = {"حكم", "راي", "رايك", "الشرع", "الاسلام", "الدين", "حلال", "حرام", "يجوز", "جواز", "مباح", "مشروع",
           "مسموح", "هل", "ينفع", "يصح"}
_PERMIT = {"يجوز", "جواز", "ينفع", "يصح", "ممكن", "مسموح", "حكم", "حلال", "حرام", "مباح"}
_UPBRINGING = {"التربية", "التربيه", "تربوية", "تربويه", "تربوي", "للتربية", "للتربيه", "التاديب", "للتاديب",
               "تاديب", "وسيلة", "وسيله", "كوسيلة", "كوسيله", "للاولاد", "للاطفال", "الابناء"}
_REMORSE = re.compile(r"ندمت|ندمان|بذنب|ذنب|ضميري|زعلان من نفسي|زعلانه من نفسي|زعلانة من نفسي|اعتذر")
_WORRY = re.compile(
    r"(?:اخاف|خايف|خايفه|خايفة|اخشي|قلقان|قلقانه|قلقانة|مرعوب|مرعوبه|مش عايز|مش عايزه|مش عايزة|لا اريد|ما بدي)"
    r"\s+(?:ان\s+|اني\s+)?(?:اوذي|اذي|اوذيه|اوذيها|اذيه|اذيها|اضر|اضربه|اضربها|اضرب|افقد اعصابي)(?![ء-ي])")

# Severity tied to the body or an instrument (normalised Arabic).
_INSTR = re.compile(r"(?<![ء-ي])(?:بال|ب)(?:حزام|عصا|عصايه|عصاية|عصايا|خرطوم|شبشب|سلك|كرباج|سوط|خشبه|خشبة|"
                    r"مسطره|مسطرة|جزمه|جزمة|حديده|حديدة|كابل|شماعه|شماعة)(?![ء-ي])")
_BODY = re.compile(
    r"(?<![ء-ي])(?:نزف|ينزف|بينزف|نزيف|دم|الدم|بالدم|دمه|دمها|كدمات|كدمه|كدمة|جرح|جروح|اتعور|اتعورت|انجرح|"
    r"انجرحت|اغمي|اغمى|غيبوبه|غيبوبة)(?![ء-ي])"
    r"|فقد(?:ت)?\s+(?:ال)?وعي|غاب(?:ت)?\s+عن\s+(?:ال)?وعي|(?<![ء-ي])(?:ال)?مستشفي(?![ء-ي])"
    r"|(?:كسر|كسرت|انكسرت|انكسر|اتكسرت|اتكسر)\s+(?:ايده|ايدها|يده|يدها|رجله|رجلها|سنه|سنانه|سنها|انفه|انفها|"
    r"ضلعه|ضلعها|دراعه|دراعها|ذراعه|ذراعها|صباعه|صباعها)(?![ء-ي])"
    r"|(?:علامات|علامة|علامه|اثار|اثر|ازرقاق|تورم|ورم|احمرار)\s+(?:علي|في)\s+(?:جسمه|جسمها|جسده|جسدها|ظهره|"
    r"ظهرها|ضهره|ضهرها|رجليه|رجليها|رجله|رجلها|ايده|ايدها|ايديه|وشه|وشها|وجهه|وجهها|جلده|جلدها)(?![ء-ي])"
    r"|(?:علي|في)\s+(?:وجهه|وجهها|وشه|وشها|راسه|راسها|دماغه|دماغها|ودنه|ودنها|عينه|عينها)(?![ء-ي])")


def _child_object(toks: list[str], i: int) -> bool:
    """The verb at i takes the child as object: a pronoun suffix, or a child noun right after it."""
    return bool(_OBJ.search(toks[i])) or any(_is_child(t) for t in toks[i + 1:i + 3])


def _not_hitting(toks: list[str], i: int) -> bool:
    return any(_in(t, _NOT_AFTER) for t in toks[i + 1:i + 4]) or (i > 0 and _in(toks[i - 1], _NOT_BEFORE))


def _negated(toks: list[str], i: int) -> bool:
    return any(_in(t, _NEG) for t in toks[max(0, i - 2):i])


def _only_fillers_before(toks: list[str], i: int) -> bool:
    return all(_in(t, _FILLERS) for t in toks[:i])


def _ar_kind(text: str) -> str | None:
    norm = _norm(text)
    if _WORRY.search(norm):
        return "self_worry"
    clauses = _clauses(text)
    asks = (any(_in(t, _ASK) for c in clauses for t in c) or "؟" in text or "?" in text
            or bool(re.search(r"ولا\s+(?:لا|لأ|لاء)(?![ء-ي])|ام\s+لا(?![ء-ي])", norm)))
    severe = bool(_INSTR.search(norm) or _BODY.search(norm))
    remorse = bool(_REMORSE.search(norm))

    for ci, toks in enumerate(clauses):
        for i, tok in enumerate(toks):
            # the parent, imperfect / habitual: «هل أضرب ابني؟»، «بضرب ابني»، «أول مرة أضرب ابني»
            if _m(_P1_IMPF, tok) and not _not_hitting(toks, i) and not _negated(toks, i) \
                    and _child_object(toks, i):
                first_time = any(_in(t, {"اول", "لاول"}) for t in toks[max(0, i - 3):i])
                habitual = _w(tok).startswith("بضرب") and _only_fillers_before(toks, i)
                if asks and not first_time and not remorse:
                    return "question"
                if habitual and severe:
                    return "abuse"
                if habitual or first_time or remorse:
                    return "regret"
                continue
            # the parent, past: «ضربت ابني» — no subject noun before it in the clause,
            # and not right after a clause about a woman or girl (then it may be "she hit")
            if _m(_P1_PAST, tok) and _only_fillers_before(toks, i) and not _negated(toks, i) \
                    and not _not_hitting(toks, i) and _child_object(toks, i) \
                    and not (ci > 0 and clauses[ci - 1] and _in(clauses[ci - 1][0], _FEM_SUBJECT)):
                return "abuse" if severe else "regret"
            # «أعاقبه بالضرب؟»
            if _m(_PUNISH, tok) and _child_object(toks, i) and asks \
                    and any(_in(t, {"بالضرب"}) for t in toks[i + 1:i + 4]):
                return "question"
            # another adult hitting the child — only with bodily or instrument severity
            male, female = _in(tok, _ADULT_M), _in(tok, _ADULT_F)
            if severe and (male or female):
                j = i + 1
                while j < len(toks) and _in(toks[j], _AUX):
                    j += 1
                if j < len(toks) and ((male and _m(_M3, toks[j])) or (female and _m(_F3, toks[j]))) \
                        and _child_object(toks, j) and not _not_hitting(toks, j):
                    return "abuse"
            if severe and _m(_PASSIVE, tok) and i > 0 and _is_child(toks[i - 1]):
                after = toks[i + 1:i + 4]
                if any(_in(t, {"من"}) for t in after) and any(_in(t, _ADULT_M | _ADULT_F) for t in after):
                    return "abuse"
            # noun-only ruling question about hitting children
            if _m(_NOUN, tok) and not _not_hitting(toks, i):
                if (i > 0 and _is_child(toks[i - 1])) or (i > 1 and _is_child(toks[i - 2])):
                    continue        # «ابني ضرب الولد…» — the child is the one hitting
                if re.search(r"ضرب(?:ه|ها|هم)$", tok):       # «هل يجوز ضربه؟»
                    if i > 0 and _in(toks[i - 1], _PERMIT):
                        return "question"
                    continue
                ruling = any(_in(t, _RULING) for t in toks[:i]) or \
                    any(_in(t, {"حلال", "حرام", "يجوز", "مباح"}) for t in toks[i + 1:i + 4])
                if not ruling:
                    continue
                if any(_AGENT.match(_w(t)) or _AGENT.match(t) for t in toks[i + 1:i + 4]):
                    continue        # «ضرب الأطفال لبعضهم»، «ضرب الطفل لأخيه»
                if any(_is_child(t) for t in toks[i + 1:i + 3]):
                    return "question"
                if any(_in(t, _UPBRINGING) for t in toks[i + 1:i + 6]):
                    return "question"
    if re.search(r"(?:هل|حكم|راي|رايك|يجوز|حلال|حرام)[^.؟?!\n]{0,20}(?:ال)?(?:عقاب|عقوبه|عقوبة|تاديب)\s*(?:ال)?بدني",
                 norm):
        return "question"
    return None


# ── English ────────────────────────────────────────────────────────────────
_EN_NOT = re.compile(
    r"\bbeat(?:s|ing)?\s+(?:myself|yourself|himself|herself|ourselves|themselves)\s+up\b"
    r"|\bhit(?:s|ting)?\s+(?:the\s+)?(?:roof|snooze|pause|play|send|reset|refresh|record|gym|books|road|hay|sack|"
    r"ceiling|rock bottom|jackpot|milestone|puberty|spot)\b|\bhit(?:s|ting)?\s+it\s+off\b"
    r"|\bhit(?:s|ting)?\s+a\s+(?:wall|milestone|nerve|snag)\b"
    r"|\bbeat(?:s|ing)?\s+(?:the\s+)?(?:traffic|rush|morning rush|heat|odds|clock|record|game|level|deadline|crowd)\b"
    r"|\bheart\s*beats?\b|\bbeat\s+(?:me|us)\s+to\b"
    r"|\bbeat(?:s|ing)?\s+(?:my|our|his|her|their)\s+(?:\w+\s+)?(?:son|daughter|child|kid|boy|girl)s?\s+(?:at|in)\b",
    re.I)
_KID = (r"(?:(?:my|our|a|an|the|his|her|their|your)\s+(?:\d+\s*-?\s*(?:years?|yrs?)\s*-?\s*olds?|(?:\w+\s+)?"
        r"(?:son|daughter|child|children|kid|kids|boy|girl|toddler|baby|teen|teenager|preteen)s?)"
        r"|\d+\s*-?\s*(?:years?|yrs?)\s*-?\s*olds?|kids|children|toddlers|him|her|them)")
_HITV = r"(?:hit|slap|beat|strike|whip|smack|spank|paddle)"
_EN_QUESTION = [
    re.compile(r"\b(?:can|could|should|may|must|do|would)\s+(?:i|we)\s+(?:ever\s+|still\s+|really\s+|just\s+)?"
               r"(?:spank|smack|paddle)\b", re.I),
    re.compile(rf"\b(?:can|could|should|may|must|do|would)\s+(?:i|we|parents|a parent|fathers|mothers|dads|moms|mums)\s+"
               rf"(?:ever\s+|still\s+|really\s+|just\s+)?{_HITV}\s+{_KID}\b", re.I),
    re.compile(rf"\bis it\s+(?:ever\s+)?(?:ok|okay|alright|fine|allowed|permissible|acceptable|haram|halal|right|wrong|"
               rf"good|bad|islamic|sunnah)\s+(?:for\s+(?:me|us|parents|a parent|a father|a mother)\s+)?to\s+"
               rf"(?:{_HITV}\s+{_KID}\b|(?:spank|smack)\b|discipline\s+{_KID}\s+by\s+"
               rf"(?:hitting|spanking|smacking|slapping|beating))", re.I),
    re.compile(r"\bis\s+(?:spanking|smacking|hitting\s+(?:kids|children|a child|my\s+\w+)|physical punishment|"
               r"corporal punishment)\s+(?:ok|okay|alright|fine|allowed|permissible|acceptable|haram|halal|good|bad|"
               r"effective|wrong|right|islamic)\b", re.I),
    re.compile(r"\bwhat\s+(?:does|do)\s+(?:islam|the sharia|sharia|the quran|the qur'an|the sunnah|scholars|the deen)\s+"
               r"say\s+about\s+(?:hitting|spanking|smacking|beating|physically punishing|physical punishment|"
               r"corporal punishment)\b", re.I),
]
_EN_ADULT = (r"(?:i|we|my (?:husband|wife|partner|ex|mother|mom|mum|father|dad|mother-in-law|father-in-law)|"
             r"(?:his|her|their|our|my son's|my daughter's) (?:father|dad|mother|mom|mum|stepfather|stepdad|"
             r"stepmother|stepmom|teacher|nanny|coach|grandfather|grandmother)|the (?:teacher|nanny|babysitter|coach))")
_EN_HITPAST = (r"(?:hit|hits|beat|beats|slapped|slaps|spanked|spanks|whipped|whips|punched|punches|kicked|kicks|"
               r"smacked|smacks|struck|strikes|choked|burned)")
_EN_SEVERE = (r"(?:with\s+(?:a|his|her|my|the)\s+(?:belt|stick|cane|hanger|shoe|slipper|wire|cord|ruler|hose|rod|whip)"
              r"|bruis\w*|bleed\w*|blood\w*|black eye|broke\s+(?:his|her|their)\s+(?:arm|nose|tooth|leg|rib|finger|wrist)"
              r"|broken\s+(?:arm|nose|bone|tooth|rib|leg)|injur\w*|welts?|marks?\s+on\s+(?:his|her|their)\s+"
              r"(?:body|back|legs|arms|face|skin|neck)|passed out|fainted|unconscious|knocked (?:him|her|them) out"
              r"|on\s+(?:the|his|her|their)\s+(?:face|head)|concussion|hospital\w*)")
_EN_ABUSE = re.compile(rf"\b{_EN_ADULT}\s+(?:\w+\s+)?{_EN_HITPAST}\s+{_KID}\b[^.?!\n]{{0,80}}?\b{_EN_SEVERE}", re.I)
_EN_REGRET = re.compile(r"(?:^|[.!?]\s+)(?:(?:today|yesterday|this morning|last night|tonight)[, ]+)?i\s+"
                        r"(?:just\s+|finally\s+)?(?:hit|spanked|smacked|slapped|beat)\s+(?:my|our)\s+"
                        r"(?:\w+\s+)?(?:son|daughter|child|kid|boy|girl|toddler|baby|teen)\b(?!['’]s)", re.I)
_EN_ACCIDENT = re.compile(r"\baccident(?:al(?:ly)?)?\b|\bby mistake\b|\bwithout meaning\b", re.I)
_EN_WORRY = re.compile(r"\b(?:afraid|scared|worried|terrified)\s+(?:that\s+)?i(?:'ll| will| might| could| may)\s+"
                       r"(?:hurt|harm|hit|lose it with)\s+(?:my|him|her|them)\b"
                       r"|\bi\s+(?:don'?t|do not)\s+want\s+to\s+(?:hurt|harm)\s+(?:my|him|her|them)\b", re.I)


def _en_kind(text: str) -> str | None:
    t = _EN_NOT.sub(" ", text or "")
    if _EN_WORRY.search(t):
        return "self_worry"
    if _EN_ABUSE.search(t):
        return "abuse"
    if any(p.search(t) for p in _EN_QUESTION):
        return "question"
    if _EN_REGRET.search(t.strip()) and not _EN_ACCIDENT.search(t):
        return "regret"
    return None


def check_physical_discipline(text: str) -> str | None:
    """"question", "regret", "abuse", "self_worry", or None — None means the model answers."""
    if not text:
        return None
    return _ar_kind(text) if re.search(r"[ء-ي]", text) else _en_kind(text)


# ── replies (easy MSA; English mirrors the Arabic) ───────────────────────────
_PRAYER = re.compile(r"صلا|يصلي|تصلي|يصلو|الصلو|pray|salah|salat|namaz", re.I)

_AR_HEAD = (
    "سؤالك فيه جانب شرعي يُرجع فيه إلى أهل العلم الموثوقين في بلدك، و«المربّي» لا يُصدر فيه حكمًا.\n"
    "أما موقفنا التربوي فواضح: لا نوصي بالضرب أبدًا. قد يوقف الضرب السلوك لحظة، لكنه يعلّم الطفل "
    "الخوف بدل الفهم، ويربط الطاعة بالألم.\n"
)
_AR_PRAYER = (
    "ولتحبيب الصلاة إلى طفلك جرّب:\n"
    "• كن قدوة: صلِّ أمامه ومعه، واجعل له سجادة بجوارك.\n"
    "• اجعلها عادة: وقت ثابت، وتذكير لطيف، وجدول نجوم يرى فيه تقدّمه.\n"
    "• امدح كل صلاة يؤديها، ولا تعنّفه على التقصير.\n"
    "• اسأله بهدوء عن سبب تركها: ملل، أو خوف، أو صعوبة في الوضوء، وعالج السبب.\n"
    "• احكِ له عن رحمة الله وحب النبي ﷺ للصلاة، ليرتبط بها بالحب لا بالخوف.\n"
)
_AR_GENERAL = (
    "وهذه طرق أنفع وأبقى أثرًا:\n"
    "• هدّئ نفسك أولًا، ثم وجّه بكلمات قصيرة واضحة.\n"
    "• اتفقا مسبقًا على قواعد قليلة وعواقب منطقية هادئة، مثل حرمان مؤقت من امتياز.\n"
    "• امدح السلوك الحسن فور حدوثه؛ فالمدح يصنع العادة أسرع من العقاب.\n"
    "• ابحث عن سبب السلوك: جوع، أو تعب، أو غيرة، أو حاجة إلى اهتمامك.\n"
    "• كن قدوة فيما تطلبه منه.\n"
)
_AR_TAIL = "وإذا شعرت أن غضبك يشتد، فابتعد قليلًا ثم عُد بعد أن تهدأ. ويسعدني أن أساعدك في خطة لموقف محدد."

_EN_HEAD = (
    "Your question has a religious-ruling side that belongs to trusted scholars in your community; "
    "Almorabbi does not issue rulings.\n"
    "Our parenting position is clear: we never recommend hitting. It may stop a behaviour for a moment, "
    "but it teaches fear instead of understanding, and ties obedience to pain.\n"
)
_EN_PRAYER = (
    "To help your child love prayer, try:\n"
    "• Be the example: pray in front of them and with them, with their own mat beside yours.\n"
    "• Make it a habit: a fixed time, a gentle reminder, and a star chart where they can see their progress.\n"
    "• Praise every prayer they offer, and don't scold them for the ones they miss.\n"
    "• Calmly ask why they skip it — boredom, fear, trouble with wudu — and deal with the cause.\n"
    "• Tell them about Allah's mercy and the Prophet's ﷺ love of prayer, so it is tied to love, not fear.\n"
)
_EN_GENERAL = (
    "Approaches that work better and last longer:\n"
    "• Calm yourself first, then guide with short, clear words.\n"
    "• Agree in advance on a few rules and calm, logical consequences — such as briefly losing a privilege.\n"
    "• Praise good behaviour the moment it happens; praise builds habits faster than punishment.\n"
    "• Look for the cause: hunger, tiredness, jealousy, or a need for your attention.\n"
    "• Model what you ask of them.\n"
)
_EN_TAIL = ("If you feel your anger rising, step away for a moment and come back once you are calm. "
            "I'm glad to help you plan for a specific situation.")

_AR_ABUSE_REPLY = (
    "ما وصفته قد يعرّض طفلك لأذى حقيقي، وسلامته الآن أهم شيء.\n"
    "• أوقف الضرب فورًا. وإن كان به جرح أو نزيف أو ألم شديد أو إصابة في الرأس أو الوجه، فاعرضه على طبيب "
    "أو اذهب به إلى أقرب قسم طوارئ.\n"
    "• إن كان الأذى من شخص آخر، أو تكرّر، فتواصل مع خط حماية الطفل أو الجهات المختصة في بلدك.\n"
    "• وإن كان الغضب يغلبك أنت، فطلب المساعدة شجاعة لا ضعف: مختص نفسي أو أسري يساعدك على ضبط الغضب "
    "وإيجاد بدائل.\n"
    "«المربّي» لا يوصي بالضرب أبدًا، ونحن معك لإيجاد طرق أهدأ وأنفع."
)
_EN_ABUSE_REPLY = (
    "What you describe may put your child at real risk, and their safety comes first right now.\n"
    "• Stop the hitting now. If there is a cut, bleeding, severe pain, or an injury to the head or face, "
    "take your child to a doctor or the nearest emergency department.\n"
    "• If someone else is hurting your child, or it keeps happening, contact the child-protection line or "
    "the relevant authorities in your country.\n"
    "• If it is your own anger that takes over, asking for help is strength, not weakness: a family or "
    "mental-health professional can help you manage anger and find alternatives.\n"
    "Almorabbi never recommends hitting, and we are with you in finding calmer, better ways."
)
_AR_REGRET_REPLY = (
    "شكرًا لصراحتك؛ الندم بداية الإصلاح.\n"
    "• اعتذر لطفلك بكلمات واضحة تناسب عمره: «أخطأتُ حين ضربتك، والغضب لا يبرر الضرب».\n"
    "• طمئنه أنك تحبه، وأن الخطأ كان في الفعل لا فيه.\n"
    "• اتفقا على ما ستفعلانه في المرة القادمة: ابتعاد قصير حتى تهدأ، ثم حديث هادئ، وعاقبة منطقية متفق عليها.\n"
    "• إن ترك الضرب أثرًا في جسده فاعرضه على طبيب، وإن تكرر فاستعن بمختص أسري يساعدك على ضبط الغضب.\n"
    "«المربّي» لا يوصي بالضرب أبدًا، والحكم الشرعي يُرجع فيه إلى أهل العلم الموثوقين في بلدك."
)
_EN_REGRET_REPLY = (
    "Thank you for being honest — regret is where repair begins.\n"
    "• Apologise to your child in clear words that fit their age: \"I was wrong to hit you; being angry "
    "doesn't make hitting right.\"\n"
    "• Reassure them that you love them, and that the mistake was the act, not them.\n"
    "• Agree on what you will both do next time: a short break until you are calm, then a calm talk, and a "
    "logical consequence you agreed on.\n"
    "• If the hitting left a mark, have a doctor check your child; if it keeps happening, a family "
    "professional can help you manage anger.\n"
    "Almorabbi never recommends hitting; the religious ruling belongs to trusted scholars in your community."
)
_AR_WORRY_REPLY = (
    "شكرًا لأنك تحدثت عن هذا؛ خوفك من أن تؤذي طفلك علامة وعي ومحبة، وطلبك المساعدة خطوة شجاعة.\n"
    "• حين تشعر أن غضبك يتصاعد، ابتعد عن الموقف فورًا: تأكد أن طفلك في مكان آمن، واترك الغرفة، "
    "وتنفّس ببطء حتى تهدأ.\n"
    "• عُد إلى طفلك بعد أن تهدأ، وتحدث معه بهدوء.\n"
    "• لاحظ ما يشعل غضبك عادة (التعب، أو الضغط، أو قلة النوم)، واطلب من شريكك أو أحد أهلك أن يتولى "
    "الموقف حين تحتاج إلى استراحة.\n"
    "• تحدّث مع مختص نفسي أو أسري؛ فهو يساعدك على ضبط الغضب وإيجاد بدائل تناسب طفلك.\n"
    "وإن شعرت في أي لحظة أنك قد تؤذيه فعلًا، فابتعد عنه واتصل بشخص تثق به أو بخط الدعم في بلدك."
)
_EN_WORRY_REPLY = (
    "Thank you for saying this; being afraid of hurting your child is a sign of awareness and love, and "
    "asking for help is a brave step.\n"
    "• When you feel your anger rising, step away right away: make sure your child is somewhere safe, leave "
    "the room, and breathe slowly until you are calm.\n"
    "• Go back to your child once you are calm, and talk quietly.\n"
    "• Notice what usually sets off your anger (tiredness, stress, lack of sleep), and ask your partner or a "
    "relative to take over when you need a break.\n"
    "• Talk to a mental-health or family professional; they can help you manage anger and find alternatives "
    "that suit your child.\n"
    "If at any moment you feel you might really hurt them, move away and call someone you trust or a "
    "support line in your country."
)


def discipline_reply_text(kind: str, text: str, lang: str | None) -> str:
    english = lang == "en"
    if kind == "abuse":
        return _EN_ABUSE_REPLY if english else _AR_ABUSE_REPLY
    if kind == "regret":
        return _EN_REGRET_REPLY if english else _AR_REGRET_REPLY
    if kind == "self_worry":
        return _EN_WORRY_REPLY if english else _AR_WORRY_REPLY
    prayer = bool(_PRAYER.search(_norm(text)))
    if english:
        return _EN_HEAD + (_EN_PRAYER if prayer else _EN_GENERAL) + _EN_TAIL
    return _AR_HEAD + (_AR_PRAYER if prayer else _AR_GENERAL) + _AR_TAIL


def discipline_reply(kind: str, text: str):
    """The AssistantReply for a matched message — one builder for /draft and /stream."""
    from app.models.api import AssistantReply
    from app.services.retrieval import detect_query_language

    abuse = kind == "abuse"
    return AssistantReply(
        reply_text=discipline_reply_text(kind, text, detect_query_language(text)),
        domain="islamic_parenting",
        severity="طارئ" if abuse else ("شديد" if kind == "self_worry" else "متوسط"),
        needs_human_review=abuse,
        escalation_target="emergency_services" if abuse else None,   # only with bodily severity
        mode="discipline_guard",
    )
