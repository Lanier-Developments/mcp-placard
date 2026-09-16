"""Tool-name-verb signal extraction.

`docs/TAXONOMY.md`: "cheap and usually honest, trivially renameable." Deliberately
the weakest tier-raising signal here, by design rather than omission — the R5
near-miss fixture is explicit that keying on a verb alone is wrong: *"Near-miss (R3,
not R5): `rotate_display_name`. Same verb, ordinary domain, trivially reversible...
A classifier that keys on `rotate_` alone fails this case."* A verb only raises a
tier when paired with a domain noun the verb alone cannot supply — never on its own.
"""

from __future__ import annotations

from ..candidates import Candidate

DESTRUCTIVE_VERBS = ("delete_", "purge_", "remove_")
"""Corroborating-only: a weak R3 candidate. `docs/TAXONOMY.md`'s R5 delete/purge
examples all carry independent schema-shape evidence (a `force` boolean, a `const`
confirmation) that reaches R5 on its own — verb alone never claims R5 here."""

WRITE_VERBS = ("write_", "create_", "update_", "set_", "add_", "put_")
"""R3 corroborating evidence: `docs/TAXONOMY.md`'s R3 tier is "creates or mutates
... reversibly," and schema shape alone cannot tell a mutation from a read when
the mutated content is itself unconstrained free text — `write_note(path,
content)`'s `content` field looks, to Rule B, exactly like `search_documents`'s
`query`. The verb is what supplies "this is a write," the same corroborating role
`DESTRUCTIVE_VERBS` plays for R3 on the destructive side."""

ROTATE_VERBS = ("rotate_", "revoke_")
"""Rule-D-adjacent: `rotate_`/`revoke_` plus a credential-domain noun in the tool
name is R5 (`rotate_api_credential`); the verb alone, on an ordinary domain
(`rotate_display_name`), is not. See `CREDENTIAL_DOMAIN_NOUNS` below."""

CREDENTIAL_DOMAIN_NOUNS = (
    "credential",
    "api_key",
    "apikey",
    "secret",
    "password",
    "access_key",
    "token",
)
"""Closed by design, mirroring Rule C's own field-list philosophy: a noun list
broad enough to catch "key" bare would also catch `rotate_display_name`'s
near-relatives and defeat the fixture that exists specifically to catch that."""


def _matches_prefix(name: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        if name.startswith(prefix):
            return prefix
    return None


def extract(tool_name: str) -> list[Candidate]:
    """Extract verb-based candidates for one tool's name.

    Returns at most one candidate — this signal never stacks multiple weak votes
    for the same tool, since none of its votes are strong enough to be worth
    layering.
    """
    lowered = tool_name.lower()

    rotate_prefix = _matches_prefix(lowered, ROTATE_VERBS)
    if rotate_prefix is not None and any(noun in lowered for noun in CREDENTIAL_DOMAIN_NOUNS):
        return [
            Candidate(
                signal="tool_name_verb",
                tier="R5",
                evidence=(
                    f"tool name {tool_name!r}: rotate/revoke verb over a credential-domain noun"
                ),
                rule=None,
            )
        ]

    # A rotate/revoke verb with no credential-domain noun (`rotate_display_name`)
    # falls through to the same R3 corroboration as any other mutating verb below
    # — it is a write, not nothing, just not the R5 the credential case is.
    for prefixes in (DESTRUCTIVE_VERBS, WRITE_VERBS, ROTATE_VERBS):
        if (prefix := _matches_prefix(lowered, prefixes)) is not None:
            return [_corroborating_r3(tool_name, prefix)]

    return []


def _corroborating_r3(tool_name: str, prefix: str) -> Candidate:
    return Candidate(
        signal="tool_name_verb",
        tier="R3",
        evidence=f"tool name {tool_name!r}: {prefix.rstrip('_')!r} verb, corroborating only",
        rule=None,
    )
