#!/usr/bin/env python3
"""Regenerate tests/fixtures/mock_server_manifest.json from a fresh scan.

Use this after a deliberate change (for example bumping the pinned ``mcp``
version) instead of hand-editing the fixture:

    python scripts/regen_fixture.py            # show what would change; write nothing
    python scripts/regen_fixture.py --write    # rewrite the fixture
    python scripts/regen_fixture.py --check    # exit 1 if the fixture is stale (CI)

Read the diff before using --write. Regenerating the fixture just to turn a
red build green is adversary A5 in docs/THREAT_MODEL.md; the dry run exists so
a human or agent has to look at what changed first.

The scan below is the same pipeline tests/test_self_gating.py uses:
``analyze(build_manifest(scan_target(<mock server>)))`` rendered with
``render_manifest``.
"""

from __future__ import annotations

import argparse
import difflib
import os
import shlex
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "mock_server_manifest.json"


def fresh_scan_text() -> str:
    """Render a fresh scan of the mock server exactly as the self-gating test does."""
    # The mock server is launched as ``python -m tests.mock_server``, which must
    # resolve from the repo root (tests/conftest.py pins the same cwd).
    os.chdir(REPO_ROOT)
    sys.path.insert(0, str(REPO_ROOT))

    from mcp_placard.analysis import analyze
    from mcp_placard.manifest import build_manifest, render_manifest
    from mcp_placard.transport import scan_target

    target = " ".join([shlex.quote(sys.executable), "-m", "tests.mock_server"])
    # Keep the launched server's package cache out of the real home, as conftest does.
    with tempfile.TemporaryDirectory(prefix="placard-cache-") as cache:
        os.environ["PLACARD_CACHE_DIR"] = cache
        return render_manifest(analyze(build_manifest(scan_target(target, timeout=60))))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="rewrite the fixture")
    mode.add_argument(
        "--check", action="store_true", help="exit 1 if the fixture is stale; write nothing"
    )
    args = parser.parse_args()

    fresh = fresh_scan_text()
    current = FIXTURE.read_text(encoding="utf-8") if FIXTURE.exists() else ""

    if fresh == current:
        print("fixture is up to date")
        return 0

    diff = "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            fresh.splitlines(keepends=True),
            fromfile=f"a/{FIXTURE.relative_to(REPO_ROOT)}",
            tofile="fresh scan",
        )
    )
    print(diff)

    if args.check:
        print("fixture is stale. Review the diff above; if it is intended, run with --write.")
        return 1

    if not args.write:
        print("dry run: nothing written. Re-run with --write once you agree with the diff.")
        return 0

    FIXTURE.write_text(fresh, encoding="utf-8")
    print(f"rewrote {FIXTURE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
