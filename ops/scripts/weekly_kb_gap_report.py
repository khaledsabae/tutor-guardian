#!/usr/bin/env python3
"""Weekly knowledge-gap report — turns the week's parent questions into a
ranked list of what the knowledge base failed to answer, and sends it to
Telegram.

Usage (VPS cron, every Saturday 06:00 UTC):
    docker exec -w /app tg_backend python ops/scripts/weekly_kb_gap_report.py \
        >> /var/log/tg-kb-gaps.log 2>&1

The loop:
    chat_messages (role='user', last 7 days)
      → drop the app's own suggested questions and sub-12-character noise
      → ops/tools/retrieval_probe.py   (real classify → rewrite → retrieve)
      → ops/tools/kb_gap_judge.py      (DeepSeek verdict per (question, unit))
      → report: unanswered rate · gap domains · unserved topics → Telegram

Two things this exists to stop:

  1. Ranking questions by raw frequency measures the app's 19 suggestion
     buttons, not parents. The five most common "questions" in production were
     all chatQ_* button text. They are excluded here before anything is counted.

  2. Privacy. These are parents writing about their children, sometimes by
     name. Aggregate analysis is fine; the Telegram message must never carry a
     detail that identifies anyone. Raw question text stays in the JSON files
     on the VPS — only counts, domains, and coarse topic labels are sent.

Requires: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (or --token / --chat-id),
and DEEPSEEK_API_KEY for the judging step.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_DB = Path(os.environ.get(
    "CONVERSATIONS_DB", str(_ROOT / "ops" / "conversations.db"),
))
_ARB = _ROOT / "mobile" / "lib" / "l10n" / "app_ar.arb"
_TOOLS = _ROOT / "ops" / "tools"

# Telegram rejects messages over 4096 characters outright. weekly_dashboard.py
# has no guard because its report is a fixed size; this one grows with the
# number of gaps found, so it must chunk.
_TG_LIMIT = 3800

_MIN_CHARS = 12  # below this a "question" is a greeting or a stray tap (~8%)
_TIP_PREFIX = "بخصوص نصيحة اليوم"


def _query(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _normalize(text: str) -> str:
    """Loose match key: collapse whitespace, drop tatweel and diacritics.

    Suggested questions arrive as button text but can be edited by the parent
    or re-encoded, so an exact string compare misses some of them.
    """
    t = re.sub(r"[ـً-ْ]", "", text or "")
    return " ".join(t.split()).strip()


class SuggestionsUnavailable(RuntimeError):
    """The chatQ_* strings could not be loaded — see _suggested_questions."""


def _suggested_questions(arb_path: Path) -> set[str]:
    """The chatQ_* strings shipped in the app, normalized.

    Raises rather than degrading. The container image does not carry
    `mobile/`, so this file is present only because the production compose
    binds it read-only — and if that bind ever goes away, a report built
    without this filter would look completely normal while ranking the app's
    own suggestion buttons as if parents had typed them. A missing filter is
    not a smaller report, it is a wrong one.
    """
    if not arb_path.exists():
        raise SuggestionsUnavailable(
            f"{arb_path} غير موجود — بلا استبعاد الاقتراحات الجاهزة يقيس "
            f"التقرير أزرار التطبيق لا المستخدمين. تحقّق من الـbind في "
            f"docker-compose.production.yml، أو مرّر --arb، أو "
            f"--allow-unfiltered إن كنت تقبل تقريرًا ملوَّثًا عن عمد."
        )
    with open(arb_path, encoding="utf-8") as fh:
        arb = json.load(fh)
    keys = {
        _normalize(v) for k, v in arb.items()
        if k.startswith("chatQ") and isinstance(v, str)
    }
    if not keys:
        raise SuggestionsUnavailable(f"{arb_path} لا يحوي مفاتيح chatQ_*.")
    return keys


def collect_questions(days: int, arb_path: Path,
                      allow_unfiltered: bool = False) -> tuple[list[dict], dict]:
    """The week's genuine parent questions, plus what was filtered and why."""
    rows = _query(
        """SELECT id, content, domain, created_at
           FROM chat_messages
           WHERE role = 'user'
             AND created_at >= datetime('now', ?)
           ORDER BY id""",
        (f"-{days} days",),
    )
    try:
        suggested = _suggested_questions(arb_path)
    except SuggestionsUnavailable:
        if not allow_unfiltered:
            raise
        print("⚠️  --allow-unfiltered: التقرير يقيس الأزرار أيضًا.", file=sys.stderr)
        suggested = set()
    kept, n_sugg, n_short = [], 0, 0
    for r in rows:
        norm = _normalize(r["content"])
        if norm in suggested:
            n_sugg += 1
            continue
        if len(norm) < _MIN_CHARS:
            n_short += 1
            continue
        kept.append({**r, "norm": norm})
    return kept, {
        "total": len(rows),
        "suggested_dropped": n_sugg,
        "short_dropped": n_short,
        "kept": len(kept),
    }


