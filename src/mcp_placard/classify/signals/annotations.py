"""Declared-annotations reconciliation — never a tier candidate.

`docs/TAXONOMY.md`, "Declared vs inferred": declared annotations are evidence, never
truth, and never independently vote for a tier — the ``destructiveHint: true`` /
inferred R1 row in that table is explicitly "not a finding," which is only possible
if annotations never enter Rule F's monotonic maximum (see the note on
:class:`~mcp_placard.manifest.models.Citation`). This module's only job is
comparing what was declared against the tier schema/verb/description already
decided, and reporting the one-way disagreements the taxonomy specifies.

The fifth table row — a tool at R5 with no annotations declared at all — is
explicitly *not* a disagreement ("worth surfacing" rather than a contradiction) and
is deliberately not modeled here as one; a future report renderer is free to
surface it separately from the disagreement list.
"""

from __future__ import annotations

from ...manifest.models import Disagreement, Tier, ToolAnnotations
from ..candidates import Candidate

_R3_AND_ABOVE = {"R3", "R4", "R5"}


def find_disagreements(
    annotations: ToolAnnotations | None, inferred_tier: Tier
) -> list[Disagreement]:
    """Compare declared annotations against an already-decided inferred tier.

    Takes the tier as already resolved by :mod:`classify.combine` — this function
    never computes a tier itself, only reports where a declaration and that tier
    disagree.
    """
    if annotations is None:
        return []

    disagreements: list[Disagreement] = []

    if annotations.read_only_hint is True and inferred_tier in _R3_AND_ABOVE:
        disagreements.append(
            Disagreement(
                annotation="readOnlyHint",
                declared=True,
                inferred_tier=inferred_tier,
                reading="The server claims safety its schema does not support.",
            )
        )

    if annotations.destructive_hint is False and inferred_tier == "R5":
        disagreements.append(
            Disagreement(
                annotation="destructiveHint",
                declared=False,
                inferred_tier=inferred_tier,
                reading="Same shape as the readOnlyHint disagreement, stated more specifically.",
            )
        )

    if annotations.open_world_hint is False and inferred_tier == "R4":
        disagreements.append(
            Disagreement(
                annotation="openWorldHint",
                declared=False,
                inferred_tier=inferred_tier,
                reading="A closed world does not take a caller-influenced outbound target.",
            )
        )

    return disagreements


def extract(_annotations: ToolAnnotations | None) -> list[Candidate]:
    """Always empty. Present so ``classify/signals/`` has one module per signal
    class named in AGENTS.md, and so a reader searching for "the declared
    annotations extractor" finds this file and the explanation above rather than
    nothing at all."""
    return []
