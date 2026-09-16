"""Rule G's fail-closed schema traversal, exercised through the full classification
pipeline — proving the walker's status propagates all the way to a tier, not just
that :func:`walk_schema` reports the right status in isolation (`test_schema_walk.py`
already covers that).

Fixtures live in ``tests/fixtures/schema_traversal/`` per the Phase 2 addendum:
parser fixtures, kept separate from the tier matrix in
``test_classify_fixture_matrix.py``. Each file is one tool definition plus the
outcome it must produce.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_placard.classify import classify_tool
from mcp_placard.classify.schema_walk import TraversalStatus, walk_schema
from mcp_placard.manifest.models import ToolEntry

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "schema_traversal"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _tool_from(doc: dict) -> ToolEntry:
    return ToolEntry(
        name=doc["name"],
        description=doc["description"],
        input_schema=doc["inputSchema"],
        schema_hash="0" * 64,
        description_hash="0" * 64,
    )


FIXTURE_FILES = [
    "nested_allof_to.json",
    "ref_cycle.json",
    "depth_exceeded.json",
    "unresolvable_ref.json",
    "nested_if_match.json",
    "anyof_dangerous_branch.json",
]


def test_every_schema_traversal_fixture_file_exists() -> None:
    for filename in FIXTURE_FILES:
        assert (FIXTURES_DIR / filename).is_file(), filename


def test_a_to_field_three_allof_levels_deep_classifies_r4_with_the_full_pointer() -> None:
    doc = _load("nested_allof_to.json")
    result = classify_tool(_tool_from(doc), [])
    assert result.tier == doc["expected_tier"]
    pointers = [c.evidence for c in result.citations if c.tier == "R4"]
    assert any(doc["expected_pointer"] in evidence for evidence in pointers), pointers


def test_a_ref_cycle_classifies_unconstrained_with_cycle_detected_cited() -> None:
    doc = _load("ref_cycle.json")
    walked = walk_schema(doc["inputSchema"])
    assert walked.status is TraversalStatus.CYCLE_DETECTED

    result = classify_tool(_tool_from(doc), [])
    assert result.tier == doc["expected_tier"]
    assert any("cycle_detected" in c.evidence for c in result.citations)


def test_a_schema_past_the_depth_cap_classifies_unconstrained_with_depth_exceeded_cited() -> None:
    doc = _load("depth_exceeded.json")
    walked = walk_schema(doc["inputSchema"])
    assert walked.status is TraversalStatus.DEPTH_EXCEEDED

    result = classify_tool(_tool_from(doc), [])
    assert result.tier == doc["expected_tier"]
    assert any("depth_exceeded" in c.evidence for c in result.citations)


def test_an_unresolvable_ref_classifies_unconstrained_with_unresolvable_ref_cited() -> None:
    doc = _load("unresolvable_ref.json")
    walked = walk_schema(doc["inputSchema"])
    assert walked.status is TraversalStatus.UNRESOLVABLE_REF

    result = classify_tool(_tool_from(doc), [])
    assert result.tier == doc["expected_tier"]
    assert any("unresolvable_ref" in c.evidence for c in result.citations)


def test_an_if_match_nested_in_an_object_is_found_by_rule_d() -> None:
    """Proves the walker is shared across signal classes: schema-shape's R4
    Rule-A/C checks and Rule D's reversibility evidence both reach the same
    nested property through the same traversal."""
    doc = _load("nested_if_match.json")
    result = classify_tool(_tool_from(doc), [])
    assert result.tier == doc["expected_tier"]
    assert result.reversibility == doc["expected_reversibility"]


def test_a_dangerous_field_in_only_one_anyof_branch_classifies_at_the_higher_tier() -> None:
    doc = _load("anyof_dangerous_branch.json")
    result = classify_tool(_tool_from(doc), [])
    assert result.tier == doc["expected_tier"]
    # The safe branch's local_id must not suppress the dangerous branch's url:
    # the walker visits both anyOf branches, and Rule A's R4 candidate for `url`
    # survives the monotonic maximum regardless of what `local_id`'s branch found.
    assert any(c.tier == "R4" and "url" in c.evidence for c in result.citations)


@pytest.mark.parametrize("filename", FIXTURE_FILES)
def test_every_fixture_scan_terminates(filename: str) -> None:
    """None of these fixtures may hang the classifier — the cycle and
    depth-exceeded cases exist specifically to prove traversal always stops."""
    doc = _load(filename)
    result = classify_tool(_tool_from(doc), [])
    assert result.tier is not None
