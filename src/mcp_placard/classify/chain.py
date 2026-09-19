"""``CHAIN_EXFIL`` — the one server-level finding Phase 2 implements.

`docs/TAXONOMY.md`, "Server-level findings": blast radius is compositional. A
server exposing a sensitive read alongside an egress tool contains a complete
exfiltration chain, and neither tool alone need be alarming enough to cross a
ceiling. This is a scan-time property of the whole surface, carried on the
manifest itself (:attr:`~mcp_placard.manifest.models.Manifest.findings`) — unlike a
``diff`` finding, it does not require two manifests to compute.

Amendment 2 §4 redefined the two halves over *kinds* rather than tiers. The Phase 2
implementation expressed "read" as ``{R2, R3}`` and "egress" as ``{R4, R5}`` because
the ladder offered no other axis; R3 is a write and R5 is not egress, so every chain
the first real-server batch raised was spurious. Now: the read half is any tool of
kind ``read_sensitive``, the egress half any tool of kind ``egress``, tier is not
consulted, and a single tool carrying both kinds — every Rule H code-execution
tool does — raises the finding on its own.
"""

from __future__ import annotations

from ..manifest.models import ServerFinding, ToolClassification

SCOPE_NOTE = (
    "Evaluates tools only. Resources and prompts are enumerated but unclassified "
    "in Phase 2, so a chain whose read half is a resource — mail or file contents "
    "exposed as a resource alongside an egress tool — is not detected here."
)


def find(classification: list[ToolClassification]) -> ServerFinding | None:
    """Return the ``CHAIN_EXFIL`` finding for this surface, or ``None``.

    ``None`` when the surface lacks either half of the chain — this is not itself
    reported as "no chain found"; :attr:`Manifest.findings` is simply empty.
    """
    reads = sorted(entry.tool for entry in classification if "read_sensitive" in entry.kinds)
    egresses = sorted(entry.tool for entry in classification if "egress" in entry.kinds)
    if not reads or not egresses:
        return None

    both = sorted(set(reads) & set(egresses))
    summary = (
        f"server exposes a sensitive read ({', '.join(reads)}) alongside an egress "
        f"tool ({', '.join(egresses)}) — a complete exfiltration chain"
    )
    if both:
        summary += f"; {', '.join(both)} carries both halves alone"

    return ServerFinding(
        kind="chain_exfil",
        summary=summary,
        tools=sorted(set(reads) | set(egresses)),
        scope=SCOPE_NOTE,
    )
