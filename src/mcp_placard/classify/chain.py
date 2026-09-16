"""``CHAIN_EXFIL`` — the one server-level finding Phase 2 implements.

`docs/TAXONOMY.md`, "Server-level findings": blast radius is compositional. A
server exposing an R2-sensitive read alongside an R4 egress tool contains a
complete exfiltration chain, and neither tool alone need be alarming enough to
cross a ceiling. This is a scan-time property of the whole surface, carried on the
manifest itself (:attr:`~mcp_placard.manifest.models.Manifest.findings`) — unlike a
``diff`` finding, it does not require two manifests to compute.

Tiers R2 and R3 are treated as the "read" half and R4/R5 as the "egress" half.
These two sets are disjoint by construction, which is what guarantees the chain
always names at least two distinct tools rather than firing on one tool that
happens to satisfy both a "R2-or-above" and an "R4" reading of a single tier value.
"""

from __future__ import annotations

from ..manifest.models import ServerFinding, ToolClassification

READ_HALF_TIERS = frozenset({"R2", "R3"})
EGRESS_HALF_TIERS = frozenset({"R4", "R5"})

SCOPE_NOTE = (
    "Evaluates tools only. Resources and prompts are enumerated but unclassified "
    "in Phase 2, so a chain whose read half is a resource — mail or file contents "
    "exposed as a resource alongside an R4 egress tool — is not detected here."
)


def find(classification: list[ToolClassification]) -> ServerFinding | None:
    """Return the ``CHAIN_EXFIL`` finding for this surface, or ``None``.

    ``None`` when the surface lacks either half of the chain — this is not itself
    reported as "no chain found"; :attr:`Manifest.findings` is simply empty.
    """
    reads = sorted(entry.tool for entry in classification if entry.tier in READ_HALF_TIERS)
    egresses = sorted(entry.tool for entry in classification if entry.tier in EGRESS_HALF_TIERS)
    if not reads or not egresses:
        return None

    return ServerFinding(
        kind="chain_exfil",
        summary=(
            f"server exposes an R2+ read ({', '.join(reads)}) alongside an R4+ "
            f"egress tool ({', '.join(egresses)}) — a complete exfiltration chain"
        ),
        tools=sorted(set(reads) | set(egresses)),
        scope=SCOPE_NOTE,
    )
