"""Compare two manifests and produce findings.

Tools are paired by name, and the comparison is driven entirely by the recorded
hashes rather than by re-reading schemas or descriptions. That is the point of
recording them separately: a description rewrite that leaves the API untouched shows
up as a ``description_hash`` change with an unchanged ``schema_hash``, and nothing
else in the manifest has to be consulted to see it.

Findings deliberately report *hashes*, never the scanned text itself. Descriptions
are untrusted content — a rewritten description is precisely the thing an attacker
controls — and AGENTS.md requires that such content never be interpolated into
output that a human or a machine will act on. Reviewing the text is a job for
``git diff`` on the manifests, where it is already quoted and escaped as JSON data.
"""

from __future__ import annotations

from ..manifest.models import Manifest, ToolEntry
from .models import ChangeKind, DiffResult, Finding


def _short(digest: str) -> str:
    """Abbreviate a hash for a one-line finding; the manifests hold the full value."""
    return digest[:12]


def tier_escalation_findings(old_tool: ToolEntry, new_tool: ToolEntry) -> list[Finding]:
    """Detect a risk-tier increase between two versions of the same tool.

    **Phase 1: intentionally inert.** Both arguments always carry the tier
    ``unclassified``, because Phase 1 performs no classification at all — so there is
    no ordering to compare and this function returns no findings, by construction.

    It is wired into :func:`diff_manifests` anyway, rather than left out and added
    later, so that Phase 2 changes one function body instead of changing the shape of
    the diff. ``tests/test_diff_tier_stub.py`` asserts the inertness directly, so the
    day this starts emitting findings is the day that test has to be rewritten
    deliberately.

    Phase 2 will compare the tools' tiers against the R0-R5 ladder in
    ``docs/TAXONOMY.md`` and emit :attr:`ChangeKind.TIER_ESCALATED` on an increase.
    """
    del old_tool, new_tool  # Phase 2 grades these; Phase 1 has no ladder to grade on.
    return []


def _added_tool_finding(tool: ToolEntry) -> Finding:
    return Finding(
        kind=ChangeKind.TOOL_ADDED,
        tool=tool.name,
        summary=(f"tool {tool.name!r} added (tier {tool.tier}; schema {_short(tool.schema_hash)})"),
    )


def _removed_tool_finding(tool: ToolEntry) -> Finding:
    return Finding(
        kind=ChangeKind.TOOL_REMOVED,
        tool=tool.name,
        summary=f"tool {tool.name!r} removed (was tier {tool.tier})",
    )


def _capabilities_changed_finding(old: Manifest, new: Manifest) -> Finding | None:
    """A server-level finding — no associated tool — when ``capabilities_hash`` moves.

    Independent of every tool-level check: ``capabilities`` was split out of
    ``surface_hash`` precisely so this drift is visible on its own rather than either
    masquerading as a surface change or vanishing silently.
    """
    if old.capabilities_hash == new.capabilities_hash:
        return None
    return Finding(
        kind=ChangeKind.SERVER_CAPABILITIES_CHANGED,
        tool=None,
        summary=(
            "server capabilities changed "
            f"({_short(old.capabilities_hash)} -> {_short(new.capabilities_hash)})"
        ),
    )


def _changed_tool_findings(old_tool: ToolEntry, new_tool: ToolEntry) -> list[Finding]:
    """Findings for one tool present in both manifests."""
    findings: list[Finding] = []

    if old_tool.schema_hash != new_tool.schema_hash:
        findings.append(
            Finding(
                kind=ChangeKind.TOOL_SCHEMA_CHANGED,
                tool=new_tool.name,
                summary=(
                    f"tool {new_tool.name!r} input schema changed "
                    f"({_short(old_tool.schema_hash)} -> {_short(new_tool.schema_hash)})"
                ),
            )
        )

    if old_tool.description_hash != new_tool.description_hash:
        findings.append(
            Finding(
                kind=ChangeKind.TOOL_DESCRIPTION_CHANGED,
                tool=new_tool.name,
                summary=(
                    f"tool {new_tool.name!r} description changed "
                    f"({_short(old_tool.description_hash)} -> "
                    f"{_short(new_tool.description_hash)}) — this is a prompt change"
                ),
            )
        )

    findings.extend(tier_escalation_findings(old_tool, new_tool))
    return findings


def diff_manifests(old: Manifest, new: Manifest) -> DiffResult:
    """Compare two manifests and return every Phase 1 finding between them.

    Findings are ordered by tool name, then by the order the checks run, so two runs
    over the same pair of manifests produce identical output.
    """
    old_tools = old.tools_by_name()
    new_tools = new.tools_by_name()

    findings: list[Finding] = []
    for name in sorted(set(old_tools) | set(new_tools)):
        before = old_tools.get(name)
        after = new_tools.get(name)
        if before is None and after is not None:
            findings.append(_added_tool_finding(after))
        elif after is None and before is not None:
            findings.append(_removed_tool_finding(before))
        elif before is not None and after is not None:
            findings.extend(_changed_tool_findings(before, after))

    if (capabilities_finding := _capabilities_changed_finding(old, new)) is not None:
        findings.append(capabilities_finding)

    return DiffResult(
        findings=findings,
        surface_hash_changed=old.surface_hash != new.surface_hash,
    )
