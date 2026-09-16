"""Risk tier inference and declared-vs-inferred reconciliation.

**Not implemented in Phase 1.** Every tool in a Phase 1 manifest carries the literal
tier ``unclassified`` (``mcp_placard.manifest.models.UNCLASSIFIED``). This package is
present because AGENTS.md's directory structure names it, and because Phase 2's
classifier has a defined home — not because any inference happens yet.

Phase 2 will implement the R0-R5 ladder specified in ``docs/TAXONOMY.md``, weighing
four signal classes in decreasing order: input schema shape, declared annotations,
tool name verb, description text. Two rules from AGENTS.md constrain it in advance:
a classifier must cite which signals produced a tier so findings stay auditable, and
it must never silently downgrade a tier because a server declared itself safe.

Deliberately empty. Do not add speculative scaffolding here.
"""

from __future__ import annotations

__all__: list[str] = []