def unanswered_stats(days: int) -> dict:
    """The 3% target metric.

    Two shapes of failure, and they are not the same thing:
      * `mode='error'/'interrupted'` — the fix shipped 2026-08-13 records these
        explicitly, so they are countable rather than merely absent.
      * an orphan user row with no assistant row at all — what the old silent
        path left behind, and what still shows up for anything the new
        persistence misses.
    """
    orphans = _query(
        """WITH m AS (
             SELECT id, session_id, role, created_at,
                    LEAD(role) OVER (PARTITION BY session_id ORDER BY id) AS nr
             FROM chat_messages
             WHERE created_at >= datetime('now', ?))
           SELECT COUNT(*) n FROM m
           WHERE role='user' AND (nr IS NULL OR nr='user')""",
        (f"-{days} days",),
    )[0]["n"]
    total = _query(
        "SELECT COUNT(*) n FROM chat_messages WHERE role='user' "
        "AND created_at >= datetime('now', ?)", (f"-{days} days",),
    )[0]["n"]
    modes = _query(
        "SELECT mode, COUNT(*) n FROM chat_messages WHERE role='assistant' "
        "AND created_at >= datetime('now', ?) GROUP BY mode", (f"-{days} days",),
    )
    degraded = sum(m["n"] for m in modes if m["mode"] in ("error", "interrupted"))
    return {
        "total": total,
        "orphans": orphans,
        "degraded": degraded,
        "rate": (orphans + degraded) / total if total else 0.0,
        "modes": {m["mode"]: m["n"] for m in modes},
    }


def _run_tool(script: str, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(_TOOLS / script), *args],
        capture_output=True, text=True, timeout=3600,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def probe_and_judge(questions: list[dict], workdir: Path, sample: int,
                    max_pairs: int, concurrency: int) -> dict | None:
    """Run the shipped tools over a sample and return the judge's summary."""
    workdir.mkdir(parents=True, exist_ok=True)
    qfile = workdir / "week_questions.jsonl"
    with open(qfile, "w", encoding="utf-8") as fh:
        for q in questions[:sample]:
            fh.write(json.dumps(
                {"question": q["content"], "age_group": "unspecified"},
                ensure_ascii=False) + "\n")

    pairs = workdir / "retrieval_pairs.json"
    code, out = _run_tool("retrieval_probe.py", [
        "--questions-file", str(qfile), "--out", str(pairs), "--quiet",
    ])
    print(out.strip())
    if code != 0:
        print(f"⚠️  retrieval_probe فشل (خروج {code}) — لا حكم هذا الأسبوع.",
              file=sys.stderr)
        return None

    judged = workdir / "retrieval_judged.json"
    code, out = _run_tool("kb_gap_judge.py", [
        "--in", str(pairs), "--out", str(judged), "--quiet",
        "--max-pairs", str(max_pairs), "--concurrency", str(concurrency),
    ])
    print(out.strip())
    if code != 0:
        print(f"⚠️  kb_gap_judge فشل (خروج {code}).", file=sys.stderr)
        return None

    sys.path.insert(0, str(_TOOLS))
    from kb_gap_judge import summarize  # noqa: E402  (tool dir added above)
    with open(judged, encoding="utf-8") as fh:
        s = summarize(json.load(fh))

    # The judge only ever sees (question, unit) pairs, so a question that
    # retrieved NOTHING produces no pairs and vanishes from its summary —
    # and those are the worst-served questions of all, not the best. On the
    # first real run that was 26 of 100, which would have reported 51/72
    # unserved instead of the true 77/100.
    with open(pairs, encoding="utf-8") as fh:
        probed = json.load(fh)
    no_units = [r["question"] for r in probed if not r.get("units")]
    s["probed_questions"] = len(probed)
    s["no_unit_questions"] = no_units
    s["unserved_total"] = len(s["unserved_questions"]) + len(no_units)
    return s


