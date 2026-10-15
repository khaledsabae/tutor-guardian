#!/usr/bin/env python3
"""upload_ultra_bundle_to_hf.py — Uploads the anonymized & Teacher-distilled
Google Colab Ultra bundle (`tg_colab_ultra_bundle.zip` + individual JSONL/MD
files) to the PRIVATE HuggingFace dataset repository `khaledhamdy/tg-ultra-v6-private`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from huggingface_hub import HfApi

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = PROJECT_ROOT / "ops" / "data" / "kaggle_upload_ultra"
REPO_ID = "khaledhamdy/tg-ultra-v6-private"


def resolve_hf_token() -> str:
    tok = os.environ.get("HF_TOKEN", "").strip()
    if tok:
        return tok
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        m = re.search(r"^HF_TOKEN=([^\s#]+)", env_file.read_text(encoding="utf-8", errors="ignore"), re.M)
        if m:
            return m.group(1).strip()
    raise RuntimeError("HF_TOKEN not found in environment or .env")


def main() -> int:
    token = resolve_hf_token()
    api = HfApi(token=token)

    print(f"🔒 Ensuring PRIVATE dataset repo exists: {REPO_ID}...")
    api.create_repo(repo_id=REPO_ID, repo_type="dataset", private=True, exist_ok=True)
    info = api.repo_info(repo_id=REPO_ID, repo_type="dataset")
    assert info.private is True, f"Safety error: repo {REPO_ID} is not private!"

    files_to_upload = [
        "tg_colab_ultra_bundle.zip",
        "distilled_real_parents_sft.jsonl",
        "distilled_real_parents_dpo.jsonl",
        "reranker_teacher_pairs.jsonl",
        "real_kb_gaps_report.md",
        "real_questions_diagnostic_report.md",
    ]
    for fn in files_to_upload:
        fp = BUNDLE_DIR / fn
        if fp.exists():
            sz_mb = fp.stat().st_size / (1024 * 1024)
            print(f"☁️ Uploading {fn} ({sz_mb:.2f} MB) -> {REPO_ID}...")
            api.upload_file(
                path_or_fileobj=str(fp),
                path_in_repo=fn,
                repo_id=REPO_ID,
                repo_type="dataset",
            )
    print(f"✅ All Ultra v6 bundle artifacts uploaded privately to https://huggingface.co/datasets/{REPO_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
