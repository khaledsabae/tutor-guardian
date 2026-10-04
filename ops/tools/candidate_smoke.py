#!/usr/bin/env python3
"""Fast smoke of a candidate backend image — the in-image gate of every deploy.

The full suite does not run in the image. It runs on GitHub-hosted runners
("Backend tests", pytest + KB integrity + ruff) and deploy.yml will not build
until those passed for the exact commit being deployed. Inside the image the
question is narrower: *is this image sound?* — answered in about 20 CPU-seconds,
on a GitHub-hosted runner, before the image is published; the production host
only pulls what passed. (The full suite in the image, on the production host,
cost 16-28 minutes per deploy on 2026-10-04.)

Run inside the candidate image (ops/tools/candidate_smoke.sh does that):
  1. imports    — app.main imports every router, so a missing module or a bad
                  pin fails here;
  2. models     — both baked Hugging Face models load OFFLINE from HF_HOME and
                  produce output (an HF format drift broke loading once);
  3. database   — init_db() builds the schema on a fresh DB, twice (idempotent),
                  and stamps SCHEMA_VERSION; integrity_check passes;
  4. index      — the knowledge index baked into the image was built for exactly
                  these units (same fingerprint the container computes at startup);
  5. server     — uvicorn starts the real app as the image's CMD would, warm-up
                  included, over an index dir holding an OLD index (as the
                  production volume does): it must install the baked index, not
                  re-embed; /health and /api/app-config answer 200; SIGTERM exits
                  cleanly; time to healthy is printed;
  6. retrieval  — a query against the installed index returns units;
  7. tests      — a small pytest subset: schema migrations, the deploy-image
                  skip markers, and the assistant's guard ordering through the API.
Exits non-zero at the first failure, with the reason. Prints CPU time used.
"""
from __future__ import annotations

import json
import os
import resource
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_ROOT = Path(os.environ.get("PROJECT_ROOT", "/app"))

# Small on purpose. Each entry earns its place:
PYTEST_SUBSET = [
    # schema migrations / ensure steps on a temp DB (an old lesson_progress
    # table upgraded in place)
    "backend/tests/test_lesson_progress_migration.py",
    # the assistant's guard: fiqh precision, and emergency escalation winning
    # over the fiqh deflection through /api/assistant/draft and /stream
    "backend/tests/test_fiqh_guard_precision.py",
    # the deploy-image skip markers: these modules need repo files the image
    # does not ship (mobile/, .env.example, scripts/) and must skip cleanly here
    # rather than fail — the reason the in-image full suite went red on
    # 2026-10-04 (PR #30)
    "backend/tests/test_program_banks.py",
    "backend/tests/test_donations.py",
    "backend/tests/test_podcast_sentinels.py",
    "backend/tests/test_min_build_script.py",
]

# One thread: the container is CPU-capped, and torch would otherwise start a
# thread per host core and fight the cap. Offline: the models must come from
# the image itself (and the container runs with --network none anyway). Set in
# main(), before anything imports huggingface_hub, which reads them at import
# time — and not at module level, so importing this file has no side effects.
SMOKE_ENV = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "TOKENIZERS_PARALLELISM": "false",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "SKIP_API_SMOKE": "1",
}


class SmokeFailure(Exception):
    pass


def _step(name: str):
    def wrap(fn):
        def run(*args, **kwargs):
            t = time.monotonic()
            print(f"── {name}", flush=True)
            try:
                result = fn(*args, **kwargs)
            except SmokeFailure as exc:
                raise SmokeFailure(f"{name}: {exc}") from None
            except Exception as exc:  # noqa: BLE001 — every failure fails the smoke
                raise SmokeFailure(f"{name}: {type(exc).__name__}: {exc}") from exc
            print(f"   ok ({time.monotonic() - t:.1f}s)", flush=True)
            return result
        return run
    return wrap


@_step("imports: app.main and every router")
def check_imports() -> None:
    import app.main  # noqa: F401 — the import is the check


