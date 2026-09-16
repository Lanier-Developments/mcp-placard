"""The tier-escalation branch is wired in, and inert until Phase 2.

The Phase 1 brief requires the branch to exist in the code path rather than being
added later, and requires a test asserting it produces nothing. That is this module.

**If you are implementing Phase 2, this file is the thing you rewrite on purpose.**
These assertions are meant to fail the moment classification starts, so that turning
the branch on is a deliberate act with a visible diff, not a side effect.
"""

from __future__ import annotations

from mcp_placard.diff import ChangeKind, diff_manifests
from mcp_placard.diff.engine import tier_escalation_findings
from mcp_placard.manifest import UNCLASSIFIED
from mcp_placard.manifest.models import ToolEntry

from .conftest import make_manifest, tool_wire


def _entry(name: str, schema_hash: str, description_hash: str) -> ToolEntry:
    return ToolEntry(
        name=name,
        input_schema={"type": "object"},
        schema_hash=schema_hash,
        description_hash=description_hash,
    )


def test_the_stub_is_reachable_and_returns_nothing() -> None:
    before = _entry("t", "a" * 64, "b" * 64)
    after = _entry("t", "c" * 64, "d" * 64)
    assert tier_escalation_findings(before, after) == []


def test_the_stub_returns_nothing_even_for_identical_tools() -> None:
    tool = _entry("t", "a" * 64, "b" * 64)
    assert tier_escalation_findings(tool, tool) == []


def test_phase_one_has_no_tier_ordering_to_escalate_along() -> None:
    """The stub is inert *by construction*, not by an early return: there is exactly
    one tier in Phase 1, so no pair of tools can differ in tier."""
    manifest = make_manifest([tool_wire("a"), tool_wire("b")])
    assert {tool.tier for tool in manifest.surface.tools} == {UNCLASSIFIED}


def test_no_diff_of_any_shape_produces_a_tier_escalation_finding() -> None:
    old = make_manifest(
        [
            tool_wire("stays", description="unchanged"),
            tool_wire("changes", description="before"),
            tool_wire("goes", description="removed soon"),
        ]
    )
    new = make_manifest(
        [
            tool_wire("stays", description="unchanged"),
            tool_wire(
                "changes",
                description="after",
                input_schema={"type": "object", "properties": {"force": {"type": "boolean"}}},
            ),
            tool_wire("arrives", description="brand new"),
        ]
    )

    result = diff_manifests(old, new)
    assert result.findings  # the comparison really did run
    assert result.findings_of(ChangeKind.TIER_ESCALATED) == []


def test_the_tier_escalated_kind_is_defined_for_phase_two() -> None:
    """Defined and mapped now so Phase 2 changes one function body, not the shape of
    the diff."""
    from mcp_placard.diff import CHANGE_EXIT_CODES
    from mcp_placard.errors import EXIT_ESCALATION

    assert CHANGE_EXIT_CODES[ChangeKind.TIER_ESCALATED] == EXIT_ESCALATION
