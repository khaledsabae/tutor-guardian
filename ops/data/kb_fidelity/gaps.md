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
   **Filled 2026-10-05** from the OCR'd pages (book pp.89–104): isl-acc3d8ec (when to start,
   the Salaf's daily follow-up; the 7/10 narration described, the app's no-hitting stance as the
   app's), isl-3f0af447 (al-Bara' showing his family wudu and prayer; fathers' du'as after prayer),
   isl-c4986b8f (correcting a child's prayer gently; Muslim 535 described, no hitting advised),
   isl-7152a388 (children at Eid and Jumu'a: Bukhari 977, Ibn Battal's readiness test),
   isl-b58a4a58 (training children to fast: Bukhari 1960). The prayer journey's wudu and
   words-and-movements stages now cite isl-3f0af447.
2. **Discipline and hitting** (7 / 30 / 18). isl-19074fe7 and isl-2fafe289 claimed
   books "reject hitting" when the pages say otherwise. The app's no-hitting position
   is stated as the app's in the PR #27 units and in `backend/guardrails/policies.v1.yaml`.
   Write any further units the same way: what the scholars said, described as theirs,
   then the app's position as the app's.
   **Filled 2026-10-05 (batch 2):** isl-d38b9114 (Alukah pp.58–65: Ibn Uthaymin, Ahmad and
   Ibn al-Jawzi described as theirs, with their limits; the face hadith, Bukhari 2559; rebuke as
   discipline), isl-7a57602c and isl-0bf3f3b0 (Kayfa pp.49–53: reward rules, immediate in early
   childhood and delayed later; the punishment ladder, «avoid hitting as far as possible» as the
   author's, and her rules). Each ends with the app's no-hitting sentence.
3. **Truthfulness and lying** (10 / 78 / 15). isl-390466e2, isl-68df90c4 and
   isl-756e7d81 invented stories and narrators. Alukah p.74 (Umar checking on his son
   without warning, so that no lie is prompted) is the real material.
   **Filled 2026-10-05:** isl-1e4f7969 (book pp.73, 160, 170: Umar, a father's dying will on
   truthfulness, Abu Bakr «إن قلت ما لا أعلم»). Ramadan day 15 cites it.
4. **Patience** (18 / 62 / 10). Alukah pp.162–171: Luqman 17, patience in illness and loss.
   **Filled 2026-10-05:** isl-fc0925f0 (loss: Bukhari 5655, Anas burying his son, al-Nawawi on
   tears) and isl-30775bae (illness and qadar: Ubada's will, Urwa, Umm al-Aswad, Ibn al-Jawzi).
5. **Anger and self-control** (7 / 47 / 18). The withdrawn units invented their anger
   content: isl-22d62ea2 (a violent child), isl-50f95326 and isl-05aa623c. None of their
   pages treats anger. New units need a source that does, for example the Sahihayn's
   «لا تغضب» through the verified hadith cards.
   **Filled 2026-10-05:** isl-d8fa6d4a (causes and prevention) and isl-8e3e1052 (calming steps),
   from Ulwan pp.344–350, «ظاهرة الغضب». Bukhari 6116, 6114 and 6115 and Muslim 2204 are quoted in
   the Sahihayn wording, not the book's. Left out: «من كظم غيظًا…», which Ulwan gives to al-Bukhari
   (it is al-Tirmidhi 2021). Ahmad's and Abu Dawud's steps are described, not quoted. Ramadan day 12
   cites both units first.
6. **Du'a, tawakkul, adhkar** (8 / 42 / 9). isl-91f5606a invented a healing miracle,
   and isl-0b607846 replaced a chapter on teaching tawhid (Nuh, Ibrahim, Ya'qub's wills).
   **Filled 2026-10-05** from Alukah:
   - The tawhid chapter (pp.82–86): isl-487460bb (Nuh, Ibrahim, Ya'qub, Luqman) and isl-f4d4bad0
     (Ibn Abbas; al-Zubayr's «فاستعن عليه مولاي», Bukhari 3129; Umar and Hafsa; Umm Sulaym).
   - Du'a for children and against cursing them (pp.23–26): isl-572e7df3. Ramadan day 22 cites it
     first. The book's «مسلم (٣٠٠٩)» is described without a number, because the guard's index files
     that narration under 3006/3014.
   - The du'a before intimacy and what «لم يضره» means (pp.18–20): isl-8f2c2336.
   - The newborn (pp.27–28): isl-1ba05ed7, covering ta'widh, tahnik and du'a, with the app's
     hygiene note.
   - Ruqya (pp.130–131): isl-3fe9f565, covering Bukhari 3371, 5742 and 5739, with the app's
     "see a doctor too" line.
7. **Birr, kinship, neighbours, others' rights** (17 / 53 / 7). The family programmes
   need topic units here. Ramadan day 9 (neighbour) and day 16 (kinship) now rest on
   general "learning by example" units.
   **Filled 2026-10-05** from Ulwan, «Tarbiyat al-Awlad», «مراعاة حقوق الآخرين» (pp.376–397,
   OCR'd; the Alukah book has no chapter on them): isl-9b1b1eec (birr), isl-59632ca7 (kinship),
   isl-14660eb4 (neighbours). Ramadan days 7, 16 and 9 cite them first.
   **Filled 2026-10-05 (batch 2):** the teacher, companion and elder rights of the same chapter
   (pp.398–419): isl-de9e2767, isl-8510c683, isl-1d2d3cc0. Seeking permission (Alukah pp.170–171,
   al-Nur 58–59): isl-1deaad1d. Ulwan gives «لقد كنت على عهد رسول الله ﷺ غلامًا…» to Abu Sa'id
   "in the Sahihayn". It is Samura ibn Jundub in Muslim 964, and the unit says so.
8. **Charity and generosity** (5 / 11 / 0 left). Ramadan day 6 (generosity) and day 27
   (zakat al-fitr) have no topic unit at all.
   Day 21 (dhikr) has the same problem.
   **Filled 2026-10-05:** isl-ab4fcddf (Alukah pp.136–140, «تدريب الأولاد على البذل»),
   isl-d15a630e (dhikr: Bukhari 2822, Muslim 389, Fatima's tasbih), isl-90a3e496 (zakat al-fitr:
   Bukhari 1503 + Jarir's will on zakat, pp.92–93). Ramadan days 6, 21 and 27 cite them first.

### Single facts lost

- **Child physical activity**: at least 60 minutes of moderate-to-vigorous activity
  a day. 30 minutes on five days is the *adult* figure. Source: SFDA guide pp.25, 34.
  Withdrawn: med-0b39e5a8, med-a1df6423. **Filled 2026-10-05:** med-b0136703 (printed pp.23, 32–33).
- **Screen time under 8**: about 2 h 27 min a day, not 5 h. Source: Screen_Time_2025
  census. Withdrawn: cyb-fc24ccce. **Filled 2026-10-05:** cyb-60a0c4df (report pp.1, 15, 35).
- **Abortion ruling** (Kayfa pp.37–38): forbidden by consensus after ensoulment; before
  it, scholars range between prohibition and dislike. State it as the book's position
  and refer the reader to scholars, with no added exceptions. Withdrawn: isl-d8ac2c78.
  **Filled 2026-10-05:** isl-b630e2ad (p.37 only; the contraception sentence above it is left out).
- **"Tie your camel, then rely on Allah"** is in al-Tirmidhi, not the Sahihayn: describe
  it, don't quote it. Withdrawn: isl-9aa2ab45. **Not filled:** no readable source in
  `knowledge_base/raw_sources` carries this narration, and describing it from memory is the very
  failure this review withdrew.

Page numbers in the 2026-10-05 units are the books' printed numbers. Alukah: printed = PDF − 1
(the quarantine records above use PDF pages). SFDA guide: printed = PDF − 2. Ulwan and Kayfa:
printed = PDF. The new units are Arabic only: no `__en` twin until the English gate's
cross-family review can run.

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
