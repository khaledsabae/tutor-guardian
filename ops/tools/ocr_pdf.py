#!/usr/bin/env python3
"""
OCR extraction for Arabic/English PDFs using Tesseract + pdf2image.
Saves extracted text as .txt sidecar files for use by ingest_source.py.
"""
import argparse
import os
import sys
from pathlib import Path

from pdf2image import convert_from_path
import pytesseract


def ocr_pdf(pdf_path: Path, lang: str = "ara+eng", dpi: int = 200, max_pages: int = 0, save_txt: bool = True):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"NOT FOUND: {pdf_path}")
        return

    # Get page count
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            total_pages = len(pdf.pages)
    except Exception:
        total_pages = 0

    print(f"\n📄 {pdf_path.name}")
    print(f"   Pages: {total_pages} | DPI: {dpi} | Lang: {lang}")

    pages_to_process = total_pages if max_pages == 0 else min(max_pages, total_pages)
    print(f"   Processing: {pages_to_process} pages")

    all_text = []
    batch_size = 10
    for start in range(1, pages_to_process + 1, batch_size):
        end = min(start + batch_size - 1, pages_to_process)
        print(f"   Pages {start}-{end}...", end=" ", flush=True)
        try:
            images = convert_from_path(
                str(pdf_path),
                first_page=start,
                last_page=end,
                dpi=dpi,
            )
            batch_text = []
            for img in images:
                text = pytesseract.image_to_string(img, lang=lang)
                batch_text.append(text)
            all_text.extend(batch_text)
            print(f"✅ ({len(all_text)} pages done)")
        except Exception as e:
            print(f"❌ {e}")

    full_text = "\n\n".join(all_text)
    char_count = len(full_text)
    print(f"   ✅ Total extracted: {char_count} chars")

    if save_txt and char_count > 0:
        txt_path = pdf_path.with_suffix(".txt")
        txt_path.write_text(full_text, encoding="utf-8")
        print(f"   💾 Saved: {txt_path}")
    elif save_txt and char_count == 0:
        print(f"   ⚠️  No text extracted, not saving .txt")

    return full_text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCR extraction for PDFs")
    parser.add_argument("pdf", type=str, help="PDF file path")
    parser.add_argument("--lang", default="ara+eng", help="Tesseract lang (ara+eng)")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=0, help="Limit pages (0=all)")
    parser.add_argument("--no-save", action="store_true", help="Don't save .txt")
    args = parser.parse_args()

    ocr_pdf(
        Path(args.pdf),
        lang=args.lang,
        dpi=args.dpi,
        max_pages=args.max_pages,
        save_txt=not args.no_save,
    )
