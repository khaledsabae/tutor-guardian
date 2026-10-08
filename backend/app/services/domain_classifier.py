"""
domain_classifier.py — v3.1 (fast-path + cache + LLM via the configured primary)

Classifies questions into domains using three-tier approach:
  1. Keyword fast-path (0ms, covers ~60% of queries)
  2. LRU cache (instant for repeated queries)
  3. LLM fallback (only for ambiguous/complex questions)

This approach saves 3-5s on the majority of requests while preserving
accuracy for the edge cases that need it.

Tier 3 goes through the gateway's auxiliary helpers (app.services.ai_gateway),
so it follows whichever provider the deployment configured as primary, its
telemetry, and its monthly spend ceiling — instead of being pinned to a
local Ollama host that the main path may have already abandoned.
"""

import bisect
import json
import logging
import os
import re
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

from app.config.llm_config import DEFAULT_HOME_OLLAMA_URL
from app.services.ai_gateway import (
    AUX_TIMEOUT_S, OllamaProvider, aux_breaker, aux_cloud_provider, aux_generate,
)

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
# Resolution: OLLAMA_BASE_URL (Docker/general) first, then OLLAMA_LOCAL_BASE_URL (home-server overrides).
# In Docker production, set OLLAMA_BASE_URL=http://ollama:11434 and everything works.
# On home server, OLLAMA_LOCAL_BASE_URL takes precedence for local-only models.
_OLLAMA_ENDPOINT = (
    os.environ.get("OLLAMA_LOCAL_BASE_URL") or
    os.environ.get("OLLAMA_BASE_URL", DEFAULT_HOME_OLLAMA_URL)
)
CLASSIFIER_MODEL = (
    os.environ.get("OLLAMA_LOCAL_FAST_MODEL") or
    os.environ.get("OLLAMA_FAST_MODEL", "qwen2.5:3b")
)
# 60 predicted tokens need seconds, not a minute. The old 45s ceiling meant an
# unreachable host turned EVERY fast-path miss into a 45s wait before the
# answer even started being generated.
CLASSIFIER_TIMEOUT_S = int(os.environ.get("CLASSIFIER_TIMEOUT_S", str(AUX_TIMEOUT_S)))

VALID_DOMAINS = {"fiqh", "medical", "cyber", "development", "aqeedah"}

# What we return when classification is impossible (LLM unreachable/garbage).
# Returning ONE arbitrary domain — this used to be ["medical"] — scopes
# retrieval to a single knowledge base and labels the reply with it, so a
# question about Instagram was answered from the medical KB and presented as
# confidently medical. The trade we make instead: search every domain and let
# the cross-encoder reranker pick the winning units. That costs one extra
# retrieval leg per domain (tens of ms, all local) and slightly dilutes
# precision, but a diluted answer is recoverable and a silently wrong domain
# is not. Callers detect this list via is_uncertain() and must not treat
# UNCERTAIN_DOMAINS[0] as a real classification.
UNCERTAIN_DOMAINS: Tuple[str, ...] = (
    "medical", "cyber", "fiqh", "development", "aqeedah",
)

# ── App help: questions about the app itself ──────────────────────────────────
# Built from parts so each can be read (and tested) on its own; see the note at
# the rule's place in KEYWORD_RULES. `(?s:.*?)` lets a lookahead see a question
# written over several lines.
#
# 🚨 Every paired lookahead is anchored with `^`. Unanchored, `re.search` retries
# it at every position and a 4,000-character question (MAX_MESSAGE_CHARS) took
# 0.15–2 s depending on the machine — on the event loop, since
# `matched_fast_path` runs there. Anchored it is one pass (~1 ms) with identical
# results; test_app_help_routing times it.
_WORD_END = r"(?![ء-ي])"
# «التطبيق» as the app — not «التطبيقات» (apps in general), not «التطبيقية»,
# and not «التطبيق العملي/الفعلي» (putting advice into practice).
_APP_NOUN = (r"(?:ال|هذا\s+ال|بال|فال|وال|لل)تطبيق" + _WORD_END
             + r"(?!\s+(?:ال)?(?:عملي|فعلي|صحيح|سليم))")
_APP_ACTION = (
    r"(?:أضيف|اضيف|إضافة|اضافة|أحذف|احذف|حذف|أمسح|امسح|مسح|أغير|اغير|أغيّر|تغيير|"
    r"أستخدم|استخدم|استخدام|أستعمل|استعمل|استعمال|يعمل|يشتغل|بيشتغل|شغال|"
    r"مجان|بفلوس|مدفوع|اشتراك|إعلان|اعلان|حساب|تسجيل|إشعار|اشعار|لغة|الإنجليزي|الانجليزي|"
    r"نسخة|تحديث|خصوصية|بيانات|العملات|الشارات|المسارات|الدروس|المساعد|الذاكرة|"
    r"(?:ال|لل|بال)ذكاء\s+(?:ال)?اصطناعي|وضع\s+الطفل|ميزة|مميزات|خاصية|إعدادات|اعدادات|"
    r"أين\s+أجد|اين\s+اجد)"
)
# The WEAK signal: «التطبيق» next to an app action. It is also how parents talk
# about practice — «بعد التطبيق لمدة أسبوع لم تنجح الطريقة… هل أغير الأسلوب؟»,
# «يخطئ في التطبيق», «لا يحسن التطبيق في الدروس» — so the keywords alone never
# decide it. Beside a domain a parenting rule found, `_keyword_fast_path` adds
# app_help to the search. Alone, the model decides (`_classify_cached`): a
# parenting domain from the model wins, and when the model finds none —
# «general», nothing, or no answer at all — the question is about the app.
_APP_GENERAL = rf"^(?=(?s:.*?){_APP_NOUN})(?=(?s:.*?){_APP_ACTION})"
# «وضع الطفل» is also "the child's situation" and "putting the child (in front of
# the TV)": it counts only next to an enter/exit verb, or with a PIN, a passcode,
# handing over the phone, or «في التطبيق» — never with bare «التطبيق» or «رمز».
_APP_CHILD_MODE = (
    r"(?:أخرج|اخرج|الخروج|خروج|أطلع|اطلع)\s+(?:من\s+)?وضع\s+الطفل"
    r"|(?:أدخل|ادخل|دخول|الدخول\s+(?:إلى|الى|في|ل))\s*وضع\s+الطفل"
    r"|(?:أفعل|افعل|أفعّل|تفعيل|أشغل|اشغل|تشغيل|أقفل|اقفل|أغلق|اغلق|إغلاق|اغلاق|أفتح|افتح|فتح)"
    r"\s+وضع\s+الطفل"
    r"|^(?=(?s:.*?)وضع\s+الطفل)(?=(?s:.*?)(?:(?<![A-Za-z])(?i:pin)(?![A-Za-z])|رمز\s+(?:ال)?(?:بن|القفل|الدخول)"
    r"|الرقم\s+السري|الرمز\s+السري|كلمة\s+(?:السر|المرور)"
    r"|(?:في|داخل)\s+(?:التطبيق" + _WORD_END + r"(?!\s+(?:ال)?(?:عملي|فعلي|صحيح|سليم))"
    r"|تطبيق\s+(?:ال)?مرب)"
    r"|(?:أسلم|اسلم|أسلّم|تسليم)\s+(?:ال)?(?:جهاز|هاتف|جوال|موبايل)))"
)
# Deleting «my account / my data» is about this app only when no other platform
# is named: «أحذف حسابي على فيسبوك» is a question about Facebook. Google is not
# in the list: the app's own delete screen talks about the linked Google account.
_OTHER_PLATFORMS = (
    r"(?:فيسبوك|فيس\s+بوك|إنستغرام|انستغرام|إنستقرام|انستقرام|انستجرام|انستا|تيك\s*توك|يوتيوب|"
    r"واتساب|واتس\s*اب|واتس|سناب|تويتر|تلغرام|تلجرام|تليجرام|ديسكورد|روبلوكس|ماينكرافت|ببجي|"
    r"بابجي|فري\s*فاير|فورتنايت|ستيم|بلايستيشن|بلاي\s+ستيشن|اكس\s*بوكس|إكس\s*بوكس|"
    r"(?i:facebook|instagram|tiktok|youtube|whatsapp|snapchat|twitter|telegram|discord|roblox|"
    r"minecraft|pubg|fortnite|steam|playstation|xbox))"
)
_APP_DELETE = (
    rf"^(?!(?s:.*?){_OTHER_PLATFORMS})(?=(?s:.*?)(?:"
    r"(?:أحذف|احذف|حذف|إلغاء|الغاء|ألغي|الغي)\s+حسابي" + _WORD_END
    + r"|(?:أحذف|احذف|حذف|أمسح|امسح|مسح)\s+(?:كل\s+)?(?:بياناتي|بيانات\s+(?:أطفالي|اطفالي|طفلي))"
    + _WORD_END + r"))"
)
# Names only the app uses. Bare card names («مهمة اليوم», «خطوة اليوم»,
# «رمضان العائلة») are not here: parents quote a card to ask about its topic —
# «مهمة اليوم: كيف أعلم ابني الصدق؟» is a question about truthfulness.
_APP_FEATURES = (
    r"ما\s+يعرفه\s+المرب|ذاكرة\s+(?:ال)?مرب"
    r"|رحلة\s+الصلا[ةه]"
    r"|مساراتي|اسأل\s+المرب|شاركنا\s+رأيك"
    r"|عهد\s+المكافآت|بوابة\s+الأهل|الشارات\s+الحصرية|شارات\s+حصرية"
    r"|(?:أحفظ|احفظ)\s+تقدمي"
    r"|أراسلكم|اراسلكم|أتواصل\s+معكم|اتواصل\s+معكم|التواصل\s+معكم"
    r"|تطبيق\s+(?:ال)?مرب|المرب[يّى]\s+(?:مجان|بفلوس|مدفوع)"
)
# The STRONG signals — each enough on its own.
_APP_HELP_RULE = rf"{_APP_CHILD_MODE}|{_APP_DELETE}|{_APP_FEATURES}"
_APP_GENERAL_RE = re.compile(_APP_GENERAL, re.UNICODE)