def _topic_label(text: str) -> str:
    """A coarse bucket, never the parent's own words.

    Privacy is the reason this is keyword matching and not, say, the first six
    words of the question: a topic label cannot identify a child, a quoted
    sentence can.
    """
    buckets = [
        # First on purpose. The five curriculum domains are all about the
        # child; none is about the parent. A mother writing "بحس اني ام عصبية"
        # is asking about herself, and a keyword like عصبي would otherwise
        # file her under the child's anger — hiding the one bucket that would
        # tell us a whole domain is missing.
        ("الوالد نفسه", ("انا ام", "أنا أم", "انا اب", "أنا أب", "بحس اني",
                         "بحس إني", "نفسي اني", "زهقانة", "زهقان", "مرهقة",
                         "تعبانة نفسيا", "بعصب على")),
        ("النوم", ("نوم", "ينام", "تنام", "سهر")),
        ("الغضب والعناد", ("غضب", "عصبي", "عناد", "زعل", "نوبات")),
        ("الصلاة والعبادة", ("صلا", "صيام", "قرآن", "حجاب", "دين")),
        ("الشاشات والألعاب", ("موبايل", "تابلت", "لعبة", "ألعاب", "يوتيوب", "تيك")),
        ("الدراسة", ("مذاكر", "مدرس", "واجب", "امتحان", "درس")),
        ("الأكل", ("أكل", "ياكل", "طعام", "وزن")),
        ("الإخوة", ("أخو", "أخته", "اخوه", "غيرة")),
        ("المراهقة", ("مراهق", "بلوغ", "سن ال")),
        ("الكلام والنطق", ("كلام", "نطق", "يتكلم", "تأخر")),
    ]
    for label, keys in buckets:
        if any(k in text for k in keys):
            return label
    return "غير مصنَّف"


def format_report(days: int, filt: dict, unans: dict, judged: dict | None,
                  questions: list[dict], judge_skipped: bool = False) -> str:
    lines = [f"📊 <b>تقرير فجوات المعرفة — آخر {days} أيام</b>", ""]

    lines.append("<b>الأسئلة</b>")
    lines.append(f"  • أسئلة المستخدمين: {filt['total']}")
    lines.append(f"  • بعد استبعاد الاقتراحات الجاهزة: −{filt['suggested_dropped']}")
    lines.append(f"  • بعد استبعاد ما دون {_MIN_CHARS} حرفًا: −{filt['short_dropped']}")
    lines.append(f"  • <b>أسئلة حقيقية: {filt['kept']}</b>")
    lines.append("")

    rate = 100 * unans["rate"]
    mark = "✅" if rate < 3 else ("⚠️" if rate < 8 else "🚨")
    lines.append(f"<b>{mark} بلا إجابة: {rate:.1f}%</b>  (الهدف &lt; 3%)")
    lines.append(f"  • أسئلة يتيمة بلا صف إجابة: {unans['orphans']}")
    lines.append(f"  • إجابات معطوبة (error/interrupted): {unans['degraded']}")
    if unans["modes"]:
        top_modes = sorted(unans["modes"].items(), key=lambda x: -x[1])[:4]
        lines.append("  • أنماط الردود: "
                     + "، ".join(f"{k or '—'}={v}" for k, v in top_modes))
    lines.append("")

    tips = sum(1 for q in questions if q["content"].startswith(_TIP_PREFIX))
    if questions:
        lines.append(f"<b>محرّك المساعد</b>: {tips} من {len(questions)} "
                     f"({100*tips/len(questions):.0f}%) بدأت من نصيحة اليوم")
        lines.append("")

    lines.append("<b>المواضيع</b>")
    for topic, n in Counter(_topic_label(q["content"]) for q in questions).most_common(8):
        lines.append(f"  • {topic}: {n}")
    lines.append("")

    if judged:
        c = judged["counts"]
        probed = judged.get("probed_questions", judged["questions"])
        lines.append(f"<b>حكم الاسترجاع</b> (عيّنة {probed} سؤال · "
                     f"{judged['pairs']} زوج)")
        for g in ("صلة", "جزئية", "لا صلة", "?"):
            if c.get(g):
                lines.append(f"  • {g}: {c[g]} ({100*c[g]/judged['pairs']:.0f}%)")
        no_units = judged.get("no_unit_questions", [])
        unserved = judged["unserved_questions"]
        total_unserved = judged.get("unserved_total", len(unserved))
        lines.append(f"  • <b>لم يخدمها الاسترجاع: {total_unserved} من {probed}</b> "
                     f"({100*total_unserved/max(probed,1):.0f}%)")
        lines.append(f"    منها {len(no_units)} لم يُسترجع لها شيء أصلًا، "
                     f"و{len(unserved)} استُرجع لها ما لا يخدمها")
        gaps = unserved + no_units
        if gaps:
            lines.append("")
            lines.append("<b>أين تعمّق المحتوى</b> (مواضيع الفجوات)")
            for topic, n in Counter(_topic_label(q) for q in gaps).most_common(6):
                lines.append(f"  • {topic}: {n}")
    elif judge_skipped:
        lines.append("<i>الحكم متجاوَز بطلب صريح (--skip-judge) — أعداد فقط.</i>")
    else:
        lines.append("<i>⚠️ الحكم فشل هذا الأسبوع — راجع اللوج.</i>")

    lines.append("")
    lines.append("<i>تجميعي فقط — نصوص الأسئلة لا تغادر الخادم.</i>")
    return "\n".join(lines)