@_step("models: both baked models load offline and run")
def check_models() -> None:
    from sentence_transformers import CrossEncoder, SentenceTransformer

    from app.services.reranker import RERANKER_MODEL
    from app.services.retrieval import EMBEDDING_MODEL

    vec = SentenceTransformer(EMBEDDING_MODEL).encode(
        ["query: كيف أعلّم ابني الصلاة؟"], normalize_embeddings=True)
    if vec.shape[0] != 1 or vec.shape[1] < 64:
        raise SmokeFailure(f"embedder returned shape {vec.shape}")
    score = CrossEncoder(RERANKER_MODEL, max_length=256).predict(
        [("كيف أعلّم ابني الصلاة؟", "تعليم الطفل الصلاة بالتدريج والقدوة")])
    if len(score) != 1:
        raise SmokeFailure(f"reranker returned {score!r}")
    print(f"   {EMBEDDING_MODEL} dim={vec.shape[1]} · {RERANKER_MODEL} score={float(score[0]):.2f}")


@_step("database: init_db on a fresh DB, twice")
def check_database(db: Path) -> None:
    from app.db.init_db import SCHEMA_VERSION, init_db

    init_db()
    init_db()  # idempotent: a restart runs it against an existing DB
    conn = sqlite3.connect(db)
    try:
        version = conn.execute("SELECT version FROM schema_version").fetchall()
        tables = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    if version != [(SCHEMA_VERSION,)]:
        raise SmokeFailure(f"schema_version rows {version}, expected [({SCHEMA_VERSION},)]")
    if integrity != "ok":
        raise SmokeFailure(f"integrity_check: {integrity}")
    print(f"   schema v{SCHEMA_VERSION}, {tables} tables, integrity ok")


@_step("index: the baked knowledge index matches the units")
def check_index() -> None:
    from app.services import retrieval
    from app.services.knowledge_loader import load_default_knowledge_units

    units = load_default_knowledge_units()
    fingerprint = retrieval._fingerprint(units)
    baked = retrieval._read_fingerprint(retrieval.SEED_DIR)
    if baked != fingerprint:
        raise SmokeFailure(f"the image's baked index ({retrieval.SEED_DIR}) is for {baked}, the "
                           f"units are {fingerprint[:12]}… — every start would re-embed")
    size = sum(f.stat().st_size for f in retrieval.SEED_DIR.rglob("*") if f.is_file())
    print(f"   {len(units)} units · baked fingerprint {fingerprint[:12]}… matches · "
          f"{size / 1e6:.0f} MB")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str) -> tuple[int, dict]:
    """(status, JSON body). An HTTP error status is an answer, not a retry."""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {"body": exc.read()[:500].decode("utf-8", "replace")}