# ── Keyword Fast-Path ──────────────────────────────────────────────────────────
_MARKS = r"[\u064b-\u065f\u0670\u0640]*"
_EDGE = r"[\w\u064b-\u065f\u0670\u0640]"


def _spell(form: str, marks: str = _MARKS) -> str:
    """One word form, tolerant of tashkeel/tatweel after every letter."""
    return "".join(re.escape(letter) + marks for letter in form)


# Dialect verbs carry what MSA says with separate words: a joined negation
# («مايسمع», «مابيلعبش», «ميسمعش»), a subject ending («يسمعو», «مايلعبون»), an
# object or «لـ» pronoun («بيسمعلنا», «بيعضوه») and the Egyptian «ـش». Only the
# imperfect stems take them — past/noun stems stay explicit, because «م» + «لعب»
# is «ملعب», «عض» + «و» is «عضو», and «ب» + «عض» is «بعض».
_VERB_SUFFIX = (
    r"(?:" + "|".join(_spell(f) for f in ("وا", "ون", "و", "ين", "ي")) + r")?"
    r"(?:" + "|".join(_spell(f) for f in ("ني", "نا", "ها", "هم", "هن", "ه", "كم", "ك",
                                          "لنا", "لها", "لهم", "له", "لي", "لك")) + r")?"
    r"(?:" + _spell("ش") + r")?"
)


def _short_arabic_token(forms: list[str], verbs: Sequence[str] = ()) -> str:
    """Match explicit word forms, including conjunctions and optional marks.

    `verbs` are imperfect stems that also take a joined negation («ما»/«م») and
    the dialect endings in _VERB_SUFFIX. Every alternative is a fixed set of
    short pieces between word edges, so a match is linear in the input.
    """
    alternatives = [_spell(form) for form in forms]
    if verbs:
        alternatives.append(
            r"(?:" + _spell("ما") + r"|" + _spell("م") + r")?(?:"
            + "|".join(_spell(verb) for verb in verbs) + r")" + _VERB_SUFFIX)
    return (r"(?<!" + _EDGE + r")(?:[وف]" + _MARKS + r")?(?:"
            + "|".join(alternatives) + r")(?!" + _EDGE + r")")


# Bare roots used to match عض in بعض and لعب in لعبدالله. Keep this boundary
# local to these two roots; Arabic articles/clitics and verbal forms are explicit.
_BITE_TOKEN = r"(?:" + _short_arabic_token(
    [stem + suffix
     for stem in ("عض", "عضت")
     for suffix in ("", "ني", "ه", "ها", "هم", "نا", "ك")]
    + ["العض", "بالعض", "للعض",
       # The noun «a bite»: «عضة الطفل لأمه».
       "عضة", "العضة", "عضات", "العضات", "عضتي",
       # «تعرض لعضة» — the noun after «لـ»; «لعض» alone stays out (لعضو).
       "لعضة", "لعضات", "للعضة", "للعضات"],
    verbs=("يعض", "تعض", "نعض", "أعض", "اعض", "بيعض", "بتعض", "بنعض",
           "سيعض", "ستعض", "هيعض", "هتعض",
           # Reduplicated «يعضعض»: biting repeatedly.
           "يعضعض", "تعضعض", "بيعضعض", "بتعضعض"),
) + (
    # «عضوا» is «they bit»; «عضوًا/عضواً» with tanween is «a member».
    r"|(?<!" + _EDGE + r")(?:[وف]" + _MARKS + r")?" + _spell("عض")
    + _spell("و", r"[\u064c-\u065f\u0670\u0640]*")
    + _spell("ا", r"[\u064c-\u065f\u0670\u0640]*") + r"(?!" + _EDGE + r"))"
)
# Biting oneself: «ويقوم بعض يده» is «بـ» + «عض», which the token above must
# refuse to keep the quantifier «بعض» out. But «بعض» before a plural or
# «نفسه» is still the quantifier («بعض أصابعها بالحناء», «لعل بعض نفسه»), so
# it is biting only after «يقوم/قام/صار/بدأ…» («بـ» + verbal noun), or before
# a single organ the quantifier cannot take («بعض يده», «بعض لسانه»).
_SELF_BITE_ORGANS_SINGLE = (
    r"يده|يدها|ايده|إيده|ايدها|إيدها|لسانه|لسانها|شفته|شفتها|ذراعه|ذراعها"
)
_SELF_BITE = (
    r"(?<!\w)(?:[وف])?(?:(?:يقوم|بيقوم|تقوم|بتقوم|قام|قامت|صار|صارت|بدأ|بدأت"
    r"|بدا|بدات)\s+بعض\s+(?:" + _SELF_BITE_ORGANS_SINGLE
    + r"|يديه|يديها|أصابعه|اصابعه|أصابعها|اصابعها|صوابعه|صوابعها|إصبعه|اصبعه"
    r"|إصبعها|اصبعها|صباعه|صباعها|نفسه|نفسها|شفايفه|شفايفها)"
    r"|بعض\s+(?:" + _SELF_BITE_ORGANS_SINGLE + r"))(?!\w)"
)
_PLAY_TOKEN = _short_arabic_token(
    [stem + suffix
     for stem in ("لعب", "لعبت")
     for suffix in ("", "ه", "ها", "هم", "ك")]
    + ["اللعب", "باللعب", "للعب", "لعبة", "اللعبة", "باللعبة", "للعبة",
       "لعبنا", "لعبوا"],
    verbs=("يلعب", "تلعب", "ألعب", "العب", "نلعب", "بيلعب", "بتلعب", "بلعب",
           "بنلعب", "هيلعب", "هتلعب", "سيلعب", "ستلعب"),
)
# First-person reports such as "سمعت عنه" are not a child's hearing signal.
_HEARING_TOKEN = _short_arabic_token(
    ["سمع" + suffix for suffix in ("", "ني", "ه", "ها", "نا", "ك", "هم")]
    + ["السمع", "بالسمع", "للسمع",
       # Hearing adjectives: «ضعف سمعي», «إعاقة سمعية».
       "سمعي", "سمعية", "سمعيه", "السمعي", "السمعية", "السمعيه",
       # Egyptian negated past: «مسمعش ابني حاجة».
       "مسمعش", "ماسمعش", "سمعش"],
    verbs=("يسمع", "تسمع", "بيسمع", "بتسمع", "نسمع"),
)


def _spelled_words(forms: list[str]) -> str:
    """Whole following words for a lookahead, tolerant of optional marks."""
    return (r"(?:" + "|".join(_spell(form) for form in forms)
            + r")(?!" + _EDGE + r")")


