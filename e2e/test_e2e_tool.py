"""Tests for e2e/e2e_tool.py — run: python3 -m unittest discover -s e2e -v"""
import contextlib
import io
import json
import re
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import tempfile
import threading
import unittest
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import yaml

import e2e_tool as t

PKG = "com.alsaba.almorabbi"


def lc(pid, prio, tag, msg, tid=None):
    """One `adb logcat -v threadtime` line."""
    return f"10-04 12:00:00.000  {pid:>5} {tid or pid:>5} {prio} {tag:<8}: {msg}"


class PatternTest(unittest.TestCase):
    def test_escapes_regex_metacharacters(self):
        p = t.to_pattern("تسليم الجهاز للطفل (وضع الطفل)")
        self.assertTrue(re.fullmatch(p, "تسليم الجهاز للطفل (وضع الطفل)"))
        self.assertIsNone(re.fullmatch(p, "تسليم الجهاز للطفل وضع الطفل"))
        self.assertTrue(re.fullmatch(t.to_pattern("تم حفظ التغييرات."), "تم حفظ التغييرات."))
        self.assertIsNone(re.fullmatch(t.to_pattern("a.b"), "axb"))

    def test_placeholder_and_newline(self):
        p = t.to_pattern("أهلًا {name}! هذا وقتك 🌟")
        self.assertTrue(re.fullmatch(p, "أهلًا E2E-Maestro! هذا وقتك 🌟"))
        p = t.to_pattern("السلام عليكم\nرحلة {name} مستمرة")
        self.assertTrue(re.fullmatch(p, "السلام عليكم\nرحلة E2E-Maestro مستمرة"))
        # Maestro also tries the text with newlines turned into spaces.
        self.assertTrue(re.fullmatch(p, "السلام عليكم رحلة E2E-Maestro مستمرة"))


class L10nTest(unittest.TestCase):
    AR = {"navToday": "اليوم", "tourSkip": "تخطّي", "routineChildMode": "تسليم الجهاز للطفل (وضع الطفل)"}
    EN = {"navToday": "Today", "tourSkip": "Skip", "routineChildMode": "Hand device to child (Child Mode)"}

    def setUp(self):
        self.maps, self.missing = t.build_l10n(self.AR, self.EN)

    def test_exact_matches_either_language_only(self):
        p = self.maps["t"]["tourSkip"]
        self.assertTrue(re.fullmatch(p, "تخطّي"))
        self.assertTrue(re.fullmatch(p, "Skip"))
        self.assertIsNone(re.fullmatch(p, "Skip tour"))

    def test_lead_pattern_accepts_merged_tab_announcement(self):
        p = self.maps["lead"]["navToday"]
        self.assertTrue(re.fullmatch(p, "اليوم\nعلامة التبويب 1 من 4"))
        self.assertTrue(re.fullmatch(p, "Today\nTab 1 of 4"))
        self.assertTrue(re.fullmatch(p, "اليوم"))
        self.assertIsNone(re.fullmatch(p, "نصيحة اليوم"))

    def test_tile_pattern_accepts_a_leading_emoji_line(self):
        p = self.maps["tile"]["tourSkip"]
        self.assertTrue(re.fullmatch(p, "⚙️\nتخطّي"))
        self.assertTrue(re.fullmatch(p, "Skip"))
        self.assertIsNone(re.fullmatch(p, "Skip & help"))

    def test_contains_and_single_language(self):
        self.assertTrue(re.fullmatch(self.maps["c"]["navToday"], "⭐\nاليوم\nx"))
        self.assertTrue(re.fullmatch(self.maps["en"]["navToday"], "Today"))
        self.assertIsNone(re.fullmatch(self.maps["en"]["navToday"], "اليوم"))
        self.assertIsNone(re.fullmatch(self.maps["ar"]["navToday"], "Today"))

    def test_missing_key_never_matches_and_is_reported(self):
        self.assertIn("onbStartJourney", self.missing)
        self.assertEqual(self.maps["t"]["onbStartJourney"], "__MISSING_ARB_KEY_onbStartJourney__")

    def test_literals_are_included(self):
        self.assertTrue(re.fullmatch(self.maps["t"]["lit_langTitle"], "Choose App Language"))

    def test_rendered_js_round_trips(self):
        js = t.render_js(self.maps, "test")
        body = js.split("output.t = ", 1)[1].split(";\n", 1)[0]
        self.assertEqual(json.loads(body)["navToday"], self.maps["t"]["navToday"])
        self.assertTrue(js.isascii(), "JS must not depend on the file encoding Maestro assumes")

    def test_real_arb_files_have_every_key(self):
        arb = Path(__file__).resolve().parent.parent / "mobile" / "lib" / "l10n"
        ar = json.loads((arb / "app_ar.arb").read_text(encoding="utf-8"))
        en = json.loads((arb / "app_en.arb").read_text(encoding="utf-8"))
        _, missing = t.build_l10n(ar, en)
        self.assertEqual(missing, [])


class CiChildNameTest(unittest.TestCase):
    """The onboarding child is created as test traffic, never renamed into it:
    production refuses a rename without an FCM device proof (2026-10-21)."""
    ROOT = Path(__file__).resolve().parents[1]
    L10N = ROOT / "mobile" / "lib" / "l10n"
    FILES = ("app_ar.arb", "app_en.arb", "app_localizations_ar.dart", "app_localizations_en.dart")

    def run_helper(self, l10n_dir, name="E2E-Maestro"):
        return subprocess.run(
            [sys.executable, "-S", str(Path(t.__file__).resolve()),
             "ci-child-name", "--l10n-dir", str(l10n_dir), "--name", name],
            capture_output=True, text=True,
        )

    def copy_l10n(self, tmp, source=None):
        out = Path(tmp)
        for f in self.FILES:
            (out / f).write_bytes((source or self.L10N).joinpath(f).read_bytes())
        return out

    def test_head_strings_become_the_test_name_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            l10n = self.copy_l10n(tmp)
            before = {f: (l10n / f).read_text(encoding="utf-8") for f in self.FILES}
            proc = self.run_helper(l10n)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for lang in ("ar", "en"):
                arb = json.loads((l10n / f"app_{lang}.arb").read_text(encoding="utf-8"))
                self.assertEqual(arb["onbDefaultChildName"], "E2E-Maestro")
                dart = (l10n / f"app_localizations_{lang}.dart").read_text(encoding="utf-8")
                self.assertIn("String get onbDefaultChildName => 'E2E-Maestro';", dart)
            for f in self.FILES:
                old = before[f].splitlines()
                new = (l10n / f).read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(old), len(new), f)
                changed = [a for a, b in zip(old, new) if a != b]
                self.assertEqual(len(changed), 1, f)
                self.assertIn("onbDefaultChildName", changed[0])

    def test_the_baseline_ref_is_patchable_too(self):
        workflow = (self.ROOT / ".github/workflows/mobile-e2e.yml").read_text()
        ref = re.search(r"vars\.E2E_BASELINE_REF \|\| '([0-9a-f]{40})'", workflow).group(1)
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as tmp:
            for f in self.FILES:
                show = subprocess.run(["git", "-C", str(self.ROOT), "show", f"{ref}:mobile/lib/l10n/{f}"],
                                      capture_output=True)
                if show.returncode != 0:
                    self.skipTest(f"baseline {ref[:8]} not in this clone")
                Path(src, f).write_bytes(show.stdout)
            l10n = self.copy_l10n(tmp, Path(src))
            proc = self.run_helper(l10n)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_refuses_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            l10n = self.copy_l10n(tmp)
            before = {f: (l10n / f).read_bytes() for f in self.FILES}
            for bad in ("E2E'x", 'E2E"x', "E2E Maestro", "x", ""):
                with self.subTest(name=bad):
                    proc = self.run_helper(l10n, bad)
                    self.assertEqual(proc.returncode, 1)
                    self.assertIn("::error::", proc.stderr)
            # A key missing from one file: no file is touched, not even the others.
            dart = l10n / "app_localizations_en.dart"
            dart.write_text(dart.read_text(encoding="utf-8").replace("onbDefaultChildName", "x"),
                            encoding="utf-8")
            before[dart.name] = dart.read_bytes()
            proc = self.run_helper(l10n)
            self.assertEqual(proc.returncode, 1)
            for f in self.FILES:
                self.assertEqual((l10n / f).read_bytes(), before[f], f)

    def test_workflow_builds_head_and_baseline_with_the_run_name(self):
        workflow = (self.ROOT / ".github/workflows/mobile-e2e.yml").read_text()
        # Every variant is built with the CHILD_NAME default of the script that
        # drives it; nothing in the workflow overrides those defaults.
        self.assertNotIn("E2E_CHILD_NAME", workflow)
        names = dict(re.findall(r"- variant: (\S+)\n(?:            .*\n)*?            child_name: (\S+)\n", workflow))
        self.assertEqual(set(names), {"head", "baseline", "rehearsal-head", "rehearsal-baseline"})
        for script, variants in (("run.sh", ("head", "baseline")),
                                 ("rehearsal.sh", ("rehearsal-head", "rehearsal-baseline"))):
            default = re.search(r'^CHILD_NAME="\$\{E2E_CHILD_NAME:-([^}]+)\}"$',
                                (self.ROOT / "e2e" / script).read_text(), re.M).group(1)
            for v in variants:
                self.assertEqual(names[v], default, v)
        marker = "      - name: Create the onboarding child as test traffic\n"
        self.assertIn(marker, workflow)
        self.assertLess(workflow.index(marker), workflow.index("      - name: Build the release APK"))
        section = workflow.split(marker, 1)[1].split("      - ", 1)[0]
        self.assertNotIn("continue-on-error", section)
        self.assertNotIn("if:", section)
        self.assertIn("CHILD_NAME: ${{ matrix.child_name }}", section)
        self.assertIn('ci-child-name --l10n-dir lib/l10n --name "$CHILD_NAME"', section)
        self.assertIn('"onboarding_child_name=$CHILD_NAME"', workflow)

    def test_no_flow_renames_the_onboarding_child(self):
        mark = (FLOWS / "common" / "mark_child.yaml").read_text(encoding="utf-8")
        steps = yaml.safe_load_all(mark)
        body = [s for s in steps][-1]
        text = json.dumps(body)
        self.assertNotIn("inputText", text)
        self.assertNotIn("eraseText", text)
        # The Settings tile is a merged node (title + subtitle): `lead`, not `t`.
        self.assertIn("tapOn: '${output.lead.settingsEditChild}'", mark)
        for flow in FLOWS.rglob("*.yaml"):
            self.assertNotIn("onbDefaultChildName", flow.read_text(encoding="utf-8"), flow.name)


