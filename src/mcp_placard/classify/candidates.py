"""The shared evidence shape every signal extractor returns.

Kept separate from ``classify/signals/`` and ``classify/combine.py`` so neither
needs to import the other — extractors produce :class:`Candidate` objects,
``combine.py`` consumes them, and neither module depends on its sibling.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..manifest.models import Tier


@dataclass(frozen=True)
class Candidate:
    """One signal's vote for a tier, with the evidence behind it.

    Mirrors :class:`~mcp_placard.manifest.models.Citation` field for field — this is
    the extractor-side working type; ``Citation`` is what gets serialized into a
    manifest once the combiner has decided which candidates to keep.
    """

    signal: str
    tier: Tier
    evidence: str
    rule: str | None = None
