#!/usr/bin/env python3
"""Helpers for the emulator E2E gate (.github/workflows/mobile-e2e.yml).

Subcommands, all stdlib-only so they run on a bare GitHub runner:

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

The Ramadan rehearsal (job `rehearsal`, e2e/rehearsal.sh):
  as-of-proxy      Stand between the CI-only APKs and the candidate backend
                   and add the stage's `as_of` to every family-programs call.
  as-of-preflight  Prove the candidate honours `as_of` for each stage (and
                   the proxy adds it) before an emulator is involved; write
                   the stage dates, derived from the server's own season.
  as-of-report     Every stage's programs calls carried `as_of` and none was
                   refused.
  audio-focus      Judge two `dumpsys audio` dumps: the recitation still
                   plays after the interface ticks, and no tick took focus.
  rehearsal-gallery  The stage × variant gallery (Play build vs PR head).
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import re
import sys
from collections import Counter
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit

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


# ── ci-child-name ────────────────────────────────────────────────────────

# The onboarding creates the child under this ARB string (POST /api/children).
# A CI APK carries the test-traffic name there, so the child is BORN marked:
# renaming it afterwards is a PATCH that production refuses (403
# device_proof_required) unless the session proved itself through an FCM push,
# which a CI emulator receives only now and then (2026-10-21).
_CHILD_NAME_KEY = "onbDefaultChildName"
_CHILD_NAME_OK = re.compile(r"[A-Za-z0-9-]{2,40}")


def cmd_ci_child_name(args: argparse.Namespace) -> int:
    """Rewrite onbDefaultChildName in every ARB and its generated Dart getter.

    Both are rewritten: `flutter build` regenerates the Dart from the ARB, but
    a checkout whose generated files are newer must not keep the old string.
    Each file must hold the key exactly once, or nothing is written."""
    name = args.name
    if not _CHILD_NAME_OK.fullmatch(name):
        print(f"::error::CI child name {name!r} must match {_CHILD_NAME_OK.pattern}", file=sys.stderr)
        return 1
    l10n = Path(args.l10n_dir)
    arb_re = re.compile(r'("%s"\s*:\s*)"(?:[^"\\]|\\.)*"' % _CHILD_NAME_KEY)
    dart_re = re.compile(r"(String get %s => )'(?:[^'\\]|\\.)*';" % _CHILD_NAME_KEY)
    plan: list[tuple[Path, str]] = []
    try:
        arbs = sorted(l10n.glob("app_*.arb"))
        darts = sorted(l10n.glob("app_localizations_*.dart"))
        if not arbs or not darts:
            raise ValueError(f"no app_*.arb / app_localizations_*.dart in {l10n}")
        for files, rx, repl in ((arbs, arb_re, r'\1"%s"' % name),
                                (darts, dart_re, r"\1'%s';" % name)):
            for path in files:
                text, n = rx.subn(repl, path.read_text(encoding="utf-8"))
                if n != 1:
                    raise ValueError(f"{path.name}: {_CHILD_NAME_KEY} found {n} times, want 1")
                plan.append((path, text))
        for path, text in plan:
            path.write_text(text, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"::error::CI child name failed: {exc}", file=sys.stderr)
        return 1
    print(f"{_CHILD_NAME_KEY}={name} in {len(plan)} files under {l10n}")
    return 0


# ── l10n ─────────────────────────────────────────────────────────────────

# Every ARB key a flow uses. A key missing from the ARB becomes a pattern that
# can never match, so the flow fails on that exact step instead of guessing.
KEYS = [
    # onboarding + tour
    "onbAgeQuestion", "onbStartJourney", "onbDefaultChildName", "onbPreparing",
    "onbServerSlow", "ageGroup7to9", "tourSkip",
    # head only (noor phase 2): the staged wait line and the optional name on
    # it; the tour's replay row (both lineages) for the gallery's tour shot
    "onbPreparingStep1", "onbNameQuestion", "tourReplay",
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
    # child mode — handed over through «باب التسليم» (handoverTitle: the gate;
    # habitChildModeTitle: its habit-tracker tile; handoverYourTurn: what the
    # doors open on, in parent mode, before the session)
    "routineTitle", "routineChildMode", "childMode", "habitChildModeExit",
    "a11yExitChildMode", "handoverTitle", "habitChildModeTitle",
    "handoverYourTurn",
    "habitChildModeExitTitle", "childModePinMismatch",
    "childModePinIncorrect", "childModeEnterFailed", "childModeBudgetSpent",
    "childModeOffline", "childModePinSetupSubtitle", "childModePinConfirmSubtitle",
    "childModePinEnterSubtitle",
    # «ركن الطفل» (fresh/10_child_corner + the gallery's corner shots) — head
    # builds only: the baseline has no corner, its selectors never match, and
    # the gallery shots are guarded.
    "childCornerTileTitle", "childCornerGreeting", "childCornerStoryHint",
    "childCornerStoryNext", "childCornerBackToCorner",
    "childCornerMissionNow", "childCornerMissionGo",
    "childCornerToMission", "childReturnDevice", "routineDailyTracker",
    # failure screens
    "bootError", "forceUpdateTitle",
    # a 5xx as friendlyError shows it (lesson, ErrorRetryView, chat turn) —
    # the condition of common/server_retry.yaml
    "errorServerBody",
    # family programs (fresh/09)
    "programsTitle", "programsIntro", "programsPrayerTitle", "prayerStagesTitle",
    # gallery (e2e/flows/gallery/shoot.yaml) — must exist in the BASELINE ARBs
    # too, or the «before» runs lose every step that uses them (verified for
    # efaa740f / 1.0.68+113 on 2026-10-08).
    "pathDetailStart", "pathDetailContinue",
    # head only (1.0.74): «عرض المسار» under «متابعة» on the «واصل مسارك» card
    "focusViewPath",
    "lessonQuiz", "quizYourResult", "quizNextQuestion", "quizShowResult",
    "quizErrorLoading",
    "lessonCelebrationTitle", "lessonNextStepTitle", "lessonNextStepConfirm",
    "promiseTonight",
    "followupTitle", "followupTitleFor", "followupWorked", "followupThanksTitle",
    "reviewPromptTitle", "reviewPromptLater", "settingsThemeLight",
    "todayMissionOpen", "praiseFromFamily", "dailyGiftLabel", "missionTodayLabel",
    "ageGroup4to6", "missionDone", "missionConfirmAll", "praiseChipAhsant",
    "settingsSwitchChild", "childrenAddNew", "add", "missionOpenForChild",
    "parentDayTitle", "childName", "addChildBtn", "addChildNameHint",
    "hubParentDay", "parentDayWith",
    # «قناديل الأسبوع» (phase 3) — head builds only; the baseline's selector
    # never matches, and the shot is guarded.
    "weekLanternsTitle",
    # «القصص» leg: the hub tile (both lineages), and the head's way into a
    # story from its first leaf (head only — the baseline opens an adhkar gate).
    "bedtimeStories", "storyReadTogether",
    # The Ramadan rehearsal (e2e/flows/rehearsal/stage.yaml, job `rehearsal`).
    # Every key below exists in the Play build the rehearsal upgrades from
    # (v1.0.72+117) EXCEPT the street's ramadanStreetHint, ramadanLanternLit
    # and ramadanDayComplete and Noor's noorRamadan30 — those are only used
    # behind TAG == 'after' (the PR head). ramadanCountdown is an ICU plural,
    # which to_pattern cannot render, so the countdown is never a selector.
    "programsOpenRamadan", "ramadanStartsOnEstimate", "ramadanDayOf",
    "programsRamadanEid", "programsRamadanAfterWeek",
    "ramadanMarksTitle", "ramadanMarkChallenge", "ramadanMarkWird",
    "ramadanMarkStory", "ramadanMarkJuz", "ramadanMarkNight",
    "ramadanDayComplete", "ramadanOtherDays", "ramadanStreetHint",
    "ramadanDayN", "ramadanDayToday", "ramadanLanternLit",
    "ramadanRecapOpen", "recapTitle", "ramadanAfterWeeks",
    "noorRamadan30",
    # «عيدكم مبارك» (head only, behind TAG == 'after'): the Eid moment over
    # Today and its «إغلاق».
    "eidMomentTitle", "close",
    # sound × recitation (e2e/flows/rehearsal/sound_*.yaml): the Quran
    # reader's surah list and its bottom «استماع / إيقاف» pill.
    "holyQuran", "quranVerseCount", "quranListen", "quranStop",
    # «درب {الاسم}» and «على الأفق» (عالم الأسرة): fresh/11 and the gallery's
    # family_road shots — head builds only; the gallery guards its shots.
    "familyRoadHorizon", "familyRoadHere", "familyRoadLit",
    "familyRoadEntryBody",
]

# Strings the app hardcodes outside the ARB files.
LITERALS = {
    # features/onboarding/screens/onboarding_screen.dart, _LanguageSelectionPage
    "lit_langTitle": ("اختر لغة التطبيق", "Choose App Language"),
    "lit_langArabic": ("العربية", "العربية"),
    "lit_langEnglish": ("English", "English"),
    "praiseChipProud": ("فخورون بك", "We are proud of you"),
    # main.dart, ErrorWidget.builder — what a parent sees when a build throws
    "lit_errorWidget": (
        "تعذّر عرض هذا الجزء. حاول مرة أخرى، وإن تكرّر أرسل لنا ملاحظة.",
        "تعذّر عرض هذا الجزء. حاول مرة أخرى، وإن تكرّر أرسل لنا ملاحظة.",
    ),
    # quiz_screen.dart, _OptionTile — the option letters are Arabic whatever
    # the interface language (String.fromCharCode('أ' + index)).
    "lit_quizOptionA": ("أ", "أ"),
    # The first story in mobile/assets/data/stories*.json (content, not ARB):
    # the «القصص» leg opens it from the shelf.
    "lit_storyFirstTitle": ("يوسف وغرسة الأمل", "Yusuf and the Seed of Hope"),
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
    ("noor_face_today", "NoorFace في «اليوم»"),
    ("gift_moment", "لحظة الهدية على «اليوم»"),
    ("gift_moment_0ms", "لحظة الهدية — ٠ms (البداية)"),
    ("gift_moment_150ms", "لحظة الهدية — ١٥٠ms (الانفجار)"),
    ("gift_moment_400ms", "لحظة الهدية — ٤٠٠ms (الاستقرار)"),
    ("praise_child_sticker", "كلمة الأب على شاشة الطفل — ٤–٦ (ملصق)"),
    ("praise_child_sticker_and_text", "كلمة الأب على شاشة الطفل — ٧–١٢ (ملصق ونص)"),
    ("praise_card_0ms", "كارت كلمة الأب — ٠ms (الظهور)"),
    ("praise_card_150ms", "كارت كلمة الأب — ١٥٠ms (الحركة)"),
    ("praise_card_400ms", "كارت كلمة الأب — ٤٠٠ms (الميل والاستقرار)"),
    ("child_corner", "ركن الطفل — حكاية ثم مهمة (بعد فقط)"),
    ("child_corner_story", "ركن الطفل — صفحة من الحكاية (بعد فقط)"),
    ("child_corner_task", "ركن الطفل — المهمة بعيدًا عن الشاشة (بعد فقط)"),
    ("home_dark_noor_face", "NoorFace في «اليوم» — داكن"),
    ("home_dark_gift", "لحظة الهدية على «اليوم» — داكن"),
    ("week_lanterns", "قناديل الأسبوع تحت ① على «اليوم»"),
    ("stories_shelf", "القصص — الرف"),
    ("stories_open", "القصص — أول ما تفتح قصة (قبل: بوابة الأذكار، بعد: صفحة نور)"),
    ("stories_page", "القصص — أول صفحة"),
    ("tour_mark", "الجولة — أول إشارة (قبل: v2 على «اليوم»، بعد: v3 على ①)"),
    ("family_road", "«درب {الاسم}» — الأفق و«أنتم هنا»"),
    ("family_road_lit", "«درب {الاسم}» — ما أضأتموه"),
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
GALLERY_GUARDED = {
    "followup_card",
    "followup",
    "quiz",
    "quiz_summary",
    "path_detail",
    "noor_face_today",
    "gift_moment",
    "gift_moment_0ms",
    "gift_moment_150ms",
    "gift_moment_400ms",
    "praise_card_0ms",
    "praise_card_150ms",
    "praise_card_400ms",
    # «ركن الطفل»: the baseline has no corner, so there is never a «before».
    "child_corner",
    "child_corner_story",
    "child_corner_task",
    "home_dark_noor_face",
    "home_dark_gift",
    # Needs a server with /api/family/week, and a head build.
    "week_lanterns",
    # Last in shoot.yaml, through the settings replay row; never seen on an
    # emulator before it shipped, so a miss is a blank cell, not a red gate.
    "tour_mark",
    # «عالم الأسرة»: the baseline has no road; and the lit part needs a lantern
    # from /api/family/week.
    "family_road",
    "family_road_lit",
    # «القصص»: only the shelf is required. What a tap opens depends on which
    # book the baseline's carousel centres, and the first page is head-only.
    "stories_open",
    "stories_page",
}

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
    md = [f"## {getattr(args, 'title', None) or 'Mobile E2E (emulator)'}", ""]
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


# ── hierarchy verification ───────────────────────────────────────────────

EXPECTED_SCREEN_MARKERS: dict[str, dict[str, list[str]]] = {
    "settings": {
        "required_ar": ["الإعدادات"],
        "required_en": ["Settings"],
        "forbidden": ["علامة التبويب 1 من", "المزيد", "Tab 1 of"],
    },
    "settings_dark": {
        "required_ar": ["الإعدادات"],
        "required_en": ["Settings"],
    },
    "home": {
        "required_ar": ["اليوم"],
        "required_en": ["Today"],
        "forbidden": ["الإعدادات", "Settings"],
    },
    "home_dark": {
        "required_ar": ["اليوم"],
        "required_en": ["Today"],
        "forbidden": ["الإعدادات", "Settings"],
    },
    "home_dark_noor_face": {
        "required_ar": ["اليوم"],
        "required_en": ["Today"],
        "forbidden": ["الإعدادات", "Settings", "المزيد"],
    },
    "home_dark_gift": {
        "required_ar": ["اليوم"],
        "required_en": ["Today"],
        "forbidden": ["الإعدادات", "Settings", "المزيد"],
    },
    "noor_face_today": {
        "required_ar": ["اليوم"],
        "required_en": ["Today"],
        "forbidden": ["الإعدادات", "Settings"],
    },
    "gift_moment": {
        "required_ar": ["اليوم"],
        "required_en": ["Today"],
    },
    "praise_child_sticker": {
        "required_ar": ["أهلك يقولون لك"],
        "required_en": ["Your family says to you"],
        "forbidden": [
            "الإعدادات", "Settings", "وضع الطفل", "اختر رمز", "أدخل رمز",
            "أكّد الكل", "Confirm all", "كلمة طيبة مع التأكيد", "فخورون بك",
            "We are proud of you", "أحسنت", "Well done",
        ],
    },
    "praise_child_sticker_and_text": {
        "required_ar": ["أهلك يقولون لك", "فخورون بك"],
        "required_en": ["Your family says to you", "We are proud of you"],
        "forbidden": [
            "الإعدادات", "Settings", "وضع الطفل", "اختر رمز", "أدخل رمز",
            "أكّد الكل", "Confirm all", "كلمة طيبة مع التأكيد",
        ],
    },
    "lesson": {
        "required_ar": ["أكملت الدرس", "إكمال الدرس", "الدرس", "رجوع"],
        "required_en": ["Lesson", "Complete Lesson", "Back"],
        "forbidden": ["الإعدادات", "Settings"],
    },
    "onboarding_1_language": {
        "required_ar": ["اختر لغة التطبيق"],
        "required_en": ["Choose App Language", "Language"],
        "forbidden": ["الإعدادات", "Settings"],
    },
    "onboarding_2_first_tip": {
        "required_ar": ["ابدأ رحلتك", "7–9"],
        "required_en": ["Start your journey", "7–9"],
        "forbidden": ["الإعدادات", "Settings"],
    },
}


def verify_screen_hierarchy(
    screen: str, hierarchy_text: str, lang: str | None = None
) -> list[str]:
    """Check that the view hierarchy text matches expected markers for screen.

    Requires ALL markers in required list for the given language,
    and ensures no forbidden markers are present.
    Returns list of error descriptions (empty if valid).
    """
    rules = EXPECTED_SCREEN_MARKERS.get(screen)
    if not rules:
        return []
    errors = []

    required: list[str] = []
    if lang == "ar" and "required_ar" in rules:
        required = rules["required_ar"]
    elif lang == "en" and "required_en" in rules:
        required = rules["required_en"]
    elif "required" in rules:
        required = rules["required"]
    elif lang is None:
        req_ar = rules.get("required_ar", [])
        req_en = rules.get("required_en", [])
        ar_matches = all(req in hierarchy_text for req in req_ar) if req_ar else False
        en_matches = all(req in hierarchy_text for req in req_en) if req_en else False
        if not (ar_matches or en_matches):
            errors.append(
                f"Missing expected markers for screen '{screen}' (requires all AR {req_ar} or all EN {req_en})"
            )
        for forbidden in rules.get("forbidden", []):
            if forbidden in hierarchy_text:
                errors.append(
                    f"Found forbidden marker '{forbidden}' in screen '{screen}' hierarchy"
                )
        return errors

    for req in required:
        if req not in hierarchy_text:
            errors.append(
                f"Missing expected markers (required '{req}') for screen '{screen}'"
            )
    for forbidden in rules.get("forbidden", []):
        if forbidden in hierarchy_text:
            errors.append(
                f"Found forbidden marker '{forbidden}' in screen '{screen}' hierarchy"
            )
    return errors


def cmd_verify_hierarchy(args: argparse.Namespace) -> int:
    lang = getattr(args, "lang", "ar")
    require = getattr(args, "require", False)
    if getattr(args, "report_dir", None):
        report_dir = Path(args.report_dir)
        if not report_dir.is_dir():
            if require:
                print(f"::error title=Hierarchy check::Report dir '{report_dir}' does not exist", file=sys.stderr)
                return 1
            return 0
        dump_files = list(report_dir.rglob("screen-hierarchy/*.json")) + list(
            report_dir.rglob("screen-hierarchy/*.xml")
        )
        if not dump_files:
            if require:
                print(f"::error title=Hierarchy check::No screen hierarchy dump files found in '{report_dir}'", file=sys.stderr)
                return 1
            return 0
        total_errors = []
        verified_screens = set()
        for path in dump_files:
            text = path.read_text(encoding="utf-8", errors="replace")
            matched_screen = None
            for screen in sorted(EXPECTED_SCREEN_MARKERS.keys(), key=len, reverse=True):
                if screen in path.name:
                    matched_screen = screen
                    break
            if not matched_screen:
                if "praise_child_sticker_and_text" in path.name:
                    matched_screen = "praise_child_sticker_and_text"
                elif "praise_child_sticker" in path.name or "praiseFromFam" in path.name:
                    matched_screen = "praise_child_sticker"
                elif "home" in path.name:
                    matched_screen = "home"
                elif "lesson" in path.name:
                    matched_screen = "lesson"
                elif "settings" in path.name:
                    matched_screen = "settings"
            if matched_screen:
                errs = verify_screen_hierarchy(matched_screen, text, lang=lang)
                if errs:
                    total_errors.extend(
                        [f"{path.name} ({matched_screen}): {e}" for e in errs]
                    )
                else:
                    verified_screens.add(matched_screen)
        if total_errors:
            # Without --require this is the informational «before» pass: the
            # baseline build, which may predate the screen being checked (the
            # 4-6 praise card's «أهلك يقولون لك» is not in 1.0.71 at all). A
            # mismatch there is worth a look, not a red ##[error] that reads
            # like the reason a job failed (PR #121, 2026-10-15). The rc stays
            # 1 either way; run.sh decides what it means.
            level = "error" if require else "warning"
            for err in total_errors:
                print(f"::{level} title=Hierarchy check::{err}", file=sys.stderr)
            return 1
        return 0

    if not getattr(args, "hierarchy", None) or not getattr(args, "screen", None):
        print(
            "verify-hierarchy requires screen and hierarchy file (or --report-dir)",
            file=sys.stderr,
        )
        return 2

    path = Path(args.hierarchy)
    text = path.read_text(encoding="utf-8", errors="replace")
    errors = verify_screen_hierarchy(args.screen, text, lang=lang)
    if errors:
        for err in errors:
            print(f"::error title=Hierarchy check::{err}", file=sys.stderr)
        return 1
    print(f"PASS  screen '{args.screen}' matches hierarchy in {path}")
    return 0


# ── the Ramadan rehearsal: `as_of` on a candidate server ─────────────────
#
# Phase 5 of docs/NOOR_WAL_QANADIL_PLAN.md (gate G2): walk the family through
# Ramadan — before it, days 1/15/27, Eid, after — on the emulator, months
# ahead. The backend has a QA date override for exactly this: `as_of` on every
# family-programs route, honoured only where PROGRAMS_AS_OF_ENABLED is set
# (403 `as_of_disabled` otherwise). It is NEVER set on production.
#
# So job `rehearsal` runs the PR head's backend image on the runner with the
# switch on, and points two CI-only APKs at it (--dart-define=API_BASE_URL):
# the PR head, and the build on Play now. Neither app knows about `as_of` —
# the Play build cannot be taught, and the head must not ship a date knob — so
# this proxy adds it: every programs call passing through gets the stage's
# date, read from a one-line file the runner rewrites between stages.

# Every route of backend/app/routers/family_programs.py that takes `as_of`
# (test_e2e_tool.py derives that list from the router and holds this to it).
AS_OF_ROUTE = re.compile(
    r"^/api/(?:programs(?:/.*)?|children/\d+/(?:ramadan|prayer-journey|milestones)(?:/.*)?)$"
)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Hop-by-hop headers, plus the two the proxy sets itself.
_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "trailers", "transfer-encoding", "upgrade", "host",
    "content-length",
}


def as_of_applies(path: str) -> bool:
    """Is `path` (no query) a family-programs route that takes `as_of`?"""
    return bool(AS_OF_ROUTE.match(path))


def with_as_of(query: str, as_of: str | None) -> tuple[str, bool]:
    """The raw query with `as_of` appended — never replacing one the caller
    sent, never re-encoding what was there. Returns (query, added)."""
    if not as_of:
        return query, False
    if any(k == "as_of" for k, _ in parse_qsl(query, keep_blank_values=True)):
        return query, False
    return (f"{query}&" if query else "") + "as_of=" + quote(as_of), True


def read_stage(path: Path) -> tuple[str | None, str]:
    """The stage file — `<YYYY-MM-DD> <label>` — as (date or None, label).
    Missing, empty or malformed: no date, so nothing is added."""
    try:
        parts = path.read_text(encoding="utf-8").split()
    except OSError:
        return None, "-"
    if not parts or not _ISO_DATE.match(parts[0]):
        return None, "-"
    try:
        date.fromisoformat(parts[0])
    except ValueError:
        return None, "-"
    return parts[0], (parts[1] if len(parts) > 1 else parts[0])


def make_as_of_proxy(listen: tuple[str, int], upstream: str, stage_file: Path,
                     log: Path | None = None) -> ThreadingHTTPServer:
    """A plain HTTP/1.1 forwarder. Bodies are buffered, which is fine for the
    rehearsal (it never streams an answer from the assistant)."""
    up = urlsplit(upstream)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args) -> None:  # the TSV below is the log
            return

        def _forward(self) -> None:
            target = urlsplit(self.path)
            as_of, label = read_stage(stage_file)
            query, added = target.query, False
            if as_of_applies(target.path):
                query, added = with_as_of(query, as_of)
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP_HEADERS}
            conn = http.client.HTTPConnection(up.hostname, up.port or 80, timeout=330)
            try:
                conn.request(self.command, target.path + (f"?{query}" if query else ""),
                             body=body, headers=headers)
                resp = conn.getresponse()
                status, data, rheaders = resp.status, resp.read(), resp.getheaders()
            except OSError as exc:
                status = 502
                data = f"as-of proxy: upstream unreachable ({exc})".encode()
                rheaders = [("Content-Type", "text/plain; charset=utf-8")]
            finally:
                conn.close()
            # Logged before the answer goes out: once the app has its answer,
            # the record of it exists.
            if log is not None:
                row = "\t".join([f"{time.time():.3f}", label, self.command, target.path,
                                 as_of if added else "-", str(status)])
                with lock, log.open("a", encoding="utf-8") as fh:
                    fh.write(row + "\n")
            self.send_response_only(status)
            for k, v in rheaders:
                if k.lower() not in _HOP_HEADERS:
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _forward

    server = ThreadingHTTPServer(listen, Handler)
    server.daemon_threads = True
    return server


def _host_port(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    return host or "127.0.0.1", int(port)


def cmd_as_of_proxy(args: argparse.Namespace) -> int:
    server = make_as_of_proxy(_host_port(args.listen), args.upstream, Path(args.as_of_file),
                              Path(args.log) if args.log else None)
    print(f"as-of proxy: {args.listen} → {args.upstream} (stage file {args.as_of_file})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


# The stages, from the season the server itself knows (its estimate, or the
# configured RAMADAN_START_<year>): nothing here hardcodes a Hijri date.
# before = 30 days out (Noor's first countdown line), the month's first day,
# the middle, an odd last-ten night, Eid, and the first bridge week.
def rehearsal_stages(season: dict) -> list[dict]:
    start = date.fromisoformat(season["starts_on"])
    eid = date.fromisoformat(season["eid_on"])
    return [
        {"label": "before", "date": start - timedelta(days=30), "day": 0,
         "state": "upcoming", "days_until_start": 30},
        {"label": "day1", "date": start, "day": 1, "state": "ramadan"},
        {"label": "day15", "date": start + timedelta(days=14), "day": 15, "state": "ramadan"},
        {"label": "day27", "date": start + timedelta(days=26), "day": 27, "state": "ramadan"},
        {"label": "eid", "date": eid, "day": 0, "state": "eid"},
        {"label": "after", "date": eid + timedelta(days=5), "day": 0, "state": "after"},
    ]


def check_stage_answer(stage: dict, body: object) -> str | None:
    """What is wrong with GET /api/programs's answer for `stage`, or None."""
    if not isinstance(body, dict):
        return f"not JSON: {str(body)[:120]}"
    if body.get("date") != stage["date"].isoformat():
        return f"date {body.get('date')!r}, expected {stage['date'].isoformat()}"
    ramadan = body.get("ramadan") or {}
    if ramadan.get("state") != stage["state"]:
        return f"ramadan.state {ramadan.get('state')!r}, expected {stage['state']!r}"
    if stage["day"] and ramadan.get("day") != stage["day"]:
        return f"ramadan.day {ramadan.get('day')!r}, expected {stage['day']}"
    if "days_until_start" in stage and ramadan.get("days_until_start") != stage["days_until_start"]:
        return (f"ramadan.days_until_start {ramadan.get('days_until_start')!r}, "
                f"expected {stage['days_until_start']}")
    return None


