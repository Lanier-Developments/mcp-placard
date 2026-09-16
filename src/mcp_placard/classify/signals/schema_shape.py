"""Schema-shape signal extraction — Rules A, B, C, D, E, G.

`docs/TAXONOMY.md` calls this "the strongest signal, because it is the hardest to
fake while remaining functional." Every rule implemented here traverses the
*complete* input schema through :func:`~mcp_placard.classify.schema_walk.walk_schema`
(Rule G) rather than matching top-level property names — a `to` field three levels
inside an `allOf` branch is exactly as much a communication target as one at the
root.

Field-name recognition lists are explicit and closed by design, mirroring Rule C's
own stated philosophy: a heuristic over "fields that might be dangerous" pulls in
false positives and empties the tier of meaning. Add a name to one of these sets
only as a deliberate, reviewed change.
"""

from __future__ import annotations

from typing import Any

from ...manifest.models import Tier
from ..candidates import Candidate
from ..patterns import is_recognized_host_pinning_form
from ..schema_walk import SchemaProperty, TraversalStatus, walk_schema

JsonSchema = dict[str, Any]

COMMUNICATION_TARGET_FIELDS = frozenset(
    {
        "to",
        "cc",
        "bcc",
        "reply_to",
        "recipient",
        "recipients",
        "attendees",
        "webhook_url",
        "callback_url",
        "notify_url",
        "slack_channel",
        "channel",
        "phone",
        "sms_to",
    }
)
"""Rule C's closed allowlist. Any of these field names, found anywhere the walker
reaches, forces R4 regardless of the tool's verb — an external communication
target is egress operated by proxy."""

FORCE_BOOLEAN_FIELDS = frozenset(
    {"force", "overwrite", "recursive", "permanent", "purge", "skip_trash"}
)
"""Rule D: presence of one of these as a boolean the caller can set true forces R5
regardless of other signals — a required confirmation field raises confidence, but
these are the opposite of a confirmation: they widen or bypass a guard."""

CONCURRENCY_TOKEN_FIELDS = frozenset(
    {"if_match", "etag", "version", "expected_revision", "if_unmodified_since"}
)
"""Rule D's ``verified`` reversibility evidence: an optimistic-concurrency
parameter. Also the evidence that exempts an unconstrained destination path from
Rule D's other R5-forcing clause below."""

DESTINATION_PATH_FIELDS = frozenset({"path"})
"""Rule D's "destination path parameter" clause, deliberately narrow — see the
scope note in `docs/TAXONOMY.md`, Rule D: this forces R5 only when the path is
*also* unconstrained (no prefix pattern). A prefix-pinned path with no concurrency
token — the standing `write_note` R3 example — is not this clause; that tool's
`path` has a `pattern` and so never reaches this branch at all. Kept to the exact
name the taxonomy's own fixtures use rather than a broader guessed list, the same
discipline Rule C's field list applies."""

SENSITIVITY_EXPANDING_FIELDS = frozenset(
    {"include_secrets", "include_contact_details", "include_pii", "include_credentials"}
)
"""`docs/TAXONOMY.md`'s R1/R2 boundary: ``get_build_status`` plus `include_secrets`
is R2 where the bare tool was R1 — "the domain did not change; the sensitivity of
what comes back did." ``list_directory_users``'s `include_contact_details` is the
same shape: "the field that carries the tier." A closed list, not a `include_*`
prefix match — Rule C's own reasoning about why a broad heuristic empties the tier
of meaning applies here too: `include_archived` (`search_documents`) widens a
result set, not its sensitivity, and must not match."""

FAIL_CLOSED_TIER: Tier = "R4"
"""What a non-``complete`` traversal status resolves to (Rule G). Tied to Rule A's
own "unconstrained ⇒ caller-influenced outbound target ⇒ R4" language, since Rule G
names Rule A's and Rule C's outbound-target evasion as its primary motivating
concern for schemas too complex or indirect to fully traverse."""


def _is_unconstrained_string(subschema: JsonSchema) -> bool:
    """Rule B: a string with no ``enum`` and no restrictive ``pattern`` is free
    text — the thing that disqualifies R0 and, absent stronger evidence, floors a
    tool at R1."""
    if subschema.get("type") != "string":
        return False
    if "enum" in subschema or "const" in subschema:
        return False
    pattern = subschema.get("pattern")
    return not (isinstance(pattern, str) and pattern)


def _is_zero_steering(subschema: JsonSchema) -> bool:
    """Rule B's R0 eligibility bar: only a closed enum, a ``const``, or a boolean
    leaves a tool "cannot be steered." Everything else — a string, however tightly
    patterned, a number, an object, an array — is itself a parameter the caller
    supplies, which is R1 at minimum. `docs/TAXONOMY.md`'s `get_build_status`: a
    `pipeline_id` pinned to `^[a-z0-9-]{1,64}$` is not free text (Rule B does not
    flag it), but it is still "a constrained identifier into the server's own
    domain" — R1, not R0. R0 is reserved for schemas that offer no parameter at
    all, not merely a tightly-bounded one."""
    if subschema.get("type") == "boolean":
        return True
    return "enum" in subschema or "const" in subschema


