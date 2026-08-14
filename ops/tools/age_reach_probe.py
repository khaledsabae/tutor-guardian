#!/usr/bin/env python3
"""Measure whether the hand-authored gap units are reachable — matched and unmatched age.

The vector leg filters to the child's age band plus "unspecified", so a unit
written for 4-6 used to be invisible to a 7-9 parent rather than merely ranked
lower. `retrieve_domain_only` was added to close that. This probe is how that
change was measured, and how a regression in it would be caught.

⚠️ THE PHRASING IS THE MEASUREMENT. An earlier version of this probe reused one
question per behaviour across every age band, and reported that seed-shy-79 was
unreachable in every configuration. It is not: it ranks 1 for three phrasings.
What actually happened is that the single shy question was worded the way a 4-6
parent words it ("بيتكسف من الناس ومش بيتكلم قدام حد"), so at 7-9 the pipeline
answered with seed-shy-46 — the correct unit for that complaint. The probe was
scoring correct behaviour as a miss and inventing a corpus bug that never
existed. Every question below is therefore written for its own band: a 2-3
tantrum and a 7-9 one are not the same complaint, and a parent does not
describe them with the same words.

Two cases, and they ask different things:

  matched — the corpus HAS a unit for the child's band. Does it come back?
  gap     — the corpus has NO unit for the child's band, and the question is
            phrased for that band. Does the nearest band's unit come back
            instead of nothing? This is the case the age filter used to lose.

What the score means, precisely: it counts how often a PRE-CHOSEN target unit
lands in the delivered top-4. It is not a measure of answer quality — the
pipeline preferring a different but better-suited unit counts as a miss here.
Read it as a reachability signal, not a grade.

    python3 ops/tools/age_reach_probe.py            # against the local index
    python3 ops/tools/age_reach_probe.py --verbose  # per-question detail
    python3 ops/tools/age_reach_probe.py --compare  # vs the pre-change pipeline

Reading on 2026-08-14 against the 864-unit local index:

              shipped   before the age-free leg + pool cap
    matched     14/23        14/23
    gap          4/11         1/11

The matched column not moving is the design holding: the extra leg is fused
underneath the age-filtered one, so a unit in the child's own band keeps its
double RRF credit. The gap column is the entire reason the change exists.

Note what 14/23 also says: nine hand-written units do not reach the top-4 even
for an age-appropriate question at their own band. That is a corpus and
ranking question this probe surfaces but does not answer.
"""
import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

UNITS_DIR = REPO / "knowledge_base" / "units"

# One question per (behaviour, age band), in the words a parent of THAT age
# actually uses. Bands with no unit of their own are included on purpose —
# they are the gap cases.
QUESTIONS: dict[str, dict[str, str]] = {
    "aggression": {
        "2-3": "ابني سنتين بيعض ويخبط أخوه لما يزعل منه",
        "4-6": "ابني بيضرب زمايله في الحضانة لما حد ياخد لعبته",
        "7-9": "ابني بيتخانق بإيده في المدرسة وبيرجع بشكاوى كل أسبوع",
    },
    "bedwet": {
        "4-6": "بنتي خمس سنين لسه بتبول على نفسها بالليل",
        "7-9": "ابني تمن سنين بيصحى مبلول وبيتكسف يبات عند حد",
        "10-12": "ابني عنده ١١ سنة ولسه بيحصله تبول لا إرادي بالليل وبقى محرج جدًا",
    },
    "defiance": {
        "2-3": "ابني سنتين بيقول لأ على كل حاجة ويرمي نفسه على الأرض",
        "4-6": "ابني بيرفض ينفذ أي طلب وبيعاند حتى في اللبس والأكل",
        "7-9": "ابني بيجادلني في كل كلمة ومش بيسمع الكلام إلا بعد زعيق",
    },
    "fear": {
        "4-6": "بنتي بتخاف من الضلمة ومش عايزة تنام لوحدها",
        "7-9": "ابني بقى قلقان من أي حاجة جديدة وبيسأل كتير لو هيحصل حاجة وحشة",
        "10-12": "ابني عنده ١١ سنة وبقى قلقان من الامتحانات ومن إن حاجة تحصل لينا",
    },
    "jealousy": {
        "2-3": "ابني سنتين بقى بيزن ويرجع يعمل زي البيبي بعد ما خلفت",
        "4-6": "ابني بيغير من أخوه المولود وبيحاول يأذيه لما مابصلوش",
        "7-9": "ابني بيقارن نفسه بأخوه الصغير وبيقول إني بحبه أكتر منه",
    },
    "lying": {
        "4-6": "ابني بيحكي حاجات ماحصلتش خالص وبيقول إنها حقيقية",
        "7-9": "ابني بيكذب عليا عشان مايتعاقبش، خصوصًا في حاجات المدرسة",
        "10-12": "ابني عنده ١١ سنة وبقى بيكذب عليا في مواعيده ومع مين بيخرج",
    },
    "picky": {
        "2-3": "ابني سنتين رافض يجرب أي أكل جديد ومابياكلش غير حاجتين",
        "4-6": "ابني بيرفض الخضار خالص والأكلة بتاخد ساعة وعياط",
        "7-9": "ابني تمن سنين مابياكلش أكل البيت وعايز الوجبات السريعة بس",
        "10-12": "ابني عنده ١١ سنة بيسيب أكل البيت وبياكل شيبسي وسناكس طول اليوم",
    },
    "screen": {
        "4-6": "ابني مش بيسيب التابلت وبيعيط أول ما أقفله",
        "7-9": "ابني قاعد على الألعاب طول اليوم ومش بيخلص واجباته",
        "10-12": "ابني عنده ١١ سنة على الموبايل لحد بليل ومش عارفة أظبط وقت الشاشة",
    },
    "shy": {
        "4-6": "ابني بيتكسف من الناس ومش بيتكلم قدام حد ويختبي ورايا",
        "7-9": "ابني مالوش أصحاب في المدرسة ومش عارف يكوّن صداقات",
        "10-12": "ابني عنده ١١ سنة بيقعد لوحده ومش بيشارك مع زمايله في أي حاجة",
    },
    "sleep": {
        "2-3": "ابني سنتين بيصحى كذا مرة بالليل ومش بينام غير في حضني",
        "4-6": "ابني بيأجل النوم بحجج ومش بيرضى ينام قبل ١٢",
        "7-9": "ابني تمن سنين بيسهر وبيصحى تعبان ومش قادر يركز في المدرسة",
    },
    "tantrum": {
        "2-3": "ابني سنتين بيرمي نفسه ويعيط بصوت عالي في الشارع",
        "4-6": "ابني بيزعق ويرمي حاجات لما أقوله لأ",
        "7-9": "ابني بيتعصب فجأة ويخبط الباب لما حاجة متمشيش زي ما هو عايز",
    },
}