class HubScrollTest(unittest.TestCase):
    def test_every_down_search_for_the_parent_day_tile_looks_up_first(self):
        """The hub keeps the offset the Settings shots left (its bottom); a DOWN
        search alone missed «يوم الطفل» at 200% font (runs 38777734035 and
        39649673035), and the praise shots after it were never taken."""
        steps = list(yaml.safe_load_all((FLOWS / "gallery" / "shoot.yaml").read_text(encoding="utf-8")))[-1]
        searches = [s["scrollUntilVisible"] for s in steps
                    if isinstance(s, dict) and "scrollUntilVisible" in s
                    and s["scrollUntilVisible"]["element"]["text"] == "${output.tile.hubParentDay}"]
        self.assertGreaterEqual(len(searches), 4)
        for up, down in zip(searches[::2], searches[1::2]):
            self.assertEqual((up["direction"], down["direction"]), ("UP", "DOWN"))


class FlowReferencesTest(unittest.TestCase):
    def test_every_selector_reference_exists(self):
        """A typo in `${output.t.someKey}` must fail here, not 20 minutes into CI."""
        arb = Path(__file__).resolve().parent.parent / "mobile" / "lib" / "l10n"
        ar = json.loads((arb / "app_ar.arb").read_text(encoding="utf-8"))
        en = json.loads((arb / "app_en.arb").read_text(encoding="utf-8"))
        maps, _ = t.build_l10n(ar, en)
        flows = sorted((Path(__file__).resolve().parent / "flows").rglob("*.yaml"))
        self.assertGreater(len(flows), 10)
        refs = 0
        for flow in flows:
            for name, key in re.findall(r"output\.(\w+)\.(\w+)", flow.read_text(encoding="utf-8")):
                refs += 1
                self.assertIn(name, maps, f"{flow.name}: no map output.{name}")
                self.assertIn(key, maps[name], f"{flow.name}: no key output.{name}.{key}")
        self.assertGreater(refs, 50)


FLOWS = Path(__file__).resolve().parent / "flows"
ARB_DIR = Path(__file__).resolve().parent.parent / "mobile" / "lib" / "l10n"
SERVER_RETRY = "common/server_retry.yaml"


def _selector(pattern: str, maps: dict) -> re.Pattern:
    """A flow selector as Maestro matches it: `${output.m.k}` filled in, and
    Java's mid-pattern `(?s)` (Python refuses it) widened to the whole pattern
    — every literal dot in these patterns is escaped, so the two agree."""
    filled = re.sub(r"\$\{output\.(\w+)\.(\w+)\}",
                    lambda m: maps[m.group(1)][m.group(2)], pattern)
    return re.compile(filled.replace("(?s)", ""), re.DOTALL)


def _run_flows(node, found):
    """Every `runFlow` mapping anywhere in a parsed flow."""
    if isinstance(node, dict):
        if isinstance(node.get("runFlow"), dict):
            found.append(node["runFlow"])
        for value in node.values():
            _run_flows(value, found)
    elif isinstance(node, list):
        for value in node:
            _run_flows(value, found)
    return found


class ServerRetryGuardTest(unittest.TestCase):
    """common/server_retry.yaml, the 5xx guard. It used to wait for the raw
    "TgApiError(5xx)" that friendlyError stopped printing on 2026-10-08, so it
    never fired and one 502 failed whole journeys (gallery/05_after_en,
    fresh/09, fresh/03). Pin it to the text the app shows."""

    @classmethod
    def setUpClass(cls):
        cls.ar = json.loads((ARB_DIR / "app_ar.arb").read_text(encoding="utf-8"))
        cls.en = json.loads((ARB_DIR / "app_en.arb").read_text(encoding="utf-8"))
        cls.maps, _ = t.build_l10n(cls.ar, cls.en)
        docs = list(yaml.safe_load_all((FLOWS / SERVER_RETRY).read_text(encoding="utf-8")))
        cls.loop = docs[1][0]["repeat"]
        cls.cmds = cls.loop["commands"]
        cls.when = next(c["runFlow"] for c in cls.cmds if "runFlow" in c)
        cls.server_down = _selector(cls.loop["while"]["visible"], cls.maps)

    def texts(self, key):
        return self.ar[key], self.en[key]

    def test_while_and_when_ask_the_same_question(self):
        self.assertEqual(self.loop["while"]["visible"], self.when["when"]["visible"])

    def test_fires_on_the_server_line_friendly_error_shows(self):
        for body in self.texts("errorServerBody"):
            self.assertTrue(self.server_down.fullmatch(body), body)  # its own node
            self.assertTrue(self.server_down.fullmatch(f"🛠️\n{body}\nRetry"), body)  # merged
        for wrap, body in zip(self.texts("chatSessionStartFailed"), self.texts("errorServerBody")):
            line = wrap.replace("{error}", body)
            self.assertTrue(self.server_down.fullmatch(line), line)

    def test_fires_on_the_raw_error_of_builds_before_friendly_error(self):
        # efaa740f — the workflow's baseline default — printed '$err'.
        self.assertTrue(self.server_down.fullmatch(
            "TgApiError(502): The origin web server returned an invalid or "
            "incomplete response to Cloudflare"))
        self.assertTrue(self.server_down.fullmatch("TgApiError(503)"))

    def test_leaves_every_other_failure_to_fail(self):
        for key in ("errorOfflineBody", "errorUnknownBody", "errorNotFoundBody",
                    "errorSessionBody", "errorRateLimitedBody",
                    "chatConnectionInterrupted", "lessonErrorLoading"):
            for text in self.texts(key):
                self.assertIsNone(self.server_down.fullmatch(text), f"{key}: {text}")
        for raw in ("TgApiError(404): Not Found", "TgApiError(429)", "TgApiError(null): timeout"):
            self.assertIsNone(self.server_down.fullmatch(raw), raw)

    def test_taps_the_retry_of_every_5xx_surface(self):
        tap = _selector(self.when["commands"][0]["tapOn"], self.maps)
        for key in ("retry", "chatRetry"):  # EmptyState/ErrorRetryView, chat turn
            for label in self.texts(key):
                self.assertTrue(tap.fullmatch(label), f"{key}: {label}")

    def test_is_bounded_to_two_retries_about_a_minute_apart(self):
        # A restart or deploy holds the server ~50 s; a real outage must still
        # fail, so: two retries, each after a pause, ~60 s in all.
        self.assertEqual(self.loop["times"], 2)
        pause = next(c["extendedWaitUntil"] for c in self.cmds if "extendedWaitUntil" in c)
        self.assertTrue(pause["optional"])
        self.assertGreaterEqual(self.loop["times"] * int(pause["timeout"]), 50_000)
        self.assertLessEqual(self.loop["times"] * int(pause["timeout"]), 70_000)

    def test_incident_sites_use_it_and_nothing_waits_for_the_raw_error(self):
        callers = {}
        for flow in sorted(FLOWS.rglob("*.yaml")):
            rel = flow.relative_to(FLOWS).as_posix()
            text = flow.read_text(encoding="utf-8")
            if rel != SERVER_RETRY:
                self.assertNotIn("TgApiError", text, f"{rel}: wait for the shown text, not the raw error")
            for run in _run_flows(list(yaml.safe_load_all(text)), []):
                if str(run.get("file", "")).endswith(SERVER_RETRY):
                    callers[rel] = run.get("env", {})
        self.assertLessEqual(
            {"fresh/02_today_lesson.yaml", "gallery/shoot.yaml",
             "fresh/09_programs.yaml", "fresh/03_assistant.yaml"}, set(callers))
        for rel, env in callers.items():
            self.assertIn("retry", env.get("SHOT", ""), f"{rel}: run.sh warns on *retry* shots")
            # A retried page keeps its error up while it reloads, so READY must
            # be the content alone or the pause ends at once.
            ready = env.get("READY", "")
            self.assertTrue(ready, f"{rel}: READY missing")
            for err in ("errorServerBody", "lessonErrorLoading", "output.t.retry", "chatRetry"):
                self.assertNotIn(err, ready, f"{rel}: READY must not match the error page")