def _is_url_shaped(prop: SchemaProperty) -> bool:
    return prop.name == "url" or prop.subschema.get("format") == "uri"


def _outbound_target_candidate(prop: SchemaProperty) -> Candidate:
    """Rule A / Rule E: a URL-shaped field is R4 egress unless its ``pattern``
    matches one of Rule E's recognized host-pinning forms."""
    pattern = prop.subschema.get("pattern")
    if isinstance(pattern, str) and is_recognized_host_pinning_form(pattern):
        return Candidate(
            signal="schema_shape",
            tier="R1",
            evidence=f"{prop.pointer}: host-pinned by a recognized pattern",
            rule="Rule E",
        )
    return Candidate(
        signal="schema_shape",
        tier="R4",
        evidence=f"{prop.pointer}: caller-influenced outbound target, no recognized host pin",
        rule="Rule A",
    )


def extract(input_schema: JsonSchema) -> tuple[list[Candidate], TraversalStatus]:
    """Extract schema-shape candidates for one tool's input schema.

    Returns the candidates alongside the traversal status that produced them, so a
    caller building a :class:`~mcp_placard.manifest.models.ToolClassification` can
    cite the traversal outcome even when it is not ``complete``.
    """
    result = walk_schema(input_schema)

    if result.status is not TraversalStatus.COMPLETE:
        return (
            [
                Candidate(
                    signal="schema_shape",
                    tier=FAIL_CLOSED_TIER,
                    evidence=f"schema traversal did not complete: {result.status.value}"
                    + (f" ({result.detail})" if result.detail else ""),
                    rule="Rule G",
                )
            ],
            result.status,
        )

    candidates: list[Candidate] = []
    has_concurrency_token = any(prop.name in CONCURRENCY_TOKEN_FIELDS for prop in result.properties)
    has_unconstrained_free_text = False
    has_steering_field = False

    for prop in result.properties:
        if prop.name in SENSITIVITY_EXPANDING_FIELDS:
            candidates.append(
                Candidate(
                    signal="schema_shape",
                    tier="R2",
                    evidence=f"{prop.pointer}: flag widens the sensitivity of what is returned",
                    rule=None,
                )
            )

        if prop.name in COMMUNICATION_TARGET_FIELDS:
            candidates.append(
                Candidate(
                    signal="schema_shape",
                    tier="R4",
                    evidence=f"{prop.pointer}: recognized communication-target field {prop.name!r}",
                    rule="Rule C",
                )
            )

        if _is_url_shaped(prop):
            candidates.append(_outbound_target_candidate(prop))

        if prop.name in FORCE_BOOLEAN_FIELDS and prop.subschema.get("type") == "boolean":
            candidates.append(
                Candidate(
                    signal="schema_shape",
                    tier="R5",
                    evidence=f"{prop.pointer}: {prop.name!r} is a boolean the caller can set true",
                    rule="Rule D",
                )
            )

        if prop.name in DESTINATION_PATH_FIELDS and prop.subschema.get("type") == "string":
            pattern = prop.subschema.get("pattern")
            unconstrained = not (isinstance(pattern, str) and pattern)
            if unconstrained and not has_concurrency_token:
                candidates.append(
                    Candidate(
                        signal="schema_shape",
                        tier="R5",
                        evidence=(
                            f"{prop.pointer}: unconstrained destination path, "
                            "no concurrency token present anywhere in the schema"
                        ),
                        rule="Rule D",
                    )
                )

        if _is_unconstrained_string(prop.subschema):
            has_unconstrained_free_text = True
        elif not _is_zero_steering(prop.subschema):
            has_steering_field = True

    if not candidates:
        if has_unconstrained_free_text:
            candidates.append(
                Candidate(
                    signal="schema_shape",
                    tier="R1",
                    evidence=(
                        "unconstrained free-text parameter present; "
                        "R0 requires a closed input surface"
                    ),
                    rule="Rule B",
                )
            )
        elif has_steering_field:
            candidates.append(
                Candidate(
                    signal="schema_shape",
                    tier="R1",
                    evidence=(
                        "a constrained parameter is present; R0 requires a fully "
                        "closed input surface (empty, or enum/const/boolean only)"
                    ),
                    rule="Rule B",
                )
            )
        else:
            candidates.append(
                Candidate(
                    signal="schema_shape",
                    tier="R0",
                    evidence="closed input schema: no free text, no recognized dangerous field",
                    rule="Rule B",
                )
            )

    return candidates, result.status