@_step("server: a real startup installs the baked index; /health, /api/app-config")
def check_server(env: dict) -> None:
    from app.services import retrieval

    # What the production volume holds after the last deploy: an index for
    # OTHER units. Startup must replace it with the baked one, not re-embed.
    persist = retrieval.CHROMA_PERSIST_DIR
    persist.mkdir(parents=True, exist_ok=True)
    (persist / "_content_fingerprint").write_text("an-index-for-older-units")
    port = _free_port()
    log = tempfile.TemporaryFile(mode="w+")
    # The image's own CMD, on loopback, with the full warm-up (both models and
    # the index) — exactly what the production container does before it
    # answers its first health check.
    t0 = time.monotonic()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "backend",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=APP_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 300
        health = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise SmokeFailure(f"uvicorn exited with {proc.returncode} before answering")
            try:
                health = _get(f"{base}/health")
                break
            except OSError:  # not listening yet
                time.sleep(0.5)
        if health is None:
            raise SmokeFailure("no answer from /health within 300 s")
        startup = time.monotonic() - t0
        status, body = health
        checks = body.get("checks", {})
        if status != 200 or body.get("status") != "ok" or checks.get("sqlite") != "ok" \
                or checks.get("chromadb") != "ok":
            raise SmokeFailure(f"/health answered {status} {body}")
        log.seek(0)
        boot = log.read()
        if "Installed the knowledge index baked into the image" not in boot:
            raise SmokeFailure("startup did not install the baked index")
        if "Re-embedding all" in boot:
            raise SmokeFailure("startup re-embedded the knowledge base")
        if retrieval._read_fingerprint(persist) != retrieval._read_fingerprint(retrieval.SEED_DIR):
            raise SmokeFailure("the index dir does not hold the baked index after startup")
        print(f"   startup (warm-up: both models + baked index) → healthy in {startup:.1f}s, "
              f"no re-embedding")
        status, cfg = _get(f"{base}/api/app-config")
        if status != 200 or not isinstance(cfg.get("minimum_build_number"), int):
            raise SmokeFailure(f"/api/app-config answered {status} {cfg}")
        print(f"   /health {body['checks']} · /api/app-config minimum_build_number="
              f"{cfg['minimum_build_number']}")
        proc.send_signal(signal.SIGTERM)
        try:
            code = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            raise SmokeFailure("uvicorn did not stop within 30 s of SIGTERM") from None
        # uvicorn re-raises the signal it caught once it has shut down, so a
        # clean stop exits -15; the lifespan's own line is the real evidence.
        log.seek(0)
        if code not in (0, -signal.SIGTERM) or "Application shutdown complete" not in log.read():
            raise SmokeFailure(f"uvicorn did not shut down cleanly (exit {code})")
    except SmokeFailure:
        log.seek(0)
        tail = log.read()[-3000:]
        print(f"   ── server log (tail) ──\n{tail}", flush=True)
        raise
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


@_step("retrieval: a query against the installed index returns units")
def check_retrieval() -> None:
    from app.services import retrieval

    retrieval._ensure_index()  # current now: must neither copy nor embed again
    hits = retrieval.with_live_collection(lambda c: c.query(
        query_embeddings=[retrieval.embed_query("كيف أعلّم ابني الصلاة؟")],
        n_results=3, include=["metadatas"]))
    ids = hits["ids"][0]
    if len(ids) != 3:
        raise SmokeFailure(f"query returned {ids}")
    print(f"   top hits: {', '.join(ids)}")


@_step("tests: migrations, deploy-image skip markers, assistant guard")
def check_tests(env: dict) -> None:
    missing = [p for p in PYTEST_SUBSET if not (APP_ROOT / p).exists()]
    if missing:
        raise SmokeFailure(f"smoke test files missing from the image: {missing}")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs",
         *PYTEST_SUBSET],
        cwd=APP_ROOT, env=env)
    if result.returncode != 0:
        raise SmokeFailure(f"pytest subset exited {result.returncode}")


def main() -> int:
    started = time.monotonic()
    for key, value in SMOKE_ENV.items():
        os.environ.setdefault(key, value)
    work = Path(tempfile.mkdtemp(prefix="candidate-smoke-"))
    db = work / "smoke.db"
    # Everything the app needs to boot, and nothing from production: no .env,
    # no secrets, no volumes. A throwaway DB and a throwaway child-mode secret.
    os.environ["CONVERSATIONS_DB"] = str(db)
    os.environ.setdefault("CHILD_MODE_SECRET", secrets.token_hex(16))
    env = dict(os.environ)
    try:
        check_imports()
        check_models()
        check_database(db)
        check_index()
        check_server(env)
        check_retrieval()
        check_tests(env)
    except SmokeFailure as exc:
        print(f"\n❌ candidate smoke FAILED — {exc}", flush=True)
        return 1
    finally:
        own = resource.getrusage(resource.RUSAGE_SELF)
        kids = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = own.ru_utime + own.ru_stime + kids.ru_utime + kids.ru_stime
        peak_mb = max(own.ru_maxrss, kids.ru_maxrss) / 1024
        print(f"smoke: {time.monotonic() - started:.0f}s wall, {cpu:.0f}s CPU "
              f"(user+sys, incl. children), peak RSS {peak_mb:.0f} MB", flush=True)
    print("✅ candidate smoke passed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