_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_json(method: str, url: str, token: str | None = None, body: object = None,
              timeout: float = 30) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with _NO_PROXY.open(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    try:
        return status, json.loads(raw.decode("utf-8") or "null")
    except ValueError:
        return status, raw.decode("utf-8", "replace")


def as_of_preflight(upstream: str, proxy: str | None, stage_file: Path | None) -> tuple[list[str], list[str], list[dict]]:
    """(failures, report lines, stages). Mints one throwaway session on the
    CANDIDATE (never production), then asks it about every stage."""
    fails: list[str] = []
    lines: list[str] = []
    status, minted = http_json("POST", f"{upstream}/api/chat/sessions",
                               body={"device_id": str(uuid.uuid4())})
    token = minted.get("token") if isinstance(minted, dict) else None
    if status != 201 or not token:
        return [f"session mint answered {status}"], lines, []
    status, today = http_json("GET", f"{upstream}/api/programs?tz_offset_minutes=0", token)
    season = ((today or {}).get("ramadan") or {}).get("season") if isinstance(today, dict) else None
    if status != 200 or not season:
        return [f"GET /api/programs answered {status} with no Ramadan season: {str(today)[:160]}"], lines, []
    lines.append(f"- season {season.get('hijri_year')}: starts {season.get('starts_on')} "
                 f"({season.get('start_source')}), {season.get('days')} days, Eid {season.get('eid_on')}; "
                 f"server date today {today.get('date')} → {today['ramadan'].get('state')}")
    stages = rehearsal_stages(season)
    for stage in stages:
        url = f"{upstream}/api/programs?tz_offset_minutes=0&as_of={stage['date'].isoformat()}"
        status, body = http_json("GET", url, token)
        if status == 403:
            fails.append(f"{stage['label']}: as_of refused (403 {body}) — PROGRAMS_AS_OF_ENABLED is off on the candidate")
            continue
        problem = f"answered {status}" if status != 200 else check_stage_answer(stage, body)
        if problem:
            fails.append(f"{stage['label']} ({stage['date']}): {problem}")
        else:
            r = body["ramadan"]
            lines.append(f"- {stage['label']:<6} as_of={stage['date']} → {r.get('state')}"
                         + (f" day {r.get('day')}" if r.get("day") else "")
                         + (f", {r.get('days_until_start')} days to go" if r.get("days_until_start") else ""))
    if proxy and stage_file is not None and stages:
        probe = stages[2]  # day15
        previous = stage_file.read_text(encoding="utf-8") if stage_file.exists() else None
        stage_file.write_text(f"{probe['date'].isoformat()} preflight\n", encoding="utf-8")
        try:
            status, body = http_json("GET", f"{proxy}/api/programs?tz_offset_minutes=0", token)
        finally:
            if previous is None:
                stage_file.unlink(missing_ok=True)
            else:
                stage_file.write_text(previous, encoding="utf-8")
        problem = f"answered {status}" if status != 200 else check_stage_answer(probe, body)
        if problem:
            fails.append(f"through the proxy, no as_of in the URL: {problem}")
        else:
            lines.append(f"- through the proxy, no as_of in the URL → day {body['ramadan'].get('day')} "
                         "(the proxy adds it)")
    return fails, lines, stages


def cmd_as_of_preflight(args: argparse.Namespace) -> int:
    fails, lines, stages = as_of_preflight(
        args.upstream.rstrip("/"), args.proxy.rstrip("/") if args.proxy else None,
        Path(args.as_of_file) if args.as_of_file else None)
    if stages and args.stages_out:
        Path(args.stages_out).write_text(
            "".join(f"{s['label']}\t{s['date'].isoformat()}\t{s['day']}\n" for s in stages),
            encoding="utf-8")
    verdict = "FAIL" if fails else "PASS"
    report = [f"### as_of preflight on the candidate: {verdict}", ""] + lines
    report += [f"- FAIL {f}" for f in fails]
    text = "\n".join(report) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    for f in fails:
        print(f"::error title=Ramadan rehearsal preflight::{f}")
    return 1 if fails else 0


def as_of_report(rows: list[str], expected: list[str]) -> tuple[list[str], list[str]]:
    """(failures, Markdown table) from the proxy's TSV log. Each expected
    stage label needs at least one programs call that carried its date and
    was answered 2xx; no call may have been refused or crashed."""
    per: dict[str, Counter] = {}
    fails: list[str] = []
    for row in rows:
        parts = row.split("\t")
        if len(parts) < 6 or parts[4] == "-":
            continue
        _, label, method, path, as_of, status = parts[:6]
        code = int(status) if status.isdigit() else 0
        per.setdefault(label, Counter())["2xx" if 200 <= code < 300 else str(code)] += 1
        if code == 403:
            fails.append(f"{label}: {method} {path} as_of={as_of} refused (403)")
        elif code >= 500 or code == 0:
            fails.append(f"{label}: {method} {path} as_of={as_of} answered {status}")
    table = ["| stage | programs calls with as_of | answers |", "|---|---|---|"]
    for label in expected + sorted(set(per) - set(expected)):
        counts = per.get(label, Counter())
        table.append(f"| {label} | {sum(counts.values())} | "
                     + (", ".join(f"{k}×{v}" for k, v in sorted(counts.items())) or "—") + " |")
        if label in expected and counts["2xx"] == 0:
            fails.append(f"{label}: no programs call carried the stage's as_of — the stage proved nothing")
    return fails, table


def cmd_as_of_report(args: argparse.Namespace) -> int:
    log = Path(args.log)
    rows = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    expected = [l.strip() for l in Path(args.expect).read_text(encoding="utf-8").splitlines()
                if l.strip()] if args.expect and Path(args.expect).exists() else []
    fails, table = as_of_report(rows, expected)
    text = "\n".join([f"### as_of per stage: {'FAIL' if fails else 'PASS'}", ""] + table
                     + [f"- FAIL {f}" for f in fails]) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    for f in fails:
        print(f"::error title=Ramadan rehearsal as_of::{f}")
    return 1 if fails else 0


# ── sound × recitation: `dumpsys audio`, before and after the ticks ───────
#
# Plan phase 2 gate: the interface sounds (audioplayers, low-latency, focus
# NONE, UI sonification) must never stop a recitation (just_audio). The
# runner starts a recitation in the Quran reader, takes a dump, sounds three
# ticks, takes more dumps. The audio service is the witness — not the app:
#   players   «AudioPlaybackConfiguration piid:N … type:T u/pid:U/P state:S
#             attr:AudioAttributes: usage=X …»  (one line per player)
#   focus     the stack («-- pack: … -- loss: L -- uid: U -- attr: … usage=X»)
#             and its log («requestAudioFocus() from uid/pid U/P AA=X/…»)
#   events    «<time> player piid:N event:started» per start (SoundPool
#             reports one per play), in a ring buffer: judged by time

_AUDIO_PLAYER = re.compile(
    r"AudioPlaybackConfiguration\s+piid:(?P<piid>\d+)\b.*?\btype:(?P<type>\S+).*?"
    r"\bu/pid:(?P<uid>\d+)/(?P<pid>\d+).*?\bstate:(?P<state>\w+).*?\busage=(?P<usage>\w+)"
)
_AUDIO_NEW_PLAYER = re.compile(
    r"new player piid:(?P<piid>\d+)\b.*?\buid/pid:(?P<uid>\d+)/\d+.*?\busage=(?P<usage>\w+)"
)
# Event-log lines carry their time; the logs are ring buffers, so «new since
# the dump before the ticks» is decided by time, never by counting lines — in
# run 38722537691 older processes' starts fell out of the buffer between the
# two dumps (39 → 37) while two new ticks went in.
_AUDIO_TS = r"(?P<ts>\d\d-\d\d \d\d:\d\d:\d\d:\d{3})"
_AUDIO_ANY_TS = re.compile(r"^\s*" + _AUDIO_TS + r"\s", re.M)
_AUDIO_STARTED = re.compile(_AUDIO_TS + r"\s+player piid:(?P<piid>\d+)\s+event:started\b")
_AUDIO_FOCUS_REQUEST = re.compile(
    _AUDIO_TS + r"\s+requestAudioFocus\(\)\s+from uid/pid (?P<uid>\d+)/\d+\s+AA=(?P<usage>\w+)"
)
_AUDIO_FOCUS_ENTRY = re.compile(
    r"--\s*loss:\s*(?P<loss>\w+).*?--\s*uid:\s*(?P<uid>\d+).*?\busage=(?P<usage>\w+)"
)
SONIFICATION = {"USAGE_ASSISTANCE_SONIFICATION"}
MEDIA = {"USAGE_MEDIA"}


def parse_audio_dump(text: str) -> dict:
    players = [m.groupdict() for m in _AUDIO_PLAYER.finditer(text)]
    usage_of = {p["piid"]: (p["uid"], p["usage"]) for p in players}
    for m in _AUDIO_NEW_PLAYER.finditer(text):
        usage_of.setdefault(m["piid"], (m["uid"], m["usage"]))
    return {
        "players": players,
        "usage_of": usage_of,
        "started": [m.groupdict() for m in _AUDIO_STARTED.finditer(text)],
        "focus_requests": [m.groupdict() for m in _AUDIO_FOCUS_REQUEST.finditer(text)],
        "last_ts": max((m["ts"] for m in _AUDIO_ANY_TS.finditer(text)), default=""),
        "focus_stack": [m.groupdict() for m in _AUDIO_FOCUS_ENTRY.finditer(text)],
    }


def _playing(dump: dict, uid: str, usages: set[str]) -> list[dict]:
    return [p for p in dump["players"]
            if p["uid"] == uid and p["usage"] in usages and p["state"] == "started"]


def _tick_starts(dump: dict, uid: str, since: str) -> int:
    """Interface-sound starts of the app logged after `since`."""
    return sum(1 for e in dump["started"]
               if e["ts"] > since and dump["usage_of"].get(e["piid"], ("", ""))[0] == uid
               and dump["usage_of"][e["piid"]][1] in SONIFICATION)


def audio_verdict(before: str, afters: list[str], uid: int | str) -> tuple[str, list[str]]:
    """PASS · FAIL · INCONCLUSIVE, with the evidence. A check that cannot
    show the recitation playing, or cannot show a tick sounding, proves
    nothing — that is INCONCLUSIVE, never PASS."""
    uid = str(uid)
    b = parse_audio_dump(before)
    a = [parse_audio_dump(t) for t in afters]
    notes: list[str] = []
    reciting = _playing(b, uid, MEDIA)
    if not reciting:
        return "INCONCLUSIVE", ["no media player of the app was playing before the ticks — "
                                "the recitation never started, so there was nothing to protect"]
    notes.append("before: recitation playing — " + ", ".join(
        f"piid {p['piid']} ({p['type']})" for p in reciting))
    fails: list[str] = []
    since = b["last_ts"]
    focus_before = [r for r in b["focus_requests"] if r["uid"] == uid and r["usage"] in SONIFICATION]
    for i, d in enumerate(a, 1):
        now = _playing(d, uid, MEDIA)
        notes.append(f"after #{i}: " + ("recitation playing — " + ", ".join(
            f"piid {p['piid']}" for p in now) if now else "no media player of the app playing"))
        asked = [r for r in d["focus_requests"]
                 if r["uid"] == uid and r["usage"] in SONIFICATION and r["ts"] > since]
        if asked:
            fails.append(f"after #{i}: a tick asked for audio focus "
                         f"({len(asked)} new request(s), usage {asked[-1]['usage']})")
        lost = [e for e in d["focus_stack"] if e["uid"] == uid and e["usage"] in MEDIA
                and e["loss"].lower() not in ("none", "null")]
        if lost:
            fails.append(f"after #{i}: the recitation's focus was taken ({lost[0]['loss']})")
    if focus_before:
        fails.append(f"an interface sound asked for audio focus earlier in this run "
                     f"({len(focus_before)} request(s))")
    if not any(_playing(d, uid, MEDIA) for d in a):
        fails.append("the recitation stopped: no media player of the app was playing in any dump after the ticks")
    starts = max((_tick_starts(d, uid, since) for d in a), default=0)
    heard = starts > 0 or any(
        _playing(d, uid, SONIFICATION) and not _playing(b, uid, SONIFICATION) for d in a)
    notes.append(f"ticks seen by the audio service: {starts} new start(s)"
                 if heard else "ticks seen by the audio service: none")
    holds = [e for e in b["focus_stack"] if e["uid"] == uid]
    notes.append("the recitation holds audio focus (usage " + holds[0]["usage"] + ")" if holds
                 else "the app holds no audio focus at all (the recitation plays without requesting it)")
    if fails:
        return "FAIL", fails + notes
    if not heard:
        return "INCONCLUSIVE", ["no tick reached the audio service — the probe did not sound, "
                                "so this run says nothing about a tick over a recitation"] + notes
    return "PASS", notes


def cmd_audio_focus(args: argparse.Namespace) -> int:
    read = lambda p: Path(p).read_text(encoding="utf-8", errors="replace")
    verdict, evidence = audio_verdict(read(args.before), [read(p) for p in args.after], args.uid)
    line = f"SOUND×RECITATION CHECKPOINT: {verdict}"
    text = "\n".join([f"### {line}", ""] + [f"- {e}" for e in evidence]) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    if verdict == "FAIL":
        print(f"::error title=Sound × recitation::{evidence[0]}")
    elif verdict == "INCONCLUSIVE":
        print(f"::error title=Sound × recitation (inconclusive)::{evidence[0]}")
    else:
        print("::notice title=Sound × recitation::PASS — " + "; ".join(evidence))
    return {"PASS": 0, "FAIL": 1}.get(verdict, 2)


# ── the rehearsal gallery: each stage, Play build vs PR head ──────────────
#
# e2e/flows/rehearsal/stage.yaml names every shot
#   ${TAG}__${VARIANT}__<stage>_<screen>   tag before = the Play build,
# after = the PR head; run_flow prefixes rehearsal__<flow>__. One table per
# stage: the Play build in Arabic beside the head in Arabic, English and dark.

REHEARSAL_COLUMNS = [
    ("before", "ar", "Play v1.0.72 · عربي"),
    ("after", "ar", "الـPR · عربي"),
    ("after", "en", "الـPR · English"),
    ("after", "ar_dark", "الـPR · عربي داكن"),
]
REHEARSAL_STAGES = [
    ("before", "قبل رمضان (٣٠ يومًا)", [
        ("before_today", "«اليوم»"),
        ("before_today_noor", "نور يعدّ الأيام (أول مرة فقط)"),
        ("before_programs", "برامج الأسرة"),
        ("before_ramadan", "رمضان العائلة — العدّ التنازلي"),
    ]),
    ("day1", "اليوم ١", [
        ("day1_programs", "برامج الأسرة"),
        ("day1_marks", "علامات اليوم"),
        ("day1_street", "شارع القناديل"),
    ]),
    ("day15", "اليوم ١٥", [
        ("day15_programs", "برامج الأسرة"),
        ("day15_marks", "علامات اليوم"),
        ("day15_street", "شارع القناديل"),
    ]),
    ("day27", "اليوم ٢٧ (ليلة وترية)", [
        ("day27_programs", "برامج الأسرة"),
        ("day27_marks", "علامات اليوم — اكتمال اليوم «الحمد لله»"),
        ("day27_street", "شارع القناديل"),
    ]),
    ("eid", "العيد", [
        ("eid_moment", "«عيدكم مبارك» فوق «اليوم» (أول مرة فقط)"),
        ("eid_programs", "برامج الأسرة"),
        ("eid_ramadan", "بطاقة العيد"),
        ("eid_street", "شارع القناديل"),
        ("eid_recap", "الملخّص — «رمضان عائلتنا»"),
    ]),
    ("after", "بعد رمضان (الأسبوع ١)", [
        ("after_programs", "برامج الأسرة"),
        ("after_ramadan", "أسابيع الاستمرار"),
        ("after_street", "شارع القناديل"),
    ]),
]
# Noor's countdown line shows once per countdown day per install, and the Eid
# moment once per Hijri year: only the first pass to open Today on that date
# can photograph them.
REHEARSAL_GUARDED = {"before_today_noor", "eid_moment"}
_REHEARSAL_FILE = re.compile(
    r"^rehearsal__.*?__(?P<tag>before|after)__(?P<variant>ar_dark|ar|en)"
    r"__(?P<screen>[a-z0-9_]+?)(?:_\d+)?\.png$"
)


def index_rehearsal(screens: Path) -> dict[tuple[str, str, str], str]:
    known = {s for _, _, rows in REHEARSAL_STAGES for s, _ in rows}
    index: dict[tuple[str, str, str], str] = {}
    for png in sorted(screens.glob("rehearsal__*.png")):
        m = _REHEARSAL_FILE.match(png.name)
        if m and m["screen"] in known:
            index.setdefault((m["tag"], m["variant"], m["screen"]), png.name)
    return index


def cmd_rehearsal_gallery(args: argparse.Namespace) -> int:
    screens, out = Path(args.screens), Path(args.out)
    images = out / "images"
    images.mkdir(parents=True, exist_ok=True)
    index = index_rehearsal(screens) if screens.exists() else {}

    def cell(name: str | None, caption: str) -> str:
        if name is None:
            return "—"
        shutil.copy(screens / name, images / name)
        return f'<img src="images/{name}" width="200" alt="{caption}">'

    md = ["## بروفة رمضان — معرض المراحل", "",
          "الخادم مرشّح على الـrunner (صورة باكند الـPR، `PROGRAMS_AS_OF_ENABLED=1`)، "
          "وكل مرحلة تاريخها من `as_of`. العمود الأول نسخة Play الحالية، والباقي رأس الـPR.", ""]
    counts = Counter()
    blind = []
    head = "| الشاشة | " + " | ".join(c[2] for c in REHEARSAL_COLUMNS) + " |"
    for _stage, title, rows in REHEARSAL_STAGES:
        md += [f"### {title}", "", head, "|---" * (len(REHEARSAL_COLUMNS) + 1) + "|"]
        for screen, caption in rows:
            cells = []
            for tag, variant, _ in REHEARSAL_COLUMNS:
                name = index.get((tag, variant, screen))
                counts["shot" if name else "missing"] += 1
                if name is None and tag == "after" and screen not in REHEARSAL_GUARDED:
                    blind.append(f"{variant}:{screen}")
                cells.append(cell(name, caption))
            md.append(f"| {caption} | " + " | ".join(cells) + " |")
        md.append("")
    stats = f"shots={counts['shot']} missing={counts['missing']} blind-after={len(blind)}"
    md.append(f"<!-- gallery: {stats} -->")
    out.mkdir(parents=True, exist_ok=True)
    (out / "gallery-summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"rehearsal gallery: {stats} → {out / 'gallery-summary.md'}")
    if args.require_after and blind:
        print("::error title=Ramadan rehearsal gallery::خانة الـPR فاضية: " + ", ".join(blind))
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("deactivate-analytics", help="disable Analytics in a disposable CI manifest")
    s.add_argument("--manifest", required=True)
    s.set_defaults(func=cmd_deactivate_analytics)

    s = sub.add_parser("ci-child-name", help="create the onboarding child under the test-traffic name")
    s.add_argument("--l10n-dir", required=True)
    s.add_argument("--name", required=True)
    s.set_defaults(func=cmd_ci_child_name)

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
    s.add_argument("--title", help="heading (default: Mobile E2E (emulator))")
    s.set_defaults(func=cmd_summary)

    s = sub.add_parser("as-of-proxy", help="forward to the candidate, adding the stage's as_of")
    s.add_argument("--listen", default="127.0.0.1:8090", help="host:port")
    s.add_argument("--upstream", required=True, help="the candidate backend, e.g. http://127.0.0.1:8091")
    s.add_argument("--as-of-file", required=True, help="one line: <YYYY-MM-DD> <stage label>")
    s.add_argument("--log", help="TSV: time, stage, method, path, as_of added (or -), status")
    s.set_defaults(func=cmd_as_of_proxy)

    s = sub.add_parser("as-of-preflight", help="prove the candidate honours as_of for every stage")
    s.add_argument("--upstream", required=True)
    s.add_argument("--proxy", help="the as-of proxy, checked to add as_of itself")
    s.add_argument("--as-of-file", help="the proxy's stage file (restored afterwards)")
    s.add_argument("--stages-out", help="TSV: label, date, day — what the runner walks")
    s.add_argument("--out", help="Markdown report")
    s.set_defaults(func=cmd_as_of_preflight)

    s = sub.add_parser("as-of-report", help="every stage's programs calls carried as_of")
    s.add_argument("--log", required=True, help="the proxy's TSV log")
    s.add_argument("--expect", help="file with the stage labels that must appear, one per line")
    s.add_argument("--out", help="Markdown report")
    s.set_defaults(func=cmd_as_of_report)

    s = sub.add_parser("audio-focus", help="judge dumpsys audio before/after the ticks")
    s.add_argument("--before", required=True)
    s.add_argument("--after", required=True, action="append", help="one or more dumps after the ticks")
    s.add_argument("--uid", required=True, help="the app's uid")
    s.add_argument("--out", help="Markdown verdict")
    s.set_defaults(func=cmd_audio_focus)

    s = sub.add_parser("rehearsal-gallery", help="the Ramadan rehearsal's stage gallery")
    s.add_argument("screens")
    s.add_argument("--out", required=True)
    s.add_argument("--require-after", action="store_true",
                   help="fail if any non-guarded stage screen lacks a PR-head shot")
    s.set_defaults(func=cmd_rehearsal_gallery)

    s = sub.add_parser("verify-hierarchy", help="check view hierarchy text matches expected screen")
    s.add_argument("screen", nargs="?", help="screen id")
    s.add_argument("hierarchy", nargs="?", help="path to hierarchy dump file")
    s.add_argument("--report-dir", help="dir with maestro test reports to scan")
    s.add_argument("--lang", default="ar", help="screen language (ar or en)")
    s.add_argument("--require", action="store_true", help="fail if report-dir or dump files are missing")
    s.set_defaults(func=cmd_verify_hierarchy)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
