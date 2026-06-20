#!/usr/bin/env python3
"""
Unified PDF-to-knowledge-units ingest pipeline.

Batch-processes PDFs from raw_sources/<domain>/ and generates knowledge unit
JSON files in knowledge_base/units/ via Ollama (local fast model).

Usage:
    # Process all unprocessed PDFs in development domain
    python ops/tools/ingest_pdf.py --domain development --reference "UNICEF/Centers for Disease Control"

    # Process a single PDF
    python ops/tools/ingest_pdf.py --domain medical --file ADHD_NIMH.pdf --reference "NIMH"

    # Dry-run: show what would be processed
    python ops/tools/ingest_pdf.py --domain development --dry-run

    # Resume an interrupted run
    python ops/tools/ingest_pdf.py --domain medical --resume

    # Skip known-bad files
    python ops/tools/ingest_pdf.py --domain islamic_parenting --skip "Tawid_Salah.pdf"
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UNITS_DIR = PROJECT_ROOT / "knowledge_base" / "units"
RAW_DIR = PROJECT_ROOT / "knowledge_base" / "raw_sources"
SCHEMA_PATH = PROJECT_ROOT / "knowledge_base" / "schema" / "knowledge_unit.schema.json"
PROGRESS_DIR = PROJECT_ROOT / "ops" / "tools" / ".ingest_progress"

# ── Ollama configuration ────────────────────────────────────
_LOCAL_BASE = os.environ.get("OLLAMA_LOCAL_BASE_URL", "http://100.109.163.64:11434")
OLLAMA_URL = f"{_LOCAL_BASE.rstrip('/')}/api/generate"
MODEL = os.environ.get("OLLAMA_LOCAL_FAST_MODEL", "qwen2.5:3b")

# ── Domain mapping: directory name → canonical domain ───────
DIR_TO_DOMAIN = {
    "medical": "medical",
    "digital_safety": "cyber",
    "cyber": "cyber",
    "development": "development",
    "islamic_parenting": "islamic_parenting",
}

EXTRACTION_PROMPT = """أنت مساعد تربوي خبير. حلل النص التالي واستخرج وحدة معرفة بصيغة JSON فقط (بدون أي نص خارج الأقواس {{}}).
الحقول المطلوبة:
- text_simplified: ملخص واضح ومبسط للأهل (جملتان إلى 4 جمل بالعربية الفصحى).
- behavior_type: نوع السلوك أو الموضوع الرئيسي (مثال: فرط حركة، قلق، إدمان ألعاب). استخدم عربي فقط.
- age_group: اختر واحداً فقط: 0-3, 4-6, 7-9, 10-12, 13-15, 16-18, unspecified.
- severity: اختر واحداً: خفيف, متوسط, شديد, طارئ.
- intervention_type: اختر واحداً: وقائي, إرشادي, علاجي, إحالة_لطبيب.
- labels: قائمة بـ 3-5 وسوم عربية قصيرة تصف المحتوى.
- title: عنوان مختصر للوحدة (أقصى 10 كلمات).
- language: ar, en, أو mixed.

