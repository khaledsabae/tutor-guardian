#!/usr/bin/env python3
"""Generate flashcards + quizzes for the 25 new lessons (the _bNN ones) from
their own text, using the local Ollama model with forced-JSON output. Saves
files under docs/lesson_assets/ and links them into docs/lesson_index.json so
the lesson screen shows '📇 فلاش كاردز' and '❓ اختبر نفسك'.

Extractive Q/A from the (well-written) lesson summary — the local model is
reliable for this. Output is validated, CJK/glued-Latin stripped, retried.

Run:  python scripts/gen_flashcards_quizzes.py [--limit N] [--only <lesson_id>]
"""
import argparse
import json
import os
import pathlib
import re
import urllib.request

BASE = pathlib.Path(__file__).resolve().parent.parent
LESSONS_DIR = BASE / "knowledge_base" / "curriculum" / "lessons"
FC_DIR = BASE / "docs" / "lesson_assets" / "flashcards"
QZ_DIR = BASE / "docs" / "lesson_assets" / "quizzes"
INDEX = BASE / "docs" / "lesson_index.json"

OLLAMA = (os.environ.get("OLLAMA_LOCAL_BASE_URL")
          or os.environ.get("OLLAMA_BASE_URL", "http://100.109.163.64:11434"))
MODEL = os.environ.get("FC_MODEL", "qwen2.5:3b")

_CJK = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿가-힯＀-￯]+")
_GLUED_LATIN = re.compile(r"(?<=[؀-ۿ])[A-Za-z]+|[A-Za-z]+(?=[؀-ۿ])")


def clean(s: str) -> str:
    if not isinstance(s, str):
        return s
    s = _CJK.sub("", s)
    s = _GLUED_LATIN.sub("", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def ollama_json(prompt: str, retries: int = 3):
    payload = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "format": "json", "options": {"temperature": 0.3, "num_predict": 900},
    }).encode()
    for _ in range(retries):
        try:
            req = urllib.request.Request(
                f"{OLLAMA.rstrip('/')}/api/generate", data=payload,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                raw = json.loads(r.read().decode()).get("response", "")
            return json.loads(raw)
        except Exception:
            continue
    return None


FC_PROMPT = """أنت تصمم بطاقات تعليمية (فلاش كاردز) لوالد عربي من نص الدرس التالي.
العنوان: {title}
النص: {summary}
النشاط: {try_this}

أنشئ 4 بطاقات. كل بطاقة: "front" سؤال قصير، "back" إجابة عملية موجزة (سطر أو سطرين).
أجب بـ JSON فقط بهذا الشكل بالضبط:
{{"cards":[{{"front":"...","back":"..."}}]}}"""

QZ_PROMPT = """أنت تصمم اختباراً قصيراً لوالد عربي من نص الدرس التالي.
العنوان: {title}
النص: {summary}

أنشئ 3 أسئلة اختيار من متعدد. كل سؤال: "question"، و"answerOptions" قائمة من 3 خيارات،
كل خيار له "text" و"isCorrect" (واحد صحيح فقط) و"rationale" قصير، و"hint" تلميح قصير.
أجب بـ JSON فقط بهذا الشكل بالضبط:
{{"questions":[{{"question":"...","answerOptions":[{{"text":"...","isCorrect":true,"rationale":"..."}},{{"text":"...","isCorrect":false,"rationale":"..."}},{{"text":"...","isCorrect":false,"rationale":"..."}}],"hint":"..."}}]}}"""


def valid_cards(obj):
    cards = (obj or {}).get("cards")
    if not isinstance(cards, list) or not cards:
        return None
    out = []
    for c in cards:
        f, b = clean(c.get("front", "")), clean(c.get("back", ""))
        if f and b:
            out.append({"front": f, "back": b})
    return out or None


def valid_quiz(obj):
    qs = (obj or {}).get("questions")
    if not isinstance(qs, list) or not qs:
        return None
    out = []
    for q in qs:
        opts = q.get("answerOptions")
        if not isinstance(opts, list) or len(opts) < 2:
            continue
        co = [o for o in opts if o.get("isCorrect")]
        if len(co) != 1:
            continue
        cleaned = [{"text": clean(o.get("text", "")),
                    "isCorrect": bool(o.get("isCorrect")),
                    "rationale": clean(o.get("rationale", ""))}
                   for o in opts if clean(o.get("text", ""))]
        question = clean(q.get("question", ""))
        if question and len(cleaned) >= 2 and any(o["isCorrect"] for o in cleaned):
            out.append({"question": question, "answerOptions": cleaned,
                        "hint": clean(q.get("hint", ""))})
    return out or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    FC_DIR.mkdir(parents=True, exist_ok=True)
    QZ_DIR.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    by_id = {l["lesson_id"]: l for l in index["lessons"]}

    new = [f for f in sorted(LESSONS_DIR.glob("*.json"))
           if f.stem.rsplit("_", 1)[-1].startswith("b")]
    if args.only:
        new = [f for f in new if f.stem == args.only]
    if args.limit:
        new = new[:args.limit]

    done = 0
    for f in new:
        d = json.loads(f.read_text(encoding="utf-8"))
        lid, title = d["id"], d["title"]
        cards = valid_cards(ollama_json(FC_PROMPT.format(
            title=title, summary=d["summary"], try_this=d.get("try_this", ""))))
        quiz = valid_quiz(ollama_json(QZ_PROMPT.format(
            title=title, summary=d["summary"])))
        if not cards or not quiz:
            print(f"✗ {lid}: cards={bool(cards)} quiz={bool(quiz)} — skipped")
            continue
        fc_id, qz_id = f"gen_{lid}_fc", f"gen_{lid}_qz"
        fc_rel = f"docs/lesson_assets/flashcards/{fc_id}.json"
        qz_rel = f"docs/lesson_assets/quizzes/{qz_id}.json"
        (FC_DIR / f"{fc_id}.json").write_text(
            json.dumps({"title": f"{title} — بطاقات", "cards": cards},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        (QZ_DIR / f"{qz_id}.json").write_text(
            json.dumps({"title": f"{title} — اختبار", "questions": quiz},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        entry = by_id.get(lid)
        if entry is not None:
            a = entry.setdefault("assets", {})
            a["flashcards"] = [{"id": fc_id, "file": fc_rel,
                                "title": f"{title} — بطاقات", "item_count": len(cards)}]
            a["quizzes"] = [{"id": qz_id, "file": qz_rel,
                             "title": f"{title} — اختبار", "item_count": len(quiz)}]
        done += 1
        print(f"✓ {lid}: {len(cards)} cards, {len(quiz)} quiz Qs")

    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"\nDone: {done}/{len(new)} lessons got flashcards+quizzes")


if __name__ == "__main__":
    main()