class LogcatGateTest(unittest.TestCase):
    def scan(self, lines, allow=()):
        return t.scan_logcat(lines, PKG, [re.compile(a) for a in allow])

    def test_clean_log_passes(self):
        failures, _ = self.scan([
            lc(500, "I", "ActivityManager", f"Start proc 4242:{PKG}/u0a190 for next-top-activity"),
            lc(4242, "I", "flutter", "something informational"),
        ])
        self.assertEqual(failures, [])

    def test_fatal_exception_in_app_fails(self):
        failures, _ = self.scan([
            lc(4242, "E", "AndroidRuntime", "FATAL EXCEPTION: main"),
            lc(4242, "E", "AndroidRuntime", f"Process: {PKG}, PID: 4242"),
            lc(4242, "E", "AndroidRuntime", "java.lang.NullPointerException: boom"),
        ])
        self.assertEqual(len(failures), 1)
        self.assertIn("FATAL EXCEPTION", failures[0])

    def test_fatal_exception_in_other_process_is_ignored(self):
        failures, notes = self.scan([
            lc(777, "E", "AndroidRuntime", "FATAL EXCEPTION: main"),
            lc(777, "E", "AndroidRuntime", "Process: com.android.something, PID: 777"),
        ])
        self.assertEqual(failures, [])

    def test_anr_and_native_crash_fail(self):
        failures, _ = self.scan([
            lc(500, "E", "ActivityManager", f"ANR in {PKG} ({PKG}/.MainActivity)"),
            lc(9000, "F", "DEBUG", f"pid: 4242, tid: 4250, name: 1.ui  >>> {PKG} <<<"),
        ])
        kinds = sorted(f.split(":")[0] for f in failures)
        self.assertEqual(kinds, ["ANR", "NATIVE CRASH"])

    def test_flutter_errors_fail(self):
        failures, _ = self.scan([
            lc(4242, "I", "flutter", "Null check operator used on a null value"),
            lc(4242, "I", "flutter", "#0      _HomeState.build (package:almorabbi/screens/home_screen.dart:42)"),
            lc(4242, "I", "flutter", "#1      StatelessElement.build (package:flutter/src/widgets/framework.dart:5)"),
            lc(4242, "I", "flutter", "Another exception was thrown: Null check operator used on a null value"),
            lc(4242, "E", "flutter", "[ERROR:flutter/runtime/dart_vm_initializer.cc(40)] Unhandled Exception: Bad state"),
        ])
        self.assertEqual(len(failures), 3, failures)
        self.assertIn("Null check operator", failures[0])  # the message, not the frame

    def test_recorded_non_fatal_fails_only_for_the_app(self):
        lines = [
            lc(500, "I", "ActivityManager", f"Start proc 4242:{PKG}/u0a190 for activity"),
            lc(4242, "V", "FirebaseCrashlytics", "Persisting non-fatal event for session abc"),
            lc(31337, "V", "FirebaseCrashlytics", "Persisting non-fatal event for session other"),
        ]
        failures, _ = self.scan(lines)
        self.assertEqual(len(failures), 1)
        self.assertIn("session abc", failures[0])

    def test_allowlist_turns_failure_into_note(self):
        failures, notes = self.scan(
            [lc(4242, "E", "flutter", "[ERROR:flutter/impeller/x.cc] known emulator noise")],
            allow=[r"known emulator noise"],
        )
        self.assertEqual(failures, [])
        self.assertTrue(any("allowlisted" in n for n in notes))

    def test_main_once_per_process_passes(self):
        failures, notes = self.scan([
            lc(500, "I", "ActivityManager", f"Start proc 4242:{PKG}/u0a190 for next-top-activity"),
            lc(4242, "I", "flutter", "tg.main: entrypoint started", tid=4260),
            lc(500, "I", "ActivityManager", f"Start proc 5151:{PKG}/u0a190 for next-top-activity"),
            lc(5151, "I", "flutter", "tg.main: entrypoint started", tid=5170),
        ])
        self.assertEqual(failures, [])
        self.assertIn("main() runs per process: 4242=1, 5151=1", notes)

    def test_second_dart_entrypoint_in_one_process_fails(self):
        # What every process of 1.0.66 does: audio_service's engine runs main()
        # again, on its own UI thread, in the same process.
        failures, _ = self.scan([
            lc(500, "I", "ActivityManager", f"Start proc 4242:{PKG}/u0a190 for next-top-activity"),
            lc(4242, "I", "flutter", "tg.main: entrypoint started", tid=4260),
            lc(4242, "D", "MediaBrowserCompat", "Connecting to a MediaBrowserService."),
            lc(4242, "I", "flutter", "tg.main: entrypoint started", tid=4290),
        ])
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("SECOND DART ENTRYPOINT", failures[0])
        self.assertIn("2 times in process 4242", failures[0])

    def test_builds_without_the_marker_are_not_judged(self):
        failures, notes = self.scan([
            lc(500, "I", "ActivityManager", f"Start proc 4242:{PKG}/u0a190 for next-top-activity"),
            lc(4242, "I", "flutter", "something informational"),
        ])
        self.assertEqual(failures, [])
        self.assertFalse(any(n.startswith("main() runs") for n in notes))

    def run_gate(self, lines, *extra):
        """main() on a logcat file, its stdout captured: an uncaptured `::error::`
        line becomes a real annotation on the CI job that runs these tests (it
        did — every E2E run since the gate landed showed "logcat has only 10
        lines" from this test, and three reruns on 2026-10-08 chased it)."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "logcat.txt"
            path.write_text("\n".join(lines), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = t.main(["logcat-gate", str(path), "--out", str(Path(d) / "g.txt"), *extra])
            return rc, out.getvalue(), (Path(d) / "g.txt").read_text(encoding="utf-8")

    def test_gate_refuses_an_empty_capture(self):
        rc, stdout, report = self.run_gate([lc(1, "I", "x", "y") for _ in range(10)], "--min-lines", "200")
        self.assertEqual(rc, 1)
        self.assertIn("::error::logcat has only 10 lines", stdout)
        # The verdict file (job summary, artifact) says why, not "PASS".
        self.assertIn("FAIL  capture: only 10 lines", report)
        self.assertNotIn("PASS", report)

    def test_gate_refuses_a_truly_empty_file(self):
        rc, stdout, report = self.run_gate([], "--min-lines", "200")
        self.assertEqual(rc, 1)
        self.assertIn("FAIL  capture: only 0 lines", report)

    def test_short_capture_still_reports_the_crash_it_saw(self):
        rc, _, report = self.run_gate([
            lc(4242, "E", "AndroidRuntime", "FATAL EXCEPTION: main"),
            lc(4242, "E", "AndroidRuntime", f"Process: {PKG}, PID: 4242"),
        ], "--package", PKG, "--min-lines", "200")
        self.assertEqual(rc, 1)
        self.assertIn("FAIL  capture:", report)
        self.assertIn("FATAL EXCEPTION", report)

    def test_full_capture_passes_without_capture_failure(self):
        rc, stdout, report = self.run_gate([lc(1, "I", "x", "y") for _ in range(250)], "--min-lines", "200")
        self.assertEqual(rc, 0)
        self.assertNotIn("::error::", stdout)
        self.assertIn("PASS", report)



class AnalyticsIsolationTest(unittest.TestCase):
    ANDROID = "{http://schemas.android.com/apk/res/android}"
    FLAG = "firebase_analytics_collection_deactivated"

    def run_helper(self, path):
        return subprocess.run(
            [sys.executable, "-S", str(Path(t.__file__).resolve()),
             "deactivate-analytics", "--manifest", str(path)],
            capture_output=True, text=True,
        )

    def test_head_and_old_baseline_use_head_artifact_helper(self):
        # Execute the workflow's injection script, with only the head helper
        # downloaded outside the old checkout. No baseline e2e_tool exists.
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/mobile-e2e.yml").read_text()
        producer = workflow.split("  keystore:\n", 1)[1].split("  build:\n", 1)[0]
        self.assertIn("ref: ${{ github.event.pull_request.head.sha || github.sha }}", producer)
        self.assertIn("sparse-checkout: e2e/e2e_tool.py", producer)
        self.assertIn("sparse-checkout-cone-mode: false", producer)
        self.assertIn("name: e2e-ci-helper", producer)
        self.assertIn("path: e2e/e2e_tool.py", producer)
        self.assertIn("if-no-files-found: error", producer)
        build = workflow.split("  build:\n", 1)[1].split("  e2e:\n", 1)[0]
        self.assertIn("needs: [changes, keystore]", build)
        self.assertIn("- variant: head", build)
        self.assertIn("- variant: baseline", build)
        self.assertIn("ref: ${{ matrix.ref }}", build)
        self.assertIn("name: e2e-ci-helper\n          path: ${{ runner.temp }}/ci-helper", build)
        self.assertIn("'$OUT/ci-config.txt'".replace("'", '"'), build)
        self.assertIn("'firebase_analytics_collection_deactivated=true'", build)
        marker = "      - name: Deactivate Firebase Analytics for CI APKs\n"
        self.assertIn(marker, workflow)
        section = workflow.split(marker, 1)[1].split("      - ", 1)[0]
        self.assertNotIn("if:", section)
        self.assertNotIn("continue-on-error", section)
        script = section.split("        run: |\n", 1)[1]
        script = "\n".join(line[10:] for line in script.splitlines())
        self.assertLess(workflow.index(marker), workflow.index("      - name: Build the release APK"))
        for variant in ("head", "baseline"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                helper = root / "ci-helper"
                helper.mkdir()
                (helper / "e2e_tool.py").write_bytes(Path(t.__file__).read_bytes())
                mobile = root / variant / "mobile"
                manifest = mobile / "android/app/src/main/AndroidManifest.xml"
                manifest.parent.mkdir(parents=True)
                manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:name="${applicationName}" /></manifest>')
                result = subprocess.run(["bash", "-e", "-c", script], cwd=mobile,
                                        env={**os.environ, "RUNNER_TEMP": tmp},
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                flag = ET.parse(manifest).find("application/meta-data")
                self.assertEqual(flag.get(self.ANDROID + "name"), self.FLAG)
                self.assertEqual(flag.get(self.ANDROID + "value"), "true")
                # Fail closed in the actual bash step: an injection error must
                # prevent any subsequent build command from being reached.
                manifest.write_text("<manifest/>")
                reached = root / "build-started"
                failed = subprocess.run(["bash", "-e", "-c", script +
                                         '\ntouch "' + str(reached) + '"'],
                                        cwd=mobile, env={**os.environ, "RUNNER_TEMP": tmp},
                                        capture_output=True, text=True)
                self.assertEqual(failed.returncode, 1, failed.stderr)
                self.assertFalse(reached.exists())

    def test_rejects_invalid_manifest_without_changing_it(self):
        cases = ["<manifest/>", "<manifest><application/><application/></manifest>",
                 "<manifest>",
                 '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application><meta-data android:name="FLAG"/><meta-data android:name="FLAG"/></application></manifest>',
                 '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application><meta-data android:name="FLAG" android:resource="@bool/analytics"/></application></manifest>']
        for source in cases:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "AndroidManifest.xml"
                path.write_text(source.replace("FLAG", self.FLAG))
                before = path.read_bytes()
                result = self.run_helper(path)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(path.read_bytes(), before)

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_helper(Path(tmp) / "missing.xml").returncode, 1)

    def test_preserves_attributes_components_comments_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AndroidManifest.xml"
            path.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="example"><!--keep--><application android:name="${applicationName}" android:label="App"><activity android:name=".MainActivity"/><meta-data android:name="other" android:value="yes"/><meta-data android:name="FLAG" android:value="false" android:enabled="true"/></application></manifest>'.replace("FLAG", self.FLAG))
            self.assertEqual(self.run_helper(path).returncode, 0)
            app = ET.parse(path).find("application")
            self.assertEqual(app.attrib, {self.ANDROID + "name": "${applicationName}", self.ANDROID + "label": "App"})
            self.assertEqual(app.find("activity").get(self.ANDROID + "name"), ".MainActivity")
            metas = app.findall("meta-data")
            self.assertEqual(len(metas), 2)
            self.assertEqual(metas[0].get(self.ANDROID + "value"), "yes")
            self.assertEqual(metas[1].get(self.ANDROID + "value"), "true")
            self.assertEqual(metas[1].get(self.ANDROID + "enabled"), "true")
            self.assertIn("<!--keep-->", path.read_text())
            before = path.read_bytes()
            self.assertEqual(self.run_helper(path).returncode, 0)
            self.assertEqual(path.read_bytes(), before)


class GalleryTest(unittest.TestCase):
    """The before/after pairing: names drive everything, so fabricate files."""

    def run_gallery(self, names, extra=()):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            screens = root / "screens"
            screens.mkdir()
            for name in names:
                (screens / name).write_bytes(b"\x89PNG")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = t.main(["gallery", str(screens), "--out", str(root / "gallery"), *extra])
            summary = (root / "gallery" / "gallery-summary.md").read_text(encoding="utf-8")
            images = sorted(p.name for p in (root / "gallery" / "images").glob("*.png"))
            return rc, out.getvalue(), summary, images

    # ── --require-after: the gate must never go green while blind ─────────

    def complete_shots(self, drop=()):
        """Every screen in every variant, before and after, plus onboarding."""
        names = []
        for v in ("ar", "en", "ar_font2x"):
            for s, _c in t.GALLERY_SCREENS:
                names.append(f"gallery__01_before_{v}__before__{v}__{s}.png")
                names.append(f"gallery__05_after_{v}__after__{v}__{s}.png")
        for s, _c in t.GALLERY_ONBOARDING:
            names.append(f"gallery__00_onboarding__{s}.png")
            names.append(f"fresh__01_onboarding__{s}.png")
        return [n for n in names if n not in drop]

    def test_require_after_is_green_on_a_complete_shoot(self):
        rc, stdout, _, images = self.run_gallery(
            self.complete_shots(), extra=("--require-after",))
        self.assertEqual(rc, 0)
        self.assertNotIn("::error", stdout)
        self.assertTrue(images)

    def test_require_after_fails_on_an_empty_after_cell(self):
        # An «after» column showing «—» is a BLIND gate: run 37895766558
        # shipped exactly this — every after cell empty, check still green.
        rc, stdout, summary, _ = self.run_gallery(
            self.complete_shots(drop=("gallery__05_after_en__after__en__celebration.png",)),
            extra=("--require-after",))
        self.assertEqual(rc, 1)
        self.assertIn("::error title=E2E gallery", stdout)
        self.assertIn("en:celebration", stdout)
        # The summary is still written, with the hole visible for a human.
        self.assertIn("| احتفال إكمال الدرس |", summary)

    def test_guarded_screens_may_stay_empty_under_require_after(self):
        drop = tuple(
            f"gallery__05_after_{v}__after__{v}__{s}.png"
            for v in ("ar", "en", "ar_font2x")
            for s in t.GALLERY_GUARDED
        )
        rc, stdout, _, _ = self.run_gallery(
            self.complete_shots(drop=drop), extra=("--require-after",))
        self.assertEqual(rc, 0)
        self.assertNotIn("::error", stdout)

    def test_pairs_before_and_after_and_copies_the_images(self):
        rc, stdout, summary, images = self.run_gallery([
            "gallery__01_before_ar__before__ar__home.png",
            "gallery__05_after_ar__after__ar__home.png",
            "fresh__01_onboarding__onboarding_1_language.png",
        ])
        self.assertEqual(rc, 0)
        # The pair, side by side, linked relatively within the artifact.
        self.assertIn('<img src="images/gallery__01_before_ar__before__ar__home.png" width="270"', summary)
        self.assertIn('<img src="images/gallery__05_after_ar__after__ar__home.png" width="270"', summary)
        self.assertIn("gallery__01_before_ar__before__ar__home.png", images)
        self.assertIn("gallery__05_after_ar__after__ar__home.png", images)
        # The one complete pair; everything else this run never took is missing.
        self.assertIn("<!-- gallery: complete=1 before-only=0 after-only=1 missing=", summary)
        self.assertIn("gallery: complete=1", stdout)

    def test_home_does_not_swallow_home_after_lesson(self):
        _, _, summary, images = self.run_gallery([
            "gallery__01_before_ar__before__ar__home_after_lesson.png",
        ])
        self.assertIn("gallery__01_before_ar__before__ar__home_after_lesson.png", images)
        # The home cell stayed empty — no greedy prefix match.
        self.assertNotIn("before__ar__home.png\"", summary)
        self.assertIn("before-only=1", summary)

    def test_maestro_collision_suffix_is_ignored(self):
        rc, _, summary, images = self.run_gallery([
            "gallery__01_before_ar__before__ar__home_2.png",
            "gallery__05_after_ar__after__ar__home.png",
        ])
        self.assertEqual(rc, 0)
        self.assertIn("complete=1", summary)
        self.assertIn("gallery__01_before_ar__before__ar__home_2.png", images)

    def test_onboarding_pairs_across_lineages(self):
        # «before» = the gallery lineage's baseline onboarding; «after» = the
        # fresh lineage's head onboarding (same flow file, same shot names).
        _, _, summary, _ = self.run_gallery([
            "gallery__00_onboarding__onboarding_1_language.png",
            "fresh__01_onboarding__onboarding_1_language.png",
        ])
        self.assertIn("complete=1", summary)
        self.assertIn("images/gallery__00_onboarding__onboarding_1_language.png", summary)
        self.assertIn("images/fresh__01_onboarding__onboarding_1_language.png", summary)

    def test_repeated_flows_pair_the_oldest_run(self):
        _, _, summary, _ = self.run_gallery([
            "gallery__01_before_ar__before__ar__home.png",
            "gallery__09_before_ar_retry__before__ar__home.png",
            "gallery__05_after_ar__after__ar__home.png",
        ])
        self.assertIn("images/gallery__01_before_ar__before__ar__home.png", summary)
        self.assertNotIn("gallery__09_before_ar_retry", summary)

    def test_no_shots_at_all_still_writes_the_summary(self):
        rc, _, summary, images = self.run_gallery([])
        self.assertEqual(rc, 0)
        self.assertEqual(images, [])
        # 3 variants × 13 screens + 2 onboarding shots, all accounted for.
        total = 3 * len(t.GALLERY_SCREENS) + len(t.GALLERY_ONBOARDING)
        self.assertIn(f"missing={total}", summary)
        self.assertEqual(summary.count("| — | — |"), total)

    def test_summary_command_reads_the_gallery_stats(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "screens").mkdir()
            (root / "screens" / "gallery__01_before_ar__before__ar__home.png").write_bytes(b"\x89PNG")
            (root / "gallery").mkdir()
            (root / "gallery" / "gallery-summary.md").write_text(
                "<!-- gallery: complete=1 before-only=0 after-only=0 missing=41 -->\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = t.main(["summary", str(root)])
            self.assertEqual(rc, 0)
            self.assertIn("Gallery قبل/بعد: complete=1", out.getvalue())

    def test_praise_screens_are_ungarded_and_fail_if_missing(self):
        # praise_child_sticker and praise_child_sticker_and_text must NOT be guarded
        self.assertNotIn("praise_child_sticker", t.GALLERY_GUARDED)
        self.assertNotIn("praise_child_sticker_and_text", t.GALLERY_GUARDED)
        rc, stdout, _, _ = self.run_gallery(
            self.complete_shots(drop=("gallery__05_after_ar__after__ar__praise_child_sticker.png",)),
            extra=("--require-after",),
        )
        self.assertEqual(rc, 1)
        self.assertIn("ar:praise_child_sticker", stdout)


class ShootOrderTest(unittest.TestCase):
    """What one leg of gallery/shoot.yaml leaves on screen is where the next starts."""

    @staticmethod
    def scroll(cmd):
        s = cmd.get("scrollUntilVisible") if isinstance(cmd, dict) else None
        return (s["element"]["text"], s.get("direction")) if s else None

    def test_lantern_search_scrolls_back_up_to_the_mission(self):
        # Run 38688818497 (#112): production has no /api/family/week, so the
        # lantern search ran Today to its bottom. Tapping the Today tab keeps
        # that offset, the praise leg's DOWN search for ③ («افتح مهمة اليوم»)
        # never found it, and every 7–12 praise shot (and at 200% font the
        # 4–6 one too) came out blank in both lineages.
        import yaml
        flow = Path(__file__).resolve().parent / "flows" / "gallery" / "shoot.yaml"
        steps = list(yaml.safe_load_all(flow.read_text(encoding="utf-8")))[-1]
        lanterns = "${output.c.weekLanternsTitle}"
        mission = "${output.t.todayMissionOpen}"
        start = next(i for i, c in enumerate(steps) if self.scroll(c) == (lanterns, "DOWN"))
        praise = next(i for i, c in enumerate(steps)
                      if i > start and self.scroll(c) == (mission, "DOWN"))
        restores = [
            c for c in steps[start + 1:praise]
            if isinstance(c, dict) and "runFlow" in c
            and c["runFlow"].get("when", {}).get("notVisible") == lanterns
            and any(self.scroll(x) == (mission, "UP") for x in c["runFlow"].get("commands", []))
        ]
        self.assertTrue(restores, "a missed lantern row must scroll Today back UP to ③ "
                        "before the praise leg searches DOWN for it")


class HierarchyVerificationTest(unittest.TestCase):
    def test_matching_hierarchy_passes(self):
        sample = '<node text="الإعدادات" resource-id="settings_title"/>'
        errors = t.verify_screen_hierarchy("settings", sample)
        self.assertEqual(errors, [])

    def test_missing_required_marker_fails(self):
        sample = '<node text="شاشة عشوائية"/>'
        errors = t.verify_screen_hierarchy("settings", sample)
        self.assertTrue(errors)
        self.assertIn("Missing expected markers", errors[0])

    def test_forbidden_marker_fails_home_dark_noor_face(self):
        # A shot on "المزيد" mistakenly taken as home_dark_noor_face must fail
        sample = '<node text="اليوم"/><node text="المزيد"/>'
        errors = t.verify_screen_hierarchy("home_dark_noor_face", sample)
        self.assertTrue(errors)
        self.assertIn("Found forbidden marker 'المزيد'", errors[0])

    def test_forbidden_marker_fails_settings(self):
        # A settings shot mistakenly on tab root
        sample = '<node text="الإعدادات"/><node text="علامة التبويب 1 من 4"/>'
        errors = t.verify_screen_hierarchy("settings", sample)
        self.assertTrue(errors)
        self.assertIn("Found forbidden marker", errors[0])

    def test_cli_verify_hierarchy(self):
        with tempfile.TemporaryDirectory() as d:
            dump_file = Path(d) / "dump.xml"
            dump_file.write_text('<node text="اليوم"/>', encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                rc = t.main(["verify-hierarchy", "home", str(dump_file)])
            self.assertEqual(rc, 0)

            dump_bad = Path(d) / "bad.xml"
            dump_bad.write_text('<node text="المزيد"/>', encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stdout(err), contextlib.redirect_stderr(err):
                rc_bad = t.main(["verify-hierarchy", "home_dark_noor_face", str(dump_bad)])
            self.assertEqual(rc_bad, 1)
            self.assertIn("Found forbidden marker 'المزيد'", err.getvalue())

    def test_pin_pad_hierarchy_fails_when_labeled_praise_child_sticker(self):
        # Exact PIN setup hierarchy text from run 37974593492 where camera captured
        # the PIN keypad instead of the child's praise card.
        sample_pin_hierarchy = (
            '{"accessibilityText": "وضع الطفل"}, '
            '{"accessibilityText": "اختر رمزًا من أربعة أرقام يحمي وضع الطفل. ستحتاج إليه للخروج منه."}, '
            '{"accessibilityText": "1"}, {"accessibilityText": "2"}, {"accessibilityText": "3"}, '
            '{"accessibilityText": "4"}, {"accessibilityText": "5"}, {"accessibilityText": "6"}, '
            '{"accessibilityText": "7"}, {"accessibilityText": "8"}, {"accessibilityText": "9"}, '
            '{"accessibilityText": "0"}, {"accessibilityText": "⌫"}'
        )
        errors = t.verify_screen_hierarchy(
            "praise_child_sticker", sample_pin_hierarchy, lang="ar"
        )
        self.assertTrue(errors)
        self.assertTrue(any("Missing expected markers" in e for e in errors))
        self.assertTrue(any("Found forbidden marker 'وضع الطفل'" in e for e in errors))

    def test_ordinary_mission_hierarchy_without_praise_fails_praise_marker(self):
        # Ordinary child mission card without praiseFromFamily must fail
        # the praise screen marker check.
        sample_mission_hierarchy = (
            '{"text": "مهمة اليوم"}, '
            '{"text": "رتّب غرفتك"}, '
            '{"text": "رتّب سريرك وضع الألعاب في الصندوق"}, '
            '{"text": "فهمت وسأنطلق"}, '
            '{"text": "أنجزتها"}'
        )
        errors_ar = t.verify_screen_hierarchy(
            "praise_child_sticker", sample_mission_hierarchy, lang="ar"
        )
        self.assertTrue(errors_ar)
        self.assertTrue(any("Missing expected markers" in e for e in errors_ar))

        errors_en = t.verify_screen_hierarchy(
            "praise_child_sticker", sample_mission_hierarchy, lang="en"
        )
        self.assertTrue(errors_en)
    def test_sticker_only_fails_when_note_text_present(self):
        # 4-6 must only have sticker (praiseFromFamily), no note text
        sample_4_6_with_note = '{"accessibilityText": "أهلك يقولون لك"}, {"text": "فخورون بك"}'
        errors = t.verify_screen_hierarchy("praise_child_sticker", sample_4_6_with_note, lang="ar")
        self.assertTrue(errors)
        self.assertTrue(any("Found forbidden marker 'فخورون بك'" in e for e in errors))

    def test_sticker_only_passes_with_family_semantics_and_no_note(self):
        sample_4_6 = '{"accessibilityText": "أهلك يقولون لك"}, {"text": "رتّب غرفتك"}'
        errors = t.verify_screen_hierarchy("praise_child_sticker", sample_4_6, lang="ar")
        self.assertEqual(errors, [])

    def test_sticker_and_text_requires_both_family_and_note(self):
        # 7-12 missing note text must fail
        sample_missing_note = '{"accessibilityText": "أهلك يقولون لك"}'
        errors = t.verify_screen_hierarchy("praise_child_sticker_and_text", sample_missing_note, lang="ar")
        self.assertTrue(errors)
        self.assertTrue(any("Missing expected markers (required 'فخورون بك')" in e for e in errors))

        # 7-12 with both must pass
        sample_complete = '{"accessibilityText": "أهلك يقولون لك"}, {"text": "فخورون بك"}'
        errors_complete = t.verify_screen_hierarchy("praise_child_sticker_and_text", sample_complete, lang="ar")
        self.assertEqual(errors_complete, [])

    def test_verify_hierarchy_cli_require_flag(self):
        with tempfile.TemporaryDirectory() as d:
            non_existent = Path(d) / "no_such_dir"
            err = io.StringIO()
            with contextlib.redirect_stdout(err), contextlib.redirect_stderr(err):
                # Without --require, returns 0
                self.assertEqual(t.main(["verify-hierarchy", "--report-dir", str(non_existent)]), 0)
                # With --require, returns 1
                self.assertEqual(t.main(["verify-hierarchy", "--report-dir", str(non_existent), "--require"]), 1)

            # Empty report dir
            empty_dir = Path(d) / "empty"
            empty_dir.mkdir()
            with contextlib.redirect_stdout(err), contextlib.redirect_stderr(err):
                self.assertEqual(t.main(["verify-hierarchy", "--report-dir", str(empty_dir)]), 0)
                self.assertEqual(t.main(["verify-hierarchy", "--report-dir", str(empty_dir), "--require"]), 1)

            # Report dir with valid screen passes
            partial_dir = Path(d) / "partial"
            dump_dir = partial_dir / "screen-hierarchy"
            dump_dir.mkdir(parents=True)
            (dump_dir / "01_home.json").write_text('{"text": "اليوم"}', encoding="utf-8")
            with contextlib.redirect_stdout(err), contextlib.redirect_stderr(err):
                self.assertEqual(t.main(["verify-hierarchy", "--report-dir", str(partial_dir)]), 0)
                self.assertEqual(t.main(["verify-hierarchy", "--report-dir", str(partial_dir), "--require"]), 0)

            # Report dir with failing screen markers fails with and without --require
            bad_dir = Path(d) / "bad"
            bad_dump = bad_dir / "screen-hierarchy"
            bad_dump.mkdir(parents=True)
            (bad_dump / "step-1-praise_child_sticker.json").write_text(
                '{"accessibilityText": "أهلك يقولون لك"}, {"text": "فخورون بك"}', encoding="utf-8"
            )
            with contextlib.redirect_stdout(err), contextlib.redirect_stderr(err):
                self.assertEqual(t.main(["verify-hierarchy", "--report-dir", str(bad_dir)]), 1)
                self.assertEqual(t.main(["verify-hierarchy", "--report-dir", str(bad_dir), "--require"]), 1)

            # Report dir with both praise screens properly matched and passing
            complete_dir = Path(d) / "complete"
            comp_dump = complete_dir / "screen-hierarchy"
            comp_dump.mkdir(parents=True)
            (comp_dump / "step-1-praise_child_sticker_and_text.json").write_text(
                '{"accessibilityText": "أهلك يقولون لك"}, {"text": "فخورون بك"}', encoding="utf-8"
            )
            (comp_dump / "step-2-praise_child_sticker.json").write_text(
                '{"accessibilityText": "أهلك يقولون لك"}', encoding="utf-8"
            )
            with contextlib.redirect_stdout(err), contextlib.redirect_stderr(err):
                self.assertEqual(t.main(["verify-hierarchy", "--report-dir", str(complete_dir), "--require"]), 0)

    def test_informational_pass_annotates_a_warning_not_an_error(self):
        # PR #121: the «before» gallery pass (baseline 1.0.71, no praise card
        # text yet) printed ##[error] «Missing expected markers» on every run —
        # green ones too — and it read like the reason the job failed.
        with tempfile.TemporaryDirectory() as d:
            dump = Path(d) / "screen-hierarchy"
            dump.mkdir(parents=True)
            (dump / "step-219-praiseFromFam.json").write_text('{"text": "اليوم"}', encoding="utf-8")
            for extra, level, other in (([], "::warning ", "::error "),
                                        (["--require"], "::error ", "::warning ")):
                err = io.StringIO()
                with contextlib.redirect_stdout(err), contextlib.redirect_stderr(err):
                    rc = t.main(["verify-hierarchy", "--report-dir", d, *extra])
                self.assertEqual(rc, 1)
                self.assertIn(level + "title=Hierarchy check::", err.getvalue())
                self.assertIn("Missing expected markers", err.getvalue())
                self.assertNotIn(other, err.getvalue())



# ── the Ramadan rehearsal ────────────────────────────────────────────────

ROUTER = Path(__file__).resolve().parents[1] / "backend/app/routers/family_programs.py"
_ROUTE = re.compile(r'@router\.(get|post|put|delete)\(\s*"([^"]+)".*?\ndef \w+\((.*?)\):\n', re.S)
_SAMPLE = {"{child_id}": "7", "{day}": "15", "{key}": "first_fast"}


def router_routes():
    """(sample path, takes as_of) for every route of the programs router."""
    out = []
    for _method, path, params in _ROUTE.findall(ROUTER.read_text(encoding="utf-8")):
        sample = "/api" + path
        for k, v in _SAMPLE.items():
            sample = sample.replace(k, v)
        out.append((sample, re.search(r"\bas_of\b", params) is not None))
    return out


class AsOfRouteTest(unittest.TestCase):
    def test_exactly_the_router_routes_that_take_as_of(self):
        routes = router_routes()
        self.assertGreaterEqual(sum(1 for _, takes in routes if takes), 15)
        self.assertGreaterEqual(sum(1 for _, takes in routes if not takes), 2)
        for sample, takes in routes:
            with self.subTest(sample):
                self.assertEqual(t.as_of_applies(sample), takes)

    def test_everything_else_is_left_alone(self):
        for path in ("/api/children", "/api/children/7", "/api/children/7/progress",
                     "/api/family/week", "/api/chat/sessions", "/api/programsx",
                     "/api/app-config", "/health", "/api/value-tracking/child-mode/prayer/today"):
            with self.subTest(path):
                self.assertFalse(t.as_of_applies(path))

    def test_as_of_is_appended_never_replaced(self):
        self.assertEqual(t.with_as_of("tz_offset_minutes=-300&lang=en", "2027-02-22"),
                         ("tz_offset_minutes=-300&lang=en&as_of=2027-02-22", True))
        self.assertEqual(t.with_as_of("", "2027-02-22"), ("as_of=2027-02-22", True))
        self.assertEqual(t.with_as_of("as_of=2027-01-01&lang=ar", "2027-02-22"),
                         ("as_of=2027-01-01&lang=ar", False))
        self.assertEqual(t.with_as_of("lang=ar", None), ("lang=ar", False))

    def test_stage_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "as_of.txt"
            self.assertEqual(t.read_stage(f), (None, "-"))
            for text, want in (("2027-02-22 ar_day15\n", ("2027-02-22", "ar_day15")),
                               ("2027-02-22\n", ("2027-02-22", "2027-02-22")),
                               ("", (None, "-")),
                               ("tomorrow day1", (None, "-")),
                               ("2027-13-40 day1", (None, "-"))):
                f.write_text(text, encoding="utf-8")
                self.assertEqual(t.read_stage(f), want, text)


class _Recorder(BaseHTTPRequestHandler):
    """A fake candidate: records what reached it, answers with a status
    chosen by the path (…/forbidden → 403) and echoes the request."""
    protocol_version = "HTTP/1.1"
    seen = []

    def log_message(self, *args):
        return

    def _answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        type(self).seen.append({"method": self.command, "path": self.path, "body": body,
                                "auth": self.headers.get("Authorization")})
        status = 403 if self.path.split("?")[0].endswith("/forbidden") else 200
        data = json.dumps({"path": self.path, "body": body}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_DELETE = _answer


def _serve(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class AsOfProxyTest(unittest.TestCase):
    def setUp(self):
        _Recorder.seen = []
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.stage = root / "as_of.txt"
        self.log = root / "proxy.tsv"
        self.upstream = _serve(ThreadingHTTPServer(("127.0.0.1", 0), _Recorder))
        up = f"http://127.0.0.1:{self.upstream.server_address[1]}"
        self.proxy = _serve(t.make_as_of_proxy(("127.0.0.1", 0), up, self.stage, self.log))
        self.base = f"http://127.0.0.1:{self.proxy.server_address[1]}"

    def tearDown(self):
        for s in (self.proxy, self.upstream):
            s.shutdown()
            s.server_close()
        self.tmp.cleanup()

    def test_programs_calls_get_the_stage_date(self):
        self.stage.write_text("2027-02-22 ar_day15\n", encoding="utf-8")
        status, body = t.http_json("GET", f"{self.base}/api/programs?tz_offset_minutes=180&lang=ar", token="tok")
        self.assertEqual(status, 200)
        self.assertEqual(body["path"], "/api/programs?tz_offset_minutes=180&lang=ar&as_of=2027-02-22")
        self.assertEqual(_Recorder.seen[-1]["auth"], "Bearer tok")
        status, body = t.http_json("POST", f"{self.base}/api/programs/ramadan/marks?lang=ar",
                                   token="tok", body={"mark": "challenge_done", "done": True})
        self.assertEqual(body["path"], "/api/programs/ramadan/marks?lang=ar&as_of=2027-02-22")
        self.assertEqual(json.loads(body["body"]), {"mark": "challenge_done", "done": True})
        rows = [r.split("\t") for r in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r[1:] for r in rows], [
            ["ar_day15", "GET", "/api/programs", "2027-02-22", "200"],
            ["ar_day15", "POST", "/api/programs/ramadan/marks", "2027-02-22", "200"],
        ])

    def test_other_calls_pass_untouched(self):
        self.stage.write_text("2027-02-22 ar_day15\n", encoding="utf-8")
        _, body = t.http_json("GET", f"{self.base}/api/children/7/progress?x=1")
        self.assertEqual(body["path"], "/api/children/7/progress?x=1")
        self.assertTrue(self.log.read_text(encoding="utf-8").rstrip().endswith("\t-\t200"))

    def test_no_stage_no_date(self):
        self.stage.write_text("", encoding="utf-8")
        _, body = t.http_json("GET", f"{self.base}/api/programs?lang=ar")
        self.assertEqual(body["path"], "/api/programs?lang=ar")

    def test_the_server_status_is_passed_through(self):
        self.stage.write_text("2027-02-22 ar_day15\n", encoding="utf-8")
        status, body = t.http_json("GET", f"{self.base}/api/programs/forbidden")
        self.assertEqual(status, 403)
        self.assertEqual(body["path"], "/api/programs/forbidden?as_of=2027-02-22")

    def test_an_unreachable_server_is_a_502_not_a_hang(self):
        dead = t.make_as_of_proxy(("127.0.0.1", 0), "http://127.0.0.1:9", self.stage)
        _serve(dead)
        try:
            status, _ = t.http_json("GET", f"http://127.0.0.1:{dead.server_address[1]}/api/programs")
            self.assertEqual(status, 502)
        finally:
            dead.shutdown()
            dead.server_close()


SEASON = {"hijri_year": 1448, "starts_on": "2027-02-08", "days": 30, "eid_on": "2027-03-10",
          "start_source": "estimate"}


def _locate(today):
    """backend/app/services/ramadan_program.locate for one season."""
    start, eid = date(2027, 2, 8), date(2027, 3, 10)
    if today < start:
        return {"state": "upcoming", "days_until_start": (start - today).days}
    if today < eid:
        return {"state": "ramadan", "day": (today - start).days + 1}
    if today == eid:
        return {"state": "eid"}
    if today < eid + timedelta(days=29):
        return {"state": "after", "after_week": (today - eid - timedelta(days=1)).days // 7 + 1}
    return {"state": "off_season"}


class _Candidate(BaseHTTPRequestHandler):
    """A fake candidate backend: sessions, and GET /api/programs that honours
    as_of only when `enabled` — like PROGRAMS_AS_OF_ENABLED."""
    protocol_version = "HTTP/1.1"
    enabled = True
    shift_days = 0  # a broken server answers the wrong day

    def log_message(self, *args):
        return

    def _send(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path == "/api/chat/sessions":
            return self._send(201, {"session_id": "s", "token": "tok"})
        self._send(404, {})

    def do_GET(self):
        parts = urlsplit(self.path)
        if parts.path == "/health":
            return self._send(200, {"status": "ok"})
        if parts.path != "/api/programs" or self.headers.get("Authorization") != "Bearer tok":
            return self._send(401, {})
        q = dict(parse_qsl(parts.query))
        today = date(2026, 10, 15)
        if "as_of" in q:
            if not type(self).enabled:
                return self._send(403, {"detail": {"error": "as_of_disabled"}})
            today = date.fromisoformat(q["as_of"]) + timedelta(days=type(self).shift_days)
        ramadan = {"season": SEASON, **_locate(today)}
        self._send(200, {"date": today.isoformat(), "ramadan": ramadan, "children": []})


class AsOfPreflightTest(unittest.TestCase):
    def setUp(self):
        _Candidate.enabled, _Candidate.shift_days = True, 0
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.stage, self.stages, self.out = root / "as_of.txt", root / "stages.tsv", root / "pre.md"
        self.server = _serve(ThreadingHTTPServer(("127.0.0.1", 0), _Candidate))
        self.up = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.proxy = _serve(t.make_as_of_proxy(("127.0.0.1", 0), self.up, self.stage))
        self.via = f"http://127.0.0.1:{self.proxy.server_address[1]}"

    def tearDown(self):
        for s in (self.proxy, self.server):
            s.shutdown()
            s.server_close()
        self.tmp.cleanup()

    def run_cli(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = t.main(["as-of-preflight", "--upstream", self.up, "--proxy", self.via,
                         "--as-of-file", str(self.stage), "--stages-out", str(self.stages),
                         "--out", str(self.out)])
        return rc, out.getvalue()

    def test_stages_come_from_the_server_season(self):
        stages = t.rehearsal_stages(SEASON)
        self.assertEqual([(s["label"], s["date"].isoformat(), s["day"]) for s in stages], [
            ("before", "2027-01-09", 0), ("day1", "2027-02-08", 1), ("day15", "2027-02-22", 15),
            ("day27", "2027-03-06", 27), ("eid", "2027-03-10", 0), ("after", "2027-03-15", 0)])
        for s in stages:
            with self.subTest(s["label"]):
                self.assertIsNone(t.check_stage_answer(
                    s, {"date": s["date"].isoformat(), "ramadan": _locate(s["date"])}))

    def test_a_candidate_that_honours_as_of_passes_and_writes_the_stages(self):
        self.stage.write_text("2027-01-09 b_before\n", encoding="utf-8")
        rc, stdout = self.run_cli()
        self.assertEqual(rc, 0, stdout)
        self.assertIn("as_of preflight on the candidate: PASS", stdout)
        self.assertIn("through the proxy, no as_of in the URL → day 15", stdout)
        self.assertEqual(self.stages.read_text().splitlines()[2], "day15\t2027-02-22\t15")
        # The proxy's stage file is put back as it was.
        self.assertEqual(self.stage.read_text(encoding="utf-8"), "2027-01-09 b_before\n")

    def test_switch_off_is_a_failure(self):
        _Candidate.enabled = False
        rc, stdout = self.run_cli()
        self.assertEqual(rc, 1)
        self.assertIn("PROGRAMS_AS_OF_ENABLED is off on the candidate", stdout)
        self.assertIn("::error title=Ramadan rehearsal preflight::", stdout)

    def test_a_wrong_day_is_a_failure(self):
        _Candidate.shift_days = 1
        rc, stdout = self.run_cli()
        self.assertEqual(rc, 1)
        self.assertIn("day15 (2027-02-22): date '2027-02-23'", stdout)


class AsOfReportTest(unittest.TestCase):
    def row(self, label, as_of, status, path="/api/programs"):
        return f"1.0\t{label}\tGET\t{path}\t{as_of}\t{status}"

    def test_every_expected_stage_needs_an_answered_call(self):
        rows = [self.row("ar_day1", "2027-02-08", 200), self.row("ar_day1", "-", 200, "/api/app-config")]
        fails, table = t.as_of_report(rows, ["ar_day1", "ar_day15"])
        self.assertEqual(fails, ["ar_day15: no programs call carried the stage's as_of — the stage proved nothing"])
        self.assertIn("| ar_day1 | 1 | 2xx×1 |", table)

    def test_a_refusal_or_a_crash_fails(self):
        rows = [self.row("ar_day1", "2027-02-08", 200), self.row("ar_day1", "2027-02-08", 403),
                self.row("b_eid", "2027-03-10", 500)]
        fails, _ = t.as_of_report(rows, ["ar_day1"])
        self.assertEqual(len(fails), 2)
        self.assertIn("refused (403)", fails[0])
        self.assertIn("answered 500", fails[1])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            log, expect = Path(d) / "p.tsv", Path(d) / "e.txt"
            log.write_text(self.row("en_eid", "2027-03-10", 200) + "\n", encoding="utf-8")
            expect.write_text("en_eid\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(t.main(["as-of-report", "--log", str(log), "--expect", str(expect)]), 0)
                expect.write_text("en_eid\nen_after\n", encoding="utf-8")
                self.assertEqual(t.main(["as-of-report", "--log", str(log), "--expect", str(expect)]), 1)
            self.assertIn("::error title=Ramadan rehearsal as_of::en_after", out.getvalue())


def audio_dump(players=(), focus_stack=(), focus_log=(), events=(), at="12:00:00:000"):
    """A `dumpsys audio` excerpt in the shape Android 15 prints. Log lines
    are stamped `at`; an event may be (piid, its own time)."""
    out = ["MediaFocusControl dump time: 12:00:00:000", "",
           "Audio Focus stack entries (last is top of stack):"]
    for uid, usage, loss in focus_stack:
        out.append(f"  source:android.os.BinderProxy@1 -- pack: {PKG} -- client: android.media.AudioManager@2 "
                   f"-- gain: GAIN -- flags:  -- loss: {loss} -- notified: true -- limbo false -- uid: {uid} "
                   f"-- attr: AudioAttributes: usage={usage} content=CONTENT_TYPE_MUSIC flags=0x800 tags= "
                   f"bundle=null -- sdk:35")
    out += ["", "  focus commands as seen by MediaFocusControl:"]
    for uid, usage in focus_log:
        out.append(f"  10-15 {at} requestAudioFocus() from uid/pid {uid}/4321 AA={usage}/CONTENT_TYPE_SONIFICATION "
                   f"clientId=android.media.AudioManager@3 callingPack={PKG} req=1 flags=0x0 sdk=35")
    out += ["", "PlaybackActivityMonitor dump time: 12:00:00:000", "", "  players:"]
    for piid, typ, uid, state, usage in players:
        out.append(f"  AudioPlaybackConfiguration piid:{piid} deviceIds:[2] type:{typ} u/pid:{uid}/4321 "
                   f"state:{state} attr:AudioAttributes: usage={usage} content=CONTENT_TYPE_MUSIC flags=0x800 "
                   f"tags= bundle=null session:17 mutedState:none")
    out += ["", "  playback activity as reported through PlayerBase:"]
    for event in events:
        piid, when = event if isinstance(event, tuple) else (event, at)
        out.append(f"  10-15 {when} player piid:{piid} event:started DeviceId:2")
    return "\n".join(out) + "\n"


UID = "10190"
RECITING = (31, "android.media.AudioTrack", UID, "started", "USAGE_MEDIA")
TICKS_IDLE = (23, "android.media.SoundPool", UID, "idle", "USAGE_ASSISTANCE_SONIFICATION")
TICKS_ON = (23, "android.media.SoundPool", UID, "started", "USAGE_ASSISTANCE_SONIFICATION")


LATER = "12:00:05:000"


def after_dump(**kw):
    return audio_dump(at=LATER, **kw)


class AudioVerdictTest(unittest.TestCase):
    def before(self, **kw):
        return audio_dump(players=kw.get("players", (RECITING, TICKS_IDLE)),
                          focus_stack=kw.get("focus_stack", ()), events=kw.get("events", ()))

    def test_recitation_survives_three_ticks(self):
        after = after_dump(players=(RECITING, TICKS_ON), events=(23, 23, 23))
        verdict, notes = t.audio_verdict(self.before(), [after], UID)
        self.assertEqual(verdict, "PASS", notes)
        self.assertIn("ticks seen by the audio service: 3 new start(s)", notes)

    def test_one_sample_between_two_ayat_is_not_a_stop(self):
        gap = after_dump(players=(TICKS_ON,), events=(23,))
        playing = after_dump(players=((32, "android.media.AudioTrack", UID, "started", "USAGE_MEDIA"), TICKS_ON),
                             events=(23, 23))
        self.assertEqual(t.audio_verdict(self.before(), [gap, playing], UID)[0], "PASS")

    def test_a_paused_recitation_fails(self):
        paused = (31, "android.media.AudioTrack", UID, "paused", "USAGE_MEDIA")
        after = after_dump(players=(paused, TICKS_ON), events=(23,))
        verdict, notes = t.audio_verdict(self.before(), [after, after], UID)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("the recitation stopped", notes[0])

    def test_a_tick_that_asks_for_focus_fails_even_if_nothing_paused(self):
        after = after_dump(players=(RECITING, TICKS_ON), events=(23,),
                           focus_log=((UID, "USAGE_ASSISTANCE_SONIFICATION"),))
        verdict, notes = t.audio_verdict(self.before(), [after], UID)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("a tick asked for audio focus", notes[0])

    def test_the_recitation_losing_its_focus_fails(self):
        before = self.before(focus_stack=((UID, "USAGE_MEDIA", "none"),))
        after = after_dump(players=(RECITING, TICKS_ON), events=(23,),
                           focus_stack=((UID, "USAGE_MEDIA", "LOSS_TRANSIENT"),))
        verdict, notes = t.audio_verdict(before, [after], UID)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("LOSS_TRANSIENT", notes[0])

    def test_nothing_reciting_is_inconclusive_not_pass(self):
        before = self.before(players=(TICKS_IDLE,))
        after = after_dump(players=(TICKS_ON,), events=(23,))
        self.assertEqual(t.audio_verdict(before, [after], UID)[0], "INCONCLUSIVE")

    def test_no_tick_heard_is_inconclusive_not_pass(self):
        after = after_dump(players=(RECITING, TICKS_IDLE))
        verdict, notes = t.audio_verdict(self.before(), [after], UID)
        self.assertEqual(verdict, "INCONCLUSIVE")
        self.assertIn("the probe did not sound", notes[0])

    def test_old_starts_leaving_the_ring_buffer_are_not_ticks(self):
        # Run 38722537691: between the two dumps the buffer dropped older
        # starts of the same uid (39 → 37) while two new ticks went in.
        before = self.before(events=((23, "11:59:00:000"), (23, "11:59:30:000"), (23, "12:00:00:000")))
        same_old = after_dump(players=(RECITING, TICKS_IDLE), events=((23, "12:00:00:000"),))
        self.assertEqual(t.audio_verdict(before, [same_old], UID)[0], "INCONCLUSIVE")
        two_new = after_dump(players=(RECITING, TICKS_IDLE),
                             events=((23, "12:00:00:000"), (23, "12:00:03:000"), (23, "12:00:04:000")))
        verdict, notes = t.audio_verdict(before, [two_new], UID)
        self.assertEqual(verdict, "PASS", notes)
        self.assertIn("ticks seen by the audio service: 2 new start(s)", notes)

    def test_the_real_dumps_of_run_38722537691(self):
        """Copied verbatim from that run's e2e-rehearsal artifact: two ticks
        (11:39:42, 11:39:44) over Al-Fatiha, recitation playing throughout,
        holding GAIN with no loss, and no tick asked for focus."""
        data = Path(__file__).resolve().parent / "testdata"
        before = (data / "dumpsys_audio_run38722537691_before.txt").read_text(encoding="utf-8")
        after = (data / "dumpsys_audio_run38722537691_after.txt").read_text(encoding="utf-8")
        verdict, notes = t.audio_verdict(before, [after], "10209")
        self.assertEqual(verdict, "PASS", notes)
        self.assertIn("ticks seen by the audio service: 2 new start(s)", notes)
        self.assertIn("the recitation holds audio focus (usage USAGE_MEDIA)", notes)
        # The same dumps, read as if the ticks had paused it, must fail.
        paused = after.replace("u/pid:10209/17741 state:started attr:AudioAttributes: usage=USAGE_MEDIA",
                               "u/pid:10209/17741 state:paused attr:AudioAttributes: usage=USAGE_MEDIA")
        self.assertEqual(t.audio_verdict(before, [paused], "10209")[0], "FAIL")
        lost = after.replace("-- loss: none -- notified: true -- limbofalse -- uid: 10209",
                             "-- loss: LOSS_TRANSIENT -- notified: true -- limbofalse -- uid: 10209")
        self.assertEqual(t.audio_verdict(before, [lost], "10209")[0], "FAIL")

    def test_other_apps_are_not_the_app(self):
        other = (40, "android.media.AudioTrack", "10055", "started", "USAGE_MEDIA")
        before = self.before(players=(other, TICKS_IDLE))
        after = after_dump(players=(other, TICKS_ON), events=(23,),
                           focus_log=(("10055", "USAGE_ASSISTANCE_SONIFICATION"),))
        self.assertEqual(t.audio_verdict(before, [after], UID)[0], "INCONCLUSIVE")

    def test_cli_exit_codes_and_checkpoint_line(self):
        with tempfile.TemporaryDirectory() as d:
            b, a, o = Path(d) / "b.txt", Path(d) / "a.txt", Path(d) / "v.md"
            b.write_text(self.before(), encoding="utf-8")
            cases = ((after_dump(players=(RECITING, TICKS_ON), events=(23,)), 0, "PASS"),
                     (after_dump(players=(TICKS_ON,), events=(23,)), 1, "FAIL"),
                     (after_dump(players=(RECITING, TICKS_IDLE)), 2, "INCONCLUSIVE"))
            for text, code, word in cases:
                with self.subTest(word):
                    a.write_text(text, encoding="utf-8")
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        rc = t.main(["audio-focus", "--uid", UID, "--before", str(b), "--after", str(a),
                                     "--out", str(o)])
                    self.assertEqual(rc, code)
                    self.assertIn(f"SOUND×RECITATION CHECKPOINT: {word}", out.getvalue())
                    self.assertIn(f"SOUND×RECITATION CHECKPOINT: {word}", o.read_text(encoding="utf-8"))


class RehearsalGalleryTest(unittest.TestCase):
    def shots(self, drop=()):
        names = []
        for tag, variant, _ in t.REHEARSAL_COLUMNS:
            for stage, _title, rows in t.REHEARSAL_STAGES:
                for screen, _c in rows:
                    names.append(f"rehearsal__x_{stage}__{tag}__{variant}__{screen}.png")
        return [n for n in names if n not in drop]

    def run_gallery(self, names, *extra):
        with tempfile.TemporaryDirectory() as d:
            screens = Path(d) / "screens"
            screens.mkdir()
            for n in names:
                (screens / n).write_bytes(b"\x89PNG")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = t.main(["rehearsal-gallery", str(screens), "--out", str(Path(d) / "g"), *extra])
            md = (Path(d) / "g" / "gallery-summary.md").read_text(encoding="utf-8")
            return rc, out.getvalue(), md

    def test_complete(self):
        rc, stdout, md = self.run_gallery(self.shots(), "--require-after")
        self.assertEqual(rc, 0, stdout)
        self.assertIn("blind-after=0", md)
        self.assertIn("### العيد", md)

    def test_a_missing_head_shot_fails_but_a_missing_play_shot_does_not(self):
        rc, stdout, _ = self.run_gallery(
            self.shots(drop=("rehearsal__x_eid__after__en__eid_recap.png",
                             "rehearsal__x_day1__before__ar__day1_street.png")), "--require-after")
        self.assertEqual(rc, 1)
        self.assertIn("en:eid_recap", stdout)
        self.assertNotIn("day1_street", stdout)

    def test_noor_once_only_line_is_guarded(self):
        drop = tuple(f"rehearsal__x_before__after__{v}__before_today_noor.png" for v in ("ar", "en", "ar_dark"))
        self.assertEqual(self.run_gallery(self.shots(drop=drop), "--require-after")[0], 0)

    def test_maestro_suffix_and_prefix_screens_do_not_collide(self):
        names = ["rehearsal__ar_before__after__ar__before_today_2.png",
                 "rehearsal__ar_before__after__ar__before_today_noor.png"]
        with tempfile.TemporaryDirectory() as d:
            for n in names:
                (Path(d) / n).write_bytes(b"x")
            index = t.index_rehearsal(Path(d))
        self.assertEqual(index[("after", "ar", "before_today")], names[0])
        self.assertEqual(index[("after", "ar", "before_today_noor")], names[1])

    def test_every_gallery_screen_is_a_shot_the_flow_takes(self):
        flow = (Path(__file__).resolve().parent / "flows/rehearsal/stage.yaml").read_text(encoding="utf-8")
        templates = re.findall(r"takeScreenshot: '\$\{TAG\}__\$\{VARIANT\}__([^']+)'", flow)
        self.assertGreater(len(templates), 8)
        for stage, _title, rows in t.REHEARSAL_STAGES:
            producible = {tpl.replace("${STAGE}", stage) for tpl in templates}
            for screen, _c in rows:
                with self.subTest(screen):
                    self.assertIn(screen, producible)


if __name__ == "__main__":
    unittest.main()