النص:
{chunk}"""

# Files confirmed to be empty/broken — skip silently
SKIP_FILES = {
    "Tawid_Salah.pdf",
    "UNICEF_Online_Protection.pdf",
}


# ── Helpers ──────────────────────────────────────────────────

def extract_pdf_text(path: Path) -> str:
    """Extract text from a PDF using pdfplumber. Returns empty string on failure."""
    import pdfplumber
    try:
        with pdfplumber.open(path) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n".join(pages)
    except Exception as e:
        print(f"  ⚠️  PDF parse error: {e}")
        return "" 


def extract_sidecar_text(pdf_path: Path) -> str | None:
    """Read a .txt sidecar file if it exists (for OCR output)."""
    txt_path = pdf_path.with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8")
    return None


def detect_is_arabic_doc(text: str) -> bool:
    """Detect if a document is primarily Arabic (>20% Arabic chars across first 2000 chars)."""
    sample = text[:2000]
    arabic = sum(1 for c in sample if "\u0600" <= c <= "\u06FF")
    return arabic > len(sample) * 0.20


def clean_ocr_text(text: str) -> str:
    """Remove OCR noise: short lines, low-content lines.

    For Arabic documents, filter lines with <30% Arabic chars.
    For English documents, only remove very short lines and pure numbers.
    """
    is_arabic = detect_is_arabic_doc(text)
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) < 15:
            continue
        if is_arabic:
            arabic = sum(1 for c in line if "\u0600" <= c <= "\u06FF")
            if arabic < len(line) * 0.3:
                continue
        else:
            # For English: skip purely numeric/header lines
            non_alpha = sum(1 for c in line if not c.isalpha() and not c.isspace())
            if non_alpha > len(line) * 0.7:
                continue
        cleaned.append(line)
    return "\n".join(cleaned)


def chunk_text(text: str, max_words: int = 250, overlap: int = 50) -> list[str]:
    """Split by headings first, then by max_words with overlap.

    Headings typically start with ##/-- or Arabic chapter markers.
    """
    sections = re.split(
        r"\n(?=\#\#|[\-]{3,}|(?:الباب|الفصل|الجزء|المبحث|المقدمة|الخاتمة|أولاً|ثانياً|ثالثاً|رابعاً))",
        text,
    )
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        words = section.split()
        if len(words) <= max_words + overlap:
            chunks.append(section)
        else:
            for i in range(0, len(words), max_words - overlap):
                chunk_words = words[i : i + max_words]
                chunks.append(" ".join(chunk_words))
    return chunks


# ── DeepSeek (OpenAI-compatible) extraction — fast + CJK-clean ──────────
# When DEEPSEEK_API_KEY is set, extraction uses DeepSeek instead of the slow,
# CJK-prone local qwen model. Native api.deepseek.com endpoint.
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def _strip_json(raw: str) -> dict | None:
    raw = re.sub(r"```(?:json)?\s*|```", "", raw).strip()
    return json.loads(raw)


def call_deepseek(chunk: str) -> dict | None:
    """Extract a knowledge unit via DeepSeek (OpenAI-compatible)."""
    from openai import OpenAI

    prompt = EXTRACTION_PROMPT.format(chunk=chunk)
    try:
        client = OpenAI(api_key=DEEPSEEK_KEY, base_url=DEEPSEEK_BASE, timeout=90)
        r = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=900,
        )
        return _strip_json(r.choices[0].message.content or "")
    except (json.JSONDecodeError, KeyError, Exception) as e:  # noqa: BLE001
        print(f"  ⚠️  DeepSeek error: {e}")
        return None


def call_ollama(chunk: str) -> dict | None:
    """Call the configured LLM (DeepSeek if keyed, else Ollama) and parse JSON."""
    if DEEPSEEK_KEY:
        return call_deepseek(chunk)
    prompt = EXTRACTION_PROMPT.format(chunk=chunk)
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 600},
    }
    try:
        with httpx.Client(timeout=90) as client:
            r = client.post(OLLAMA_URL, json=payload)
            r.raise_for_status()
            raw = r.json().get("response", "")
            return _strip_json(raw)
    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
        print(f"  ⚠️  Ollama error: {e}")
        return None


def validate_unit(unit: dict) -> bool:
    """Validate against the knowledge_unit JSON schema."""
    from jsonschema import Draft202012Validator, ValidationError

    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    try:
        Draft202012Validator(schema).validate(unit)
        return True
    except ValidationError as e:
        print(f"  ❌ Schema: {e.message}")
        return False


def load_progress(source_name: str) -> int:
    """Load the last processed chunk index for a given source."""
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    pf = PROGRESS_DIR / f"{source_name}.json"
    if pf.exists():
        try:
            data = json.loads(pf.read_text(encoding="utf-8"))
            return data.get("last_chunk_index", 0)
        except Exception:
            pass
    return 0


def save_progress(source_name: str, index: int):
    """Save progress for a source."""
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    pf = PROGRESS_DIR / f"{source_name}.json"
    pf.write_text(
        json.dumps({"last_chunk_index": index}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_progress(source_name: str):
    """Delete progress file on successful completion."""
    pf = PROGRESS_DIR / f"{source_name}.json"
    if pf.exists():
        pf.unlink()


def already_has_units(source_name: str) -> int:
    """Count existing units that reference this source_file."""
    count = 0
    for fp in sorted(UNITS_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if data.get("source_file") == source_name:
                count += 1
        except Exception:
            pass
    return count


def build_unit(
    data: dict,
    chunk: str,
    source_name: str,
    domain: str,
    reference_info: str,
    source_meta_author: str = "",
    source_meta_year: int | None = None,
) -> dict:
    """Build a complete knowledge unit dict from extracted data."""
    # Generate ID: domain prefix + UUID suffix
    domain_prefix = domain[:3]
    unit_id = f"{domain_prefix}-{uuid.uuid4().hex[:8]}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    age_group = data.get("age_group", "unspecified")
    valid_ages = {"0-3", "4-6", "7-9", "10-12", "13-15", "16-18", "unspecified"}
    if age_group not in valid_ages:
        age_group = "unspecified"

    severity = data.get("severity", "متوسط")
    valid_severities = {"خفيف", "متوسط", "شديد", "طارئ"}
    if severity not in valid_severities:
        severity = "متوسط"

    intervention = data.get("intervention_type", "إرشادي")
    valid_interventions = {"وقائي", "إرشادي", "علاجي", "إحالة_لطبيب"}
    if intervention not in valid_interventions:
        intervention = "إرشادي"

    labels = data.get("labels", [])
    if isinstance(labels, str):
        labels = [t.strip() for t in labels.split(",") if t.strip()]
    if not labels:
        labels = ["عام"]

    language = data.get("language", "ar")

    return {
        "id": unit_id,
        "domain": domain,
        "source_file": source_name,
        "title": data.get("title", "")[:120],
        "language": language,
        "age_group": age_group,
        "behavior_type": data.get("behavior_type", "عام"),
        "intervention_type": intervention,
        "severity": severity,
        "reference_type": "تقرير_طبي" if domain == "medical" else "كتاب_تربوي",
        "reference_info": reference_info,
        "text_original": chunk,
        "text_simplified": data.get("text_simplified", ""),
        "labels": labels,
        "created_at": now,
        "updated_at": now,
        "version": "1.0.0",
        "source_meta": {
            "source_title": Path(source_name).stem,
            "source_author": source_meta_author,
        },
    }


def process_source(
    pdf_path: Path,
    domain: str,
    reference_info: str,
    resume: bool = False,
    max_units: int | None = None,
) -> tuple[int, int]:
    """Process a single PDF: extract text → chunk → Ollama → save units.

    Returns (accepted, skipped).
    """
    source_name = pdf_path.name
    print(f"\n{'=' * 60}")
    print(f"  📄  {source_name}")
    print(f"{'=' * 60}")

    # Already has units? Count them.
    existing = already_has_units(source_name)
    if existing > 0:
        print(f"  📊  Already has {existing} unit(s). Skipping (already processed).")
        return 0, 0

    # Extract text
    sidecar = extract_sidecar_text(pdf_path)
    if sidecar:
        text = sidecar
        print(f"  📝  Using .txt sidecar ({len(text)} chars)")
    else:
        text = extract_pdf_text(pdf_path)
        if not text or len(text.strip()) < 50:
            print(f"  ⚠️  Minimal text extracted ({len(text)} chars) — skipping")
            return 0, 1
        print(f"  ✅  Extracted {len(text)} chars")

    # Clean and chunk
    text = clean_ocr_text(text)
    chunks = chunk_text(text)
    # Filter very short chunks
    chunks = [c for c in chunks if len(c.split()) >= 30]
    print(f"  📦  {len(chunks)} chunks (≥30 words each)")

    if len(chunks) == 0:
        print(f"  ⚠️  No valid chunks — skipping")
        return 0, 1

    # Apply max_units limit (most useful for large texts)
    if max_units and max_units < len(chunks):
        chunks = chunks[:max_units]
        print(f"  🎯  Truncated to {max_units} chunks")

    # Resume support
    start_idx = load_progress(source_name) if resume else 0
    if start_idx > 0:
        print(f"  ▶️  Resuming from chunk {start_idx}")

    accepted = 0
    skipped = 0

    for i in range(start_idx, len(chunks)):
        chunk = chunks[i]
        print(f"\n  [{i + 1}/{len(chunks)}] {len(chunk)} chars — {chunk[:80]}...", end=" ")

        data = call_ollama(chunk)
        if not data:
            print("❌ فشل")
            skipped += 1
            if resume:
                save_progress(source_name, i + 1)
            time.sleep(2)
            continue

        print(f"✅ {data.get('behavior_type', '?')} / {data.get('age_group', '?')}", end="")

        unit = build_unit(data, chunk, source_name, domain, reference_info)

        if validate_unit(unit):
            out_path = UNITS_DIR / f"{unit['id']}.json"
            out_path.write_text(
                json.dumps(unit, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            accepted += 1
            print(f"  → {out_path.name}")
        else:
            print(f"  ⚠️  Schema validation failed — skipped")
            skipped += 1

        if resume:
            save_progress(source_name, i + 1)

        # Rate limit: 1s between calls
        time.sleep(1)

    # Clear progress on full success
    if resume and skipped == 0:
        clear_progress(source_name)

    print(f"\n  ✅  {accepted} accepted, {skipped} skipped")
    return accepted, skipped


def main():
    parser = argparse.ArgumentParser(description="Batch PDF → knowledge units ingestion")
    parser.add_argument(
        "--domain",
        choices=list(DIR_TO_DOMAIN.keys()),
        help="Domain directory under raw_sources/",
    )
    parser.add_argument("--file", help="Single PDF filename to process (requires --domain)")
    parser.add_argument("--reference", default="", help="Reference info (source, author)")
    parser.add_argument(
        "--max-units", type=int, help="Max units per source (for large texts)"
    )
    parser.add_argument("--resume", action="store_true", help="Resume interrupted run")
    parser.add_argument(
        "--skip",
        nargs="*",
        default=[],
        help="Additional filenames to skip",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")

    args = parser.parse_args()

    # Collect skip list
    skip_set = SKIP_FILES | set(args.skip)

    # Resolve PDFs
    if args.file:
        if not args.domain:
            print("❌ --domain is required when using --file")
            sys.exit(1)
        pdfs = [RAW_DIR / args.domain / args.file]
    elif args.domain:
        pdfs = sorted((RAW_DIR / args.domain).glob("*.pdf"))
    else:
        # Process all domains
        pdfs = []
        for d in sorted(DIR_TO_DOMAIN.keys()):
            pdfs.extend(sorted((RAW_DIR / d).glob("*.pdf")))

    # Filter
    pdfs = [p for p in pdfs if p.name not in skip_set]

    # Filter out already-processed PDFs (have any units)
    unprocessed = []
    for p in pdfs:
        if already_has_units(p.name) == 0:
            unprocessed.append(p)
        else:
            print(f"  ⏭️  {p.name}: already has units — skipping")

    print(f"\n{'=' * 60}")
    print(f"  📥  Unified PDF Ingestion Pipeline")
    print(f"  🖥️  Ollama: {OLLAMA_URL}  |  Model: {MODEL}")
    print(f"{'=' * 60}")
    print(f"\n  📂  {len(unprocessed)} PDF(s) to process")

    if args.dry_run:
        for p in unprocessed:
            print(f"     → {p.name} ({p.parent.name})")
        print("\n  ✅ Dry-run complete. Pass --dry-run to process.")
        return

    if not unprocessed:
        print("  ✅ Nothing to process.")
        return

    total_accepted = 0
    total_skipped = 0

    for pdf_path in unprocessed:
        dir_name = pdf_path.parent.name
        domain: str = DIR_TO_DOMAIN.get(dir_name, dir_name)  # type: ignore[arg-type]
        reference = args.reference or pdf_path.parent.name

        acc, skp = process_source(
            pdf_path,
            domain=domain,
            reference_info=reference,
            resume=args.resume,
            max_units=args.max_units,
        )
        total_accepted += acc
        total_skipped += skp

    print(f"\n{'=' * 60}")
    print(f"  🏁  Total: {total_accepted} accepted, {total_skipped} skipped")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