def _chunk(text: str, limit: int = _TG_LIMIT) -> list[str]:
    """Split on line boundaries so a report never dies at Telegram's 4096."""
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit:
            chunks.append(cur.rstrip())
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur.rstrip())
    return chunks or [""]


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok_all = True
    for part in _chunk(text):
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": part, "parse_mode": "HTML",
        }).encode()
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if not json.loads(resp.read()).get("ok", False):
                    ok_all = False
        except Exception as e:  # noqa: BLE001
            print(f"Telegram send failed: {e}", file=sys.stderr)
            ok_all = False
    return ok_all


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Weekly KB gap report")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--sample", type=int, default=100,
                    help="questions sent through retrieval + judging")
    ap.add_argument("--max-pairs", type=int, default=400)
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--workdir", default="/tmp/kb_gaps")
    ap.add_argument("--arb", default=str(_ARB),
                    help="app_ar.arb holding the chatQ_* suggestion strings")
    ap.add_argument("--allow-unfiltered", action="store_true",
                    help="run even without the suggestion list (report will be skewed)")
    ap.add_argument("--skip-judge", action="store_true",
                    help="counts only — no retrieval, no DeepSeek spend")
    ap.add_argument("--token", help="Telegram bot token (or env TELEGRAM_BOT_TOKEN)")
    ap.add_argument("--chat-id", help="Telegram chat ID (or env TELEGRAM_CHAT_ID)")
    ap.add_argument("--dry-run", action="store_true", help="print, do not send")
    args = ap.parse_args(argv)

    print(f"Collecting questions (last {args.days} days) from {_DB}...")
    try:
        questions, filt = collect_questions(
            args.days, Path(args.arb), args.allow_unfiltered)
    except SuggestionsUnavailable as exc:
        print(f"🚨 {exc}", file=sys.stderr)
        return 2
    print(f"  {filt}")

    print("Computing unanswered rate...")
    unans = unanswered_stats(args.days)
    print(f"  {unans}")

    judged = None
    if args.skip_judge:
        print("Judging skipped (--skip-judge).")
    elif not questions:
        print("No questions this week — nothing to judge.")
    else:
        print(f"Probing + judging a sample of {min(args.sample, len(questions))}...")
        judged = probe_and_judge(questions, Path(args.workdir), args.sample,
                                 args.max_pairs, args.concurrency)

    report = format_report(args.days, filt, unans, judged, questions,
                           judge_skipped=args.skip_judge)

    if args.dry_run:
        print("\n" + report)
        return 0

    token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = args.chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Warning: no Telegram credentials, printing report only", file=sys.stderr)
        print(report)
        return 0

    if send_telegram(token, chat_id, report):
        print("Report sent to Telegram successfully")
        return 0
    print("Failed to send report", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
