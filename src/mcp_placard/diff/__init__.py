"""Manifest comparison and escalation rules.

``diff`` reads two manifests and produces findings plus the single exit code CI acts
on. It never touches a server, so it depends on ``manifest`` alone and not on the
MCP SDK.

Phase 1 detects added tools, removed tools, input-schema changes, and description
changes. The tier-escalation branch is wired into the code path and returns nothing
until Phase 2 supplies a classifier — see
:func:`~mcp_placard.diff.engine.tier_escalation_findings`.
"""

from __future__ import annotations

from .engine import diff_manifests, tier_escalation_findings
from .models import (
    CHANGE_EXIT_CODES,
    ChangeKind,
    DiffResult,
    Finding,
)

__all__ = [
    "CHANGE_EXIT_CODES",
    "ChangeKind",
    "DiffResult",
    "Finding",
    "diff_manifests",
    "tier_escalation_findings",
]
