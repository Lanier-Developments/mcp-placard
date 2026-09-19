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

Amendment 2 changed two rules here after the first real-server batch:

* **Rule D's destination clause** now needs the tool to be *established as writing*
  before an unguarded path forces R5 — a ``path`` on ``read_file`` is a source, and
  the rule was never about sources. Two of its three conditions are schema-local and
  decided here; the third ("an independent signal places the tool at R3 or above")
  crosses signal boundaries and is resolved by the orchestrator through
  :func:`deferred_destination_clause`.
* **Rule C's ``to``** is exempt when a sibling ``from`` exists and no content-carrying
  sibling does — edges and ranges have a ``from``; messages have a body.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
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

COMMUNICATION_CONTENT_FIELDS = frozenset({"body", "message", "text", "subject", "content", "html"})
"""Rule C's exemption discriminator (Amendment 2 §2). ``to`` with a sibling ``from``
is an edge or a range *unless* one of these travels with it — ``send_email(from, to,
subject, body)`` must still be R4, and content is what separates it from
``create_relation(from, to, relationType)``. Applies to ``to`` only."""

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
parameter, anywhere in the schema. Also the evidence that exempts an unconstrained
destination path from Rule D's R5-forcing clause. See :func:`has_guarded_write_token`
for the ``sha``-with-content form Amendment 2 §6 added."""

GUARDED_SHA_FIELD = "sha"
"""Amendment 2 §6: ``sha`` counts as a concurrency token only when a content-carrying
sibling sits in the same object — GitHub's Contents API idiom. ``sha`` alone is a
plain commit reference on read tools and evidences nothing."""

CONTENT_CARRYING_FIELDS = frozenset({"content", "contents", "data", "text", "edits"})
"""Rule D, condition 2 (Amendment 2 §1, list per Amendment 3 §3.1): a path with one of
these as a sibling in the same object is a write destination. Also kind ``write``
evidence on its own. ``body`` is deliberately absent — it names a message or comment
body far more often than a file body (GitHub's ``create_pull_request_review`` has
``comments[].{path, body}`` where ``path`` is what the comment is *about*), so it
lives in :data:`COMMUNICATION_CONTENT_FIELDS` only. A server that does use ``body``
for file content loses condition 2 alone; a write verb still reaches it through
condition 1 and a destination-named field through condition 3."""

PATH_LIKE_FIELDS = frozenset({"path"})
"""Rule D's path-like parameter, kept to the exact name the taxonomy's fixtures use.
Direction-neutral: a ``path`` is a destination only under one of Rule D's three
conditions, never on its own."""

DESTINATION_NAMED_FIELDS = frozenset(
    {"destination", "dest", "target_path", "output_path", "to_path", "new_path"}
)
"""Rule D, condition 3 (Amendment 2 §1): the parameter name itself denotes a
destination. ``move_file(source, destination)`` is R5 on this alone, absent a
concurrency token."""

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


def is_unconstrained_string(subschema: JsonSchema) -> bool:
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


def parent_pointer(pointer: str) -> str:
    """The JSON Pointer of the object a property belongs to.

    ``/properties/relations/items/properties/to`` → ``/properties/relations/items``.
    "Sibling in the same object" (Rules C and D) means "shares this parent."
    Properties reached through different ``allOf``/``anyOf`` branches have different
    parents and are deliberately not siblings — a schema may present two call shapes,
    and a field in one says nothing about a field in the other.
    """
    head, _sep, _name = pointer.rpartition("/properties/")
    return head


def sibling_names(properties: list[SchemaProperty]) -> dict[str, set[str]]:
    """Group every property name by its parent object's pointer."""
    groups: dict[str, set[str]] = defaultdict(set)
    for prop in properties:
        groups[parent_pointer(prop.pointer)].add(prop.name)
    return groups


def has_guarded_write_token(properties: list[SchemaProperty]) -> bool:
    """Rule D's "concurrency token present" test, shared with ``reversibility``.

    True on any :data:`CONCURRENCY_TOKEN_FIELDS` member anywhere in the schema, or on
    a :data:`GUARDED_SHA_FIELD` with a content-carrying sibling in its own object.
    """
    siblings = sibling_names(properties)
    for prop in properties:
        if prop.name in CONCURRENCY_TOKEN_FIELDS:
            return True
        if prop.name == GUARDED_SHA_FIELD and (
            siblings[parent_pointer(prop.pointer)] & CONTENT_CARRYING_FIELDS
        ):
            return True
    return False


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
        kinds=frozenset({"egress"}),
    )


@dataclass(frozen=True)
class _Analysis:
    candidates: list[Candidate]
    deferred: Candidate | None
    status: TraversalStatus


