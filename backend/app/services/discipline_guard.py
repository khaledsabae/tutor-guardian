"""Physical discipline — «المربّي» never instructs it.

A parent asking «هل أضرب ابني لأنه لا يصلي؟» or "can I spank my son?" does not
reach the model. Until 2026-10-04 it did, and two knowledge units retrieval
could hand it said «يمكن ضرب الأطفال على ترك الصلاة بعد سن العاشرة كآخر وسيلة
تأديبية». The system prompt forbade recommending it; a prompt is a request, not
a guarantee. This is a guarantee.

Three outcomes, all deterministic:

* ``question`` — whether, when, or how to hit a child. The religious ruling is
  deferred to trusted scholars (the app issues no fatwa — FIQH_GUARD.md), and the
  reply gives the app's own non-physical alternatives; the prayer variant when
  the question is about prayer.
* ``regret`` — «ضربت ابني» / "I hit my son": a confession. Repair (apologise,
  reassure, agree on next time), a doctor if it left a mark, help if it recurs.
* ``abuse`` — hitting described with a weapon, an injury, the face, every day,
  or "I can't stop". The child's safety comes first: medical care, the
  child-protection line in the parent's country, and help for the parent.

What it deliberately does NOT catch: a child hitting a sibling («ابني يضرب
أخاه»), times tables («جدول الضرب»), «ضرب الأمثال», a heartbeat. Those are
ordinary questions with ordinary answers. Precision is regression-tested in
backend/tests/test_discipline_guard.py.
"""
from __future__ import annotations

import re

# ── normalisation (same idea as fiqh_guard / intent_guard) ─────────────────
_MARKS = re.compile(r"[ً-ٰٟـ]")


def _norm_ar(text: str) -> str:
    text = _MARKS.sub("", text)
    for a in ("آ", "أ", "إ", "ٱ"):
        text = text.replace(a, "ا")
    return text.replace("ى", "ي").replace("ة", "ه")


_A = r"[ء-ي]"
_B = rf"(?<!{_A})"           # Arabic word start
_E = rf"(?!{_A})"            # Arabic word end

# the child, as an object of the verb or named after it
_CHILD = (r"(?:ابني|ابنتي|بنتي|ولدي|طفلي|طفلتي|اولادي|اطفالي|عيالي|ابنائي|بناتي|الطفل|الاطفال|"
          r"الولد|البنت|الابن|الابناء|الاولاد|الصغار|الصغير|العيال|ابنه|ابنها|ابنهم|طفله|طفلها|الصبي|الصبيان)")
# first-person / generic hitting, as a verb with or without an object suffix
_HIT_1P = rf"{_B}(?:و|ف)?(?:ا|ن|ب|بن|سا|سن|هل ا)ضرب(?:ه|ها|هم|هما|و|وه|وها)?{_E}"
_HIT_PAST_1P = rf"{_B}(?:و|ف)?ضربت(?:ه|ها|هم|هما)?{_E}"
_HIT_NOUN = rf"{_B}(?:ال|بال|وال)?ضرب{_E}"
_HADITH_WORD = rf"{_B}(?:و)?اضربوهم{_E}"
_ASK = (r"(?:هل|ينفع|يجوز|جواز|يصح|ممكن|مسموح|اقدر|استطيع|لازم|المفروض|حكم|متي|امتي|كيف|ازاي|"
        r"حلال|حرام|مباح|ما راي|رايك|افضل|صح|خطا)")
_SEVERE = (rf"{_B}(?:بالحزام|بالعصا|بالعصايه|بالخرطوم|بالشبشب|بالسلك|بالكرباج|بالسوط|بالخشبه|بالمسطره|"
           r"نزف|ينزف|نزيف|(?:ال|بال)?دم|كدمات|كدمه|ازرق|ازرقت|علامات|اثار|كسر|انكسر|تورم|ورم|"
           r"بقوه|بشده|بعنف|كل يوم|يوميا|علي وجهه|علي وجهها|علي راسه|علي راسها|في وجهه|في وجهها|"
           rf"مش قادر اوقف|لا استطيع التوقف|ما اقدر اوقف|اغمي عليه|اغمي عليها){_E}")
_OTHER_ADULT = (r"(?:ابوه|ابوها|امه|امها|زوجي|زوجتي|جده|جدته|جدها|جدتها|المدرس|المدرسه|المعلم|المعلمه|"
                r"الشيخ|المحفظ|خاله|عمه|خالها|عمها|زوج امه|زوجه ابيه)")
