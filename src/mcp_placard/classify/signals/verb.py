"""Tool-name-verb signal extraction.

`docs/TAXONOMY.md`: "cheap and usually honest, trivially renameable." Deliberately
the weakest tier-raising signal here, by design rather than omission — the R5
near-miss fixture is explicit that keying on a verb alone is wrong: *"Near-miss (R3,
not R5): `rotate_display_name`. Same verb, ordinary domain, trivially reversible...
A classifier that keys on `rotate_` alone fails this case."* A verb only raises a
tier when paired with a domain noun the verb alone cannot supply — never on its own.

Verbs are matched as whole tokens anywhere in the split name, snake and camel
(Phase 2.1 deliverable 8). The original prefix match meant ``git_add`` never matched
``add_`` and every namespaced mutation verb escaped — a bug, not a gap.
"""

from __future__ import annotations

import re

from ..candidates import Candidate

DESTRUCTIVE_VERBS = frozenset({"delete", "purge", "remove", "reset"})
"""Corroborating-only: a weak R3 candidate carrying kind ``destructive``.
`docs/TAXONOMY.md`'s R5 delete/purge examples all carry independent schema-shape
evidence (a `force` boolean, a `const` confirmation) that reaches R5 on its own —
verb alone never claims R5 here."""

WRITE_VERBS = frozenset(
    {
        "write",
        "create",
        "update",
        "set",
        "add",
        "put",
        "merge",
        "push",
        "checkout",
        "commit",
        "fork",
        "move",
        "rename",
    }
)
"""R3 corroborating evidence carrying kind ``write``: `docs/TAXONOMY.md`'s R3 tier is
"creates or mutates ... reversibly," and schema shape alone cannot tell a mutation
from a read when the mutated content is itself unconstrained free text —
`write_note(path, content)`'s `content` field looks, to Rule B, exactly like
`search_documents`'s `query`. The verb is what supplies "this is a write." The second
row is the set the 2026-09-17 real-server batch found missing."""

ROTATE_VERBS = frozenset({"rotate", "revoke"})
"""Rule-D-adjacent: `rotate`/`revoke` plus a credential-domain noun in the tool
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

_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
_SEPARATORS = re.compile(r"[_\-./:\s]+")


def name_tokens(tool_name: str) -> list[str]:
    """Split a tool name into lowercase tokens at snake, kebab, dotted, and camel
    boundaries: ``createOrUpdateFile`` → ``["create", "or", "update", "file"]``."""
    spaced = _CAMEL_BOUNDARY.sub(r"\1_\2", tool_name)
    return [token for token in _SEPARATORS.split(spaced.lower()) if token]


def _first_match(tokens: list[str], verbs: frozenset[str]) -> str | None:
    for token in tokens:
        if token in verbs:
            return token
    return None


def extract(tool_name: str) -> list[Candidate]:
    """Extract verb-based candidates for one tool's name.

    Returns at most one candidate — this signal never stacks multiple weak votes
    for the same tool, since none of its votes are strong enough to be worth
    layering.
    """
    tokens = name_tokens(tool_name)
    lowered = tool_name.lower()

    rotate_verb = _first_match(tokens, ROTATE_VERBS)
    if rotate_verb is not None and any(noun in lowered for noun in CREDENTIAL_DOMAIN_NOUNS):
        return [
            Candidate(
                signal="tool_name_verb",
                tier="R5",
                evidence=(
                    f"tool name {tool_name!r}: rotate/revoke verb over a credential-domain noun"
                ),
                rule=None,
                kinds=frozenset({"destructive"}),
            )
        ]

    # A rotate/revoke verb with no credential-domain noun (`rotate_display_name`)
    # falls through to the same R3 corroboration as any other mutating verb below
    # — it is a write, not nothing, just not the R5 the credential case is.
    if (verb := _first_match(tokens, DESTRUCTIVE_VERBS)) is not None:
        return [_corroborating_r3(tool_name, verb, "destructive")]
    if (verb := _first_match(tokens, WRITE_VERBS | ROTATE_VERBS)) is not None:
        return [_corroborating_r3(tool_name, verb, "write")]

    return []


def _corroborating_r3(tool_name: str, verb: str, kind: str) -> Candidate:
    return Candidate(
        signal="tool_name_verb",
        tier="R3",
        evidence=f"tool name {tool_name!r}: {verb!r} verb, corroborating only",
        rule=None,
        kinds=frozenset({kind}),  # type: ignore[arg-type]
    )
