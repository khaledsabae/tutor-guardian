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

import json
import logging
import os
import re
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

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
    os.environ.get("OLLAMA_BASE_URL", "http://100.109.163.64:11434")
)
CLASSIFIER_MODEL = (
    os.environ.get("OLLAMA_LOCAL_FAST_MODEL") or
    os.environ.get("OLLAMA_FAST_MODEL", "qwen2.5:3b")
)
# 60 predicted tokens need seconds, not a minute. The old 45s ceiling meant an
# unreachable host turned EVERY fast-path miss into a 45s wait before the
# answer even started being generated.
CLASSIFIER_TIMEOUT_S = int(os.environ.get("CLASSIFIER_TIMEOUT_S", str(AUX_TIMEOUT_S)))

VALID_DOMAINS = {"fiqh", "medical", "cyber", "development"}

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
UNCERTAIN_DOMAINS: Tuple[str, ...] = ("medical", "cyber", "fiqh", "development")

# ── Keyword Fast-Path ──────────────────────────────────────────────────────────
# Maps clear Arabic keywords directly to domains. The key insight:
# these are unambiguous terms that an LLM would always classify the same way.
# Pattern: (regex_pattern, domain, confidence_description)
KEYWORD_RULES: List[Tuple[str, str]] = [
    # Fiqh / Islamic parenting — clear religious terms (incl. verb forms) (expanded: behavior+ritual phrases)
    (r"صلاة|صيام|زكاة|حج|عمرة|قرآن|سنة|حديث|دعاء|أذكار|مسجد|وضوء|غسل|حلال|حرام|بدعة|شرك|توحيد|إيمان|عبادة|فقه|سورة|آية|أخلاق|قيم|بر الوالدين|صفات المؤمن|تربية إسلامية|تعليم.*دين|تحفيظ.*قرآن|حفظ.*قرآن|مصحف|جزاء|ثواب|إثم|ذنب|توبة|استغفار|يصل[يي]|يصوم|يزكي|يحج|يدعو|يتوضأ|يغتسل|يتوب|يستغفر|الصلوات|الفجر|الظهر|العصر|المغرب|العشاء|الوضوء|الصيام|الزكاة|الحج|العمرة|القرآن|الحديث|الدعاء|الأذكار|المسجد|كذب|يكذب|كذب\s*أطفال|يسرق|يسرقون|يحب\s*الموسيقى|لبس\s*الذهب|يدخن|يسخر\s*من\s*الدين|يحبب|أح[ب]+ب|يحب\s*الغناء|أصلي\s*عن\s*طفلي|أصلي\s*مع\s*طفلي|أفلام\s*غير\s*مناسبة|سنن\s*الفطرة|حقوق\s*الطفل|عناد|يأثم|كذب\s*أبيض|آداب\s*المسجد|آداب\s*الدعاء|قواعد\s*إسلامية|يحرم\s*تعليم|يحرم|يسب\s*الدين|يدعو\s*أبنائي", "fiqh"),
    # Cyber — digital/screen/gaming terms (expanded: streaming, social, platform names)
    (r"إدمان\s*(ألعاب|إنترنت|شاشة|هاتف|موبايل|تيك\s*توك|يوتيوب|فيديو|بلاي\s*ستيشن|xbox|نيتفلكس|نتفلكس|يوتيوب|سوشال|ألعاب)|تيك\s*توك|يوتيوب|شاشة|هاتف|موبايل|إنترنت|سوشيال|سوشال\s*ميديا|فيسبوك|واتساب|سناب|تويتر|إنستغرام|انستقرام|انستا|فايبر|فكونتاكت|واتس\s*اب|تليجرام|تلجرام|تويت|ريلز|لايك|followers|تنمر\s*إلكتروني|تنمر\s*رقمي|أمان\s*رقمي|خصوصية|محتوى\s*غير\s*لائق|محتويات\s*إباحية|إباحية|العاب\s*إلكترونية|بلايستيشن|screen|تلفزيون|أندرويد|ios|تطبيقات|porn|محتوى.*رقمي|رقمي|سيبراني|إلكتروني|محتوى\s*عنيف|ألعاب\s*مخيفة|قناة\s*سيئة|مواقع|أونلاين|تواصل\s*مع\s*غريب|غريب\s*على\s*النت|إرسال\s*صور|ترسل\s*صور|رسائل\s*لولد|حدود\s*لاستخدام\s*الشاشة|ساعات\s*على\s*الموبايل|كلمات\s*من\s*النت|إنستغرام|يسكرولين|فيس\s*بوك|واتس\s*أب", "cyber"),
    # Medical — clear health/psychological terms (incl. verb forms) (expanded: more clinical terms)
    (r"توحد|اضطراب|طيف\s*توحد|autism|adhd|فرط\s*حركة|نقص\s*انتباه|قلق|اكتئاب|وسواس|وساوس|نوبات\s*هلع|فوبيا|رهاب|خوف|يخاف|غضب|نوبات|عدوان|عنف|ضرب|عض|قضم|صراخ|تبول\s*لاإرادي|تبول\s*فراش|تأتأة|تلعثم|كلام|يتكلم|نطق|تخاطب|تأخر\s*نطق|تأخر\s*كلام|تأخر\s*نمائي|تقييم|تشخيص|علاج|دواء|طبيب|أخصائي|نفسي|مستشفى|حالة|مرض|صحة\s*نفسية|نوم|أرق|أحلام.*مزعجة|كوابيس|نقص.*وزن|سمنة.*أطفال|بدانة|سمنة|حساسية|ربو|سكري.*أطفال|تشنجات|صرع|لجنة|إعاقة|إعاقات|صعوبات.*تعلم|عسر.*قراءة|عسر.*كتابة|dyslexia|انطواء|عزلة|انعزال|مخاوف|نفسي|توتر|قلقي|القلق|الاكتئاب|التوحد|الوسواس|الرهاب|الخوف|الغضب|النوم|الأرق|أظافره|أظافرها|يأكل\s*التراب|يشد\s*شعرها|كثير\s*البكاء|تخاف\s*من\s*الناس|لا\s*تريد\s*الذهاب\s*للمدرسة|لا\s*ينام|لا\s*يتكلم|يرفض\s*الأكل|يعنف\s*إخوته|يتبول\s*في\s*الفراش|تشد\s*شعرها|عنده\s*ADHD", "medical"),
    # Development — milestones, physical growth (expanded: more milestone phrases)
    (r"مشي|يمشي|حبو|زحف|أسنان|تسنين|نمو|تطور|مهارات\s*حركية|مهارات\s*حسية|مراحل\s*عمرية|شهور|سنين|وزن|طول|رضاعة|فطام|طعام|أكل|يأكل|تغذية|تدريب\s*حمام|نونية|كلام|كلمات|جمل|يتكلم|تحدث|تواصل|نظرة|ابتسامة|ملامسة|إمساك|جلوس|يجلس|وقوف|يقف|عناق|تفاعل|اجتماعي|لعب|يلعب|ألعاب\s*تعليمية|مهارات.*يدوية|تدخل\s*مبكر|تطعيم|تحصين|أطفال.*رضع|مولود|حديث.*ولادة|منعكس|انعكاس|حواس|بصر|سمع|milestone|CDC|نمو.*طفل|تطور.*طفل|النمو|التطور|المشي|الحبو|الكلام|النطق|لا\s*يبتسم|لا\s*يجلس|لا\s*يمسك\s*الرضاعة|لا\s*يكلم|لا\s*يستعمل\s*الحمام|لا\s*يركض|متأخر\s*في\s*النمو|تأخر\s*في\s*النمو|أكل\s*رمل|يأكل\s*رمل|يضرب\s*نفسها|تضرب\s*نفسها", "development"),
]

