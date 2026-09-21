"""Score the held-out malicious set, once, at the end of the phase.

Phase 3 brief §5: the synthetic samples and the heuristics share an author, so
recall on the synthetic set is close to meaningless. A held-out set authored
independently against the pattern-class table is scored once and the number is
reported as-is, whatever it is.

Reads every ``*.json`` in ``tests/fixtures/injection/heldout/`` in the same encoded
format as ``../malicious/synthetic.json`` and prints, per class and overall, how
many samples produced a finding of the expected class on the expected element.
Never imported by the test suite; never run in CI.

Usage: ``python scripts/score_heldout.py``
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mcp_placard.inject import analyze_manifest  # noqa: E402
from mcp_placard.inject.corpus import sample_manifest  # noqa: E402

HELDOUT = ROOT / "tests" / "fixtures" / "injection" / "heldout"


def main() -> int:
    files = sorted(p for p in HELDOUT.glob("*.json"))
    if not files:
        print("no held-out files found; nothing to score")
        return 0
    per_class: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    misses: list[str] = []
    for path in files:
        document = json.loads(path.read_text(encoding="utf-8"))
        for sample in document.get("samples", []):
            manifest, element = sample_manifest(sample)
            found = {f.pattern_class for f in analyze_manifest(manifest) if f.element == element}
            expected = set(sample.get("expected_classes") or [sample["class"]])
            hit = bool(found & expected)
            counts = per_class[sample["class"]]
            counts[1] += 1
            counts[0] += int(hit)
            if not hit:
                misses.append(
                    f"{path.name}:{sample['id']} expected {sorted(expected)} got {sorted(found)}"
                )
    total_hit = sum(v[0] for v in per_class.values())
    total = sum(v[1] for v in per_class.values())
    print("held-out detection, reported as-is:")
    for cls, (hit, n) in sorted(per_class.items()):
        print(f"  {cls:18} {hit}/{n}")
    print(f"  {'overall':18} {total_hit}/{total}")
    if misses:
        print("misses:")
        for line in misses:
            print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
