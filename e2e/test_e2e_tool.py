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
        self.assertIn("needs: keystore", build)
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


if __name__ == "__main__":
    unittest.main()
