"""The diff rule table.

AGENTS.md: *diff rules are tested as a table of (old manifest, new manifest,
expected exit code). Add a row before changing the rule.* This module is that table.
A change to ``CHANGE_EXIT_CODES`` that is not accompanied by a row here is a change
to CI semantics that nobody agreed to.

Since 0.3.0 the exit status is a **bitmask** — escalation 1, prompt change 2,
removal 4, injection 8 — so the table's load-bearing rows are the combinations:
every subset of the bits that the tool-level checks can produce is a row, and each
one asserts the exact OR rather than a "winner". Injection rows (bit 8) live in
``test_inject_diff.py`` beside the analyzer that produces them; together the two
tables cover all sixteen values.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from mcp_placard.diff import ChangeKind, diff_manifests
from mcp_placard.errors import (
    EXIT_DESCRIPTION_CHANGE,
    EXIT_ESCALATION,
    EXIT_OK,
    EXIT_REMOVED,
)
from mcp_placard.manifest import Manifest, build_manifest

from .conftest import make_manifest, make_raw, tool_wire

SCHEMA_A = {"type": "object", "properties": {"query": {"type": "string"}}}
SCHEMA_B = {
    "type": "object",
    "properties": {"query": {"type": "string"}, "force": {"type": "boolean"}},
}
PURGE = {"type": "object", "properties": {"force": {"type": "boolean"}}}
"""``purge`` carries a Rule D force boolean, so it is R5 under the real classifier —
above the default ceiling — and its addition escalates on the merits rather than
on Phase 1's "unclassified ⇒ escalate" default, which no longer applies now that
``diff`` re-analyses every side under the current ruleset."""


def _baseline() -> Manifest:
    return make_manifest(
        [
            tool_wire("search", description="Search things.", input_schema=SCHEMA_A),
            tool_wire("write", description="Write things."),
        ]
    )


def _unchanged() -> Manifest:
    return _baseline()


def _description_changed() -> Manifest:
    return make_manifest(
        [
            tool_wire(
                "search", description="Search things, ranked by recency.", input_schema=SCHEMA_A
            ),
            tool_wire("write", description="Write things."),
        ]
    )


def _schema_changed() -> Manifest:
    return make_manifest(
        [
            tool_wire("search", description="Search things.", input_schema=SCHEMA_B),
            tool_wire("write", description="Write things."),
        ]
    )


def _tool_added() -> Manifest:
    return make_manifest(
        [
            tool_wire("search", description="Search things.", input_schema=SCHEMA_A),
            tool_wire("write", description="Write things."),
            tool_wire("purge", description="Purge things.", input_schema=PURGE),
        ]
    )


def _tool_removed() -> Manifest:
    return make_manifest([tool_wire("search", description="Search things.", input_schema=SCHEMA_A)])


def _added_and_description_changed() -> Manifest:
    return make_manifest(
        [
            tool_wire("search", description="Rewritten.", input_schema=SCHEMA_A),
            tool_wire("write", description="Write things."),
            tool_wire("purge", description="Purge things.", input_schema=PURGE),
        ]
    )


def _removed_and_description_changed() -> Manifest:
    return make_manifest([tool_wire("search", description="Rewritten.", input_schema=SCHEMA_A)])


def _removed_and_added() -> Manifest:
    return make_manifest(
        [
            tool_wire("search", description="Search things.", input_schema=SCHEMA_A),
            tool_wire("purge", description="Purge things.", input_schema=PURGE),
        ]
    )


def _removed_added_and_description_changed() -> Manifest:
    return make_manifest(
        [
            tool_wire("search", description="Rewritten.", input_schema=SCHEMA_A),
            tool_wire("purge", description="Purge things.", input_schema=PURGE),
        ]
    )


def _resource_only_change() -> Manifest:
    return build_manifest(
        make_raw(
            [
                tool_wire("search", description="Search things.", input_schema=SCHEMA_A),
                tool_wire("write", description="Write things."),
            ],
            resources=[{"name": "new", "uri": "file:///new"}],
        )
    )


DIFF_TABLE: list[tuple[str, Callable[[], Manifest], Callable[[], Manifest], int]] = [
    # ---- single categories
    ("identical manifests", _baseline, _unchanged, EXIT_OK),
    (
        "description changed on existing tool",
        _baseline,
        _description_changed,
        EXIT_DESCRIPTION_CHANGE,
    ),
    ("input schema changed", _baseline, _schema_changed, EXIT_ESCALATION),
    ("tool added", _baseline, _tool_added, EXIT_ESCALATION),
    ("tool removed", _baseline, _tool_removed, EXIT_REMOVED),
    # ---- bit combinations: the OR, never a winner
    (
        "added + description changed = 1|2",
        _baseline,
        _added_and_description_changed,
        EXIT_ESCALATION | EXIT_DESCRIPTION_CHANGE,
    ),
    (
        "removed + description changed = 4|2",
        _baseline,
        _removed_and_description_changed,
        EXIT_REMOVED | EXIT_DESCRIPTION_CHANGE,
    ),
    ("removed + added = 4|1", _baseline, _removed_and_added, EXIT_REMOVED | EXIT_ESCALATION),
    (
        "removed + added + description changed = 4|1|2",
        _baseline,
        _removed_added_and_description_changed,
        EXIT_REMOVED | EXIT_ESCALATION | EXIT_DESCRIPTION_CHANGE,
    ),
    # ---- reversal rows: a diff is directional
    ("tool added, read backwards, is a removal", _tool_added, _baseline, EXIT_REMOVED),
    (
        "tool removed, read backwards, is an addition below the ceiling",
        _tool_removed,
        _baseline,
        EXIT_OK,
    ),
    # ---- other surface drift is reported, not failed
    ("resource added only", _baseline, _resource_only_change, EXIT_OK),
]


@pytest.mark.parametrize(
    ("label", "old", "new", "expected"),
    DIFF_TABLE,
    ids=[row[0] for row in DIFF_TABLE],
)
def test_diff_exit_codes(
    label: str,
    old: Callable[[], Manifest],
    new: Callable[[], Manifest],
    expected: int,
) -> None:
    assert diff_manifests(old(), new()).exit_code == expected, label


def test_the_tool_level_checks_cover_every_combination_of_their_three_bits() -> None:
    """Bits 1, 2, 4 in every subset — eight values. Bit 8's eight complements are
    in ``test_inject_diff.py``; the two tables together are the sixteen rows the
    0.3.0 ruling asks for."""
    produced = {expected for _label, _old, _new, expected in DIFF_TABLE}
    assert produced == {0, 1, 2, 3, 4, 5, 6, 7}


def test_no_bit_masks_another() -> None:
    """The property the bitmask exists for: a consumer gating on one category sees
    it regardless of what else happened in the run. The old precedence rule
    reported 3 for this exact pair and hid the escalation."""
    result = diff_manifests(_baseline(), _removed_and_added())
    assert result.exit_code & EXIT_ESCALATION
    assert result.exit_code & EXIT_REMOVED
    assert not result.exit_code & EXIT_DESCRIPTION_CHANGE


def test_description_finding_is_still_emitted_and_still_sets_its_bit() -> None:
    """AGENTS.md: a prompt change is always reviewable. Under the bitmask it is
    not merely listed — its bit is set whatever else happened."""
    result = diff_manifests(_baseline(), _added_and_description_changed())
    assert result.exit_code & EXIT_DESCRIPTION_CHANGE
    assert result.findings_of(ChangeKind.TOOL_DESCRIPTION_CHANGED)


def test_findings_are_ordered_deterministically() -> None:
    result = diff_manifests(_baseline(), _added_and_description_changed())
    names = [finding.tool for finding in result.findings]
    assert names == sorted(names)


def test_a_description_only_change_leaves_the_schema_hash_alone() -> None:
    """The central Phase 1 claim, asserted on the findings rather than the hashes."""
    result = diff_manifests(_baseline(), _description_changed())
    kinds = {finding.kind for finding in result.findings}
    assert kinds == {ChangeKind.TOOL_DESCRIPTION_CHANGED}


def test_findings_report_hashes_not_scanned_text() -> None:
    """Scanned content is untrusted and is never interpolated into output a human or
    a machine will act on. The manifests are where the text is reviewed."""
    result = diff_manifests(_baseline(), _description_changed())
    summary = result.findings[0].summary
    assert "recency" not in summary
    assert "prompt change" in summary


def test_surface_hash_change_is_reported_without_failing_the_build() -> None:
    result = diff_manifests(_baseline(), _resource_only_change())
    assert result.findings == []
    assert result.surface_hash_changed
    assert result.exit_code == EXIT_OK


def test_identical_manifests_report_no_surface_change() -> None:
    result = diff_manifests(_baseline(), _unchanged())
    assert not result.surface_hash_changed


def test_capabilities_only_change_is_its_own_server_level_finding() -> None:
    """Proves the split actually happened: a capabilities-only change moves
    ``capabilities_hash`` and produces its own finding, and moves neither
    ``surface_hash`` nor any tool-level finding."""
    old = build_manifest(make_raw([tool_wire("a")], capabilities={"tools": {"listChanged": False}}))
    new = build_manifest(make_raw([tool_wire("a")], capabilities={"tools": {"listChanged": True}}))

    result = diff_manifests(old, new)
    assert old.surface_hash == new.surface_hash
    assert result.exit_code == EXIT_ESCALATION

    findings = result.findings_of(ChangeKind.SERVER_CAPABILITIES_CHANGED)
    assert len(findings) == 1
    assert findings[0].tool is None
