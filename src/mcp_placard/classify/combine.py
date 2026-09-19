"""Rule F: signals combine as a monotonic maximum, never a weighted score.

`docs/TAXONOMY.md`, Rule F: *tier assignment is the maximum tier supported by any
signal. Signal ordering exists only to determine which signal is cited first in
the finding, and to resolve which evidence is recorded when several support the
same tier. Ordering never reduces a tier.* This module is the one place that
maximum is taken — extractors never see each other's output, and nothing upstream
of here is allowed to average, weight, or otherwise blend candidates.

Kinds combine as a plain union (Amendment 2 §3). There is nothing to maximise:
kinds are unordered by meaning, and a tool that is both ``write`` and ``egress`` is
both, not the "larger" of the two.
"""

from __future__ import annotations

from ..manifest.models import KIND_ORDER, TIER_ORDER, Citation, Kind, Tier
from .candidates import Candidate


def combine(candidates: list[Candidate]) -> tuple[Tier, list[Citation], list[Kind]]:
    """Combine every candidate into the tool's tier, its full citation list, and
    its kinds.

    Every candidate becomes a citation, not only the one that won — an R1
    candidate sits alongside the R4 candidate that decided the tier, because
    ordering governs citation, not exclusion.
    """
    if not candidates:
        raise ValueError(
            "combine() requires at least one candidate; the schema-shape extractor "
            "always produces one (Rule B's closed-schema fallback), so an empty "
            "list here means a caller skipped it, not that no signal fired"
        )

    winning_tier = max(candidates, key=lambda candidate: TIER_ORDER.index(candidate.tier)).tier
    citations = [
        Citation(
            signal=candidate.signal,
            tier=candidate.tier,
            evidence=candidate.evidence,
            rule=candidate.rule,
            kinds=sorted(candidate.kinds, key=KIND_ORDER.index),
        )
        for candidate in candidates
    ]
    union: set[Kind] = set()
    for candidate in candidates:
        union |= candidate.kinds
    return winning_tier, citations, sorted(union, key=KIND_ORDER.index)
