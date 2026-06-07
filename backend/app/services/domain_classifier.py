"""
domain_classifier.py — v2.1 (LLM-based, home-server aware)

Classifies questions into domains using a small local LLM instead of keyword matching.
This handles Arabic morphology, synonyms, and context naturally.
Uses env-driven home-server URL (OLLAMA_LOCAL_BASE_URL / OLLAMA_LOCAL_FAST_MODEL).
"""
import json
import logging
import os
import urllib.request
from typing import List

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
_LOCAL_BASE = os.environ.get("OLLAMA_LOCAL_BASE_URL", "http://100.109.163.64:11434")
OLLAMA_URL = f"{_LOCAL_BASE.rstrip('/')}/api/generate"
CLASSIFIER_MODEL = os.environ.get("OLLAMA_LOCAL_FAST_MODEL", "qwen2.5:3b")

VALID_DOMAINS = {"fiqh", "medical", "cyber", "development"}

CLASSIFY_PROMPT = """صنّف سؤال الوالد/الوالدة في مجال واحد أو أكثر من القائمة التالية.
اقرأ السؤال بعناية واختر المجال الأنسب للمحتوى الفعلي، وليس للكلمات المفتاحية فقط.

- fiqh: أي سؤال عن التربية الإسلامية، أخلاق، قيم، دين، شريعة، القرآن، السنة النبوية، الصلاة، الصيام، تربية البنات أو الأولاد من منظور إسلامي، الحلال والحرام في التربية
- medical: صحة نفسية، سلوكيات مقلقة، قلق، اكتئاب، توحد، فرط حركة، تأخر نمائي، استشارة طبيب أو أخصائي نفسي، علاج نفسي
- cyber: شاشات، إدمان ألعاب فيديو إلكترونية، هاتف ذكي، إنترنت، يوتيوب، تيك توك، تنمر إلكتروني عبر الإنترنت، أمان رقمي، مواقع التواصل الاجتماعي
- development: نمو جسدي، مراحل عمرية طبيعية، مشي، أسنان، مهارات حركية، إعاقة، تدخل مبكر، كلام وتطور اللغة

السؤال: {question}

أجب بـ JSON فقط، بدون أي نص خارج الأقواس:
{{"domains": ["fiqh"]}}"""

# ── Core ───────────────────────────────────────────────────────────────────────

def _call_llm(question: str) -> List[str] | None:
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

        # Extract JSON object from response (handles markdown fences, thinking tokens, etc.)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(raw[start:end])
            domains = result.get("domains", [])
            # Filter to valid domains only
            filtered = [d for d in domains if d in VALID_DOMAINS]
            if filtered:
                logger.debug("LLM classified '%s...' as %s", question[:40], filtered)
                return filtered

        logger.warning("LLM returned invalid domain list: %s", raw[:200])
        return None

    except Exception as e:
        logger.warning("LLM classification failed: %s", e)
        return None


def classify_domains(question: str) -> List[str]:
    """
    Classify a question into relevant domains using LLM.
    Falls back to 'medical' if LLM fails (safe default for child-related queries).
    """
    if not question or not question.strip():
        return ["medical"]

    llm_result = _call_llm(question)
    if llm_result:
        return llm_result

    logger.info("LLM classifier failed for '%s...', falling back to medical", question[:40])
    return ["medical"]


def classify_single_domain(question: str) -> str:
    """Back-compat wrapper returning the single top domain as string."""
    return classify_domains(question)[0]
