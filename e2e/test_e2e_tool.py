"""Tests for e2e/e2e_tool.py — run: python3 -m unittest discover -s e2e -v"""
import json
import re
import tempfile
import unittest
from pathlib import Path

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

    def test_gate_refuses_an_empty_capture(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "logcat.txt"
            path.write_text("\n".join(lc(1, "I", "x", "y") for _ in range(10)), encoding="utf-8")
            rc = t.main(["logcat-gate", str(path), "--min-lines", "200", "--out", str(Path(d) / "g.txt")])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
