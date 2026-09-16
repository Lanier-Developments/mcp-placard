"""Risk tier inference and declared-vs-inferred reconciliation.

Reads a built :class:`~mcp_placard.manifest.models.Manifest` and returns a new one
with real classification filled in — :func:`classify_manifest` never touches
``surface_hash`` or ``capabilities_hash``, and never calls a server or re-hashes
anything outside ``classification_hash``. That boundary matters: ``manifest/``
builds the structural manifest and does not classify risk; this package classifies
and does not build.

The pipeline per tool, in order:

1. Every signal extractor in :mod:`classify.signals` runs independently and
   produces zero or more :class:`~classify.candidates.Candidate` objects — they do
   not see each other's output.
2. :func:`classify.combine.combine` takes the monotonic maximum over every
   candidate (Rule F) and turns each into a
   :class:`~mcp_placard.manifest.models.Citation`.
3. :func:`classify.overrides.apply` applies the operator's allowlist, if the tier
   it produced is above R3 and reversibility is meaningful.
4. :func:`classify.reversibility.compute` runs for any tool at R3 or above.
5. :func:`classify.signals.annotations.find_disagreements` compares the declared
   annotations against the final tier.

Then, once every tool has a :class:`~mcp_placard.manifest.models.ToolClassification`,
:func:`classify.chain.find` looks for ``CHAIN_EXFIL`` across the whole surface.
"""

from __future__ import annotations

from ..manifest.build import compute_classification_hash
from ..manifest.models import TIER_ORDER, Manifest, ToolClassification, ToolEntry
from . import chain
from .combine import combine
from .overrides import OverrideEntry
from .overrides import apply as apply_overrides
from .reversibility import compute as compute_reversibility
from .signals import description, schema_shape, verb
from .signals.annotations import find_disagreements

__all__ = ["OverrideEntry", "classify_manifest", "classify_tool"]

_R3_INDEX = TIER_ORDER.index("R3")


def classify_tool(tool: ToolEntry, overrides: list[OverrideEntry]) -> ToolClassification:
    """Classify one tool: combine every signal, apply overrides, and reconcile
    against what the server itself declared."""
    schema_candidates, _traversal_status = schema_shape.extract(tool.input_schema)
    candidates = [
        *schema_candidates,
        *verb.extract(tool.name),
        *description.extract(tool.description),
    ]

    inferred_tier, citations = combine(candidates)
    final_tier, override_applied = apply_overrides(tool.name, inferred_tier, overrides)

    reversibility = None
    if TIER_ORDER.index(final_tier) >= _R3_INDEX:
        reversibility = compute_reversibility(tool.input_schema, tool.annotations)

    disagreements = find_disagreements(tool.annotations, final_tier)

    return ToolClassification(
        tool=tool.name,
        tier=final_tier,
        citations=citations,
        reversibility=reversibility,
        disagreements=disagreements,
        override=override_applied,
    )


def classify_manifest(
    manifest: Manifest, *, overrides: list[OverrideEntry] | None = None
) -> Manifest:
    """Classify every tool in ``manifest`` and return a new manifest carrying the
    result. Does not mutate ``manifest`` in place — ``build_manifest`` and
    ``classify_manifest`` are both pure functions over their input.
    """
    resolved_overrides = overrides or []
    classification = [classify_tool(tool, resolved_overrides) for tool in manifest.surface.tools]
    chain_finding = chain.find(classification)

    return manifest.model_copy(
        update={
            "classification": classification,
            "classification_hash": compute_classification_hash(classification),
            "findings": [chain_finding] if chain_finding is not None else [],
        }
    )