_MEDIA = [
    "الإذاعة", "الاذاعة", "إذاعة", "الراديو", "راديو", "التلفزيون",
    "التليفزيون", "التلفاز", "يوتيوب", "اليوتيوب", "البودكاست", "بودكاست",
    "الأخبار", "الاخبار", "برنامج", "البرنامج", "قناة", "القناة",
    "النت", "الإنترنت", "الانترنت", "فيسبوك", "الفيسبوك", "تيك", "التيك",
]

# «سماعة/سماعات» is a hearing aid and also headphones («سماعة بلوتوث»,
# «سماعات الأذن هل تضر»). It counts as a child's hearing only with a medical
# qualifier after it, a need/wear verb before it, or a hearing-loss word
# anywhere in the question («زراعة قوقعة وسماعة»). Every piece is fixed-length.
_HEARING_AID_DEVICE = (
    r"(?<!\w)(?:[وف])?(?:بال|ال|لل|ب)?سماع(?:ة|ات|تين|ته|تها|اته|اتها)(?!\w)"
)
_HEARING_AID_RE = re.compile(
    r"(?<!\w)(?:[وف])?(?:يحتاج|تحتاج|يحتاجون|محتاج|محتاجة|محتاجه|يلبس|تلبس|بيلبس"
    r"|بتلبس|لبس|لبست|يركب|تركب|ركب|ركبت|ركبنا|ركبوا)\s+(?:(?:له|لها|لهم)\s+)?"
    + _HEARING_AID_DEVICE
    + r"|" + _HEARING_AID_DEVICE + r"\s+(?:(?:ال)?(?:طبية|طبيه|طبي|سمعية|سمعيه)"
    r"|للسمع|(?:ال)?(?:أذن|اذن)\s+(?:ال)?(?:طبية|طبيه))(?!\w)",
    re.UNICODE,
)
_HEARING_AID_DEVICE_RE = re.compile(_HEARING_AID_DEVICE, re.UNICODE)
_HEARING_LOSS_CONTEXT_RE = re.compile(
    r"(?<!\w)(?:[وف])?(?:(?:ال|بال)?(?:قوقعة|قوقعه)|ضعف\s+(?:في\s+)?(?:ال)?سمع\w*"
    r"|(?:ضعيف|ضعيفة|ضعيفه)\s+السمع|ثقل\s+(?:في\s+)?(?:ال)?سمع\w*|أصم|اصم|صماء"
    r"|الصمم|بالصمم|سمعه|سمعها)(?!\w)",
    re.UNICODE,
)


def _hearing_aid(text: str) -> bool:
    return bool(_HEARING_AID_RE.search(text)
                or (_HEARING_AID_DEVICE_RE.search(text)
                    and _HEARING_LOSS_CONTEXT_RE.search(text)))


# The past forms in _HEARING_TOKEN (سمع/سمعنا/سمعه/سمعها/سمعك/…) are also the
# noun «his/her/our hearing», so they stay. But followed by reported speech —
# «عن …», «من الشيخ», «في الإذاعة», «على اليوتيوب», «أن …» — they are someone
# hearing *about* something, the same reading «سمعت عن» already has; so are the
# parents' present «نسمع/بنسمع/تسمع/بتسمع عن …» («تسمع» here is «you hear»;
# behind a negation or a girl it is «she hears» and is kept, see
# _mask_reported_hearing). Only that word is masked
# before the rules run; a child's hearing named elsewhere in the question
# («ابني لا يسمع، سمعنا عن طبيب») still reaches development. «عن بعد/قرب/طريق»
# is how far or how a child hears, never a topic.
_REPORTED_HEARING_RE = re.compile(
    _short_arabic_token(
        [stem + suffix
         for stem in ("سمع", "نسمع", "بنسمع", "تسمع", "بتسمع")
         for suffix in ("", "ني", "ه", "ها", "نا", "ك", "هم")])
    + r"(?=(?:\s+" + _spelled_words([
        "أحد", "احد", "حد", "كثير", "كثيرا", "الكثير", "كتير", "مرة", "مرارا",
        "دائما", "دايما", "سابقا", "مؤخرا", "شيئا", "شيء", "كلاما", "كلام",
        "مني", "منك", "منه", "منها", "منكم"]) + r"){0,2}\s+(?:"
    + _spelled_words(["عن"]) + r"(?!\s+(?:بعد|قرب|طريق)(?!\w))"
    + r"|" + _spelled_words(["من"]) + r"\s+" + _spelled_words([
        "الشيخ", "شيخ", "الإمام", "الامام", "إمام", "الخطيب", "الداعية",
        "المحاضر", "صديق", "صديقي", "صديقتي", "صديقه", "صديقها", "أصدقائي",
        "الناس", "الدكتور", "الدكتورة", "دكتور", "الطبيب", "الطبيبة", "طبيب",
        "الأستاذ", "الاستاذ", "الأستاذة", "الاستاذة", "المعلم", "المعلمة",
        "الإذاعة", "الاذاعة", "الراديو", "التلفزيون", "التلفاز",
        "يوتيوب", "اليوتيوب"])
    + r"|" + _spelled_words(["في"]) + r"\s+" + _spelled_words(_MEDIA + [
        "المحاضرة", "محاضرة", "الدرس", "درس", "الخطبة", "خطبة", "المسجد"])
    + r"|" + _spelled_words(["على", "علي"]) + r"\s+" + _spelled_words(_MEDIA)
    + r"|" + _spelled_words(["أن", "ان", "إن", "أنه", "انه", "إنه",
                             "أنها", "انها", "إنها"]) + r"(?!\s+شاء(?!\w))"
    + r"))",
    re.UNICODE,
)
# «ضعف سمعه أن يكون…» — after one of these nouns «سمعه» is the child's hearing
# whatever follows it.
_HEARING_HEAD_NOUNS = frozenset({
    "ضعف", "فقد", "فقدان", "فحص", "نقص", "حاسة", "حاسه", "قوة", "قوه",
    "سلامة", "سلامه", "مستوى", "اختبار", "تقييم", "مشكلة", "مشكله", "مشاكل",
})
_PREVIOUS_WORD_RE = re.compile(r"(\w+)\s+$")
# «تسمع/بتسمع» is also the third person feminine: «بنتي ما تسمع إن ناديتها»
# is the girl's hearing, whatever reported-speech lookalike follows it.
_SHE_HEARS_RE = re.compile(r"(?:[وف])?ب?تسمع")
_NEGATIONS = frozenset({"ما", "لا", "مش", "مو", "لم", "مب"})
_GIRL_REFERENTS = frozenset({
    "بنتي", "ابنتي", "بنتنا", "ابنتنا", "طفلتي", "طفلتنا", "رضيعتي", "رضيعتنا",
    "بنيتي", "البنت", "الطفلة", "بنوتي",
})


def _strip_conjunction(word: str) -> str:
    return word[1:] if len(word) > 2 and word[0] in "وف" else word


def _mask_reported_hearing(question: str) -> str:
    def mask(match: "re.Match[str]") -> str:
        # A bounded window keeps this constant per match on a 50k-char input.
        before = re.sub(_MARKS, "", question[max(0, match.start() - 48):match.start()])
        previous = _PREVIOUS_WORD_RE.search(before)
        if previous and previous.group(1) in _HEARING_HEAD_NOUNS:
            return match.group()
        if _SHE_HEARS_RE.match(re.sub(_MARKS, "", match.group())):
            words = [_strip_conjunction(w) for w in re.findall(r"\w+", before)[-3:]]
            if (words and words[-1] in _NEGATIONS) or _GIRL_REFERENTS.intersection(words):
                return match.group()
        return " " * len(match.group())
    return _REPORTED_HEARING_RE.sub(mask, question)


# The Persian keyboard's yeh and kaf are the Arabic ones (privacy._keyboard
# does the same; «ى» stays itself). Not imported from there: privacy pulls in
# the DB layer, and the classifier sits on the request path of every question.
_KEYBOARD = str.maketrans({"\u06cc": "ي", "\u06a9": "ك"})