# The band each behaviour is probed at when the corpus has nothing for it.
# Deliberately adjacent to a covered band: the question is whether the nearest
# unit is reachable, not whether an unrelated one is.
GAP_BAND = {
    "aggression": "7-9", "bedwet": "10-12", "defiance": "7-9",
    "fear": "10-12", "jealousy": "7-9", "lying": "10-12",
    "picky": "10-12", "screen": "10-12", "shy": "10-12",
    "sleep": "7-9", "tantrum": "7-9",
}


def load_units() -> dict[str, list[tuple[str, str, str]]]:
    """{behaviour: [(unit_id, age_group, domain), ...]} for the seeded units."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    for f in sorted(UNITS_DIR.glob("seed-*.json")):
        u = json.loads(f.read_text(encoding="utf-8"))
        slug = u["id"].removeprefix("seed-").rsplit("-", 1)[0]
        out.setdefault(slug, []).append((u["id"], u["age_group"], u["domain"]))
    return out


_BAND_ORDER = ["prenatal-1", "2-3", "4-6", "7-9", "10-12", "13-15", "16-18"]


def nearest_unit(units: list[tuple[str, str, str]], band: str):
    """The seeded unit whose band sits closest to `band`."""
    i = _BAND_ORDER.index(band)
    return min(units, key=lambda u: abs(_BAND_ORDER.index(u[1]) - i))


def delivered(query: str, domain: str, age_group: str,
              legacy: bool = False) -> list[str]:
    """The delivered top-4. `legacy` reconstructs the pipeline as it was before
    the age-free vector leg and the rerank-pool cap, so a claimed improvement
    can be re-measured instead of taken on trust."""
    from app.services import retrieval

    if not legacy:
        return [u.get("unit_id") for u in
                retrieval.retrieve_hybrid(query_text=query, domains=[domain],
                                          age_group=age_group, top_n=4)]

    from app.services.bm25_index import get_bm25
    from app.services.reranker import rerank
    from app.core.taxonomy import canonical_domain

    legs = [retrieval.retrieve_relevant_units(
        query_text=query, domain=domain, age_group=age_group, top_k=8)]
    legs.append(get_bm25().search(query, domain=canonical_domain(domain),
                                  top_k=8))
    fused = retrieval._rrf_merge(*legs)          # no cap, as it was
    return [u.get("unit_id") for u in rerank(query, fused, top_n=4)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--compare", action="store_true",
                    help="measure the pre-change pipeline too")
    args = ap.parse_args(argv)

    by_behaviour = load_units()
    rows = []

    for slug, units in sorted(by_behaviour.items()):
        asked = QUESTIONS.get(slug)
        if not asked:
            print(f"  ⚠️  no phrasings for {slug} — skipped", file=sys.stderr)
            continue

        for uid, band, domain in sorted(units):
            q = asked.get(band)
            if not q:
                print(f"  ⚠️  no {band} phrasing for {slug} — skipped",
                      file=sys.stderr)
                continue
            top = delivered(q, domain, band)
            old = delivered(q, domain, band, legacy=True) if args.compare else None
            rows.append(("matched", uid, band, old, uid in top, top))

        gap_band = GAP_BAND.get(slug)
        q = asked.get(gap_band) if gap_band else None
        if q and not any(b == gap_band for _, b, _ in units):
            target, _, domain = nearest_unit(units, gap_band)
            top = delivered(q, domain, gap_band)
            old = delivered(q, domain, gap_band, legacy=True) if args.compare else None
            rows.append(("gap", target, gap_band, old, target in top, top))

    for case in ("matched", "gap"):
        sel = [r for r in rows if r[0] == case]
        hit = sum(1 for r in sel if r[4])
        line = f"{case:8}: shipped {hit}/{len(sel)}"
        if args.compare:
            was = sum(1 for r in sel if r[3] is not None and r[1] in r[3])
            line += f"   before the change {was}/{len(sel)}"
        print(line)
        if args.verbose:
            for _, uid, asked_at, _, ok, top in sel:
                print(f"   {'✅' if ok else '❌'} {uid:22} asked_at={asked_at:6} "
                      f"top4={top}")

    print("\nScore = how often a pre-chosen target reaches the delivered top-4."
          "\nNot a quality grade: a better-suited unit winning counts as a miss.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
