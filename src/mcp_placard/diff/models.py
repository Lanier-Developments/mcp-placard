"""Findings and results produced by comparing two manifests.

The exit code is the product of this package, so the mapping from "what changed" to
"what number does CI see" lives in data here rather than in branching in the CLI.

**The exit status is a bitmask of finding categories** (0.3.0). Each category owns
one bit — escalation 1, prompt change 2, removal 4, injection 8 — and the status is
their OR. A run with an escalation and a prompt change exits ``3``; a consumer asks
``(( rc & 2 ))`` for "does this need a prompt review" independent of everything else
in the run. No category can mask another.

That property is the one AGENTS.md's category doctrine promised and the earlier
precedence rule (``3 > 1 > 2 > 0``) quietly withdrew: any precedence order is a
ladder, and every ladder hides a category. A run that removed one R0 tool and added
an R5 egress tool used to report ``3``, and a consumer gating on ``1`` missed the
escalation. Now it reports ``5``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..errors import (
    DIFF_FINDING_BITS,
    EXIT_DESCRIPTION_CHANGE,
    EXIT_ESCALATION,
    EXIT_INJECTION,
    EXIT_OK,
    EXIT_REMOVED,
)


class ChangeKind(StrEnum):
    """The kinds of change Placard detects.

    Mostly scoped to tools on purpose. Phase 1's tool-level mandate is added tool,
    removed tool, schema change, and description change; resource and prompt drift is
    visible through ``surface_hash`` and is graded in a later phase.

    ``SERVER_CAPABILITIES_CHANGED`` is a server-level kind: it has no associated
    tool (:attr:`Finding.tool` is ``None`` for it), because it describes the server's
    declared MCP capabilities block, not any single tool.

    ``INJECTION_FINDING`` (Phase 3) is an injection heuristic match that is present
    in the new manifest and absent from the old one, both analysed under the current
    ruleset — see ``diff/engine.py`` on re-analysis. Its :attr:`Finding.tool` is the
    owning tool for a tool-scoped element and ``None`` for server instructions,
    prompts, and resources.
    """

    TOOL_ADDED = "tool_added"
    TOOL_REMOVED = "tool_removed"
    TOOL_SCHEMA_CHANGED = "tool_schema_changed"
    TOOL_DESCRIPTION_CHANGED = "tool_description_changed"
    TIER_ESCALATED = "tier_escalated"
    SERVER_CAPABILITIES_CHANGED = "server_capabilities_changed"
    INJECTION_FINDING = "injection_finding"


CHANGE_EXIT_CODES: dict[ChangeKind, int] = {
    ChangeKind.TOOL_REMOVED: EXIT_REMOVED,
    ChangeKind.TOOL_DESCRIPTION_CHANGED: EXIT_DESCRIPTION_CHANGE,
    ChangeKind.TIER_ESCALATED: EXIT_ESCALATION,
    ChangeKind.SERVER_CAPABILITIES_CHANGED: EXIT_ESCALATION,
    ChangeKind.INJECTION_FINDING: EXIT_INJECTION,
}
"""The finding bit for kinds whose bit never varies by context.

``TOOL_ADDED`` and ``TOOL_SCHEMA_CHANGED`` are deliberately absent: since Phase 2's
diff narrowing, their bit depends on where the tool's tier sits relative to the
configured ceiling and on whether the schema change actually moved the tier — see
``diff/engine.py``, which sets :attr:`Finding.exit_code` explicitly for those two
kinds rather than looking it up here. A ``Finding`` of any other kind always takes
its bit from this table.

``SERVER_CAPABILITIES_CHANGED`` → 1
    A capability delta can be entirely benign (an SDK-derived flag shifting on a
    client upgrade) or can mean the server started advertising something new to
    subscribe to or be notified through. Nothing in this build can tell those apart,
    so an ungraded delta is treated as an escalation rather than silently passed.
    Note that this bit only says *something in the capabilities block moved*; it does
    not mean any tool's surface changed at all.

``INJECTION_FINDING`` → 8, its own bit rather than joining escalation
    Injection findings almost always arrive alongside a prompt change, because the
    attack lives in description text. The useful signal for a reviewer is precisely
    the difference between "the prompt changed" (``2``) and "the prompt changed and
    it looks hostile" (``2 | 8``). Folding injection into bit 0 would erase it.
"""


class Finding(BaseModel):
    """One reviewable difference between two manifests."""

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    tool: str | None
    """The tool this finding is about, or ``None`` for a server-level finding."""

    summary: str
    """One line, safe to print. Scanned content is never interpolated raw — see
    ``diff.engine``, which reports hashes rather than description text, and
    ``inject.render`` for the one place an excerpt is shown, escaped."""

    exit_code: int
    """The finding bit this finding on its own contributes — one of
    :data:`~mcp_placard.errors.DIFF_FINDING_BITS`, or ``0`` for a finding that is
    reported but does not fail the build (a tool added below the ceiling). A real
    field, not a kind-keyed lookup: ``TOOL_ADDED``'s bit depends on the added tool's
    tier against the configured ceiling, and ``TOOL_SCHEMA_CHANGED``'s depends on
    whether the change actually moved the tier — both are context ``diff/engine.py``
    has and this model does not."""


class DiffResult(BaseModel):
    """The complete comparison of two manifests."""

    model_config = ConfigDict(frozen=True)

    findings: list[Finding] = Field(default_factory=list)
    surface_hash_changed: bool = False
    """True when the two manifests' ``surface_hash`` values differ.

    This can be true with no findings — a changed resource, prompt, or server
    instruction moves the surface hash but is not a Phase 1 finding. The CLI reports
    it so the change is not invisible, and it does not affect the exit code.
    """

    notes: list[str] = Field(default_factory=list)
    """Diagnostics about how the comparison was made, for stderr — e.g. that one side
    was re-analysed under the current ruleset before comparing (Phase 3 §4). Not
    findings; they never affect the exit code."""

    @property
    def exit_code(self) -> int:
        """The exit status: the OR of every finding's bit.

        Every value is a subset of :data:`~mcp_placard.errors.DIFF_FINDING_BITS`, so
        the result is in ``0..15`` and each bit answers one question independently.
        """
        status = EXIT_OK
        for finding in self.findings:
            status |= finding.exit_code
        assert status & ~sum(DIFF_FINDING_BITS) == 0, status  # noqa: S101 - invariant
        return status

    def findings_of(self, kind: ChangeKind) -> list[Finding]:
        """Every finding of one kind, in report order."""
        return [finding for finding in self.findings if finding.kind is kind]