# «سمعت» is also feminine past tense: she heard. Restore that reading only
# with a child subject at a clause boundary and an explicit auditory object.
# A child mentioned elsewhere, an adult speaker, or «سمعت عن ...» is not enough.
_CHILD_HEARING_SUBJECT = (
    r"(?:^|[.!؟\n،؛]|\b(?:لأن|لان|لكن|إن|ان)\s+)\s*"
    r"(?:[وف])?(?:بنتي|ابنتي|بنتنا|ابنتنا|طفلتي|طفلتنا|رضيعتي|رضيعتنا)"
    r"\s+(?:هي\s+)?(?:ما\s+|لا\s+)?"
)
_AUDITORY_OBJECT = r"(?:(?:ال)?(?:صوت|أصوات|جرس|صفارة)|ندائي|نداء|اسمي|اسمها)(?!\w)"
_CHILD_PAST_HEARING_RE = re.compile(
    _CHILD_HEARING_SUBJECT + r"(?:"
    r"سمعت\s+" + _AUDITORY_OBJECT
    # An object pronoun needs its audible referent, not a reported topic.
    + r"|سمعت(?:ه|ها)\s+(?:لما|حين|عندما)\s+(?:رن|رنت|دق|دقت)\s+" + _AUDITORY_OBJECT
    # Parent heard the daughter explicitly report inability to perceive sound.
    + r"|سمعتها\s+(?:تقول|قالت)\s+(?:إنها|أنها|انها)\s+(?:لا|ما)\s+"
    r"تلتقط\s+(?:أي\s+)?" + _AUDITORY_OBJECT
    # Parent never heard the daughter respond to her name or a sound.
    + r"|سمعت(?:ه|ها)\s+(?:تستجيب|تلتفت|ترد)\s+(?:لل|ل|على\s+|إلى\s+)?"
    + _AUDITORY_OBJECT + r")",
    re.UNICODE,
)


# Maps clear Arabic keywords directly to domains. The key insight:
# these are unambiguous terms that an LLM would always classify the same way.
# Pattern: (regex_pattern, domain, confidence_description)
KEYWORD_RULES: List[Tuple[str, str]] = [
    # Fiqh / Islamic parenting — clear religious terms (incl. verb forms) (expanded: behavior+ritual phrases)
    #
    # Two bare tokens were removed here after measuring retrieval on real parent
    # questions; both are ordinary Arabic words whose everyday sense dominates
    # in a question about a child, and both were routing questions into the
    # islamic_parenting KB on their own:
    #   «غسل» matched «طفلي بيرفض يغسل سنانه» (brushing teeth). Ritual ghusl is
    #        still covered by «الغسل» / «غسل الجنابة» / «يغتسل» / «وضوء».
    #   «سنة» matched «طفلي عنده سنة ونص» (a year and a half). The Sunnah is
    #        still covered by the explicit phrases below plus «حديث»/«سنن الفطرة».
    # Narrowing a rule is the safe direction: the question falls through to the
    # LLM tier, which classifies it properly. Widening one is what mis-routes
    # silently.
    (r"صلاة|صيام|زكاة|حج|عمرة|قرآن|السنة النبوية|سنة النبي|سنن النبي|حديث|دعاء|أذكار|مسجد|وضوء|الغسل|غسل\s*الجنابة|غسل\s*الجمعة|حلال|حرام|بدعة|شرك|توحيد|إيمان|عبادة|فقه|سورة|آية|أخلاق|قيم|بر الوالدين|صفات المؤمن|تربية إسلامية|تعليم.*دين|تحفيظ.*قرآن|حفظ.*قرآن|مصحف|جزاء|ثواب|إثم|ذنب|توبة|استغفار|يصل[يي]|يصوم|يزكي|يحج|يدعو|يتوضأ|يغتسل|يتوب|يستغفر|الصلوات|الفجر|الظهر|العصر|المغرب|العشاء|الوضوء|الصيام|الزكاة|الحج|العمرة|القرآن|الحديث|الدعاء|الأذكار|المسجد|كذب|يكذب|كذب\s*أطفال|يسرق|يسرقون|يحب\s*الموسيقى|لبس\s*الذهب|يدخن|يسخر\s*من\s*الدين|يحبب|أح[ب]+ب|يحب\s*الغناء|أصلي\s*عن\s*طفلي|أصلي\s*مع\s*طفلي|أفلام\s*غير\s*مناسبة|سنن\s*الفطرة|حقوق\s*الطفل|عناد|يأثم|كذب\s*أبيض|آداب\s*المسجد|آداب\s*الدعاء|قواعد\s*إسلامية|يحرم\s*تعليم|يحرم|يسب\s*الدين|يدعو\s*أبنائي", "fiqh"),
    # Aqeedah — a child's questions about the Creator, the unseen, and the
    # hereafter. Ten units exist for these (7-9) but were unreachable: the
    # classifier never emitted `aqeedah`, so «بنتي بقت تسأل عن الموت» — a
    # question the app itself suggests — could not retrieve «ما بعد الموت؟».
    #
    # PHRASES ONLY, never bare tokens. «الله» is the most common word in
    # everyday Arabic (الحمد لله، إن شاء الله، ماشاء الله) and a bare rule on it
    # would route almost every question here — the same substring failure that
    # made «سم» match «يسمع» and answer ordinary questions with «اتصل بالطوارئ».
    # Each alternative below has to carry a question ABOUT belief to fire.
    (r"من\s*هو\s*الله|أين\s*الله|شكل\s*الله|وين\s*ربنا|مين\s*ربنا"
     r"|يسأل\s*عن\s*(الله|ربنا|الدين)|بتسأل\s*عن\s*(الله|ربنا|الدين)"
     r"|تسأل\s*عن\s*(الله|ربنا)|بيسأل\s*عن\s*(الله|ربنا)"
     r"|بعد\s*الموت|الحياة\s*الآخرة|يوم\s*القيامة|الجنة\s*والنار"
     # «بنتي بقت تسأل عن الموت» — the app's own suggested question. Anchored on
     # a child ASKING about death (a creed question) so it can't catch a
     # bereavement or a medical question that merely mentions the word.
     r"|(يسأل|تسأل|بيسأل|بتسأل|سألني|سألتني)\s*عن\s*(ال)?موت"
     r"|أركان\s*الإيمان|القضاء\s*والقدر|أسماء\s*الله|صفات\s*الله"
     r"|ليه\s*خلقنا|لماذا\s*خلقنا|مين\s*خلق|من\s*خلق\s*(الله|الكون|الناس)"
     r"|وجود\s*الله|يشك\s*في\s*(الله|الدين)|تشك\s*في\s*(الله|الدين)"
     r"|الملائكة|شبهات|إلحاد|ملحد|مراقبة\s*الله|يراقبنا", "aqeedah"),
    # Cyber — digital/screen/gaming terms (expanded: streaming, social, platform names)
    (r"إدمان\s*(ألعاب|إنترنت|شاشة|هاتف|موبايل|تيك\s*توك|يوتيوب|فيديو|بلاي\s*ستيشن|xbox|نيتفلكس|نتفلكس|يوتيوب|سوشال|ألعاب)|تيك\s*توك|يوتيوب|شاشة|هاتف|موبايل|إنترنت|سوشيال|سوشال\s*ميديا|فيسبوك|واتساب|سناب|تويتر|إنستغرام|انستقرام|انستا|فايبر|فكونتاكت|واتس\s*اب|تليجرام|تلجرام|تويت|ريلز|لايك|followers|تنمر\s*إلكتروني|تنمر\s*رقمي|أمان\s*رقمي|خصوصية|محتوى\s*غير\s*لائق|محتويات\s*إباحية|إباحية|العاب\s*إلكترونية|بلايستيشن|screen|تلفزيون|أندرويد|ios|تطبيقات|porn|محتوى.*رقمي|رقمي|سيبراني|إلكتروني|محتوى\s*عنيف|ألعاب\s*مخيفة|قناة\s*سيئة|مواقع|أونلاين|تواصل\s*مع\s*غريب|غريب\s*على\s*النت|إرسال\s*صور|ترسل\s*صور|رسائل\s*لولد|حدود\s*لاستخدام\s*الشاشة|ساعات\s*على\s*الموبايل|كلمات\s*من\s*النت|إنستغرام|يسكرولين|فيس\s*بوك|واتس\s*أب", "cyber"),
    # Medical — clear health/psychological terms (incl. verb forms) (expanded: more clinical terms)
    (r"توحد|اضطراب|طيف\s*توحد|autism|adhd|فرط\s*حركة|نقص\s*انتباه|قلق|اكتئاب|وسواس|وساوس|نوبات\s*هلع|فوبيا|رهاب|خوف|يخاف|غضب|نوبات|عدوان|عنف|ضرب|" + _BITE_TOKEN + r"|" + _SELF_BITE + r"|قضم|صراخ|تبول\s*لاإرادي|تبول\s*فراش|تأتأة|تلعثم|كلام|يتكلم|نطق|تخاطب|تأخر\s*نطق|تأخر\s*كلام|تأخر\s*نمائي|تقييم|تشخيص|علاج|دواء|طبيب|أخصائي|نفسي|مستشفى|حالة|مرض|صحة\s*نفسية|نوم|أرق|أحلام.*مزعجة|كوابيس|نقص.*وزن|سمنة.*أطفال|بدانة|سمنة|حساسية|ربو|سكري.*أطفال|تشنجات|صرع|لجنة|إعاقة|إعاقات|صعوبات.*تعلم|عسر.*قراءة|عسر.*كتابة|dyslexia|انطواء|عزلة|انعزال|مخاوف|نفسي|توتر|قلقي|القلق|الاكتئاب|التوحد|الوسواس|الرهاب|الخوف|الغضب|النوم|الأرق|أظافره|أظافرها|يأكل\s*التراب|يشد\s*شعرها|كثير\s*البكاء|تخاف\s*من\s*الناس|لا\s*تريد\s*الذهاب\s*للمدرسة|لا\s*ينام|لا\s*يتكلم|يرفض\s*الأكل|يعنف\s*إخوته|يتبول\s*في\s*الفراش|تشد\s*شعرها|عنده\s*ADHD"
     # «ابني يدخن» alone stays a fiqh-only match above (bare moral-prohibition
     # framing, covered by an existing test). But smoking driven by friends is
     # a health/peer-pressure question, and the medical KB's smoking-cessation
     # units were unreachable because the fast-path never emitted "medical"
     # for it. This is additive (_keyword_fast_path returns every matching
     # domain, not just one), so the fiqh match is untouched — the question
     # now also retrieves from medical.
     r"|(صحاب|أصحاب|صديق|أصدقاء|رفاق).{0,15}(يدخن|بيدخن)|ضغط\s*(الأقران|أصدقاء|رفاق)|تدخين|سجاير|سيجارة|إدمان\s*النيكوتين|نيكوتين", "medical"),
    # Development — milestones, physical growth (expanded: more milestone phrases)
    (r"مشي|يمشي|حبو|زحف|أسنان|تسنين|نمو|تطور|مهارات\s*حركية|مهارات\s*حسية|مراحل\s*عمرية|شهور|سنين|وزن|طول|رضاعة|فطام|طعام|أكل|يأكل|تغذية|تدريب\s*حمام|نونية|كلام|كلمات|جمل|يتكلم|تحدث|تواصل|نظرة|ابتسامة|ملامسة|إمساك|جلوس|يجلس|وقوف|يقف|عناق|تفاعل|اجتماعي|" + _PLAY_TOKEN + r"|ألعاب\s*تعليمية|مهارات.*يدوية|تدخل\s*مبكر|تطعيم|تحصين|أطفال.*رضع|مولود|حديث.*ولادة|منعكس|انعكاس|حواس|بصر|" + _HEARING_TOKEN + r"|milestone|CDC|نمو.*طفل|تطور.*طفل|النمو|التطور|المشي|الحبو|الكلام|النطق|لا\s*يبتسم|لا\s*يجلس|لا\s*يمسك\s*الرضاعة|لا\s*يكلم|لا\s*يستعمل\s*الحمام|لا\s*يركض|متأخر\s*في\s*النمو|تأخر\s*في\s*النمو|أكل\s*رمل|يأكل\s*رمل|يضرب\s*نفسها|تضرب\s*نفسها", "development"),
    # App help — a question about «المربّي» itself (adding a child, child mode,
    # memory, deleting the account, is it free…). Without this rule such a
    # question went to the model classifier, came back "general", and was
    # answered with no retrieval at all — so the app-help units could never be
    # found and the model was left to guess at menus. Last on purpose: when a
    # question also matches a parenting rule («رحلة الصلاة» → fiqh), that
    # domain stays the label and both are searched.
    #
    # Narrow by construction (tests: test_app_help_routing.py). Only strong
    # signals live in this rule: names only the app uses, «وضع الطفل» with an
    # enter/exit verb or a PIN, and deleting «حسابي/بياناتي» when no other
    # platform is named. «التطبيق» + an app action is NOT here — parents say
    # «التطبيق» for putting advice into practice — it is the weak signal that
    # `_keyword_fast_path` handles after this list (alone → the model decides).
    # Card names are never triggers: «نصيحة اليوم» starts 28% of questions, and
    # «مهمة اليوم»/«خطوة اليوم»/«رمضان العائلة» are quoted to ask about a topic.
    (_APP_HELP_RULE, "app_help"),
]

