"""Score the held-out malicious sets, once, at the end of a phase.

Phase 3 brief §5: the synthetic samples and the heuristics share an author, so recall
on the synthetic set is close to meaningless. A held-out set authored independently
against the pattern-class table is scored once and the number is reported as-is.

Reads every ``*.json`` in ``tests/fixtures/injection/heldout/`` and reports **each
provenance separately** — they measure different things and pooling them would average
a headline number with a coverage probe and a false-positive count.

- A sample with a non-empty ``expected_classes`` is a **detection** requirement: it
  passes when one of those classes fires on its element.
- A sample with an **empty** ``expected_classes`` is a **false-positive** check: it
  passes when *nothing at all* fires on its element, of any class. These are counted
  and printed separately and never enter a detection figure — a false positive must
  never be able to read as a detection.

Held-out v1's per-class numbers print alongside, because the pair across a rewritten
ruleset is the finding; a single number has nothing to be measured against.

**This script writes nothing.** It does not touch ``baseline.json``: the ratchet moves
by decision, in a commit that says so, not as a side effect of measuring.

Never imported by the test suite; never run in CI.

Usage: ``python scripts/score_heldout.py``
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mcp_placard import RULESET_VERSION  # noqa: E402
from mcp_placard.inject import analyze_manifest  # noqa: E402
from mcp_placard.inject.corpus import sample_manifest  # noqa: E402

HELDOUT = ROOT / "tests" / "fixtures" / "injection" / "heldout"

#: Held-out v1, scored once on ruleset 3.0 and reported as-is. Source:
#: ``docs/dispatches/2026-09-21_from-chief_to-jr_heldout-v1-findings.md``, and the
#: table in ``docs/INJECTION.md``. Five samples per class, 24 of 35 overall.
HELDOUT_V1 = {
    "exfil_sink": (5, 5),
    "hidden_content": (5, 5),
    "sensitive_target": (5, 5),
    "concealment": (3, 5),
    "cross_scope": (3, 5),
    "markup_smuggling": (3, 5),
    "override": (0, 5),
}
V1_RULESET = "3.0"

#: Only this provenance is comparable with v1. v1 sampled the tool-owned surfaces
#: exactly as ``heldout-v2`` does; it never covered prompt or resource elements, so
#: printing its numbers beside ``heldout-v2-surfaces`` would invite a regression
#: reading of what is a first-coverage number.
V1_COMPARABLE = "heldout-v2"

#: Report order, headline first. Anything not listed is reported after these, in
#: filename order.
PROVENANCE_ORDER = ("heldout-v2", "heldout-v2-surfaces", "heldout-v2-benign")


def _pct(hit: int, total: int) -> str:
    return f"{100 * hit // total:>3}%" if total else "  —"


def _score(sample: dict[str, Any]) -> tuple[bool, list[Any]]:
    """``(passed, findings_on_this_element)`` for one sample.

    For a detection sample, passing means an expected class fired. For a benign
    sample — empty ``expected_classes`` — passing means nothing fired at all.
    """
    manifest, element = sample_manifest(sample)
    findings = [f for f in analyze_manifest(manifest) if f.element == element]
    expected = set(sample.get("expected_classes") or [])
    if not expected:
        return not findings, findings
    return bool({f.pattern_class for f in findings} & expected), findings


def _report_detection(provenance: str, samples: list[dict[str, Any]]) -> None:
    per_class: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    misses: list[str] = []
    for sample in samples:
        passed, findings = _score(sample)
        counts = per_class[sample["class"]]
        counts[1] += 1
        counts[0] += int(passed)
        if not passed:
            found = sorted({f.pattern_class for f in findings})
            misses.append(
                f"      {sample['id']:24} expected {sorted(sample['expected_classes'])} "
                f"got {found or '[]'}"
            )

    comparable = provenance == V1_COMPARABLE
    print(f"\n  {provenance} — {len(samples)} samples")
    if comparable:
        print(
            f"    {'class':18} {'v1 (' + V1_RULESET + ')':>12} {'':>5}"
            f" {'v2 (' + RULESET_VERSION + ')':>12}"
        )
    else:
        print(f"    {'class':18} {'detected':>12}")
        print("    (no v1 counterpart — v1 never covered these surfaces, so a lower")
        print("     number here is first coverage, not a regression)")

    for cls, (hit, total) in sorted(per_class.items()):
        row = f"    {cls:18}"
        if comparable:
            v1 = HELDOUT_V1.get(cls)
            row += f" {f'{v1[0]}/{v1[1]}' if v1 else '—':>12} {_pct(*v1) if v1 else '   —':>5}"
        row += f" {f'{hit}/{total}':>12} {_pct(hit, total):>5}"
        print(row)

    hit = sum(v[0] for v in per_class.values())
    total = sum(v[1] for v in per_class.values())
    row = f"    {'overall':18}"
    if comparable:
        v1_hit = sum(h for h, _ in HELDOUT_V1.values())
        v1_total = sum(t for _, t in HELDOUT_V1.values())
        row += f" {f'{v1_hit}/{v1_total}':>12} {_pct(v1_hit, v1_total):>5}"
    row += f" {f'{hit}/{total}':>12} {_pct(hit, total):>5}"
    print(row)

    if misses:
        print("    misses:")
        for line in misses:
            print(line)


def _report_false_positives(provenance: str, samples: list[dict[str, Any]]) -> None:
    """A false-positive count, not a detection count. Each firing sample is a dispute
    to adjudicate — Doc wrote these as legitimate text — so print what is needed to
    argue it: the element, the rule that fired, the author's note, and the excerpt."""
    fired: list[dict[str, Any]] = []
    for sample in samples:
        passed, findings = _score(sample)
        if not passed:
            fired.append({"sample": sample, "findings": findings})

    print(f"\n  {provenance} — {len(samples)} samples, false-positive count")
    print(f"    false positives: {len(fired)} of {len(samples)}")
    for entry in fired:
        sample = entry["sample"]
        print(f"\n      {sample['id']}  ({sample['element']})")
        for finding in entry["findings"]:
            print(f"        element : {finding.element}")
            print(f"        rule    : {finding.rule}")
            print(f"        excerpt : {finding.excerpt}")
        if sample.get("note"):
            print(f"        note    : {sample['note']}")
    if fired:
        print(
            "\n    Each of the above is a claim that the rule is wrong, not proof that it\n"
            "    is. Some resolve as annotated hard cases instead. To Chief before any of\n"
            "    it reaches baseline.json."
        )


def main() -> int:
    files = sorted(p for p in HELDOUT.glob("*.json"))
    if not files:
        print("no held-out files found; nothing to score")
        return 0

    print(f"held-out scoring under ruleset {RULESET_VERSION}. Reported as-is.")
    print("Provenances are reported separately and never pooled.")

    documents = []
    for path in files:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("samples"):
            documents.append((document.get("provenance") or path.stem, document, path.name))

    def order(entry: tuple[str, dict[str, Any], str]) -> tuple[int, str]:
        provenance = entry[0]
        rank = (
            PROVENANCE_ORDER.index(provenance)
            if provenance in PROVENANCE_ORDER
            else len(PROVENANCE_ORDER)
        )
        return rank, entry[2]

    for provenance, document, _name in sorted(documents, key=order):
        samples = document["samples"]
        detection = [s for s in samples if s.get("expected_classes")]
        benign = [s for s in samples if not s.get("expected_classes")]
        if detection:
            _report_detection(provenance, detection)
        if benign:
            _report_false_positives(provenance, benign)

    print("\nNothing was written. baseline.json moves by decision, not by measurement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
