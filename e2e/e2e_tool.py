#!/usr/bin/env python3
"""Helpers for the emulator E2E gate (.github/workflows/mobile-e2e.yml).

Five subcommands, all stdlib-only so they run on a bare GitHub runner:

  deactivate-analytics  Permanently disable Firebase Analytics in a CI manifest.
  l10n         Build flows/common/l10n.js from the app's ARB files, so every
               Maestro selector is written against an ARB *key* and matches
               the Arabic and the English rendering alike. Re-run per install
               lineage: the baseline build is matched with its own strings.
  logcat-gate  Fail on a FATAL EXCEPTION or native crash in the app process,
               an ANR, a Flutter framework/Dart error (release mode), or the
               app's main() running more than once in one process.
  summary      Render results.tsv + the gate verdict as Markdown.
  gallery      Pair the before/after gallery shots (lineage "gallery" in
               run.sh) into gallery-summary.md + an images/ folder, uploaded
               as the e2e-gallery artifact — one download, every pair side
               by side.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import re
import sys
from pathlib import Path

# Firebase Android configuration: this build-time deactivation cannot be
# re-enabled through setAnalyticsCollectionEnabled at runtime.
# https://firebase.google.com/docs/analytics/android/configure-data-collection
_ANDROID = "{http://schemas.android.com/apk/res/android}"
_ANALYTICS_FLAG = "firebase_analytics_collection_deactivated"


def cmd_deactivate_analytics(args: argparse.Namespace) -> int:
    """Change only a disposable CI manifest; reject ambiguous SDK settings."""
    path = Path(args.manifest)
    temporary = None
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        tree = ET.parse(path, parser=parser)
        root = tree.getroot()
        apps = root.findall("application")
        if root.tag != "manifest" or len(apps) != 1:
            raise ValueError("expected exactly one manifest/application")
        app = apps[0]
        flags = [node for node in app.findall("meta-data")
                 if node.get(_ANDROID + "name") == _ANALYTICS_FLAG]
        if len(flags) > 1:
            raise ValueError("duplicate Analytics deactivation metadata")
        if flags and _ANDROID + "resource" in flags[0].attrib:
            raise ValueError("Analytics deactivation uses an ambiguous resource")
        if not flags:
            flags = [ET.SubElement(app, "meta-data", {_ANDROID + "name": _ANALYTICS_FLAG})]
        flags[0].set(_ANDROID + "value", "true")
        ET.register_namespace("android", _ANDROID[1:-1])
        # Replace atomically: failures must not leave a partly written manifest.
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            tree.write(stream, encoding="utf-8", xml_declaration=True)
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"::error::Analytics isolation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"{_ANALYTICS_FLAG}=true in {path}")
    return 0


# ── l10n ─────────────────────────────────────────────────────────────────

# Every ARB key a flow uses. A key missing from the ARB becomes a pattern that
# can never match, so the flow fails on that exact step instead of guessing.
KEYS = [
    # onboarding + tour
    "onbAgeQuestion", "onbStartJourney", "onbDefaultChildName", "onbPreparing",
    "onbServerSlow", "ageGroup7to9", "tourSkip",
    # shell
    "navToday", "navLearn", "navAssistant", "navMore", "hubTitle", "pathsTitle",
    # settings / child profile
    "settings", "settingsTitle", "settingsEditChild", "editChildTitle", "save",
    "editChildSaveBtn", "editChildSaved", "language", "english", "arabic",
    "settingsTheme", "settingsThemeDark",
    # today + lesson
    "startThisLesson", "browsePaths", "continueBtn",
    "lessonMarkComplete", "lessonCompleted", "lessonErrorLoading", "retry",
    # assistant
    "chatTypeHint", "a11ySendQuestion", "chatStop", "feedbackHelpful", "chatRetry",
    # child mode
    "routineTitle", "routineChildMode", "childMode", "habitChildModeExit",
    "a11yExitChildMode",
    "habitChildModeExitTitle", "childModeHandoff", "childModePinMismatch",
    "childModePinIncorrect", "childModeEnterFailed", "childModeBudgetSpent",
    "childModeOffline",
    # failure screens
    "bootError", "forceUpdateTitle",
    # family programs (fresh/09)
    "programsTitle", "programsIntro", "programsPrayerTitle", "prayerStagesTitle",
    # gallery (e2e/flows/gallery/shoot.yaml) — must exist in the BASELINE ARBs
    # too, or the «before» runs lose every step that uses them (verified for
    # efaa740f / 1.0.68+113 on 2026-10-08).
    "pathDetailStart", "pathDetailContinue",
    "lessonQuiz", "quizYourResult", "quizNextQuestion", "quizShowResult",
    "quizErrorLoading",
    "lessonCelebrationTitle", "lessonNextStepTitle", "lessonNextStepConfirm",
    "followupTitle", "followupTitleFor", "followupWorked", "followupThanksTitle",
    "reviewPromptTitle", "reviewPromptLater", "settingsThemeLight",
]

# Strings the app hardcodes outside the ARB files.
LITERALS = {
    # features/onboarding/screens/onboarding_screen.dart, _LanguageSelectionPage
    "lit_langTitle": ("اختر لغة التطبيق", "Choose App Language"),
    "lit_langArabic": ("العربية", "العربية"),
    "lit_langEnglish": ("English", "English"),
    # main.dart, ErrorWidget.builder — what a parent sees when a build throws
    "lit_errorWidget": (
        "تعذّر عرض هذا الجزء. حاول مرة أخرى، وإن تكرّر أرسل لنا ملاحظة.",
        "تعذّر عرض هذا الجزء. حاول مرة أخرى، وإن تكرّر أرسل لنا ملاحظة.",
    ),
    # quiz_screen.dart, _OptionTile — the option letters are Arabic whatever
    # the interface language (String.fromCharCode('أ' + index)).
    "lit_quizOptionA": ("أ", "أ"),
}

_PLACEHOLDER = re.compile(r"(\{\w+\})")
_META = re.compile(r"([\\.^$|?*+()\[\]{}])")


def to_pattern(message: str) -> str:
    """ARB message → Java regex matching the rendered text.

    `{name}` placeholders match anything; a newline matches the newline Flutter
    keeps as well as the space Maestro substitutes for it.
    """
    out = []
    for part in _PLACEHOLDER.split(message):
        if _PLACEHOLDER.fullmatch(part):
            out.append(".*")
        else:
            out.append(_META.sub(r"\\\1", part).replace("\n", r"\s"))
    return "".join(out)


def _either(ar: str, en: str) -> str:
    a, e = to_pattern(ar), to_pattern(en)
    return a if a == e else f"(?:{a}|{e})"


def build_l10n(ar: dict, en: dict) -> tuple[dict, list[str]]:
    """Return ({map name: {key: pattern}}, missing keys)."""
    maps: dict[str, dict[str, str]] = {
        "t": {}, "c": {}, "lead": {}, "tile": {}, "ar": {}, "en": {},
    }
    missing = []
    pairs = {k: (ar.get(k), en.get(k)) for k in KEYS}
    pairs.update(LITERALS)
    for key, (a, e) in pairs.items():
        if not isinstance(a, str) or not isinstance(e, str):
            missing.append(key)
            never = f"__MISSING_ARB_KEY_{key}__"
            for m in maps.values():
                m[key] = never
            continue
        either = _either(a, e)
        maps["t"][key] = either  # the whole text, either language
        maps["c"][key] = f"(?s).*{either}.*"  # contained in a merged node
        # Flutter merges the texts under one tappable widget into one node,
        # one line each. `lead`: the text, then optional lines — a nav
        # destination ("Today" + "Tab 1 of 4") or a settings row (title +
        # subtitle). `tile`: optional lines, then the text — a hub tile
        # (emoji + label).
        maps["lead"][key] = f"(?s){either}(?:\\s.*)?"
        maps["tile"][key] = f"(?s)(?:.*\\s)?{either}"
        maps["ar"][key] = to_pattern(a)  # one language only — proves a switch
        maps["en"][key] = to_pattern(e)
    return maps, missing


def render_js(maps: dict, source: str) -> str:
    lines = [
        f"// GENERATED by e2e/e2e_tool.py l10n from {source} - do not edit or commit.",
        "// t: exact text (ar|en), c: contained, lead/tile: first/last line of a merged node, ar/en: exact, one language",
    ]
    for name, mapping in maps.items():
        lines.append(f"output.{name} = {json.dumps(mapping, ensure_ascii=True, indent=1)};")
    return "\n".join(lines) + "\n"


def cmd_l10n(args: argparse.Namespace) -> int:
    arb = Path(args.arb_dir)
    ar = json.loads((arb / "app_ar.arb").read_text(encoding="utf-8"))
    en = json.loads((arb / "app_en.arb").read_text(encoding="utf-8"))
    maps, missing = build_l10n(ar, en)
    Path(args.out).write_text(render_js(maps, str(arb)), encoding="utf-8")
    for key in missing:
        # Expected for an older baseline build (keys added since); the unit test
        # pins the head build's ARB to the full list.
        print(f"note: ARB key '{key}' missing in {arb}; a step that uses it fails")
    print(f"wrote {args.out} ({len(KEYS) + len(LITERALS) - len(missing)} keys)")
    return 0


# ── logcat gate ──────────────────────────────────────────────────────────

# `adb logcat -v threadtime`:  MM-DD HH:MM:SS.mmm  PID  TID PRIO TAG : message
_LINE = re.compile(r"^\S+\s+\S+\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+(.*?)\s*: (.*)$")

# Flutter release builds print FlutterError.presentError through
# debugPrintStack: the exception text, then the Dart frames. The first error of
# a run has no fixed prefix, so the frames are the marker.
_DART_FRAME = re.compile(r"^#\d+\s+\S|^\s*#\d\d abs [0-9a-f]+|^\*\*\* \*\*\* \*\*\*")

# mobile/lib/main.dart prints this once per run of main(). Two in one process
# mean a second Flutter engine is running the whole app: every startup side
# effect twice, and on a fresh install two device ids — the 2026-10 "device
# twin", caused by audio_service's plugin starting an engine of its own. Builds
# before the marker print nothing, so they are simply not counted.
_MAIN_MARKER = "tg.main: entrypoint started"


def _parse(line: str):
    m = _LINE.match(line)
    if not m:
        return None
    pid, _tid, prio, tag, msg = m.groups()
    return int(pid), prio, tag.strip(), msg


def scan_logcat(lines: list[str], package: str, allow: list[re.Pattern]) -> tuple[list[str], list[str]]:
    """Return (failures, notes). Each failure is one human-readable line."""
    failures: list[str] = []
    notes: list[str] = []
    app_pids: set[int] = set()
    pkg = re.escape(package)
    start_proc = re.compile(rf"Start proc (\d+):{pkg}[/ ]")
    fatal_proc = re.compile(rf"^Process: {pkg}, PID: (\d+)")
    native = re.compile(rf">>> {pkg} <<<")
    anr = re.compile(rf"ANR in {pkg}\b|Application Not Responding: {pkg}\b")

    def allowed(text: str) -> bool:
        return any(p.search(text) for p in allow)

    def fail(kind: str, text: str) -> None:
        line = f"{kind}: {text.strip()[:300]}"
        if allowed(line):
            notes.append(f"allowlisted {line}")
        elif line not in failures:
            failures.append(line)

    pending_fatal: str | None = None
    prev_flutter_msg = ""
    in_trace = False
    main_runs: dict[int, int] = {}
    for raw in lines:
        parsed = _parse(raw.rstrip("\n"))
        if not parsed:
            continue
        pid, prio, tag, msg = parsed

        m = start_proc.search(msg)
        if m:
            app_pids.add(int(m.group(1)))

        if tag == "AndroidRuntime":
            if msg.startswith("FATAL EXCEPTION"):
                pending_fatal = msg
                continue
            if pending_fatal is not None:
                m = fatal_proc.match(msg)
                if m:
                    app_pids.add(int(m.group(1)))
                    fail("FATAL EXCEPTION", f"{pending_fatal} — {msg}")
                    pending_fatal = None
                    continue
                if msg.startswith("Process:"):
                    pending_fatal = None  # another app's crash, not ours
        if native.search(msg):
            fail("NATIVE CRASH", msg)
        if anr.search(msg):
            fail("ANR", msg)

        if tag != "flutter":
            ours = not app_pids or pid in app_pids
            if ours and tag == "FirebaseCrashlytics" and "Persisting non-fatal event" in msg:
                # The app's own triage (core/crash_triage.dart) already drops
                # connectivity noise and layout overflow before recording, so a
                # recorded non-fatal is a real Dart/Flutter error.
                fail("FLUTTER ERROR (recorded non-fatal)", msg)
            continue

        # tag == "flutter": the Dart side of the app.
        if msg.startswith(_MAIN_MARKER):
            main_runs[pid] = main_runs.get(pid, 0) + 1
        if prio in "EF":
            fail("FLUTTER ERROR (engine)", msg)
        elif "Another exception was thrown" in msg or "EXCEPTION CAUGHT BY" in msg:
            fail("FLUTTER ERROR", msg)
        elif _DART_FRAME.search(msg):
            if not in_trace:
                fail("FLUTTER ERROR (Dart stack trace)", prev_flutter_msg or msg)
            in_trace = True
            continue
        in_trace = False
        prev_flutter_msg = msg

    if pending_fatal is not None:
        notes.append(f"unattributed {pending_fatal}")
    for pid, runs in sorted(main_runs.items()):
        if runs > 1:
            fail("SECOND DART ENTRYPOINT",
                 f"main() ran {runs} times in process {pid} — a second Flutter engine is running the app")
    notes.append(f"app pids seen: {sorted(app_pids) or 'none'}")
    if main_runs:
        notes.append("main() runs per process: "
                     + ", ".join(f"{pid}={n}" for pid, n in sorted(main_runs.items())))
    return failures, notes


def load_allowlist(path: Path | None) -> list[re.Pattern]:
    if not path or not path.exists():
        return []
    pats = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pats.append(re.compile(line))
    return pats


def cmd_logcat_gate(args: argparse.Namespace) -> int:
    lines = Path(args.logcat).read_text(encoding="utf-8", errors="replace").splitlines()
    allow = load_allowlist(Path(args.allowlist) if args.allowlist else None)
    failures, notes = scan_logcat(lines, args.package, allow)
    # A capture this short proves nothing, so it is a failure in its own right —
    # recorded in the verdict file too, which used to say "PASS" beside it.
    short = len(lines) < args.min_lines
    if short:
        failures = [f"capture: only {len(lines)} lines (< {args.min_lines}) — the gate proves nothing"] + failures
    report = [f"logcat lines scanned: {len(lines)}"]
    report += [f"FAIL  {f}" for f in failures] or ["PASS  no crash, ANR or Flutter error"]
    report += [f"note  {n}" for n in notes]
    text = "\n".join(report) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    if short:
        print(f"::error::logcat has only {len(lines)} lines — capture failed, so the gate proves nothing")
    return 1 if failures else 0


# ── gallery ──────────────────────────────────────────────────────────────
#
# run.sh's "gallery" lineage photographs the same screens on the baseline
# build («before») and the PR head («after») — Arabic, English, and a 200%
# font-scale pass. The shots land in the flat e2e-screenshots dir named
#   gallery__<flow>__<tag>__<variant>__<screen>.png
# where tag ∈ {before, after}. This subcommand pairs them into one Markdown
# file with relative image links, so a single artifact download is the whole
# review. Onboarding is paired across lineages: the gallery lineage's
# baseline onboarding is the «before», the fresh lineage's head onboarding
# (identical flow file, identical shot names) is the «after».

GALLERY_VARIANTS = [
    ("ar", "العربية"),
    ("en", "English"),
    ("ar_font2x", "العربية · خط ٢٠٠٪"),
]

# (screen id in the shot name, Arabic caption). Keep the ids in sync with
# e2e/flows/gallery/shoot.yaml — the pairing is a lookup, not a glob, so a
# shot that was never taken shows as a missing cell instead of vanishing.
GALLERY_SCREENS = [
    ("home", "اليوم — البداية"),
    ("followup_card", "بطاقة المتابعة على «اليوم»"),
    ("path_detail", "تفاصيل المسار"),
    ("lesson", "شاشة الدرس"),
    ("quiz", "سؤال الاختبار"),
    ("quiz_summary", "نتيجة الاختبار"),
    ("celebration", "احتفال إكمال الدرس"),
    ("next_step", "خطوة الليلة"),
    ("home_after_lesson", "اليوم بعد الإكمال"),
    ("followup", "ورقة المتابعة"),
    ("settings", "الإعدادات"),
    ("settings_dark", "الإعدادات — داكن"),
    ("home_dark", "اليوم — داكن"),
]

GALLERY_ONBOARDING = [
    ("onboarding_1_language", "أول تشغيل — اختيار اللغة"),
    ("onboarding_2_first_tip", "أول تشغيل — أول نصيحة"),
]

# Screens a shoot may legitimately miss (guarded in shoot.yaml): a follow-up
# only exists when one is due, the in-lesson quiz retry is bounded, and the
# first run starts the first lesson directly instead of continuing an existing
# path. Every OTHER screen must have an «after» shot in every variant — with
# --require-after (what run.sh passes on CI) a missing one fails the build, so
# the gallery can never go green while blind again.
GALLERY_GUARDED = {"followup_card", "followup", "quiz", "quiz_summary", "path_detail"}

# gallery__01_before_ar__before__ar__home.png — the flow name is matched
# lazily so renaming a flow cannot break the pairing. The optional trailing
# _<digits> is Maestro's collision suffix. Screen ids are looked up one by
# one, so home never swallows home_after_lesson.
_GALLERY_FILE = re.compile(
    r"^gallery__.*?__(?P<tag>before|after)__(?P<variant>ar_font2x|ar|en)"
    r"__(?P<screen>[a-z0-9_]+?)(?:_\d+)?\.png$"
)


def index_gallery(screens: Path) -> dict[tuple[str, str, str], str]:
    """{(tag, variant, screen): filename} for every gallery shot found."""
    index: dict[tuple[str, str, str], str] = {}
    for png in sorted(screens.glob("*.png")):
        m = _GALLERY_FILE.match(png.name)
        if m:
            key = (m.group("tag"), m.group("variant"), m.group("screen"))
            index.setdefault(key, png.name)
    return index


def _gallery_pair(screens: Path, before_pat: str, after_pat: str):
    """First match of each pattern (oldest flow run wins on repeats)."""
    def first(pat: str) -> str | None:
        for name in sorted(screens.glob(pat)):
            return name.name
        return None
    return first(before_pat), first(after_pat)


def cmd_gallery(args: argparse.Namespace) -> int:
    screens = Path(args.screens)
    out = Path(args.out)
    images = out / "images"
    images.mkdir(parents=True, exist_ok=True)
    index = index_gallery(screens)

    def cell(fname: str | None, caption: str) -> str:
        if fname is None:
            return "—"
        shutil.copy(screens / fname, images / fname)
        return f'<img src="images/{fname}" width="270" alt="{caption}">'

    md = [
        "## معرض «قبل/بعد»",
        "",
        "«قبل» = نسخة الإنتاج الحالية (baseline APK) · «بعد» = رأس هذا الـPR.",
        "الصور في مجلد `images/` بجوار هذا الملف — التنزيل واحد والمراجعة كاملة.",
        "",
    ]
    counts = {"complete": 0, "before-only": 0, "after-only": 0, "missing": 0}

    def table(rows) -> None:
        md.extend(["| الشاشة | قبل | بعد |", "|---|---|---|"])
        md.extend(rows)

    for variant, label in GALLERY_VARIANTS:
        rows = []
        for screen, caption in GALLERY_SCREENS:
            before = index.get(("before", variant, screen))
            after = index.get(("after", variant, screen))
            if before and after:
                counts["complete"] += 1
            elif before:
                counts["before-only"] += 1
            elif after:
                counts["after-only"] += 1
            else:
                counts["missing"] += 1
            rows.append(f"| {caption} | {cell(before, caption)} | {cell(after, caption)} |")
        md.extend([f"### {label}", ""])
        table(rows)
        md.append("")

    rows = []
    for screen, caption in GALLERY_ONBOARDING:
        before, after = _gallery_pair(
            screens, f"gallery__*__{screen}.png", f"fresh__01_onboarding__{screen}.png")
        if before and after:
            counts["complete"] += 1
        elif before:
            counts["before-only"] += 1
        elif after:
            counts["after-only"] += 1
        else:
            counts["missing"] += 1
        rows.append(f"| {caption} | {cell(before, caption)} | {cell(after, caption)} |")
    md.extend(["### أول التشغيل (عربي، عبر المسارين gallery/fresh)", ""])
    table(rows)
    md.append("")

    stats = "complete={complete} before-only={before-only} after-only={after-only} missing={missing}".format(**counts)
    # Parsed by `summary` — keep the exact comment form.
    md.append(f"<!-- gallery: {stats} -->")
    (out / "gallery-summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"gallery: {stats} → {out / 'gallery-summary.md'}")

    if args.require_after:
        blind = [
            f"{variant}:{screen}"
            for variant, _label in GALLERY_VARIANTS
            for screen, _caption in GALLERY_SCREENS
            if screen not in GALLERY_GUARDED
            and index.get(("after", variant, screen)) is None
        ]
        for screen, _caption in GALLERY_ONBOARDING:
            if _gallery_pair(screens, f"gallery__*__{screen}.png",
                             f"fresh__01_onboarding__{screen}.png")[1] is None:
                blind.append(f"onboarding:{screen}")
        if blind:
            print("::error title=E2E gallery::المعرض أعمى — خانة «بعد» فاضية: "
                  + ", ".join(blind))
            return 1
    return 0


# ── summary ──────────────────────────────────────────────────────────────

def cmd_summary(args: argparse.Namespace) -> int:
    out = Path(args.out_dir)
    rows = []
    results = out / "results.tsv"
    if results.exists():
        for line in results.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 4:
                rows.append(parts)
    md = ["## Mobile E2E (emulator)", ""]
    meta = out / "meta.md"
    if meta.exists():
        md += [meta.read_text(encoding="utf-8").strip(), ""]
    md += ["| lineage | checkpoint | result | seconds |", "|---|---|---|---|"]
    icon = {"0": "✅ pass", "skip": "⏭️ skipped"}
    for lineage, name, rc, secs, *rest in rows:
        note = rest[0] if rest else ""
        if note == "informational":
            result = "✅ pass" if rc == "0" else f"⚠️ fail (informational, rc={rc})"
        else:
            result = icon.get(rc, f"❌ fail (rc={rc})") + (f" — {note}" if note else "")
        md.append(f"| {lineage} | {name} | {result} | {secs} |")
    onboarding = [r for r in rows if r[1].startswith("01_") and r[2] not in ("0", "skip")]
    if onboarding:
        md += ["", "⚠️ Onboarding failed in: " + ", ".join(r[0] for r in onboarding)
               + ". If the child was already created, its device is NOT marked (the child keeps"
               " «طفلي» / «My child»): check the checkpoint screenshots and exclude that device by"
               " child_profiles.created_at (UTC) of this run."]
    gate = out / "logcat" / "gate.txt"
    md += ["", "### logcat gate", "```", gate.read_text(encoding="utf-8").strip() if gate.exists() else "not run", "```"]
    shots = sorted((out / "screens").glob("*.png")) if (out / "screens").exists() else []
    md += ["", f"Screenshots: {len(shots)} (artifact `e2e-screenshots`)"]
    gallery = out / "gallery" / "gallery-summary.md"
    if gallery.exists():
        m = re.search(r"<!-- gallery: (.+?) -->", gallery.read_text(encoding="utf-8"))
        if m:
            md += ["", f"Gallery قبل/بعد: {m.group(1)} (artifact `e2e-gallery`)"]
    text = "\n".join(md) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("deactivate-analytics", help="disable Analytics in a disposable CI manifest")
    s.add_argument("--manifest", required=True)
    s.set_defaults(func=cmd_deactivate_analytics)

    s = sub.add_parser("l10n", help="generate flows/common/l10n.js")
    s.add_argument("--arb-dir", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_l10n)

    s = sub.add_parser("logcat-gate", help="fail on crash / ANR / Flutter error")
    s.add_argument("logcat")
    s.add_argument("--package", default="com.alsaba.almorabbi")
    s.add_argument("--allowlist")
    s.add_argument("--out")
    s.add_argument("--min-lines", type=int, default=200)
    s.set_defaults(func=cmd_logcat_gate)

    s = sub.add_parser("gallery", help="pair the before/after shots into gallery-summary.md")
    s.add_argument("screens", help="dir with the flattened e2e screenshots")
    s.add_argument("--out", required=True, help="dir for gallery-summary.md + images/")
    s.add_argument("--require-after", action="store_true",
                   help="fail (exit 1) if any non-guarded screen lacks an «after» shot")
    s.set_defaults(func=cmd_gallery)

    s = sub.add_parser("summary", help="render the Markdown summary")
    s.add_argument("out_dir")
    s.set_defaults(func=cmd_summary)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