# ── English fast path ──────────────────────────────────────────────────────────
# A fast-path hit skips the model classifier and the query rewrite, so every
# English rule is written for precision: an ambiguous word returns None and the
# model decides. Each rule has a gate:
#   "any"    — the phrase alone is unambiguous («potty training», «ADHD»).
#   "child"  — a child is named anywhere in the question («phone», «TikTok»:
#              «I found you on Facebook» is not a question about a child).
#   "before" — a child is named earlier in the same sentence, so it is the
#              child's fever / sleep / hitting, not the parent's or the wife's.
#   "tablet" — "child", unless medicine is mentioned («takes a tablet for…»).
#   "hearing"— "child", unless a court is mentioned («his hearing in court»).
# The gates are computed once per question (no lookahead scans the rest of the
# text), and "before" is a bounded look-back, so a 50k-character question stays
# linear — test_fast_path_is_linear_on_50k_characters.
_EN_CHILD_RE = re.compile(
    r"\b(?:child(?:ren)?|sons?|daughters?|bab(?:y|ies)|toddlers?|infants?|kids?|"
    r"teens?|teenagers?|newborns?|\d{1,2}[- ](?:years?|months?)[- ]olds?)\b", re.IGNORECASE)
_EN_BEFORE_WINDOW = 80
_EN_SENTENCE_BREAK_RE = re.compile(r"[.?!\n]")
_EN_MEDICINE_RE = re.compile(
    r"\b(?:medicines?|medications?|pills?|doses?|swallow\w*|mg|antibiotics?|vitamins?|"
    r"paracetamol|ibuprofen|tylenol|panadol"
    r"|(?:take|takes|took|taking|give|gives|gave|giving)\s+(?:him\s+|her\s+)?(?:a|an|one|two|half|the|his|her)"
    r"\s+(?:\w+\s+)?tablets?)\b", re.IGNORECASE)
_EN_COURT_RE = re.compile(r"\bcourt\b", re.IGNORECASE)
# A child's ability, not a refusal or a language: «isn't talking yet», never
# «isn't talking to me», «won't talk» or «doesn't speak Arabic».
_EN_ABILITY_END = (r"(?=\s*(?:[.?!,;:\n]|$)|\s+(?:yet|at\s+all|any\s+words?"
                   r"|a\s+(?:single\s+)?word|in\s+sentences)\b)")
_EN_SPEECH_ABILITY = (r"\b(?:(?:not|isn't|isnt|aren't)\s+(?:talking|speaking)"
                      r"|(?:cannot|can't|cant|can\s+not|doesn't|doesnt|does\s+not)\s+(?:talk|speak))"
                      + _EN_ABILITY_END)
# Hitting/biting is aggression only with a victim: «hits his sister», never
# «hit puberty», «hit the books», «hits the charts» or «biting cold».
_EN_VICTIM = (r"(?:(?:his|her|their|my|our)\s+(?:(?:little|younger|older|baby|big|new)\s+)?"
              r"(?:brothers?|sisters?|siblings?|friends?|teachers?|classmates?|cousins?)"
              r"|me|us|other\s+(?:kids|children|babies|toddlers|boys|girls)"
              r"|himself|herself|themselves|friends|classmates)\b")
# Walking/sitting/standing are milestones only when they are missing: «isn't
# walking at 18 months», never «is walking to school» or «can't stand broccoli».
_EN_MOTOR_DELAY = (r"\b(?:not|isn't|isnt|aren't|can't|cant|cannot|can\s+not|doesn't|doesnt|"
                   r"does\s+not|hasn't|has\s+not|unable\s+to|never)\s+(?:yet\s+)?(?:started\s+)?"
                   r"(?:walk(?:s|ing)?|sit(?:s|ting)?|stand(?:s|ing)?|crawl(?:s|ing)?)\b"
                   r"(?!\s+up\s+for\b)"
                   r"(?=\s*(?:[.?!,;:\n]|$)|\s+(?:yet|up|alone|unsupported|independently|without"
                   r"|at\s+\d+|by\s+(?:him|her)self|on\s+(?:his|her|their)\s+own)\b)")