_OTHER_HIT = rf"{_OTHER_ADULT}\s+(?:ب|بي|ي|ت|بت)?ضرب(?:ه|ها|هم)?{_E}"
_NOT_DISCIPLINE = re.compile(
    r"جدول\s*(?:ال)?ضرب|عمليه\s*(?:ال)?ضرب|(?:ال)?ضرب\s*و\s*(?:ال)?قسمه|ضرب\s*(?:ال)?(?:مثل|امثال|امثله)|"
    r"ضربات\s*(?:ال)?قلب|ضربه\s*شمس|ضرب\s*(?:ال)?اعداد|ضرب\s*(?:ال)?ارقام")

_AR_QUESTION = [
    re.compile(rf"{_ASK}[^.؟?!\n]{{0,30}}(?:{_HIT_1P}|{_HIT_NOUN})[^.؟?!\n]{{0,30}}{_CHILD}"),
    re.compile(rf"{_ASK}[^.؟?!\n]{{0,30}}{_B}(?:ا|ن|هل ا)ضرب(?:ه|ها|هم|هما){_E}"),
    re.compile(rf"{_HIT_1P}[^.؟?!\n]{{0,25}}{_CHILD}"),
    re.compile(rf"{_HIT_NOUN}\s+{_CHILD}"),
    re.compile(rf"{_HIT_NOUN}\s+(?:علي|في|ل|عشان|لاجل|بسبب)\s*(?:ال)?(?:صلاه|تاديب|تربيه)"),
    re.compile(_HADITH_WORD),
    re.compile(rf"{_ASK}[^.؟?!\n]{{0,30}}(?:الاب|الام|الوالد|الوالده|الوالدين|الاهل|الاباء|الامهات|المربي|"
               rf"ولي الامر)[^.؟?!\n]{{0,15}}{_B}(?:ان\s+)?(?:ي|ت)ضرب"),
    # «هل يجوز ضربه؟» / «ما حكم ضربها؟» — the verbal noun with the child as its pronoun.
    # Permission words only: «هل ضربه لأخيه طبيعي؟» is the child hitting a sibling.
    re.compile(rf"(?:يجوز|جواز|ينفع|يصح|ممكن|مسموح|حكم|حلال|حرام|مباح)\s+{_B}(?:ال)?ضرب(?:ه|ها|هم|هما){_E}"),
    # «هل يجوز أن يضرب الأبُ ابنه؟» — verb before its subject
    re.compile(rf"{_ASK}[^.؟?!\n]{{0,20}}{_B}(?:ان\s+)?(?:ي|ت)ضرب\s+(?:الاب|الام|الوالد|الوالده|الوالدان|"
               r"الوالدين|الاهل|المربي|ولي الامر|الاباء)"),
    re.compile(rf"{_ASK}[^.؟?!\n]{{0,30}}(?:(?:ال)?عقاب\s*(?:ال)?بدني|(?:ال)?تاديب\s*(?:ال)?بدني|"
               r"(?:ال)?عقوبه\s*(?:ال)?بدنيه)"),
]
# «ضربت ابني وندمت» — a confession, not a question: the reply is about repair.
_AR_REGRET = re.compile(
    rf"{_HIT_PAST_1P}[^.؟?!\n]{{0,25}}{_CHILD}|{_CHILD}[^.؟?!\n]{{0,15}}{_HIT_PAST_1P}"
    # «ضربته لأنه كذب / لعدم صلاته» — the object is the child, the clause is the reason
    rf"|{_B}(?:و|ف)?ضربت(?:ه|ها|هم){_E}\s*(?:لانه|لانها|لانهم|لعدم|عشان|علشان|بسبب|لما|حين|عندما|لكي|حتي|علي)")
_AR_ABUSE = [
    re.compile(rf"(?:{_HIT_1P}|{_HIT_PAST_1P}|{_OTHER_HIT})[^.؟?!\n]{{0,60}}{_SEVERE}"),
    re.compile(rf"{_SEVERE}[^.؟?!\n]{{0,25}}(?:{_HIT_1P}|{_HIT_PAST_1P}|{_OTHER_HIT})"),
    re.compile(_OTHER_HIT),
    re.compile(r"(?:اخاف|خايف|خايفه)\s+(?:ان\s+)?(?:اذيه|اذيها|اؤذيه|اؤذيها|اقتله|اقتلها)"),
]

# ── English ────────────────────────────────────────────────────────────────
_EN_HIT = r"(?:hit|hitting|spank|spanking|spanked|smack|smacking|beat|beating|slap|slapping|strike|striking|whip|whipping|paddle|paddling|belt)"
_EN_KID = (r"(?:my|our|a|an|the|his|her)\s+(?:\w+\s+)?(?:son|daughter|child|children|kid|kids|boy|girl|toddler|baby|teen|teenager)s?"
           r"|\b\d+\s*-?\s*(?:years?|yrs?)\s*-?\s*olds?\b|\b(?:kids|children|toddlers)\b|\bhim\b|\bher\b|\bthem\b")
