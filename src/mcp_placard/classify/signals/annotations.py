"""Declared-annotations signal — escalation in one direction, reconciliation in the other.

`docs/TAXONOMY.md`, "Declared vs inferred": declared annotations are evidence, never
truth. Amendment 2 §7 split that into two asymmetric halves:

* **Self-declared danger is a claim against interest**, and the most trustworthy
  signal a server gives us. ``destructiveHint: true`` therefore *is* a tier candidate
  — a floor of R3 and kind ``destructive`` — and enters Rule F's maximum like any
  other signal. This is :func:`extract`.
* **Self-declared safety is a claim the declarer benefits from**, and is only ever
  compared against the tier the other signals decided. It never lowers a tier; where
  it contradicts the inferred tier, that contradiction is the finding. This is
  :func:`find_disagreements`.

The "declared vs inferred" table's fifth row — a tool at R5 with no annotations
declared at all — is explicitly *not* a disagreement ("worth surfacing" rather than
a contradiction) and is deliberately not modelled here as one.
"""

from __future__ import annotations

from ...manifest.models import Disagreement, Kind, Tier, ToolAnnotations
from ..candidates import Candidate

_R3_AND_ABOVE = {"R3", "R4", "R5"}


def extract(annotations: ToolAnnotations | None) -> list[Candidate]:
    """The escalating half: ``destructiveHint: true`` establishes kind
    ``destructive`` and a floor of R3 (Amendment 2 §7). No other declared value
    produces a candidate — ``readOnlyHint: true`` is a claim of safety, and safety
    claims are checked, not counted."""
    if annotations is None or annotations.destructive_hint is not True:
        return []
    return [
        Candidate(
            signal="declared_annotations",
            tier="R3",
            evidence=(
                "server declares destructiveHint: true — a claim against interest, "
                "trusted as a floor of R3"
            ),
            rule=None,
            kinds=frozenset({"destructive"}),
        )
    ]


def find_disagreements(
    annotations: ToolAnnotations | None, inferred_tier: Tier, kinds: list[Kind] | None = None
) -> list[Disagreement]:
    """Compare declared annotations against an already-decided inferred tier.

    Takes the tier and kinds as already resolved by :mod:`classify.combine` — this
    function never computes a tier itself, only reports where a declaration and
    that tier disagree. Only declared-safer-than-inferred is ever a disagreement;
    a server over-declaring its own risk costs nothing and is handled by
    :func:`extract`.
    """
    if annotations is None:
        return []

    disagreements: list[Disagreement] = []
    resolved_kinds = kinds or []

    if annotations.read_only_hint is True and inferred_tier in _R3_AND_ABOVE:
        if "code_exec" in resolved_kinds:
            # Rule H: the highest-severity disagreement the taxonomy defines.
            reading = (
                "The server declares read-only a tool that executes caller-supplied "
                "code — the highest-severity disagreement the taxonomy defines."
            )
        else:
            reading = "The server claims safety its schema does not support."
        disagreements.append(
            Disagreement(
                annotation="readOnlyHint",
                declared=True,
                inferred_tier=inferred_tier,
                reading=reading,
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