# Play in its developmental sense only: «plays Fortnite» is cyber, «plays the
# violin» or «playing football» is nothing to route.
_EN_PLAY = (r"\b(?:plays?|playing|played)\s+with\s+(?:(?:his|her|their|other|the|any)\s+)?"
            r"(?:toys?|blocks|dolls?|kids|children|peers)\b"
            r"|\b(?:doesn't|doesnt|does\s+not|won't|will\s+not|never|isn't|is\s+not|not)\s+play(?:s|ing)?\b"
            r"(?=\s*(?:[.?!,;:\n]|$)|\s+(?:at\s+all|with\s+(?:toys|other|others|anyone|kids|children|peers)"
            r"|like\s+other|alone|yet)\b)")
_EN_PLATFORMS = (r"youtube|tiktok|instagram|facebook|whatsapp|snapchat|roblox|fortnite|minecraft|"
                 r"pubg|discord|twitch|playstation|xbox|nintendo")
_EN_FAST_VERB_NEXT = (r"(?:(?=\s*(?:[.?!,;\n]|$))|(?=\s+(?:in|during|on|for|until|till|when|if|"
                      r"while|at|all|the\s+whole|half|this|every)\b))")

_EN_RULES = {
    "fiqh": [
        ("any", r"\b(?:prayers?|zakat|umrah|quran|koran|hadiths?|wudu|wudhu|halal|haram|repentance|"
                r"islamic\s+manners|ramadan|mosques?|masjid|hijab|duas|du['’]a)\b"),
        ("any", r"\bhajj\b(?!\s+(?:committee|agency|agencies|ministry|visa|package|tour|operator)s?\b)"),
        # «I prayed for my son» is the parent's supplication, not the child's prayer.
        ("any", r"\bpray(?:s|ing|ed)?\b(?!\s+(?:for|mantis)\b)"),
        ("any", r"(?<!intermittent )\bfasting\b(?!\s+(?:blood|glucose|sugar|test)\b)|\bfast(?:s|ed)\b"),
        # The verb, never the adjective: «to fast in Ramadan», not «a fast car».
        ("any", r"\b(?:to|can|should|must|will|could|would|let\s+(?:him|her|them)|make\s+(?:him|her|them))"
                r"\s+fast\b" + _EN_FAST_VERB_NEXT),
        # «Salah» and «Dua» are also names (Mo Salah, Dua Lipa): only beside a
        # word that makes them the prayer.
        ("any", r"\b(?:pray(?:s|ing|ed)?|perform(?:s|ing)?|establish(?:ing)?|teach(?:ing)?|learn(?:ing)?|"
                r"miss(?:es|ed|ing)?|offer(?:s|ing)?|during|after|before|about|for|his|her|their|our|my|"
                r"your|the|child|son|daughter|kids?|children)\s+sala[ht]\b"
                r"|\bsala[ht]\s+(?:times?|on\s+time|properly|regularly"
                r"|in\s+(?:the\s+)?(?:mosque|masjid|congregation))\b"),
        ("any", r"\b(?:make|makes|making|made|say|says|saying|recite[sd]?|reciting|read(?:s|ing)?|"
                r"learn(?:s|ing)?|teach(?:es|ing)?|memori[sz](?:e|es|ing)|a|the|what|this|his|her|my|"
                r"our|their|daily|morning|evening|bedtime|for|about|child|son|daughter|kids?|children)"
                r"\s+dua\b(?!\s+lipa\b)"),
    ],
    "aqeedah": [
        ("any", r"\b(?:who\s+is\s+(?:Allah|God)|where\s+is\s+(?:Allah|God)|who\s+created\s+(?:Allah|God|us|the\s+universe)|why\s+did\s+(?:Allah|God)\s+create\s+us|after\s+death|afterlife|heaven\s+and\s+hell|pillars\s+of\s+faith|explain\s+(?:angels|heaven|hell)(?:\s+to\s+(?:my|our|the)\s+child)?|asks?\s+about\s+(?:Allah|God|death|angels))\b"),
    ],
    "cyber": [
        ("any", r"\b(?:screen\s+time|online\s+safety|cyber\s*bullying|digital\s+privacy)\b"),
        ("child", r"\b(?:smart\s*phones?|cell\s*phones?|phones?|ipads?|gaming|video\s+games?|"
                  r"online\s+games?|social\s+media|internet|" + _EN_PLATFORMS + r")\b"),
        ("tablet", r"\btablets?\b"),
    ],
    "medical": [
        ("any", r"\b(?:autism|adhd|dyslexia|speech\s+(?:delay|problems?|therapy|development)|delayed\s+speech)\b"),
        ("before", r"(?<!\bno )\b(?:anxiety|depression|tantrums?|fever\b(?!\s+pitch)|nightmares?|asthma|"
                   r"allerg(?:y|ies)|seizures?|stuttering|bedwetting|panic\s+attacks?|"
                   r"(?<!before )(?<!after )sleep(?:s|ing)?\b(?!\s+mode))\b"),
        ("any", r"\b(?:sleep|fever|anxiety|tantrums?|nightmares?)(?:\s+(?:tips|training|problems?|issues?|"
                r"regression|schedule|routine|habits?|advice))?\s+(?:(?:in|for|of|with)\s+)?"
                r"(?:my|our|a|the|your)\s+" + _EN_CHILD_RE.pattern),
        ("before", r"\b(?:hit(?:s|ting)?|bit(?:es|ing|e)?)\s+" + _EN_VICTIM),
        ("before", r"\b(?:biting|hitting)\s+(?:problems?|phases?|habits?|behaviou?rs?|stage)\b"),
        ("before", _EN_SPEECH_ABILITY),
    ],
    "development": [
        ("any", r"\b(?:motor\s+skills|breastfeeding|weaning|potty\s+training|"
                r"speech\s+(?:delay|problems?|therapy|development)|delayed\s+speech|"
                r"hearing\s+(?:loss|aids?|tests?|impair\w*|screening)|hard\s+of\s+hearing|"
                r"(?:pretend|imaginative|parallel|symbolic|make[- ]believe)\s+play)\b"),
        ("before", r"\b(?:crawl(?:s|ing)?|teething|milestones?|eye\s+contact|"
                   r"growth\s+(?:spurts?|delay|problems?|hormones?|issues?)|(?:slow|stunted|delayed|poor)\s+growth|"
                   r"(?:his|her|their)\s+growth\b(?!\s+mindset))\b"),
        ("before", _EN_MOTOR_DELAY),
        ("before", _EN_PLAY),
        ("before", _EN_SPEECH_ABILITY),
        # Hearing voices is not a hearing question (P2-c): no «voices» here.
        ("before", r"\bhear(?:s|d)?\s+(?:(?:her|his|the|a|any)\s+)?(?:name|bell|alarm|sounds?|noises?|nothing)\b"),
        ("before", r"\b(?:cannot|can't|cant|can\s+not|doesn't|doesnt|does\s+not)\s+hear\b"
                   r"(?!\s+(?:about|from|that|of)\b)"
                   r"|\b(?:does\s+not|doesn't|doesnt)\s+respond\s+to\s+(?:sounds?|(?:his|her)\s+name)\b"),
        ("hearing", r"\b(?:his|her|their|child's|son's|daughter's|baby's)\s+hearing\b"
                    r"(?!\s+(?:about|from|that|of)\b)"),
    ],
    "app_help": [
        # Strong signals only: the app's own «child mode», and deleting «my
        # account/data» when no other platform is named (see _OTHER_PLATFORMS).
        ("any", r"\b(?:exit|enter|enable|disable|leave|open|close|turn\s+(?:on|off)|switch\s+(?:on|off|to)"
                r"|get\s+out\s+of)\s+(?:the\s+)?child\s+mode\b"),
        ("own_platform", r"\bdelete\s+my\s+(?:account|data)\b"),
    ],
}
_EN_COMPILED = {
    domain: [(gate, re.compile(pattern, re.IGNORECASE)) for gate, pattern in rules]
    for domain, rules in _EN_RULES.items()
}
_OTHER_PLATFORMS_RE = re.compile(_OTHER_PLATFORMS)
# The English weak app signal — the same contract as _APP_GENERAL: «the app» +
# an app action adds app_help beside a parenting domain; alone, the model
# decides. «teach» is not an app action: «the app told me to teach my son…».
_EN_APP_NOUN_RE = re.compile(r"\b(?:this|the|your)\s+app\b", re.IGNORECASE)
_EN_APP_ACTION_RE = re.compile(
    r"\b(?:add(?:ing)?\s+(?:a|my|another|the|her|his)\s+(?:(?:second|new|other)\s+)?child|"
    r"change\s+the\s+language|language|subscription|subscribe|settings|account|notifications?|"
    r"free|offline|premium|price|login|log\s+in|sign\s+in|password|update|version|install|"
    r"uninstall|features?|works|working|load(?:s|ing)?|crash\w*)\b", re.IGNORECASE)
