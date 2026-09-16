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

**Diff narrowing (Phase 2 deliverable 9).** Tier data lets three Phase 1 findings
stop being unconditionally conservative:

* ``tool_added`` escalates only when the added tool's tier is at or above the
  configured ceiling — below it, exit 0.
* ``tool_schema_changed`` escalates only when ``escalate_schema_changes`` is set;
  by default a schema change that does not move the tier is exit 0, and a change
  that *does* move it is caught by ``tier_escalated`` instead.
* ``tier_escalated`` is now live: any tier increase on an existing tool escalates.

A tool absent from either manifest's ``classification`` — an old Phase 1 manifest,
or a manifest nothing has classified yet — falls back to the Phase 1 conservative
default (escalate), since AGENTS.md forbids treating "we cannot grade this" as "this
is safe."
"""

from __future__ import annotations

from ..errors import EXIT_ESCALATION, EXIT_OK
from ..manifest.models import TIER_ORDER, Manifest, Tier, ToolEntry
from .models import CHANGE_EXIT_CODES, ChangeKind, DiffResult, Finding

DEFAULT_CEILING: Tier = "R4"
"""Tool additions at or above this tier escalate; below it, they do not. Matches
AGENTS.md's original "new tool at R4/R5" default, now realized as an actual
threshold instead of a blanket rule with no classifier to apply it against."""


def _short(digest: str) -> str:
    """Abbreviate a hash for a one-line finding; the manifests hold the full value."""
    return digest[:12]


def _tier_of(manifest: Manifest, tool_name: str) -> Tier | None:
    """The tool's classified tier in ``manifest``, or ``None`` if unavailable — an
    unclassified Phase 1 manifest, or a tool a classifier has not run against."""
    entry = manifest.classification_by_tool().get(tool_name)
    return entry.tier if entry is not None else None


def _at_or_above_ceiling(tier: Tier, ceiling: Tier) -> bool:
    return TIER_ORDER.index(tier) >= TIER_ORDER.index(ceiling)


def tier_escalation_findings(
    tool_name: str, old_tier: Tier | None, new_tier: Tier | None
) -> list[Finding]:
    """A tier increase on an existing tool is always an escalation.

    Requires a real tier on both sides — a tool this build cannot grade on either
    side (no classification recorded) produces no finding here, rather than
    guessing at a direction to escalate in.
    """
    if old_tier is None or new_tier is None:
        return []
    if TIER_ORDER.index(new_tier) <= TIER_ORDER.index(old_tier):
        return []
    return [
        Finding(
            kind=ChangeKind.TIER_ESCALATED,
            tool=tool_name,
            summary=f"tool {tool_name!r} tier increased ({old_tier} -> {new_tier})",
            exit_code=CHANGE_EXIT_CODES[ChangeKind.TIER_ESCALATED],
        )
    ]


def _added_tool_finding(tool: ToolEntry, new: Manifest, *, ceiling: Tier) -> Finding:
    tier = _tier_of(new, tool.name)
    if tier is None:
        return Finding(
            kind=ChangeKind.TOOL_ADDED,
            tool=tool.name,
            summary=f"tool {tool.name!r} added (unclassified; schema {_short(tool.schema_hash)})",
            exit_code=EXIT_ESCALATION,
        )
    code = EXIT_ESCALATION if _at_or_above_ceiling(tier, ceiling) else EXIT_OK
    return Finding(
        kind=ChangeKind.TOOL_ADDED,
        tool=tool.name,
        summary=f"tool {tool.name!r} added (tier {tier}; schema {_short(tool.schema_hash)})",
        exit_code=code,
    )


def _removed_tool_finding(tool: ToolEntry, old: Manifest) -> Finding:
    tier_label = _tier_of(old, tool.name) or "unclassified"
    return Finding(
        kind=ChangeKind.TOOL_REMOVED,
        tool=tool.name,
        summary=f"tool {tool.name!r} removed (was tier {tier_label})",
        exit_code=CHANGE_EXIT_CODES[ChangeKind.TOOL_REMOVED],
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
        exit_code=CHANGE_EXIT_CODES[ChangeKind.SERVER_CAPABILITIES_CHANGED],
    )


def _changed_tool_findings(
    old_tool: ToolEntry,
    new_tool: ToolEntry,
    old: Manifest,
    new: Manifest,
    *,
    escalate_schema_changes: bool,
) -> list[Finding]:
    """Findings for one tool present in both manifests."""
    findings: list[Finding] = []

    if old_tool.schema_hash != new_tool.schema_hash:
        old_tier = _tier_of(old, old_tool.name)
        new_tier = _tier_of(new, new_tool.name)
        if old_tier is None or new_tier is None:
            # Cannot be shown to have left the tier unchanged — the same
            # conservative default as an unclassified tool_added.
            code = EXIT_ESCALATION
        elif escalate_schema_changes:
            code = EXIT_ESCALATION
        else:
            # An increase is already caught by tier_escalation_findings below;
            # this finding itself only needs to escalate in the two cases above.
            code = EXIT_OK
        findings.append(
            Finding(
                kind=ChangeKind.TOOL_SCHEMA_CHANGED,
                tool=new_tool.name,
                summary=(
                    f"tool {new_tool.name!r} input schema changed "
                    f"({_short(old_tool.schema_hash)} -> {_short(new_tool.schema_hash)})"
                ),
                exit_code=code,
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
                exit_code=CHANGE_EXIT_CODES[ChangeKind.TOOL_DESCRIPTION_CHANGED],
            )
        )

    findings.extend(
        tier_escalation_findings(
            new_tool.name, _tier_of(old, old_tool.name), _tier_of(new, new_tool.name)
        )
    )
    return findings


def diff_manifests(
    old: Manifest,
    new: Manifest,
    *,
    ceiling: Tier = DEFAULT_CEILING,
    escalate_schema_changes: bool = False,
) -> DiffResult:
    """Compare two manifests and return every finding between them.

    ``ceiling`` gates ``tool_added``: at or above it, exit 1; below it, exit 0.
    ``escalate_schema_changes`` reverts ``tool_schema_changed`` to the Phase 1
    conservative default (always exit 1) for callers that want it; by default a
    schema change that does not move the tier is exit 0.

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
            findings.append(_added_tool_finding(after, new, ceiling=ceiling))
        elif after is None and before is not None:
            findings.append(_removed_tool_finding(before, old))
        elif before is not None and after is not None:
            findings.extend(
                _changed_tool_findings(
                    before, after, old, new, escalate_schema_changes=escalate_schema_changes
                )
            )

    if (capabilities_finding := _capabilities_changed_finding(old, new)) is not None:
        findings.append(capabilities_finding)

    return DiffResult(
        findings=findings,
        surface_hash_changed=old.surface_hash != new.surface_hash,
    )
