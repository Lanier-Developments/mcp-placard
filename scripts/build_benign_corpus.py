"""Materialise the benign injection corpus from the real-server fixtures.

``tests/fixtures/injection/benign/<server>.json`` is every model-facing string the
Phase 3 surface enumerator finds in ``tests/fixtures/real_servers/<server>.json`` —
tool descriptions and titles, schema property descriptions, server instructions,
prompt and resource descriptions. All of it is real, none of it is an attack, and
the heuristics must produce zero findings on it (``tests/test_inject_corpus.py``).

Materialised rather than derived at test time so the corpus is reviewable as data
and so a change to the enumerator that silently dropped strings would show up as a
diff here. The test asserts the files match a fresh enumeration.

Usage: ``python scripts/build_benign_corpus.py`` — rewrites the files in place.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from mcp_placard.inject import enumerate_text  # noqa: E402
from mcp_placard.manifest import build_manifest  # noqa: E402
from mcp_placard.manifest.raw import RawSurface  # noqa: E402

REAL = ROOT / "tests" / "fixtures" / "real_servers"
BENIGN = ROOT / "tests" / "fixtures" / "injection" / "benign"


def manifest_for(fixture: dict) -> object:
    raw = RawSurface(
        server_info=fixture.get("source") or {"name": fixture["server"], "version": "0"},
        capabilities={"tools": {"listChanged": False}},
        environment={},
        instructions=fixture.get("instructions"),
        tools=fixture["tools"],
        resources=fixture.get("resources") or [],
        resource_templates=fixture.get("resource_templates") or [],
        prompts=fixture.get("prompts") or [],
    )
    return build_manifest(raw)


def corpus_for(fixture: dict, server: str) -> dict:
    manifest = manifest_for(fixture)
    return {
        "server": server,
        "captured": fixture.get("surface_captured") or fixture.get("captured"),
        "elements": [
            {"element": e.element, "pointer": e.pointer, "text": e.text}
            for e in enumerate_text(manifest)  # type: ignore[arg-type]
        ],
    }


def main() -> int:
    BENIGN.mkdir(parents=True, exist_ok=True)
    total = 0
    for path in sorted(REAL.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        corpus = corpus_for(fixture, path.stem)
        out = BENIGN / path.name
        out.write_text(
            json.dumps(corpus, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        total += len(corpus["elements"])
        print(f"{out.relative_to(ROOT)}: {len(corpus['elements'])} elements")
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
