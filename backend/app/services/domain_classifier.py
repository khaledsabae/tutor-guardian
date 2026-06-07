"""
domain_classifier.py — v3.0 (fast-path + cache + LLM fallback)

Classifies questions into domains using three-tier approach:
  1. Keyword fast-path (0ms, covers ~60% of queries)
  2. LRU cache (instant for repeated queries)
  3. LLM fallback (only for ambiguous/complex questions)

This approach saves 3-5s on the majority of requests while preserving
accuracy for the edge cases that need it.
"""

import json
import logging
import os
import re
import urllib.request
from functools import lru_cache
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
# Resolution: OLLAMA_BASE_URL (Docker/general) first, then OLLAMA_LOCAL_BASE_URL (home-server overrides).
# In Docker production, set OLLAMA_BASE_URL=http://ollama:11434 and everything works.
# On home server, OLLAMA_LOCAL_BASE_URL takes precedence for local-only models.
_OLLAMA_ENDPOINT = (
    os.environ.get("OLLAMA_LOCAL_BASE_URL") or
    os.environ.get("OLLAMA_BASE_URL", "http://100.109.163.64:11434")
)
OLLAMA_URL = f"{_OLLAMA_ENDPOINT.rstrip('/')}/api/generate"
CLASSIFIER_MODEL = (
    os.environ.get("OLLAMA_LOCAL_FAST_MODEL") or
    os.environ.get("OLLAMA_FAST_MODEL", "qwen2.5:3b")
)

VALID_DOMAINS = {"fiqh", "medical", "cyber", "development"}

# ── Keyword Fast-Path ──────────────────────────────────────────────────────────
# Maps clear Arabic keywords directly to domains. The key insight:
# these are unambiguous terms that an LLM would always classify the same way.
# Pattern: (regex_pattern, domain, confidence_description)
KEYWORD_RULES: List[Tuple[str, str]] = [
    # Fiqh / Islamic parenting — clear religious terms (incl. verb forms)
    (r"صلاة|صيام|زكاة|حج|عمرة|قرآن|سنة|حديث|دعاء|أذكار|مسجد|وضوء|غسل|حلال|حرام|بدعة|شرك|توحيد|إيمان|عبادة|فقه|سورة|آية|أخلاق|قيم|بر الوالدين|صفات المؤمن|تربية إسلامية|تعليم.*دين|تحفيظ.*قرآن|حفظ.*قرآن|مصحف|جزاء|ثواب|إثم|ذنب|توبة|استغفار|يصل[يي]|يصوم|يزكي|يحج|يدعو|يتوضأ|يغتسل|يتوب|يستغفر|الصلوات|الفجر|الظهر|العصر|المغرب|العشاء|الوضوء|الصيام|الزكاة|الحج|العمرة|القرآن|الحديث|الدعاء|الأذكار|المسجد", "fiqh"),
    # Cyber — digital/screen/gaming terms
    (r"إدمان\s*(ألعاب|إنترنت|شاشة|هاتف|موبايل|تيك\s*توك|يوتيوب|فيديو|بلاي\s*ستيشن|xbox|نيتفلكس|نتفلكس)|تيك\s*توك|يوتيوب|شاشة|هاتف|موبايل|إنترنت|سوشيال|فيسبوك|واتساب|سناب|تويتر|تنمر\s*إلكتروني|تنمر\s*رقمي|أمان\s*رقمي|خصوصية|محتوى\s*غير\s*لائق|محتويات\s*إباحية|إباحية|العاب\s*إلكترونية|بلايستيشن|screen|تلفزيون|أندرويد|ios|تطبيقات|porn|محتوى.*رقمي|رقمي|سيبراني|إلكتروني", "cyber"),
    # Medical — clear health/psychological terms (incl. verb forms)
    (r"توحد|اضطراب|طيف\s*توحد|autism|adhd|فرط\s*حركة|نقص\s*انتباه|قلق|اكتئاب|وسواس|وساوس|نوبات\s*هلع|فوبيا|رهاب|خوف|يخاف|غضب|نوبات|عدوان|عنف|ضرب|عض|قضم|صراخ|تبول\s*لاإرادي|تبول\s*فراش|تأتأة|تلعثم|كلام|يتكلم|نطق|تخاطب|تأخر\s*نطق|تأخر\s*كلام|تأخر\s*نمائي|تقييم|تشخيص|علاج|دواء|طبيب|أخصائي|نفسي|مستشفى|حالة|مرض|صحة\s*نفسية|نوم|أرق|أحلام.*مزعجة|كوابيس|نقص.*وزن|سمنة.*أطفال|بدانة|حساسية|ربو|سكري.*أطفال|تشنجات|صرع|لجنة|إعاقة|إعاقات|صعوبات.*تعلم|عسر.*قراءة|عسر.*كتابة|dyslexia|انطواء|عزلة|انعزال|مخاوف|نفسي|توتر|قلقي|القلق|الاكتئاب|التوحد|الوسواس|الرهاب|الخوف|الغضب|النوم|الأرق|أظافره|أظافرها", "medical"),
    # Development — milestones, physical growth
    (r"مشي|يمشي|حبو|زحف|أسنان|تسنين|نمو|تطور|مهارات\s*حركية|مهارات\s*حسية|مراحل\s*عمرية|شهور|سنين|وزن|طول|رضاعة|فطام|طعام|أكل|يأكل|تغذية|تدريب\s*حمام|نونية|كلام|كلمات|جمل|يتكلم|تحدث|تواصل|نظرة|ابتسامة|ملامسة|إمساك|جلوس|يجلس|وقوف|يقف|عناق|تفاعل|اجتماعي|لعب|يلعب|ألعاب\s*تعليمية|مهارات.*يدوية|تدخل\s*مبكر|تطعيم|تحصين|أطفال.*رضع|مولود|حديث.*ولادة|منعكس|انعكاس|حواس|بصر|سمع|milestone|CDC|نمو.*طفل|تطور.*طفل|النمو|التطور|المشي|الحبو|الكلام|النطق", "development"),
]

