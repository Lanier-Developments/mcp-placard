"""Rule D's reversibility confidence state.

`docs/TAXONOMY.md`, Rule D: a scanner that never invokes a tool cannot verify at
scan time whether revision history exists, so the tier itself no longer encodes a
binary reversible/irreversible guess. Every tool at R3 or above instead carries an
explicit confidence state, computed from the same shared traversal
(:func:`~mcp_placard.classify.schema_walk.walk_schema`) every other schema-shape
signal uses — proving the walker is shared across signal classes, not
reimplemented per rule.
"""

from __future__ import annotations

from typing import Any

from ..manifest.models import Reversibility, ToolAnnotations
from .schema_walk import TraversalStatus, walk_schema
from .signals.schema_shape import CONCURRENCY_TOKEN_FIELDS

JsonSchema = dict[str, Any]


def compute(input_schema: JsonSchema, annotations: ToolAnnotations | None) -> Reversibility:
    """Compute the reversibility confidence state for one tool's input schema.

    Callers only invoke this once a tool's tier is already known to be R3 or
    above — reversibility is not a meaningful question below that, and this
    function does not itself check the tier.
    """
    result = walk_schema(input_schema)
    if result.status is not TraversalStatus.COMPLETE:
        return "unverifiable"

    if any(prop.name in CONCURRENCY_TOKEN_FIELDS for prop in result.properties):
        return "verified"

    if annotations is not None and annotations.idempotent_hint is True:
        return "asserted"

    return "unverifiable"
