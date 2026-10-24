"""«صورة حيّة» experiment — the numbers the weekly report and the month-end
verdict read from `story_events` (routers/story_events.py).

Arms: `motion` (living pictures + narrator cues) and `static` (the same
paintings still). Devices with the system's reduce-motion on always see the
still picture and are left out of every number here — they did not choose an
arm, and counting them would tilt `static`.

Pure functions over plain rows, so they test without a database.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

ARMS = ("motion", "static")
LOVED = 3  # rating 3 = 😍, 2 = 🙂, 1 = 😐

# Below these the verdict says "not enough data" instead of guessing.
MIN_OPENS_PER_ARM = 100
MIN_RATINGS_PER_ARM = 30


def _ts(value) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def arm_summary(rows: list[dict], arm: str) -> dict:
    """One arm's numbers over [rows] (already limited to the period)."""
    rs = [r for r in rows if r["variant"] == arm and not r["reduce_motion"]]
    by = defaultdict(list)
    for r in rs:
        by[r["name"]].append(r)
    opens = len(by["story_opened"])
    finished = len(by["story_finished"])
    ratings = {k: 0 for k in (1, 2, 3)}
    for r in by["story_rated"]:
        if r["rating"] in ratings:
            ratings[r["rating"]] += 1
    listened = sum(1 for r in by["story_page_viewed"]
                   if r["narration_on"] and r["page_index"] == 0)
    listened_through = sum(1 for r in by["story_finished"] if r["narration_on"])
    rated = sum(ratings.values())
    return {
        "arm": arm,
        "devices": len({r["device_id"] for r in rs}),
        "opens": opens,
        "finished": finished,
        "completion": finished / opens if opens else None,
        "pages_per_open": len(by["story_page_viewed"]) / opens if opens else None,
        "ratings": ratings,
        "rated": rated,
        "loved_share": ratings[LOVED] / rated if rated else None,
        "listen_starts": listened,
        "listen_through": min(1.0, listened_through / listened) if listened else None,
    }


def reopen_rate(rows: list[dict], arm: str, first_from: datetime, first_to: datetime) -> float | None:
    """Of the (device, story) pairs first opened in [first_from, first_to),
    the share opened again 1 h – 7 days after that first open. [rows] must
    reach 7 days past first_to."""
    opens = defaultdict(list)
    for r in rows:
        if r["name"] == "story_opened" and r["variant"] == arm and not r["reduce_motion"]:
            opens[(r["device_id"], r["story_id"])].append(_ts(r["created_at"]))
    pairs = again = 0
    for times in opens.values():
        times.sort()
        first = times[0]
        if not (first_from <= first < first_to):
            continue
        pairs += 1
        if any(timedelta(hours=1) <= t - first <= timedelta(days=7) for t in times[1:]):
            again += 1
    return again / pairs if pairs else None


def device_completion(rows: list[dict], arm: str) -> tuple[int, int]:
    """(devices that finished at least one story, devices that opened one) —
    the same question with the device as the unit, so one keen reader's
    twenty openings cannot carry an arm."""
    opened, finished = set(), set()
    for r in rows:
        if r["variant"] != arm or r["reduce_motion"]:
            continue
        if r["name"] == "story_opened":
            opened.add(r["device_id"])
        elif r["name"] == "story_finished":
            finished.add(r["device_id"])
    return len(finished & opened), len(opened)


@dataclass(frozen=True)
class ZTest:
    p1: float
    p2: float
    n1: int
    n2: int
    z: float
    p_value: float


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> ZTest | None:
    """Pooled two-proportion z-test, two-sided. None if a side is empty or
    the pooled proportion is 0 or 1 (no variance to test)."""
    if n1 <= 0 or n2 <= 0:
        return None
    p1, p2 = x1 / n1, x2 / n2
    pool = (x1 + x2) / (n1 + n2)
    var = pool * (1 - pool) * (1 / n1 + 1 / n2)
    if var <= 0:
        return None
    z = (p1 - p2) / math.sqrt(var)
    return ZTest(p1, p2, n1, n2, z, math.erfc(abs(z) / math.sqrt(2)))


def min_detectable_difference(p: float, n_per_arm: int) -> float | None:
    """Smallest difference a two-sided 5% test finds with 80% power at
    baseline [p] and [n_per_arm] per arm (normal approximation)."""
    if n_per_arm <= 0:
        return None
    return (1.96 + 0.84) * math.sqrt(2 * p * (1 - p) / n_per_arm)


def verdict(rows: list[dict]) -> dict:
    """The month-end call: which STORY_MOTION_MODE to set, and why."""
    m, s = arm_summary(rows, "motion"), arm_summary(rows, "static")
    out = {"motion": m, "static": s, "completion": None, "loved": None,
           "device_completion": None, "mode": None, "reasons": []}
    enough_opens = min(m["opens"], s["opens"]) >= MIN_OPENS_PER_ARM
    enough_ratings = min(m["rated"], s["rated"]) >= MIN_RATINGS_PER_ARM
    if enough_opens:
        out["completion"] = two_proportion_z(m["finished"], m["opens"], s["finished"], s["opens"])
        out["device_completion"] = two_proportion_z(
            *device_completion(rows, "motion"), *device_completion(rows, "static"))
    if enough_ratings:
        out["loved"] = two_proportion_z(m["ratings"][LOVED], m["rated"],
                                        s["ratings"][LOVED], s["rated"])
    if not enough_opens and not enough_ratings:
        out["mode"] = None
        out["reasons"].append(
            f"not enough data: opens {m['opens']}/{s['opens']} (need {MIN_OPENS_PER_ARM} each), "
            f"ratings {m['rated']}/{s['rated']} (need {MIN_RATINGS_PER_ARM} each)")
        return out

    def winner(t: ZTest | None) -> str | None:
        if t is None or t.p_value >= 0.05:
            return None
        return "motion" if t.p1 > t.p2 else "static"

    wc, wl = winner(out["completion"]), winner(out["loved"])
    if wc and wl and wc != wl:
        out["reasons"].append(f"mixed: completion favours {wc}, 😍 favours {wl}")
    elif wc or wl:
        out["mode"] = wc or wl
        out["reasons"].append(
            f"{out['mode']} wins on " + " and ".join(
                k for k, w in (("completion", wc), ("😍 share", wl)) if w))
    else:
        out["reasons"].append(
            "no difference this sample can detect (p ≥ 0.05) — the arms read and are "
            "liked about the same; pick by preference")
    if not enough_opens:
        out["reasons"].append(f"completion not tested: fewer than {MIN_OPENS_PER_ARM} opens in an arm")
    if not enough_ratings:
        out["reasons"].append(f"😍 not tested: fewer than {MIN_RATINGS_PER_ARM} ratings in an arm")
    return out
