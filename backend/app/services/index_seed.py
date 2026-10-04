"""Bake the knowledge index into the backend image (run by backend/Dockerfile).

Production cannot afford to embed the knowledge base at startup: on a
CPU-throttled host (2026-10-04, ~95% steal) re-embedding every unit outran the
deploy's 420 s health window, which rolls a release back — and the container
serves nothing while it embeds. So the image build, on a GitHub-hosted runner,
does it once:

  python -m app.services.index_seed

runs the container's own startup call — retrieval._ensure_index(), same units,
same embedding model (already baked into the image, loaded offline), same
fingerprint — into retrieval.CHROMA_PERSIST_DIR, and checks the result. The
Dockerfile then moves that directory to retrieval.SEED_DIR, which the
production volume does not cover; at startup, _install_seed_if_current()
copies it into the volume whenever the volume's index is for other units.
"""
from __future__ import annotations

import sys
import time

from app.services import retrieval
from app.services.knowledge_loader import load_default_knowledge_units


def main() -> int:
    target = retrieval.CHROMA_PERSIST_DIR
    if target.exists() and any(target.iterdir()):
        print(f"refusing to bake into a non-empty {target}", file=sys.stderr)
        return 1
    started = time.monotonic()
    retrieval._ensure_index()
    units = load_default_knowledge_units()
    fingerprint = retrieval._fingerprint(units)
    on_disk = retrieval._read_fingerprint(target)
    count = retrieval.with_live_collection(lambda c: c.count())
    if on_disk != fingerprint or count != len(units):
        print(f"baked index is wrong: fingerprint {on_disk} vs {fingerprint}, "
              f"{count} vectors for {len(units)} units", file=sys.stderr)
        return 1
    print(f"baked knowledge index: {count} units, fingerprint {fingerprint[:12]}…, "
          f"{time.monotonic() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
