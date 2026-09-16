"""Traverse a tool's input schema and yield every reachable property.

The shared utility every schema-shape signal consumes (AGENTS.md, "Risk Taxonomy";
`docs/TAXONOMY.md` Rule G). Rule A's caller-influenced outbound targets, Rule C's
communication-target fields, and Rule D's concurrency tokens all evade detection
identically if matching stops at the top level — so no signal extractor implements
its own field matching. They all call :func:`walk_schema` instead.

Traversal descends through nested objects (``properties``), arrays of objects
(``items``), and ``$ref`` / ``allOf`` / ``anyOf`` / ``oneOf`` composition. A ``$ref``
resolves only against the schema's own ``#/...`` document — an external reference is
never fetched, consistent with AGENTS.md's "never dereference scanned content."

Paths are rendered as real JSON Pointers (RFC 6901: ``/properties/foo/items/...``),
which is the literal reading of "the finding cites the full JSON-pointer path" in the
Phase 2 brief. The brief's own illustrative prose (``input.notification.targets[0]``)
is informal shorthand for "a nested path," not a distinct syntax to reproduce — a
report renderer is free to prettify a JSON Pointer for display, but the pointer
itself is what this module produces and what a finding cites as evidence.

Rule G's fail-closed clause is load-bearing: a schema too complex or too indirect to
traverse is a schema whose safety cannot be established. Traversal stops at the
first depth-cap breach, ``$ref`` cycle, or unresolvable ``$ref`` and reports that
failure rather than the properties collected so far — the caller treats *any*
non-``complete`` status as grounds to classify the whole tool as unconstrained,
so a partial property list would be misleading, not merely incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

JsonSchema = dict[str, Any]

MAX_DEPTH = 12
"""Recursion budget for one schema. Generous for any realistic tool input schema —
real schemas rarely nest past 4-5 levels — and finite by design, the same trade the
transport layer's ``MAX_PAGES`` budget makes for a paginated listing."""


class TraversalStatus(StrEnum):
    """The outcome of walking one schema. Only :attr:`COMPLETE` permits grading the
    schema on what was found; every other value means the schema itself, not any
    property inside it, is the evidence."""

    COMPLETE = "complete"
    DEPTH_EXCEEDED = "depth_exceeded"
    CYCLE_DETECTED = "cycle_detected"
    UNRESOLVABLE_REF = "unresolvable_ref"


@dataclass(frozen=True)
class SchemaProperty:
    """One property reachable while traversing an input schema."""

    pointer: str
    """JSON Pointer (RFC 6901) to this property's own subschema, e.g.
    ``/properties/notification/properties/targets/items/properties/webhook_url``."""

    name: str
    """The property's own key — the last path segment, for convenience."""

    subschema: JsonSchema
    """This property's own schema fragment, exactly as declared."""


@dataclass(frozen=True)
class TraversalResult:
    """The complete output of :func:`walk_schema`."""

    properties: list[SchemaProperty]
    """Every property found before traversal stopped. Only meaningful when
    ``status`` is :attr:`TraversalStatus.COMPLETE` — a fail-closed caller must not
    grade a schema on a partial property list."""

    status: TraversalStatus
    detail: str | None = None
    """Human-readable specifics for a non-complete status — which ``$ref`` could not
    be resolved, for instance. ``None`` when ``status`` is ``complete``."""


def _pointer_escape(segment: str) -> str:
    """Escape one JSON Pointer reference-token per RFC 6901 (``~`` then ``/``)."""
    return segment.replace("~", "~0").replace("/", "~1")


def _resolve_ref(root: JsonSchema, ref: str) -> JsonSchema | None:
    """Resolve a ``$ref`` against the schema's own document only.

    Anything other than a local fragment (``#/...``) is treated as unresolvable —
    this scanner never fetches anything a scanned schema references, the same rule
    that governs every other kind of scanned content.
    """
    if not ref.startswith("#/"):
        return None
    node: Any = root
    for raw_segment in ref[2:].split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or segment not in node:
            return None
        node = node[segment]
    return node if isinstance(node, dict) else None


def walk_schema(root_schema: JsonSchema, *, max_depth: int = MAX_DEPTH) -> TraversalResult:
    """Traverse ``root_schema`` and collect every property it reaches.

    Depth-first, so a fail-closed status is discovered as soon as possible and
    traversal stops there rather than continuing to explore siblings that would
    otherwise look safe.
    """
    properties: list[SchemaProperty] = []
    active_refs: set[str] = set()
    outcome: tuple[TraversalStatus, str | None] = (TraversalStatus.COMPLETE, None)

    def walk(schema: Any, pointer: str, depth: int) -> bool:
        """Return ``True`` to keep going, ``False`` once ``outcome`` is decided."""
        nonlocal outcome

        if depth > max_depth:
            outcome = (TraversalStatus.DEPTH_EXCEEDED, f"depth exceeded at {pointer or '/'!r}")
            return False
        if not isinstance(schema, dict):
            return True

        if "$ref" in schema:
            ref = schema["$ref"]
            if not isinstance(ref, str):
                outcome = (
                    TraversalStatus.UNRESOLVABLE_REF,
                    f"non-string $ref at {pointer or '/'!r}",
                )
                return False
            if ref in active_refs:
                outcome = (TraversalStatus.CYCLE_DETECTED, f"$ref cycle through {ref!r}")
                return False
            target = _resolve_ref(root_schema, ref)
            if target is None:
                outcome = (TraversalStatus.UNRESOLVABLE_REF, f"cannot resolve {ref!r}")
                return False
            active_refs.add(ref)
            try:
                return walk(target, pointer, depth + 1)
            finally:
                active_refs.discard(ref)

        for keyword in ("allOf", "anyOf", "oneOf"):
            branches = schema.get(keyword)
            if isinstance(branches, list):
                for index, branch in enumerate(branches):
                    if not walk(branch, f"{pointer}/{keyword}/{index}", depth + 1):
                        return False

        props = schema.get("properties")
        if isinstance(props, dict):
            for name, subschema in props.items():
                if not isinstance(subschema, dict):
                    continue
                prop_pointer = f"{pointer}/properties/{_pointer_escape(name)}"
                properties.append(
                    SchemaProperty(pointer=prop_pointer, name=name, subschema=subschema)
                )
                if not walk(subschema, prop_pointer, depth + 1):
                    return False

        items = schema.get("items")
        if isinstance(items, dict):
            if not walk(items, f"{pointer}/items", depth + 1):
                return False
        elif isinstance(items, list):
            for index, item_schema in enumerate(items):
                if not walk(item_schema, f"{pointer}/items/{index}", depth + 1):
                    return False

        return True

    walk(root_schema, "", 0)
    status, detail = outcome
    return TraversalResult(properties=properties, status=status, detail=detail)