# Compile patterns once at module load
_COMPILED_RULES = [(re.compile(p, re.UNICODE), d) for p, d in KEYWORD_RULES]


CLASSIFY_PROMPT = """صنّف سؤال الوالد/الوالدة في مجال واحد أو أكثر من القائمة التالية.
اقرأ السؤال بعناية واختر المجال الأنسب للمحتوى الفعلي، وليس للكلمات المفتاحية فقط.

- fiqh: أي سؤال عن التربية الإسلامية، أخلاق، قيم، دين، شريعة، القرآن، السنة النبوية، الصلاة، الصيام، تربية البنات أو الأولاد من منظور إسلامي، الحلال والحرام في التربية
- medical: الصحة النفسية والسلوك — سواء كان سلوكًا يوميًا عاديًا أو حالة تحتاج مختصًا. يشمل: القلق، الاكتئاب، التوحد، فرط الحركة، التأخر النمائي، استشارة طبيب أو أخصائي نفسي؛ **وكذلك** السلوك اليومي والمشاعر والعلاقات: الخلافات مع الأصدقاء، الانطواء والانسحاب، رفض المدرسة أو البكاء عند الذهاب، الغيرة بين الإخوة، الثقة بالنفس، الحزن، الخجل، العناد، إدارة الوقت والمذاكرة
- cyber: شاشات، إدمان ألعاب فيديو إلكترونية، هاتف ذكي، إنترنت، يوتيوب، تيك توك، تنمر إلكتروني عبر الإنترنت، أمان رقمي، مواقع التواصل الاجتماعي
- development: نمو جسدي، مراحل عمرية طبيعية، مشي، أسنان، مهارات حركية، إعاقة، تدخل مبكر، كلام وتطور اللغة
- general: أسئلة لا علاقة لها بالطفل أصلًا (وصفة طعام، رياضة، طقس، أخبار، برمجة). لا تستخدمه أبدًا لسؤال يتحدث عن ابن الوالد أو ابنته أو عن سلوكهما أو مشاعرهما أو علاقاتهما أو مدرستهما — مهما بدا السؤال عاديًا أو بسيطًا، فله مجال تربوي.

السؤال: {question}

أجب بـ JSON فقط، بدون أي نص خارج الأقواس:
{{"domains": ["fiqh"]}}"""


# ── Fast-Path ──────────────────────────────────────────────────────────────────

def _keyword_fast_path(question: str) -> Optional[List[str]]:
    """Check keyword rules. Returns domain list if unambiguous match found."""
    matched: List[str] = []
    for pattern, domain in _COMPILED_RULES:
        if pattern.search(question):
            if domain not in matched:
                matched.append(domain)
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
            if _mentions_own_child(question):
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
        logger.info(
            "All classifier tiers failed for '%s...' — searching all domains",
            question[:40],
        )
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
