"""Tier escalation is now live (Phase 2 deliverable 9).

This file used to assert the branch was reachable but inert, by construction,
because Phase 1 had exactly one tier. Phase 2 replaces those assertions with real
ones — this is the file that predicted its own rewrite, and this is that rewrite.
"""

from __future__ import annotations

from mcp_placard.diff import CHANGE_EXIT_CODES, ChangeKind, diff_manifests
from mcp_placard.diff.engine import tier_escalation_findings
from mcp_placard.errors import EXIT_ESCALATION, EXIT_OK
from mcp_placard.manifest import Manifest, build_manifest

from .conftest import make_manifest, make_raw, tool_wire


def test_no_tier_data_on_either_side_produces_no_escalation_finding() -> None:
    """A tool this build cannot grade produces no ``tier_escalated`` finding — it
    is not silently treated as unchanged; ``diff/engine.py``'s other conservative
    defaults (escalating ``tool_added``/``tool_schema_changed``) carry that weight
    instead."""
    assert tier_escalation_findings("t", None, None) == []
    assert tier_escalation_findings("t", "R1", None) == []
    assert tier_escalation_findings("t", None, "R4") == []


def test_an_unchanged_tier_produces_no_finding() -> None:
    assert tier_escalation_findings("t", "R2", "R2") == []


def test_a_tier_decrease_produces_no_finding() -> None:
    """Only an increase escalates — a tool getting *less* dangerous is not news."""
    assert tier_escalation_findings("t", "R4", "R1") == []


def test_a_tier_increase_is_an_escalation() -> None:
    findings = tier_escalation_findings("t", "R1", "R4")
    assert len(findings) == 1
    assert findings[0].kind is ChangeKind.TIER_ESCALATED
    assert findings[0].exit_code == EXIT_ESCALATION
    assert "R1" in findings[0].summary and "R4" in findings[0].summary


def _classified(tools: list[dict], classification: list[dict]) -> Manifest:
    """Build a manifest and stamp classification entries onto it directly — a
    lighter-weight path than running the real classifier, for tests that only
    care about the diff/tier-comparison mechanics."""
    from mcp_placard.manifest.build import compute_classification_hash
    from mcp_placard.manifest.models import ToolClassification

    manifest = build_manifest(make_raw(tools))
    from mcp_placard import RULESET_VERSION

    entries = [ToolClassification(tool=c["tool"], tier=c["tier"]) for c in classification]
    return manifest.model_copy(
        update={
            "classification": entries,
            "classification_hash": compute_classification_hash(entries, [], RULESET_VERSION),
            # Stamped as current so diff compares the stamped tiers as-is instead of
            # re-analysing the surface (Phase 3 §4) and overwriting them.
            "ruleset_version": RULESET_VERSION,
        }
    )


def test_a_real_tier_increase_escalates_through_diff_manifests() -> None:
    old = _classified([tool_wire("t")], [{"tool": "t", "tier": "R1"}])
    new = _classified([tool_wire("t")], [{"tool": "t", "tier": "R4"}])

    result = diff_manifests(old, new)
    assert result.exit_code == EXIT_ESCALATION
    findings = result.findings_of(ChangeKind.TIER_ESCALATED)
    assert len(findings) == 1
    assert findings[0].tool == "t"


def test_a_real_tier_decrease_does_not_escalate() -> None:
    old = _classified([tool_wire("t")], [{"tool": "t", "tier": "R4"}])
    new = _classified([tool_wire("t")], [{"tool": "t", "tier": "R1"}])

    result = diff_manifests(old, new)
    assert result.findings_of(ChangeKind.TIER_ESCALATED) == []
    assert result.exit_code == EXIT_OK


def test_an_unclassified_pair_is_reanalysed_so_a_real_tier_move_is_caught() -> None:
    """Phase 1's "with no tier data, ``tier_escalated`` cannot fire" no longer holds:
    since Phase 3 §4, ``diff`` re-analyses any side with no recorded ruleset from its
    stored surface. The ``changes`` tool gains a Rule D ``force`` boolean here, so
    the re-analysed pair *does* show a tier increase — on the merits, R0 to R5 —
    and the comparison says on which side re-analysis happened."""
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
    [escalation] = result.findings_of(ChangeKind.TIER_ESCALATED)
    assert escalation.tool == "changes"
    assert len(result.notes) == 2  # both sides carried no ruleset


def test_the_tier_escalated_kind_still_maps_to_escalation() -> None:
    assert CHANGE_EXIT_CODES[ChangeKind.TIER_ESCALATED] == EXIT_ESCALATION
