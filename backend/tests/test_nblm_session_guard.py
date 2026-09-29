"""scripts/lib/nblm_session.sh — the NotebookLM session guard.

Drives the real bash library against a stub `notebooklm` placed first on PATH
and a throwaway HOME, so the real profiles in ~/.notebooklm are never touched.

The stub mimics the two behaviours that matter from notebooklm-py 0.8.0:
  · `-p P source list … --json` prints {"sources": …} only when
    $HOME/.notebooklm/profiles/P/storage_state.json holds a VALID session
  · `-p P login --browser-cookies chrome` WRITES that file whatever Chrome
    holds ("Saved anyway") — the behaviour that clobbered the live session
"""
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "lib" / "nblm_session.sh"

STUB = r"""#!/usr/bin/env bash
echo "$*" >> "$STUB_CALLS"
profile=""
if [ "$1" = "-p" ]; then profile="$2"; shift 2; fi
f="$HOME/.notebooklm/profiles/$profile/storage_state.json"
case "$1" in
  source)
    if [ -f "$f" ] && grep -q VALID "$f"; then echo '{"sources": []}'; exit 0; fi
    echo "Error: Authentication expired" >&2; exit 1 ;;
  login)
    mkdir -p "$(dirname "$f")"
    printf '%s' "$STUB_CHROME" > "$f"
    echo "Saved anyway, but you may need to re-run login if these are invalid."
    exit 0 ;;
esac
exit 2
"""


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "home"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "notebooklm"
    stub.write_text(STUB)
    stub.chmod(0o755)
    e = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HOME": str(home),
        "NBLM_BIN": "notebooklm",
        "NBLM_SLEEP_SCALE": "0",
        "NOTEBOOK_MAIN": "nb-test",
        "LOG": str(tmp_path / "run.log"),
        "STUB_CALLS": str(tmp_path / "calls.log"),
        "STUB_CHROME": "DEAD-chrome",
    }
    return {"env": e, "home": home, "tmp": tmp_path}


def _pdir(ctx, name="tg-video") -> Path:
    return ctx["home"] / ".notebooklm" / "profiles" / name


def _live(ctx, content: str | None = None, name="tg-video") -> Path:
    f = _pdir(ctx, name) / "storage_state.json"
    if content is not None:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    return f


def _run(ctx, script: str, **extra) -> subprocess.CompletedProcess:
    e = {**ctx["env"], **extra}
    return subprocess.run(
        ["bash", "-c", f'set -u; . "{LIB}"; {script}'],
        env=e, capture_output=True, text=True, timeout=60,
    )


def _calls(ctx) -> str:
    p = Path(ctx["env"]["STUB_CALLS"])
    return p.read_text() if p.exists() else ""


def _baks(ctx) -> list[str]:
    return sorted(p.name for p in _pdir(ctx).glob("storage_state.json.bak-*"))


def test_live_valid_no_extraction_and_lastgood_refreshed(env):
    live = _live(env, "VALID-live")
    r = _run(env, 'ensure_session tg-video; echo "RC=$?"')
    assert "RC=0" in r.stdout, r.stdout + r.stderr
    assert "login" not in _calls(env)
    assert live.read_text() == "VALID-live"
    assert (live.parent / "storage_state.json.lastgood").read_text() == "VALID-live"
    assert _baks(env) == []


def test_live_invalid_valid_candidate_replaces_atomically_with_backup(env):
    live = _live(env, "DEAD-live")
    r = _run(env, 'ensure_session tg-video; echo "RC=$?"', STUB_CHROME="VALID-chrome")
    assert "RC=0" in r.stdout, r.stdout + r.stderr
    # extraction went to the candidate profile, never to the live one
    assert "-p tg-video.candidate login --browser-cookies chrome" in _calls(env)
    assert "-p tg-video login" not in _calls(env)
    assert live.read_text() == "VALID-chrome"
    baks = _baks(env)
    assert len(baks) == 1
    assert (live.parent / baks[0]).read_text() == "DEAD-live"
    assert (live.parent / "storage_state.json.lastgood").read_text() == "VALID-chrome"
    assert not _pdir(env, "tg-video.candidate").exists()


