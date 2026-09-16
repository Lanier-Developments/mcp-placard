"""Findings and results produced by comparing two manifests.

The exit code is the product of this package, so the mapping from "what changed" to
"what number does CI see" lives in data here rather than in branching in the CLI.

Precedence, when several findings apply at once: ``3 > 1 > 2 > 0``.

* **3 first** because it also covers *server unreachable*. If the scan itself cannot
  be trusted, no judgement made from it can be either, so it outranks everything.
* **1 over 2** because an escalation is a capability change and a description change
  is a prompt change; capability wins when both are present.
* **2 never disappears.** It may be outranked in the exit code, but the finding is
  always listed. AGENTS.md is explicit that a prompt change is always reviewable and
  is not silenceable by tier configuration.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..errors import (
    EXIT_DESCRIPTION_CHANGE,
    EXIT_ESCALATION,
    EXIT_OK,
    EXIT_REMOVED_OR_UNREACHABLE,
)

EXIT_PRECEDENCE: tuple[int, ...] = (
    EXIT_REMOVED_OR_UNREACHABLE,
    EXIT_ESCALATION,
    EXIT_DESCRIPTION_CHANGE,
    EXIT_OK,
)
"""Exit codes in descending precedence. The first one present in a run is reported."""


class ChangeKind(StrEnum):
    """The kinds of change Placard detects.

    Mostly scoped to tools on purpose. Phase 1's tool-level mandate is added tool,
    removed tool, schema change, and description change; resource and prompt drift is
    visible through ``surface_hash`` and is graded in a later phase.

    ``SERVER_CAPABILITIES_CHANGED`` is the one server-level kind: it has no
    associated tool (:attr:`Finding.tool` is ``None`` for it), because it describes
    the server's declared MCP capabilities block, not any single tool.
    """

    TOOL_ADDED = "tool_added"
    TOOL_REMOVED = "tool_removed"
    TOOL_SCHEMA_CHANGED = "tool_schema_changed"
    TOOL_DESCRIPTION_CHANGED = "tool_description_changed"
    TIER_ESCALATED = "tier_escalated"
    SERVER_CAPABILITIES_CHANGED = "server_capabilities_changed"


CHANGE_EXIT_CODES: dict[ChangeKind, int] = {
    ChangeKind.TOOL_ADDED: EXIT_ESCALATION,
    ChangeKind.TOOL_REMOVED: EXIT_REMOVED_OR_UNREACHABLE,
    ChangeKind.TOOL_SCHEMA_CHANGED: EXIT_ESCALATION,
    ChangeKind.TOOL_DESCRIPTION_CHANGED: EXIT_DESCRIPTION_CHANGE,
    ChangeKind.TIER_ESCALATED: EXIT_ESCALATION,
    ChangeKind.SERVER_CAPABILITIES_CHANGED: EXIT_ESCALATION,
}
"""Exit code each kind of change contributes.

Three readings are deliberately conservative, and all three narrow in a later phase:

``TOOL_ADDED`` → 1
    AGENTS.md reserves escalation for a new tool at R4/R5. With no classifier, no
    added tool can be *shown* to sit below the ceiling, and AGENTS.md forbids
    silently downgrading. An unclassified addition is therefore treated as an
    escalation. Phase 2 narrows this to genuinely high-tier additions.

``TOOL_SCHEMA_CHANGED`` → 1
    A schema change can widen blast radius without any other visible signal — a new
    ``force`` flag, a ``path`` that stops being constrained to a prefix. Ungraded, it
    is treated as an escalation. Phase 2 grades the delta instead.

``SERVER_CAPABILITIES_CHANGED`` → 1
    A capability delta can be entirely benign (an SDK-derived flag shifting on a
    client upgrade) or can mean the server started advertising something new to
    subscribe to or be notified through. Nothing in Phase 1 can tell those apart, so
    an ungraded delta is treated as an escalation rather than silently passed —
    exactly the same reasoning as the two rows above it. Note that this exit code
    only says *something in the capabilities block moved*; unlike the two rows above,
    it does not mean any tool's surface changed at all.
"""


class Finding(BaseModel):
    """One reviewable difference between two manifests."""

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    tool: str | None
    """The tool this finding is about, or ``None`` for a server-level finding —
    currently only :attr:`ChangeKind.SERVER_CAPABILITIES_CHANGED`."""

    summary: str
    """One line, safe to print. Scanned content is never interpolated raw — see
    ``diff.engine``, which reports hashes rather than description text."""

    @property
    def exit_code(self) -> int:
        """The exit code this finding on its own would produce."""
        return CHANGE_EXIT_CODES[self.kind]


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

    @property
    def exit_code(self) -> int:
        """The single exit code for this comparison, by documented precedence."""
        codes = {finding.exit_code for finding in self.findings}
        for candidate in EXIT_PRECEDENCE:
            if candidate in codes:
                return candidate
        return EXIT_OK

    def findings_of(self, kind: ChangeKind) -> list[Finding]:
        """Every finding of one kind, in report order."""
        return [finding for finding in self.findings if finding.kind is kind]