_EN_REPORTED_SPEECH = re.compile(
    r"\breported\s+speech\b|\bspeech\s+(?:was|is)\s+reported\b", re.IGNORECASE)
# Arabic text (an Arabic word of 2+ letters; a stray «أ» does not count) keeps
# its Arabic verdict. The English layer there only adds domains beside an
# Arabic match («ابني بيلعب Fortnite» → + cyber), never decides alone — except
# ADHD, which the Arabic rule spells only in lower case.
_AR_WORD_RE = re.compile(r"[ء-ي]{2,}")
_EN_ADHD_RE = re.compile(r"\badhd\b", re.IGNORECASE)
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{2}")


def _en_child_before(start: int, child_ends: List[int], breaks: List[int]) -> bool:
    """A child named in the same sentence, ending at most 80 characters before."""
    i = bisect.bisect_right(child_ends, start) - 1
    if i < 0 or start - child_ends[i] > _EN_BEFORE_WINDOW:
        return False
    j = bisect.bisect_right(breaks, child_ends[i])
    return j >= len(breaks) or breaks[j] >= start


def _english_domains(text: str, child_assumed: bool = False) -> set:
    """Domains the English rules find in `text` (see the gates above)."""
    text = text.replace("’", "'")
    child_ends = [m.end() for m in _EN_CHILD_RE.finditer(text)]
    has_child = child_assumed or bool(child_ends)
    breaks = [m.start() for m in _EN_SENTENCE_BREAK_RE.finditer(text)]
    found = set()
    for domain, rules in _EN_COMPILED.items():
        for gate, pattern in rules:
            if gate == "any":
                hit = pattern.search(text) is not None
            elif gate == "own_platform":
                hit = (pattern.search(text) is not None
                       and not _OTHER_PLATFORMS_RE.search(text))
            elif gate == "before" and not child_assumed:
                hit = any(_en_child_before(m.start(), child_ends, breaks)
                          for m in pattern.finditer(text))
            elif not has_child:
                hit = False
            elif gate == "tablet":
                hit = pattern.search(text) is not None and not _EN_MEDICINE_RE.search(text)
            elif gate == "hearing":
                hit = pattern.search(text) is not None and not _EN_COURT_RE.search(text)
            else:
                hit = pattern.search(text) is not None
            if hit:
                found.add(domain)
                break
    return found


def _english_weak_app(text: str) -> bool:
    return bool(_EN_APP_NOUN_RE.search(text) and _EN_APP_ACTION_RE.search(text))


def _english_signals(question: str) -> Tuple[set, set, bool]:
    """(strong, additive, weak_app) English signals for the fast path.

    strong   — enough on their own, like an Arabic rule match.
    additive — added only beside a domain some other rule already found.
    weak_app — «the app» + an app action (see _EN_APP_ACTION_RE).
    """
    if not _LATIN_WORD_RE.search(question):
        return set(), set(), False  # nothing English to read (most questions)
    text = _EN_REPORTED_SPEECH.sub(" ", question)
    if _AR_WORD_RE.search(text):
        strong = {"medical"} if _EN_ADHD_RE.search(text) else set()
        own_child = bool(_OWN_CHILD_RE.search(text))
        additive = _english_domains(text, child_assumed=own_child) - {"app_help"}
        return strong, additive, False
    return _english_domains(text), set(), _english_weak_app(text)


# Compile patterns once at module load
_COMPILED_RULES = [(re.compile(p, re.UNICODE), d) for p, d in KEYWORD_RULES]


CLASSIFY_PROMPT = """صنّف سؤال الوالد/الوالدة في مجال واحد أو أكثر من القائمة التالية.
اقرأ السؤال بعناية واختر المجال الأنسب للمحتوى الفعلي، وليس للكلمات المفتاحية فقط.

- fiqh: أي سؤال عن التربية الإسلامية، دين، شريعة، القرآن، السنة النبوية، الصلاة، الصيام، تربية البنات أو الأولاد من منظور إسلامي، الحلال والحرام في التربية
- medical: الصحة النفسية والسلوك — سواء كان سلوكًا يوميًا عاديًا أو حالة تحتاج مختصًا. يشمل: القلق، الاكتئاب، التوحد، فرط الحركة، التأخر النمائي، استشارة طبيب أو أخصائي نفسي؛ **وكذلك** السلوك اليومي والمشاعر والعلاقات: الخلافات مع الأصدقاء، الانطواء والانسحاب، رفض المدرسة أو البكاء عند الذهاب، الغيرة بين الإخوة، الثقة بالنفس، الحزن، الخجل، العناد، الخوف (من الظلام أو غيره)، الكذب، إدارة الوقت والمذاكرة
- aqeedah: أسئلة الطفل عن الخالق والغيب: من هو الله، أين الله، لماذا خلقنا، ما بعد الموت، الجنة والنار، الملائكة، أركان الإيمان، القضاء والقدر، الشك أو الشبهات حول الدين. (يختلف عن fiqh: هذا عن **الاعتقاد** لا عن الأحكام والعبادات العملية.)
- cyber: شاشات، إدمان ألعاب فيديو إلكترونية، هاتف ذكي، إنترنت، يوتيوب، تيك توك، تنمر إلكتروني عبر الإنترنت، أمان رقمي، مواقع التواصل الاجتماعي
- development: نمو جسدي، مراحل عمرية طبيعية، مشي، أسنان، مهارات حركية، إعاقة، تدخل مبكر، كلام وتطور اللغة
- general: أسئلة لا علاقة لها بالطفل أصلًا (وصفة طعام، رياضة، طقس، أخبار، برمجة). لا تستخدمه أبدًا لسؤال يتحدث عن ابن الوالد أو ابنته أو عن سلوكهما أو مشاعرهما أو علاقاتهما أو مدرستهما — مهما بدا السؤال عاديًا أو بسيطًا، فله مجال تربوي.

تنبيه مهم: مجرد أن السؤال عن صفة أو سلوك عام (خوف، غيرة، كذب، عناد، خجل) لا يجعله fiqh تلقائيًا.
استخدم fiqh فقط لو فيه إشارة دينية صريحة (حكم شرعي، عبادة، حلال/حرام، قرآن، سنة). غير كده فهو medical.
مثال: «بنتي عندها غيرة من أخوها الصغير» → medical (سلوك وعلاقات)، مش fiqh.
مثال: «طفلتي خايفة من الضلمة بالليل» → medical (خوف)، مش fiqh.
مثال: «عايز أعلم ابني يصلي إزاي» → fiqh (عبادة صريحة).

السؤال: {question}

أجب بـ JSON فقط، بدون أي نص خارج الأقواس:
{{"domains": ["fiqh"]}}"""


# ── Fast-Path ──────────────────────────────────────────────────────────────────

def _keyword_fast_path(question: str) -> Optional[List[str]]:
    """Check keyword rules. Returns domain list if unambiguous match found."""
    matched: List[str] = []
    question = question.translate(_KEYBOARD)
    rule_text = _mask_reported_hearing(question)
    en_strong, en_additive, en_weak_app = _english_signals(question)
    rule_hits = {domain for pattern, domain in _COMPILED_RULES if pattern.search(rule_text)}
    found = rule_hits | en_strong
    if found:
        # Additive English (inside Arabic text) never decides on its own.
        found |= en_additive
    for _pattern, domain in _COMPILED_RULES:
        if domain in found and domain not in matched:
            matched.append(domain)
    hearing_text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", question)
    if "development" not in matched and (
            _CHILD_PAST_HEARING_RE.search(hearing_text)
            # The masked text: a reported «سمعه من…» is no hearing-loss context.
            or _hearing_aid(re.sub(r"[\u064b-\u065f\u0670\u0640]", "", rule_text))):
        # Same slot the development rule would give it: after the parenting
        # domains, before app_help (last on purpose — see KEYWORD_RULES).
        at = matched.index("app_help") if "app_help" in matched else len(matched)
        matched.insert(at, "development")
    if "app_help" not in matched and (_APP_GENERAL_RE.search(question) or en_weak_app):
        # The weak app signal (see _APP_GENERAL): beside a parenting domain it
        # adds app_help to the search; alone it defers to the model
        # (_classify_cached).
        if not matched:
            return None
        matched.append("app_help")
    if matched:
        logger.debug("Keyword fast-path matched '%s...' → %s", question[:40], matched)
        return matched
    return None