# Compile patterns once at module load
_COMPILED_RULES = [(re.compile(p, re.UNICODE), d) for p, d in KEYWORD_RULES]


CLASSIFY_PROMPT = """صنّف سؤال الوالد/الوالدة في مجال واحد أو أكثر من القائمة التالية.
اقرأ السؤال بعناية واختر المجال الأنسب للمحتوى الفعلي، وليس للكلمات المفتاحية فقط.

- fiqh: أي سؤال عن التربية الإسلامية، أخلاق، قيم، دين، شريعة، القرآن، السنة النبوية، الصلاة، الصيام، تربية البنات أو الأولاد من منظور إسلامي، الحلال والحرام في التربية
- medical: صحة نفسية، سلوكيات مقلقة، قلق، اكتئاب، توحد، فرط حركة، تأخر نمائي، استشارة طبيب أو أخصائي نفسي، علاج نفسي
- cyber: شاشات، إدمان ألعاب فيديو إلكترونية، هاتف ذكي، إنترنت، يوتيوب، تيك توك، تنمر إلكتروني عبر الإنترنت، أمان رقمي، مواقع التواصل الاجتماعي
- development: نمو جسدي، مراحل عمرية طبيعية، مشي، أسنان، مهارات حركية، إعاقة، تدخل مبكر، كلام وتطور اللغة

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

def _call_llm(question: str) -> Optional[List[str]]:
    """Call home-server Ollama for classification. Returns list of domains or None on failure."""
    prompt = CLASSIFY_PROMPT.format(question=question)
    payload = json.dumps({
        "model": CLASSIFIER_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 60}
    }).encode()

    try:
        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            d = json.loads(r.read().decode())
        raw = d.get("response", "").strip()

        # Extract JSON object from response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(raw[start:end])
            domains = result.get("domains", [])
            filtered = [d for d in domains if d in VALID_DOMAINS]
            if filtered:
                logger.debug("LLM classified '%s...' as %s", question[:40], filtered)
                return filtered

        logger.warning("LLM returned invalid domain list: %s", raw[:200])
        return None

    except Exception as e:
        logger.warning("LLM classification failed: %s", e)
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=256)
def classify_domains(question: str) -> List[str]:
    """
    Classify a question into relevant domains.

    Tier 1: Keyword fast-path (instant, ~0ms)
    Tier 2: LRU cache (instant for repeated queries)
    Tier 3: LLM fallback (3-5s, only for ambiguous questions)

    Falls back to 'medical' if all tiers fail (safe default for child queries).
    """
    if not question or not question.strip():
        return ["medical"]

    # Tier 1: Keyword fast-path
    fast_result = _keyword_fast_path(question)
    if fast_result:
        return fast_result

    # Tier 3: LLM (Tier 2 is the LRU decorator, handled automatically)
    llm_result = _call_llm(question)
    if llm_result:
        # Bypass cache for LLM result? No — lru_cache already cached the question,
        # so it will return this value next time without calling LLM again.
        return llm_result

    logger.info("All classifier tiers failed for '%s...', falling back to medical", question[:40])
    return ["medical"]


def classify_single_domain(question: str) -> str:
    """Back-compat wrapper returning the single top domain as string."""
    return classify_domains(question)[0]
