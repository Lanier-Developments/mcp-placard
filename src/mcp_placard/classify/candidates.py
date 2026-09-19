"""The shared evidence shape every signal extractor returns.

Kept separate from ``classify/signals/`` and ``classify/combine.py`` so neither
needs to import the other — extractors produce :class:`Candidate` objects,
``combine.py`` consumes them, and neither module depends on its sibling.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..manifest.models import Kind, Tier


@dataclass(frozen=True)
class Candidate:
    """One signal's vote for a tier, with the evidence behind it.

    Mirrors :class:`~mcp_placard.manifest.models.Citation` field for field — this is
    the extractor-side working type; ``Citation`` is what gets serialized into a
    manifest once the combiner has decided which candidates to keep.

    ``kinds`` is derived by the extractor from the same evidence that produced the
    tier (Amendment 2 §3, and the Phase 2.1 brief's instruction not to add a second
    pass that re-inspects the schema to guess kinds). A kind therefore always rides on
    a citation.
    """

    signal: str
    tier: Tier
    evidence: str
    rule: str | None = None
    kinds: frozenset[Kind] = frozenset()