_EN_ASK = (r"(?:can|could|should|may|must|is it (?:ok|okay|fine|alright|allowed|permissible|acceptable|haram|halal|right|wrong)|"
           r"am i allowed|do i need|how (?:hard|much|often)|when (?:can|should|do)|at what age|is (?:spanking|hitting|smacking))")
_EN_QUESTION = [
    re.compile(rf"\b{_EN_ASK}\b[^.?!\n]{{0,40}}\b{_EN_HIT}\b[^.?!\n]{{0,30}}(?:{_EN_KID})", re.I),
    re.compile(rf"\b(?:physical(?:ly)?\s+(?:punish\w*|discipline)|corporal\s+punishment)\b", re.I),
    re.compile(rf"\bis\s+(?:spanking|hitting|smacking)\b", re.I),
]
_EN_SEVERE = (r"(?:with a (?:belt|stick|cane|hanger|shoe|slipper|wire|cord)|bruis\w*|bleed\w*|black eye|broke|broken|"
              r"every day|daily|so hard|really hard|on (?:the|his|her) face|marks|can'?t stop|cannot stop|unconscious)")
_EN_ADULT = r"(?:i|we|my (?:husband|wife|partner)|(?:his|her|their) (?:father|dad|mother|mom|mum|stepfather|stepdad|teacher)|the teacher)"
_EN_ABUSE = [
    re.compile(rf"\b{_EN_ADULT}\s+(?:\w+\s+)?(?:hit|hits|beat|beats|slapped|slaps|spanked|spanks|whipped|whips|punched|punches|kicked|kicks)\b[^.?!\n]{{0,60}}{_EN_SEVERE}", re.I),
    re.compile(rf"\b(?:afraid|scared) (?:that )?i(?:'ll| will| might) (?:hurt|kill) (?:him|her|them|my)", re.I),
]
_EN_REGRET = re.compile(rf"\bi\s+(?:just\s+|accidentally\s+)?(?:hit|spanked|smacked|slapped|beat)\s+(?:my|our)\s+"
                        r"(?:\w+\s+)?(?:son|daughter|child|kid|boy|girl|toddler|baby|teen)", re.I)
_EN_NOT = re.compile(r"heart\s*beat|beat the|hit (?:a|the) (?:milestone|ceiling|wall|road|jackpot)|hit puberty|beats? (?:me|us) to", re.I)

_PRAYER = re.compile(r"صلا|يصلي|تصلي|يصلو|الصلو|pray|salah|salat|namaz", re.I)


def check_physical_discipline(text: str) -> str | None:
    """"abuse", "regret", "question", or None."""
    if not text:
        return None
    ar = _norm_ar(text)
    en = text
    if _NOT_DISCIPLINE.search(ar) and not any(p.search(_NOT_DISCIPLINE.sub(" ", ar)) for p in _AR_QUESTION + _AR_ABUSE):
        return None
    ar_clean = _NOT_DISCIPLINE.sub(" ", ar)
    en_clean = _EN_NOT.sub(" ", en)
    if any(p.search(ar_clean) for p in _AR_ABUSE) or any(p.search(en_clean) for p in _EN_ABUSE):
        return "abuse"
    if _AR_REGRET.search(ar_clean):
        return "regret"
    if any(p.search(ar_clean) for p in _AR_QUESTION) or any(p.search(en_clean) for p in _EN_QUESTION):
        return "question"   # before the English confession: "Can I hit my child?" contains "I hit my child"
    if _EN_REGRET.search(en_clean):
        return "regret"
    return None


# ── replies (easy MSA; English mirrors the Arabic) ───────────────────────────
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
_EN_TAIL = "If you feel your anger rising, step away for a moment and come back once you are calm. I'm glad to help you plan for a specific situation."

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


def discipline_reply_text(kind: str, text: str, lang: str | None) -> str:
    english = lang == "en"
    if kind == "abuse":
        return _EN_ABUSE_REPLY if english else _AR_ABUSE_REPLY
    if kind == "regret":
        return _EN_REGRET_REPLY if english else _AR_REGRET_REPLY
    prayer = bool(_PRAYER.search(text or ""))
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
        severity="طارئ" if abuse else "متوسط",
        needs_human_review=abuse,
        escalation_target="emergency_services" if abuse else None,
        mode="discipline_guard",
    )
