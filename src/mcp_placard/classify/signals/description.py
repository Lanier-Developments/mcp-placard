"""Description-text signal extraction.

`docs/TAXONOMY.md`: "the weakest signal for tiering, and the *only* thing that
Phase 3's injection heuristics care about... the last thing that should move a
tier." This module stays narrowly scoped to the one boundary the taxonomy says
schema shape *cannot* resolve alone — R0 vs R1 on an empty or closed schema, where
the discriminator is "whether the response is a property of the software or of the
tenant" — plus the analogous R1-vs-R2 domain-sensitivity boundary. It is not a
general prose-risk classifier, and per the Phase 2 brief, injection detection is out
of scope entirely: this module never looks for instructions in a description, only
for the same handful of domain nouns a human reviewer would skim for.
"""

from __future__ import annotations

from ..candidates import Candidate

TENANT_DATA_KEYWORDS = (
    "this tenant",
    "this workspace",
    "this deployment",
    "this organization",
    "your account",
    "your workspace",
)
"""`docs/TAXONOMY.md`'s R0 near-miss, `list_collections`: an empty schema whose
response is nonetheless "real data about a real deployment." Deliberately
multi-word phrases, not the bare nouns — ``describe_server``'s R0 worked example
legitimately says "configured workspace root" without describing tenant data, and
a bare ``"workspace"`` keyword would misclassify it. "*This* workspace" names an
instance; "*a* workspace" or "*the* workspace root" merely describes one."""

SENSITIVE_DOMAIN_KEYWORDS = (
    "mail",
    "inbox",
    "email",
    "calendar",
    "correspondence",
    "directory",
    "contact",
    "employee",
    "roster",
)
"""R2's archetype domains — mail, calendar, directory — per the R2 worked examples.
A read whose description names one of these is read-*sensitive*, not merely
read-scoped, independent of what its schema alone would suggest."""


def extract(description: str | None) -> list[Candidate]:
    """Extract description-text candidates for one tool.

    Returns at most one candidate: this signal exists to break one specific tie
    (does an otherwise-inert schema actually return tenant data, or per-domain
    sensitive data), not to build an independent case for every tier.
    """
    if not description:
        return []
    lowered = description.lower()

    for keyword in SENSITIVE_DOMAIN_KEYWORDS:
        if keyword in lowered:
            return [
                Candidate(
                    signal="description_text",
                    tier="R2",
                    evidence=f"description names a sensitive domain ({keyword!r})",
                    rule=None,
                )
            ]

    for keyword in TENANT_DATA_KEYWORDS:
        if keyword in lowered:
            return [
                Candidate(
                    signal="description_text",
                    tier="R1",
                    evidence=(
                        f"description indicates per-tenant data ({keyword!r}), "
                        "not a static capability list"
                    ),
                    rule=None,
                )
            ]

    return []
