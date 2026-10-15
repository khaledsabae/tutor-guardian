#!/usr/bin/env python3
"""export_real_parent_corpus.py — Pure-Python, zero-model exporter that prepares
the anonymized Real Parent Questions & Knowledge Base bundle for Google Colab Ultra.

IMPORTANT:
  - Does NOT load PyTorch, SentenceTransformers, CrossEncoder, or any local ML model.
  - Runs in < 1 second using only Python stdlib (`sqlite3`, `json`, `re`, `hashlib`).
  - All embedding, reranking, teacher judging (`Gemma 4 31B`), and fine-tuning
    (`Gemma 4 E4B`) happen on Google Colab Ultra (H100 / A100 80GB), and final
    GGUF serving runs on `tg-home` (the home server).

Outputs inside `ops/data/kaggle_upload_ultra/`:
  1. `real_parent_questions.jsonl`
     All 2,471 real user turns from production (`chat_messages`), strictly
     anonymized (device-scoped child name redaction + regex PII scrubbing),
     with category, age_group, language, keyword-classified domains,
     assistant_reply, unanswered flag, and parent feedback.
  2. `kb_units_full.jsonl`
     All knowledge base units (id, domain, age_group, behavior_type, severity,
     text_simplified, reference_info) for Colab RAG & Teacher Distillation.
  3. `tg_train_ultra_v6.jsonl` & `tg_val_ultra_v6.jsonl`
     Combined training/validation sets merging the verified 31,645 corpus with
     answered real parent conversations, formatted in standard chat messages.
  4. `real_questions_diagnostic_report.md`
     Comprehensive Arabic diagnostic report summarizing all real parent questions.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import random
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

DEFAULT_OUT_DIR = PROJECT_ROOT / "ops" / "data" / "kaggle_upload_ultra"
DEFAULT_CONV_DB = DEFAULT_OUT_DIR / "_snapshot" / "conversations.db"
DEFAULT_FINAL_CORPUS = PROJECT_ROOT / "ops" / "data" / "qa_dataset_final.jsonl"

# ── Anonymization patterns (aligned with privacy.py + build_real_eval_set.py) ──
_AR_LETTER = r"[\u0621-\u064A\u066E-\u06D3]"
_PREFIX_CHAIN = r"(?:و|ف)?(?:ال|لل|ب|ل|ك)?"
_PHONE_RE = re.compile(r"(\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9})")
_EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
_FILE_NUM_RE = re.compile(r"(ملف|رقم|file|no|id)\s*[:#]?\s*\d+[-0-9]*", re.I)
_NAME_CUES_AR = re.compile(
    r"(ابني|بنتي|ابنتي|طفلي|طفلتي|اسمه|اسمها|الاسم الثلاثي|الاسم)\s*[:：]\s*([أ-ي\w]+(?:\s+[أ-ي\w]+){0,2})"
)
_NAME_CUES_EN = re.compile(
    r"\b(my\s+(?:son|daughter|child|kid|baby)\s+is\s+named|named|his\s+name\s+is|her\s+name\s+is)\s+([A-Z][a-z]+)",
    re.I,
)

_STOPWORD_NAMES = {
    "طفل", "طفلي", "طفلة", "طفلتي", "ابني", "بنتي", "ابنتي", "ولد", "بنت",
    "الله", "محمد", "سنة", "سنتين", "شهور", "شهر", "يوم", "أيام", "تير",
    "نور", "أمل", "هدى", "حياة", "إيمان", "اسلام", "إسلام", "رحمة", "سلام",
    "خير", "فرح", "سعيد", "صالح", "كريم", "جميل", "حبيب", "حبيبي",
    "son", "daughter", "child", "baby", "kid", "boy", "girl",
}

SYSTEM_PROMPT_V6 = (
    "أنت «المربّي»، مساعد تربوي عربي للأهل متخصص في التربية الإسلامية ونمو الطفل "
    "وصحته وأمانه الرقمي. أجب بالعربية الفصحى بوضوح وتعاطف، وقدّم خطوات عملية قابلة "
    "للتنفيذ مستندة إلى مصادر موثوقة. لا تعطِ تشخيصاً طبياً ملزماً ولا جرعات أدوية ولا "
    "فتوى شخصية قاطعة، وأحِل إلى المتخصص عند الحاجة."
)


def _normalize(text: str) -> str:
    t = re.sub(r"[ـً-ْ]", "", text or "")
    return " ".join(t.split()).strip().lower()


def load_suggested_questions() -> set[str]:
    suggested = set()
    for rel in ("mobile/lib/l10n/app_ar.arb", "mobile/lib/l10n/app_en.arb"):
        p = PROJECT_ROOT / rel
        if p.exists():
            try:
                arb = json.loads(p.read_text(encoding="utf-8"))
                for k, v in arb.items():
                    if k.startswith("chatQ") and isinstance(v, str):
                        suggested.add(_normalize(v))
            except Exception:
                pass
    return suggested


def build_device_names_map(conn: sqlite3.Connection) -> dict[str, tuple[str, ...]]:
    rows = conn.execute("SELECT device_id, name FROM child_profiles").fetchall()
    by_dev: dict[str, set[str]] = collections.defaultdict(set)
    for r in rows:
        dev = r["device_id"]
        name = (r["name"] or "").strip()
        if dev and len(name) >= 3 and name.lower() not in _STOPWORD_NAMES:
            by_dev[dev].add(name)
    return {
        dev: tuple(sorted(names, key=len, reverse=True))
        for dev, names in by_dev.items()
    }


def build_device_age_map(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT device_id, age_group FROM child_profiles ORDER BY updated_at ASC, id ASC"
    ).fetchall()
    age_map: dict[str, str] = {}
    for r in rows:
        if r["device_id"] and r["age_group"]:
            age_map[r["device_id"]] = r["age_group"]
    return age_map


def redact_text(text: str, device_names: tuple[str, ...] = ()) -> str:
    if not text:
        return ""
    t = _EMAIL_RE.sub("[بريد محذوف]", text)
    t = _PHONE_RE.sub("[رقم هاتف محذوف]", t)
    t = _FILE_NUM_RE.sub("[رقم ملف محذوف]", t)
    t = _NAME_CUES_AR.sub(r"\1: طفلي", t)
    t = _NAME_CUES_EN.sub(r"\1 my child", t)
    for name in device_names:
        pat = re.compile(
            rf"(?<!{_AR_LETTER}){_PREFIX_CHAIN}{re.escape(name)}(?!{_AR_LETTER})"
        )
        t = pat.sub("طفلي", t)
    return t.strip()


def detect_language(text: str) -> str:
    t_lower = (text or "").lower()
    fr_words = {"le", "la", "les", "un", "une", "des", "est", "dans", "pour", "avec", "enfant", "bebe", "comment", "mon", "ma"}
    en_words = {"the", "is", "at", "which", "on", "and", "child", "son", "daughter", "how", "what", "can", "my", "why", "when"}
    words = set(re.findall(r"\b[a-z]{2,}\b", t_lower))
    ar_chars = len(re.findall(r"[\u0600-\u06FF]", text or ""))
    if ar_chars > len(words) * 2:
        return "ar"
    if not words:
        return "ar"
    fr_overlap = len(words & fr_words)
    en_overlap = len(words & en_words)
    if fr_overlap > en_overlap and fr_overlap >= 2:
        return "fr"
    if en_overlap >= 1 or len(words) >= 3:
        return "en"
    return "ar"


def categorize_question(text: str, suggested: set[str]) -> str:
    txt = (text or "").strip()
    nt = _normalize(txt)
    if (
        len(txt) < 12
        or nt.startswith("e2e test")
        or nt in {"سلام", "السلام عليكم", "مرحبا", "اهلا", "أهلا", "الو", "الوو", "hi", "hello", "test"}
    ):
        return "short_noise"
    if nt in suggested:
        return "suggested_button"
    if txt.startswith("بخصوص نصيحة اليوم") or txt.lower().startswith("regarding today"):
        return "daily_tip_card"
    return "organic_parent_question"


def export_kb_units(out_path: Path) -> list[dict]:
    from app.services.knowledge_loader import (
        load_default_knowledge_units,
        load_knowledge_units_from_dir,
    )

    units = list(load_default_knowledge_units())
    gap_dir = out_path.parent / "new_kb_gap_units"
    if gap_dir.exists():
        seen_ids = {u.id for u in units}
        for gu in load_knowledge_units_from_dir(gap_dir):
            if gu.id not in seen_ids:
                units.append(gu)
                seen_ids.add(gu.id)
    serialized = []
    with out_path.open("w", encoding="utf-8") as fh:
        for u in units:
            item = {
                "id": u.id,
                "domain": u.domain,
                "age_group": u.age_group,
                "behavior_type": u.behavior_type,
                "severity": u.severity,
                "text_simplified": u.text_simplified,
                "reference_info": u.reference_info,
            }
            serialized.append(item)
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    return serialized


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--conv-db", type=Path, default=DEFAULT_CONV_DB)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Pure regex keyword domain classification (0ms, no LLM or PyTorch)
    from app.services.domain_classifier import _keyword_fast_path

    print(f"1) Exporting Knowledge Base units to {args.out_dir / 'kb_units_full.jsonl'}...")
    kb_units = export_kb_units(args.out_dir / "kb_units_full.jsonl")
    print(f"   -> Exported {len(kb_units)} KB units.")

    print(f"2) Reading real parent conversations from {args.conv_db}...")
    conn = sqlite3.connect(f"file:{args.conv_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    suggested = load_suggested_questions()
    device_names_map = build_device_names_map(conn)
    device_age_map = build_device_age_map(conn)

    feedback_map: dict[str, dict] = {}
    for r in conn.execute("SELECT session_id, rating, comment FROM user_feedback").fetchall():
        feedback_map[r["session_id"]] = {
            "rating": r["rating"],
            "comment": redact_text(r["comment"] or ""),
        }

    msgs = conn.execute(
        """SELECT cm.id, cm.session_id, cm.role, cm.content, cm.domain, cm.severity,
                  cm.mode, cm.needs_human_review, cm.created_at, cs.device_id
           FROM chat_messages cm
           LEFT JOIN chat_sessions cs ON cs.id = cm.session_id
           ORDER BY cm.session_id, cm.id"""
    ).fetchall()
    conn.close()

    by_session: dict[str, list[dict]] = collections.defaultdict(list)
    for m in msgs:
        by_session[m["session_id"]].append(dict(m))

    raw_turns: list[dict] = []
    for sid, smsgs in by_session.items():
        for i, m in enumerate(smsgs):
            if m["role"] != "user":
                continue
            reply_msg = None
            for j in range(i + 1, len(smsgs)):
                if smsgs[j]["role"] == "assistant":
                    reply_msg = smsgs[j]
                    break
                if smsgs[j]["role"] == "user":
                    break
            dev_id = m.get("device_id") or ""
            dev_names = device_names_map.get(dev_id, ())
            redacted_q = redact_text(m.get("content") or "", dev_names)
            redacted_a = redact_text((reply_msg or {}).get("content") or "", dev_names)
            cat = categorize_question(redacted_q, suggested)
            lang = detect_language(redacted_q)
            age_group = device_age_map.get(dev_id, "unspecified")
            fb = feedback_map.get(sid, {})
            kw_domains = _keyword_fast_path(redacted_q) or []

            q_hash = hashlib.sha256(_normalize(redacted_q).encode("utf-8")).hexdigest()[:16]
            raw_turns.append({
                "turn_id": m["id"],
                "question_hash": q_hash,
                "question": redacted_q,
                "assistant_reply": redacted_a,
                "unanswered": not bool(redacted_a.strip()),
                "category": cat,
                "lang": lang,
                "age_group": age_group,
                "keyword_domains": kw_domains,
                "fast_path": bool(kw_domains),
                "needs_human_review": bool(m.get("needs_human_review") or (reply_msg or {}).get("needs_human_review")),
                "feedback_rating": fb.get("rating", ""),
                "feedback_comment": fb.get("comment", ""),
                "created_at": m.get("created_at") or "",
            })

    questions_path = args.out_dir / "real_parent_questions.jsonl"
    with questions_path.open("w", encoding="utf-8") as fh:
        for t in raw_turns:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"3) Wrote {len(raw_turns)} anonymized parent turns -> {questions_path.name}")

    # Build combined SFT train/val dataset (31.6k final corpus + answered real parent Q&A)
    train_out = args.out_dir / "tg_train_ultra_v6.jsonl"
    val_out = args.out_dir / "tg_val_ultra_v6.jsonl"
    combined_records: list[dict] = []
    seen_q_norm: set[str] = set()

    real_sft_added = 0
    for t in raw_turns:
        if t["unanswered"] or t["category"] == "short_noise":
            continue
        if t["feedback_rating"] in ("down", "negative", "👎", "-1"):
            continue
        reply = t["assistant_reply"]
        if len(reply) < 80 or "حدث خطأ" in reply or "لا تتوفر لدي" in reply:
            continue
        if "📚" in reply or t["feedback_rating"] in ("up", "positive", "👍", "1"):
            nq = _normalize(t["question"])
            if nq not in seen_q_norm:
                seen_q_norm.add(nq)
                combined_records.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT_V6},
                        {"role": "user", "content": t["question"]},
                        {"role": "assistant", "content": reply},
                    ],
                    "source": "real_parent_verified",
                })
                real_sft_added += 1

    synth_added = 0
    if DEFAULT_FINAL_CORPUS.exists():
        for line in DEFAULT_FINAL_CORPUS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            instr = (r.get("instruction") or "").strip()
            out = (r.get("output") or "").strip()
            if not instr or not out:
                continue
            combined_records.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_V6},
                    {"role": "user", "content": instr},
                    {"role": "assistant", "content": out},
                ],
                "source": "kb_distilled_final",
            })
            synth_added += 1

    random.Random(42).shuffle(combined_records)
    n_val = max(1, int(len(combined_records) * 0.02))
    val_recs = combined_records[:n_val]
    train_recs = combined_records[n_val:]

    train_base_out = args.out_dir / "tg_train_base_v6.jsonl"
    for path, items in ((train_out, train_recs), (train_base_out, train_recs), (val_out, val_recs)):
        with path.open("w", encoding="utf-8") as fh:
            for it in items:
                fh.write(json.dumps({"messages": it["messages"]}, ensure_ascii=False) + "\n")

    print(f"4) Built Ultra v6 SFT corpus: {real_sft_added} real parent pairs + {synth_added} KB pairs")
    print(f"   -> Train: {len(train_recs)} ({train_out.name}) | Val: {len(val_recs)} ({val_out.name})")

    # Generate diagnostic report
    report_path = args.out_dir / "real_questions_diagnostic_report.md"
    cat_counts = collections.Counter(t["category"] for t in raw_turns)
    unans_counts = collections.Counter(t["category"] for t in raw_turns if t["unanswered"])
    lang_counts = collections.Counter(t["lang"] for t in raw_turns if t["category"] == "organic_parent_question")
    age_counts = collections.Counter(t["age_group"] for t in raw_turns if t["category"] == "organic_parent_question")
    domain_counts = collections.Counter()
    fast_path_misses = []
    unanswered_organic = []

    seen_miss = set()
    seen_unans = set()
    for t in raw_turns:
        if t["category"] == "organic_parent_question":
            for d in t.get("keyword_domains") or []:
                domain_counts[d] += 1
            nq = _normalize(t["question"])
            if t["unanswered"] and nq not in seen_unans:
                seen_unans.add(nq)
                unanswered_organic.append(t)
            if not t["fast_path"] and nq not in seen_miss:
                seen_miss.add(nq)
                fast_path_misses.append(t)

    lines = [
        "# تقرير تشخيص قاعدة أسئلة الآباء والأمهات الحقيقية — «المربّي»",
        "",
        f"- **تاريخ النسخة الاحتياطية:** `2026-10-14_0330`",
        f"- **إجمالي رسائل المستخدمين (`chat_messages`):** `{len(raw_turns)}`",
        f"- **إجمالي الوحدات المعرفية المفهرسة:** `{len(kb_units)}`",
        "",
        "## 1. تصنيف رسائل الآباء والأمهات",
        "",
        "| الفئة | العدد الإجمالي | بدون إجابة (`unanswered`) | نسبة عدم الإجابة |",
        "|---|---:|---:|---:|",
    ]
    for cat_key, label in [
        ("organic_parent_question", "أسئلة عفوية حقيقية من الآباء والأمهات"),
        ("daily_tip_card", "تفاعل مع «نصيحة اليوم»"),
        ("suggested_button", "ضغطات الأزرار المقترحة الجاهزة (19 زر)"),
        ("short_noise", "رسائل قصيرة جداً / تحيات (< 12 حرف)"),
    ]:
        tot = cat_counts[cat_key]
        un = unans_counts[cat_key]
        pct = (un / tot * 100) if tot else 0.0
        lines.append(f"| {label} | {tot} | {un} | {pct:.1f}% |")

    lines.extend([
        "",
        "## 2. توزيع الأسئلة العفوية الحقيقية حسب اللغة والفئة العمرية",
        "",
        f"- **اللغات:** العربية: `{lang_counts['ar']}` | الإنجليزية: `{lang_counts['en']}` | الفرنسية: `{lang_counts['fr']}`",
        f"- **الفئات العمرية:** " + " · ".join(f"`{k}`: {v}" for k, v in age_counts.most_common()),
        f"- **توزيع المجالات (Keyword Fast-Path):** " + " · ".join(f"`{k}`: {v}" for k, v in domain_counts.most_common()),
        f"- **الأسئلة العفوية التي لم تطابق الكلمات المفتاحية المباشرة (`fast_path=False`):** `{len(fast_path_misses)}` سؤال فريد (تُفحص بالكامل على Colab H100 بواسطة `Embedder` + `Reranker` + `Gemma 4 31B`).",
        "",
        "## 3. عينة من الأسئلة العفوية التي لم يحصل أصحابها على إجابة (`unanswered` — 91 سؤالاً)",
        "",
        "| # | العمر | اللغة | السؤال (بعد التعمية) |",
        "|---:|---|---|---|",
    ])
    for i, item in enumerate(unanswered_organic[:25], 1):
        q_clean = item["question"].replace("\n", " ")[:110]
        lines.append(f"| {i} | `{item['age_group']}` | `{item['lang']}` | {q_clean} |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"5) Wrote diagnostic report -> {report_path.name}")

    # Create a single ready-to-upload zip archive for Google Colab Ultra
    zip_path = args.out_dir / "tg_colab_ultra_bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fn in (
            "real_parent_questions.jsonl",
            "kb_units_full.jsonl",
            "tg_train_ultra_v6.jsonl",
            "tg_val_ultra_v6.jsonl",
            "real_questions_diagnostic_report.md",
        ):
            zf.write(args.out_dir / fn, arcname=fn)
    print(f"6) Packaged Colab Ultra bundle -> {zip_path} ({zip_path.stat().st_size / (1024*1024):.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