def test_live_invalid_candidate_invalid_leaves_live_byte_identical(env):
    original = b'{"cookies": [1, 2, 3]} DEAD-live \xe2\x9c\x93'
    live = _live(env)
    live.parent.mkdir(parents=True)
    live.write_bytes(original)
    r = _run(env, 'ensure_session tg-video; echo "RC=$?"', STUB_CHROME="DEAD-chrome")
    assert "RC=1" in r.stdout, r.stdout + r.stderr
    assert live.read_bytes() == original
    assert not _pdir(env, "tg-video.candidate").exists()
    assert _baks(env) == []
    assert "INVALID" in Path(env["env"]["LOG"]).read_text()


def test_lastgood_rescues_when_live_and_chrome_are_dead(env):
    live = _live(env, "DEAD-live")
    (live.parent / "storage_state.json.lastgood").write_text("VALID-lastgood")
    r = _run(env, 'ensure_session tg-video; echo "RC=$?"', STUB_CHROME="DEAD-chrome")
    assert "RC=0" in r.stdout, r.stdout + r.stderr
    assert live.read_text() == "VALID-lastgood"
    assert [(live.parent / b).read_text() for b in _baks(env)] == ["DEAD-live"]
    assert not _pdir(env, "tg-video.candidate").exists()


def test_invalid_lastgood_does_not_touch_live(env):
    live = _live(env, "DEAD-live")
    (live.parent / "storage_state.json.lastgood").write_text("DEAD-lastgood")
    r = _run(env, 'ensure_session tg-video; echo "RC=$?"')
    assert "RC=1" in r.stdout, r.stdout + r.stderr
    assert live.read_text() == "DEAD-live"
    assert (live.parent / "storage_state.json.lastgood").read_text() == "DEAD-lastgood"
    assert _baks(env) == []
    assert not _pdir(env, "tg-video.candidate").exists()


def test_backup_rotation_keeps_five_newest_and_spares_manual_backup(env):
    live = _live(env, "DEAD-live")
    d = live.parent
    old = [f"storage_state.json.bak-2026092{i}T060000Z" for i in range(1, 7)]
    for name in old:
        (d / name).write_text("old")
    (d / "storage_state.json.bak-20260929").write_text("hand-made")
    r = _run(env, 'ensure_session tg-video; echo "RC=$?"', STUB_CHROME="VALID-chrome")
    assert "RC=0" in r.stdout, r.stdout + r.stderr
    auto = [b for b in _baks(env) if b != "storage_state.json.bak-20260929"]
    assert len(auto) == 5
    # the two oldest went; the new one (today, UTC) is kept
    assert old[0] not in auto and old[1] not in auto
    assert all(n in auto for n in old[2:])
    assert (d / "storage_state.json.bak-20260929").read_text() == "hand-made"


def test_session_validated_earlier_in_run_is_never_replaced(env):
    live = _live(env, "VALID-live")
    script = (
        'ensure_session tg-video; echo "RC1=$?"; '
        f'printf DEAD-later > "{live}"; '
        'ensure_session tg-video; echo "RC2=$?"'
    )
    r = _run(env, script, STUB_CHROME="VALID-chrome")
    assert "RC1=0" in r.stdout and "RC2=1" in r.stdout, r.stdout + r.stderr
    assert "login" not in _calls(env)
    assert live.read_text() == "DEAD-later"
    # lastgood still holds the session that was proven alive
    assert (live.parent / "storage_state.json.lastgood").read_text() == "VALID-live"


def test_cron_script_sources_the_library():
    text = (REPO / "scripts" / "cron_gen_en_media.sh").read_text()
    assert "scripts/lib/nblm_session.sh" in text
    assert "login --browser-cookies" not in text  # only the library may extract
    for f in (LIB, REPO / "scripts" / "cron_gen_en_media.sh"):
        r = subprocess.run(["bash", "-n", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
