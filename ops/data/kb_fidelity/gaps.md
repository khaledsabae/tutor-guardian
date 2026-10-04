# KB fidelity — content gaps and the re-extraction plan

Work list for the content pass after the Ollama reset. The fidelity review of
2026-10-04 withdrew **205 knowledge units**: 100 of them had been retrieved
in production, 513 retrievals in all (retrieval_log, 2026-06-12 → 2026-10-04).
Each one had a summary that did not match its own source: the topic was invented,
a narrator or ruling was misattributed, a figure was wrong, or it was a model note
with no content. The records are in `quarantined.json`, with one reason per unit,
most-retrieved first. The files are in `ops/data/en_unpublished/`.

Rules for filling a gap: write from the source text itself, never from the old
summary. Quote Qur'an and hadith only as the guards allow: hadith only from the
Sahihayn with book and number, and anything else is described, not quoted. Before
committing, run `python3 ops/tools/check_kb_fidelity.py scan`, read every flag,
and record the verdict.

## Gaps, in order

The numbers are units withdrawn / production retrievals lost / served units left
on the topic.

1. **Teaching children to pray** (32 / 122 / 42). This is the most-asked topic. Lost: isl-e20d927a,
   isl-11a3cb7e, isl-19074fe7, isl-0b607846. The app's wording on the 7/10 narration
   and on hitting is still served, in the units rewritten in PR #27: isl-c4d83813,
   isl-af807518, isl-602bfb05, isl-d54fd8e8 and isl-5b861419, plus isl-5e099094,
   isl-6e577f4f, isl-73905b43 and isl-f4e75ff2 on discipline. What is missing is the
   *practical* teaching that the Alukah chapters (pp.97–104) actually contain:
   fathers teaching wudu and prayer by doing it, children at the mosque and at Eid.
2. **Discipline and hitting** (7 / 30 / 18). isl-19074fe7 and isl-2fafe289 claimed
   books "reject hitting" when the pages say otherwise. The app's no-hitting position
   is stated as the app's in the PR #27 units and in `backend/guardrails/policies.v1.yaml`.
   Write any further units the same way: what the scholars said, described as theirs,
   then the app's position as the app's.
3. **Truthfulness and lying** (10 / 78 / 15). isl-390466e2, isl-68df90c4 and
   isl-756e7d81 invented stories and narrators. Alukah p.74 (Umar checking on his son
   without warning, so that no lie is prompted) is the real material.
4. **Patience** (18 / 62 / 10). Alukah pp.162–171: Luqman 17, patience in illness and loss.
5. **Anger and self-control** (7 / 47 / 18). The withdrawn units invented their anger
   content: isl-22d62ea2 (a violent child), isl-50f95326 and isl-05aa623c. None of their
   pages treats anger. New units need a source that does, for example the Sahihayn's
   «لا تغضب» through the verified hadith cards.
6. **Du'a, tawakkul, adhkar** (8 / 42 / 9). isl-91f5606a invented a healing miracle,
   and isl-0b607846 replaced a chapter on teaching tawhid (Nuh, Ibrahim, Ya'qub's wills).
7. **Birr, kinship, neighbours, others' rights** (17 / 53 / 7). The family programmes
   need topic units here. Ramadan day 9 (neighbour) and day 16 (kinship) now rest on
   general "learning by example" units.
8. **Charity and generosity** (5 / 11 / 0 left). Ramadan day 6 (generosity) and day 27
   (zakat al-fitr) have no topic unit at all.
   Day 21 (dhikr) has the same problem.

### Single facts lost

- **Child physical activity**: at least 60 minutes of moderate-to-vigorous activity
  a day. 30 minutes on five days is the *adult* figure. Source: SFDA guide pp.25, 34.
  Withdrawn: med-0b39e5a8, med-a1df6423.
- **Screen time under 8**: about 2 h 27 min a day, not 5 h. Source: Screen_Time_2025
  census. Withdrawn: cyb-fc24ccce.
- **Abortion ruling** (Kayfa pp.37–38): forbidden by consensus after ensoulment; before
  it, scholars range between prohibition and dislike. State it as the book's position
  and refer the reader to scholars, with no added exceptions. Withdrawn: isl-d8ac2c78.
- **"Tie your camel, then rely on Allah"** is in al-Tirmidhi, not the Sahihayn: describe
  it, don't quote it. Withdrawn: isl-9aa2ab45.

## Re-extraction plan

Ingest (`ops/tools/ingest_pdf.py`, `ingest_source.py`) used `pdfplumber.extract_text()`.
For these right-to-left PDFs that returns **visual order**: letters and words reversed.
The Alukah book also has a broken embedded font whose Unicode map swaps letters
(ؿ for م, ؾ for ل, ـ for ن, ؼ for ق …), so reversing the text cannot repair it.

| source | withdrawn / kept | method |
|---|---|---|
| Alukah_Rights_of_Children.pdf (189 pp.) | 179 / 48 | OCR every page, or take the book's HTML from alukah.net |
| Kayfa_Turabbi_Waladak.pdf | 8 / 64 | OCR. **Al_Hady_Al_Nabawi.pdf is the same book** (Layla al-Jurayba): ingest once, retire the duplicate |
| Rakaiz_Tarbiya.pdf | 3 / 29 | OCR. Its units' `reference_info` wrongly says «تربية البنات» |
| Tarbiya_Al_Banat.pdf | 3 / 27 | OCR |
| Manhaj_Nabawi_Khulayfi.pdf | 1 / 37 | OCR (it also has `(cid:N)` gaps) |
| Alliance_Positive_Parenting_Guide_Arabic.pdf | 0 / 10 | OCR |
| SFDA_Healthy_Nutrition_Guide.pdf | 2 / 3 | OCR |
| WHO / UNICEF / Screen_Time (English) | 6 / — | Extraction is fine. Skip reference lists, credits and copyright pages when chunking |

OCR that read these books well during the review (about 490 pages): `pdftoppm -r 300 -gray`
per page, then `tesseract <page> - -l ara+eng --psm 6`. The in-repo route is
`ops/tools/ocr_pdf.py --dpi 300`. It uses tesseract's default page segmentation, so spot-check
a few pages against the PDF.

Then:

1. Chunk by page or section, and keep the page number in the unit.
2. Write each summary against its OCR text only.
3. Gate ingest: refuse a chunk when `check_kb_fidelity.source_flags()` reports
   `reversed`, `glyph_substituted` or `missing_glyphs`, and OCR it instead.
4. Re-publish a withdrawn id only by fixing it against its source, moving it back, and
   deleting its entry here and in `ops/data/en_unpublished/MANIFEST.json` in the same commit.