# ── LLM Classifier (fallback) ─────────────────────────────────────────────────

def _classifier_provider():
    """Provider for the LLM tier, or None when the call must be skipped.

    Follows the configured primary (paid cloud when that is what the app is
    running on) and falls back to the local Ollama host otherwise. Returns
    None while the auxiliary circuit is open, so a dead host costs 0ms after
    the first two discoveries instead of one timeout per question.
    """
    if aux_breaker.is_open():
        logger.debug("auxiliary circuit open — skipping the classifier LLM tier")
        return None
    return aux_cloud_provider(timeout=CLASSIFIER_TIMEOUT_S) or OllamaProvider(
        base_url=_OLLAMA_ENDPOINT, model=CLASSIFIER_MODEL,
        timeout=CLASSIFIER_TIMEOUT_S,
    )


# Possessive forms a parent uses for their own child. Deliberately first-person
# only: «الأطفال ياكلوا إيه» is a general question, «ابني مابياكلش» is not.
_OWN_CHILD_RE = re.compile(
    r"(ابن|إبن|بنت|طفل|طفلت|ولد|ابنت|إبنت|عيل|عيال|أولاد|اولاد|بنات|صغير|صغيرت)"
    r"(ي|ه?ي|تي)\b|\b(ابني|بنتي|طفلي|طفلتي|ولدي|ابنتي|عيالي|أولادي|اولادي|بناتي)\b"
)


def _mentions_own_child(question: str) -> bool:
    """True when the parent is asking about their own child.

    Used to veto a "general" (off-topic) verdict — see _parse_domains.
    """
    return bool(_OWN_CHILD_RE.search(question))


def _weak_app_signal(question: str) -> bool:
    """«التطبيق» next to an app action — the weak app signal (see _APP_GENERAL);
    in an English question, «the app» next to one (see _EN_APP_ACTION_RE)."""
    if _APP_GENERAL_RE.search(question):
        return True
    return not _AR_WORD_RE.search(question) and _english_weak_app(question)


def _parse_domains(raw: str, question: str) -> Optional[List[str]]:
    """Extract the domain list from the model's JSON answer, or None."""
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw[start:end])
        except json.JSONDecodeError:
            parsed = None
        # The model can emit anything; only a dict with a list of domains counts.
        domains = parsed.get("domains", []) if isinstance(parsed, dict) else []
        if not isinstance(domains, list):
            domains = []
        # A real parenting domain always wins over "general"; only fall
        # back to off-topic when the model found no parenting domain at all.
        filtered = [d for d in domains if d in VALID_DOMAINS]
        if filtered:
            logger.debug("LLM classified '%s...' as %s", question[:40], filtered)
            return filtered
        if any(d == "general" for d in domains):
            # "general" skips retrieval entirely and answers from nothing, so a
            # false positive costs a parent the whole knowledge base. Measured
            # on production: the model called «بنتي اتخانقت مع صاحبتها وقافلة
            # على نفسها» and «ابني مابيحبش يروح المدرسة وبيعيط» off-topic —
            # both ordinary parenting questions. The prompt now pushes back on
            # that, but a prompt is guidance, not a guarantee. When the parent
            # is plainly talking about their own child we refuse the verdict
            # and search broadly instead: a diluted answer beats none.
            #
            # Except beside the weak app signal: there «general» means "about the
            # app, not the child" — «كيف أضيف طفلي الثاني في التطبيق؟» — and
            # _classify_cached turns it into app_help.
            if _mentions_own_child(question) and not _weak_app_signal(question):
                logger.info(
                    "Overriding 'general' — question is about the parent's child: '%s...'",
                    question[:40],
                )
                return list(UNCERTAIN_DOMAINS)
            logger.debug("LLM classified '%s...' as general (off-topic)", question[:40])
            return ["general"]

    logger.warning("LLM returned invalid domain list: %s", raw[:200])
    return None


def _call_llm(question: str) -> Optional[List[str]]:
    """One classification call. Returns a domain list, or None on failure."""
    provider = _classifier_provider()
    if provider is None:
        return None
    raw = aux_generate(
        provider, CLASSIFY_PROMPT.format(question=question),
        options={"temperature": 0.1, "num_predict": 60},
        tier="classifier",
    )
    if not raw:
        return None
    return _parse_domains(raw, question)


# ── Public API ─────────────────────────────────────────────────────────────────

class _ClassificationUnavailable(Exception):
    """Internal signal that the LLM tier could not answer.

    It exists so the failure is NOT memoised: lru_cache stores return values
    but not exceptions, so a transient outage can't freeze the broad fallback
    into the cache for the lifetime of the process. Never escapes this module.
    """


@lru_cache(maxsize=256)
def _classify_cached(question: str) -> Tuple[str, ...]:
    """Tiers 1 and 3 behind the LRU cache (tier 2). Raises when both fail."""
    fast_result = _keyword_fast_path(question)
    if fast_result:
        return tuple(fast_result)

    llm_result = _call_llm(question)
    if llm_result == ["general"] and _weak_app_signal(question):
        # «التطبيق» + an app action, and the model found no parenting domain:
        # a question about the app. A parenting domain from the model is kept
        # as it is — «بعد التطبيق لمدة أسبوع لم تنجح الطريقة…» stays parenting.
        return ("app_help",)
    if llm_result:
        return tuple(llm_result)

    raise _ClassificationUnavailable(question[:40])


def classify_domains(question: str) -> List[str]:
    """
    Classify a question into relevant domains.

    Tier 1: Keyword fast-path (instant, ~0ms)
    Tier 2: LRU cache (instant for repeated queries)
    Tier 3: LLM on the configured primary provider (only for ambiguous questions)

    When every tier fails, returns UNCERTAIN_DOMAINS — a broad search across
    all domains — rather than guessing one. Detect it with is_uncertain().
    """
    if not question or not question.strip():
        return list(UNCERTAIN_DOMAINS)

    try:
        return list(_classify_cached(question))
    except _ClassificationUnavailable:
        fallback = fallback_domains(question)
        logger.info(
            "All classifier tiers failed for '%s...' — searching %s",
            question[:40], fallback,
        )
        return fallback


def fallback_domains(question: str) -> List[str]:
    """The domains for a question the model gave no verdict on — down, slow,
    unparseable, or naming no domain.

    The keywords' verdict when they have one (the router's deadline can expire
    before a busy executor even ran the fast path). Otherwise the broad search,
    UNCERTAIN_DOMAINS — except when «التطبيق» + an app action is the only
    evidence: then the model's silence reads like its «general», no parenting
    domain was found, and the question goes to app_help. Computed, never
    cached — once the model is back, the next call gets its verdict.
    """
    if not question or not question.strip():
        return list(UNCERTAIN_DOMAINS)
    fast = _keyword_fast_path(question)
    if fast:
        return fast
    if _weak_app_signal(question):
        return ["app_help"]
    return list(UNCERTAIN_DOMAINS)


def is_uncertain(domains: Sequence[str]) -> bool:
    """True when `domains` is the «تعذّر التصنيف» broad fallback rather than a
    real classification — callers must not label a reply with domains[0]."""
    return tuple(domains) == UNCERTAIN_DOMAINS


def classify_single_domain(question: str) -> str:
    """Back-compat wrapper returning the single top domain as string."""
    return classify_domains(question)[0]


def matched_fast_path(question: str) -> bool:
    """True when the keyword fast-path alone classifies the question —
    i.e. it already uses KB-aligned vocabulary (query rewriting can be
    skipped without losing recall)."""
    if not question or not question.strip():
        return False
    return bool(_keyword_fast_path(question))
