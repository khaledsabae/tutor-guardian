#!/usr/bin/env python3
"""seed_vps_answer_cache_from_teacher.py — Exports all clean, standalone
`Gemma 4 31B` gold-standard answers (plus the 25 new KB gap units) into a
compact JSONL payload (`vps_answer_cache_seed.jsonl`) and seeds them into the
live production `answer_cache` (`sessions.db`) inside `tg_backend` on the VPS
(`72.62.44.131`).

Zero local ML models are loaded on `khalednew` — batch embedding uses the
already-installed `_embedder()` inside `tg_backend` on the remote VPS.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "ops" / "tools"))

from app.services.domain_classifier import _keyword_fast_path
from run_gemma4_31b_real_questions_teacher import (
    CHECKPOINT_PATH,
    OUT_DIR,
    clean_gold_answer,
    is_clean_standalone_parent_question,
)


def build_seed_rows() -> list[dict]:
    rows: list[dict] = []
    seen_keys: set[tuple[str, str, str]] = set()

    if CHECKPOINT_PATH.exists():
        for line in CHECKPOINT_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            t_out = r.get("teacher") or {}
            t_domain = (t_out.get("primary_domain") or "development").strip()
            if not t_out.get("is_valid_parenting_query", True):
                continue
            q = (r.get("question") or "").strip()
            if not is_clean_standalone_parent_question(q, domain=t_domain):
                continue
            gold = clean_gold_answer(t_out.get("gold_answer") or "")
            if len(gold) < 80 or "رواية ورش" in gold or "إعدادات التطبيق" in gold:
                continue

            kw_doms = _keyword_fast_path(q) or []
            domains_to_seed = list(dict.fromkeys(([kw_doms[0]] if kw_doms else []) + [t_domain]))
            age = r.get("age_group") or "unspecified"
            ages_to_seed = list(dict.fromkeys([age, "unspecified"]))

            for dom in domains_to_seed:
                if dom not in ("medical", "cyber", "islamic_parenting", "development", "aqeedah", "infant_pregnancy"):
                    continue
                for ag in ages_to_seed:
                    k = (q, ag, dom)
                    if k not in seen_keys:
                        seen_keys.add(k)
                        rows.append({
                            "question": q,
                            "age_group": ag,
                            "domain": dom,
                            "severity": "خفيف",
                            "answer": gold,
                        })

    gap_dir = OUT_DIR / "new_kb_gap_units"
    if gap_dir.exists():
        for fp in sorted(gap_dir.glob("*.json")):
            g = json.loads(fp.read_text(encoding="utf-8"))
            q = g["title"]
            ans = f"{g['text_simplified']}\n\n📚 المصادر: {g['reference_info']}"
            for ag in list(dict.fromkeys([g["age_group"], "unspecified"])):
                k = (q, ag, g["domain"])
                if k not in seen_keys:
                    seen_keys.add(k)
                    rows.append({
                        "question": q,
                        "age_group": ag,
                        "domain": g["domain"],
                        "severity": g.get("severity") or "خفيف",
                        "answer": ans,
                    })

    return rows


def main() -> int:
    rows = build_seed_rows()
    seed_path = OUT_DIR / "vps_answer_cache_seed.jsonl"
    with seed_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"📦 Built {len(rows)} cache seed entries -> {seed_path} ({seed_path.stat().st_size / 1024:.1f} KB)")

    subprocess.run(
        ["scp", "-o", "StrictHostKeyChecking=no", str(seed_path), "root@72.62.44.131:/tmp/vps_answer_cache_seed.jsonl"],
        check=True,
    )
    remote_cmd = r"""docker cp /tmp/vps_answer_cache_seed.jsonl tg_backend:/tmp/vps_answer_cache_seed.jsonl && docker exec tg_backend python3 -c '
import json
from app.services import answer_cache
from app.services.retrieval import _embedder

rows = [json.loads(l) for l in open("/tmp/vps_answer_cache_seed.jsonl", encoding="utf-8") if l.strip()]
unique_q_norms = sorted({answer_cache.normalize(r["question"]) for r in rows})
print(f"Batch-embedding {len(unique_q_norms)} unique normalized parent questions on VPS...")
emb_fn = _embedder()
vec_map = {}
B = 128
for i in range(0, len(unique_q_norms), B):
    batch = unique_q_norms[i:i+B]
    vecs = emb_fn([f"query: {q}" for q in batch])
    for q, v in zip(batch, vecs):
        vec_map[q] = json.dumps([float(x) for x in v])

conn = answer_cache._conn()
rev = answer_cache._kb_revision() if hasattr(answer_cache, "_kb_revision") else ""
inserted = 0
for r in rows:
    qn = answer_cache.normalize(r["question"])
    qh = answer_cache._key(r["question"], r["age_group"], r["domain"], r["severity"])
    conn.execute(
        "INSERT INTO answer_cache (qhash, question_norm, age_group, domain, severity, answer, embedding, kb_revision, redacted) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1) "
        "ON CONFLICT(qhash) DO UPDATE SET answer = excluded.answer, embedding = excluded.embedding, kb_revision = excluded.kb_revision, redacted = 1, created_at = CURRENT_TIMESTAMP",
        (qh, qn[:500], r["age_group"], r["domain"], r["severity"], r["answer"], vec_map.get(qn), rev),
    )
    inserted += 1
conn.commit()
total = conn.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0]
conn.close()
hit = answer_cache.lookup("امتى سن المناسب للطفل يستغنى فيه عن القيلوله لانها كانت تاخذ قيلوله ومن حوالي اسبوع استغنت عنها وترفضها", "2-3", "medical", "خفيف")
print(f"✅ Seeded {inserted} entries! Total active rows in production answer_cache: {total} | Live hit verified: {bool(hit)}")
'"""
    subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "root@72.62.44.131", remote_cmd], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