def _analyze(input_schema: JsonSchema) -> _Analysis:
    result = walk_schema(input_schema)

    if result.status is not TraversalStatus.COMPLETE:
        return _Analysis(
            [
                Candidate(
                    signal="schema_shape",
                    tier=FAIL_CLOSED_TIER,
                    evidence=f"schema traversal did not complete: {result.status.value}"
                    + (f" ({result.detail})" if result.detail else ""),
                    rule="Rule G",
                    kinds=frozenset({"egress"}),
                )
            ],
            None,
            result.status,
        )

    candidates: list[Candidate] = []
    deferred: Candidate | None = None
    siblings = sibling_names(result.properties)
    guarded = has_guarded_write_token(result.properties)
    has_unconstrained_free_text = False
    has_steering_field = False

    for prop in result.properties:
        own_siblings = siblings[parent_pointer(prop.pointer)] - {prop.name}

        if prop.name in SENSITIVITY_EXPANDING_FIELDS:
            candidates.append(
                Candidate(
                    signal="schema_shape",
                    tier="R2",
                    evidence=f"{prop.pointer}: flag widens the sensitivity of what is returned",
                    rule=None,
                    kinds=frozenset({"read_sensitive"}),
                )
            )

        if prop.name in COMMUNICATION_TARGET_FIELDS:
            exempt = (
                prop.name == "to"
                and "from" in own_siblings
                and not (own_siblings & COMMUNICATION_CONTENT_FIELDS)
            )
            if not exempt:
                candidates.append(
                    Candidate(
                        signal="schema_shape",
                        tier="R4",
                        evidence=(
                            f"{prop.pointer}: recognized communication-target field {prop.name!r}"
                        ),
                        rule="Rule C",
                        kinds=frozenset({"egress"}),
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
                    kinds=frozenset({"destructive"}),
                )
            )

        if prop.name in CONTENT_CARRYING_FIELDS:
            candidates.append(
                Candidate(
                    signal="schema_shape",
                    tier="R1",
                    evidence=f"{prop.pointer}: content-carrying field {prop.name!r}",
                    rule=None,
                    kinds=frozenset({"write"}),
                )
            )

        is_path_like = prop.name in PATH_LIKE_FIELDS or prop.name in DESTINATION_NAMED_FIELDS
        if is_path_like and prop.subschema.get("type") == "string":
            pattern = prop.subschema.get("pattern")
            unconstrained = not (isinstance(pattern, str) and pattern)
            if unconstrained and not guarded:
                content_siblings = sorted(own_siblings & CONTENT_CARRYING_FIELDS)
                if prop.name in DESTINATION_NAMED_FIELDS:
                    candidates.append(
                        Candidate(
                            signal="schema_shape",
                            tier="R5",
                            evidence=(
                                f"{prop.pointer}: destination-named parameter {prop.name!r}, "
                                "unconstrained, no concurrency token present anywhere in the "
                                "schema"
                            ),
                            rule="Rule D",
                            kinds=frozenset({"write"}),
                        )
                    )
                elif content_siblings:
                    candidates.append(
                        Candidate(
                            signal="schema_shape",
                            tier="R5",
                            evidence=(
                                f"{prop.pointer}: unconstrained destination path with "
                                f"content-carrying sibling {content_siblings[0]!r}, no "
                                "concurrency token present anywhere in the schema"
                            ),
                            rule="Rule D",
                            kinds=frozenset({"write"}),
                        )
                    )
                elif deferred is None:
                    deferred = Candidate(
                        signal="schema_shape",
                        tier="R5",
                        evidence=(
                            f"{prop.pointer}: unconstrained path, no concurrency token present "
                            "anywhere in the schema, on a tool an independent signal already "
                            "established as writing"
                        ),
                        rule="Rule D",
                        kinds=frozenset({"write"}),
                    )

        if is_unconstrained_string(prop.subschema):
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

    return _Analysis(candidates, deferred, result.status)


def extract(input_schema: JsonSchema) -> tuple[list[Candidate], TraversalStatus]:
    """Extract schema-shape candidates for one tool's input schema.

    Returns the candidates alongside the traversal status that produced them, so a
    caller building a :class:`~mcp_placard.manifest.models.ToolClassification` can
    cite the traversal outcome even when it is not ``complete``.
    """
    analysis = _analyze(input_schema)
    return analysis.candidates, analysis.status


def deferred_destination_clause(input_schema: JsonSchema) -> Candidate | None:
    """Rule D, condition 1 — the half of the destination clause this extractor
    cannot decide alone.

    An unconstrained, unguarded path that is neither destination-named nor
    accompanied by a content-carrying sibling forces R5 only if *an independent
    signal* (a write verb, ``destructiveHint: true``, another schema rule) already
    places the tool at R3 or above. Extractors do not see each other's output, so
    this returns the would-be candidate and lets the orchestrator apply the
    condition after every signal has run. ``None`` when no such path exists.
    """
    return _analyze(input_schema).deferred
