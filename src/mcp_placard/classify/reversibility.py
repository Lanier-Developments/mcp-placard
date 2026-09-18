"""Rule D's reversibility confidence state.

`docs/TAXONOMY.md`, Rule D: a scanner that never invokes a tool cannot verify at
scan time whether revision history exists, so the tier itself no longer encodes a
binary reversible/irreversible guess. Every tool at R3 or above instead carries an
explicit confidence state, computed from the same shared traversal
(:func:`~mcp_placard.classify.schema_walk.walk_schema`) every other schema-shape
signal uses — proving the walker is shared across signal classes, not
reimplemented per rule.

Amendment 2 §6 revised the evidence list after the first real-server batch found 0
of 26 tools reaching ``verified`` and 4 reaching ``asserted`` on a proxy that did not
support the inference:

* ``verified`` gains ``sha`` with a content-carrying sibling (GitHub's Contents API
  optimistic-concurrency idiom). ``dryRun`` and ``commitId`` were considered and
  rejected.
* ``asserted`` no longer comes from ``idempotentHint: true`` — an idempotent delete
  is not a reversible one. It now comes from description evidence that the server
  retains recoverable state.
* ``unverifiable`` becoming the common case is the honest outcome. It is what the
  scanner actually knows.
"""

from __future__ import annotations

import re
from typing import Any

from ..manifest.models import Reversibility
from .schema_walk import TraversalStatus, walk_schema
from .signals.schema_shape import has_guarded_write_token

JsonSchema = dict[str, Any]

ASSERTED_KEYWORDS = ("version", "revision", "history", "trash", "recycle", "restore", "undo")
"""Amendment 2 §6: description evidence that the server retains recoverable state.
Matched at a word start, so ``versions`` and ``restored`` count and ``diversion``
does not."""

_ASSERTED_PATTERN = re.compile(r"\b(" + "|".join(ASSERTED_KEYWORDS) + r")")


def compute(input_schema: JsonSchema, description: str | None) -> Reversibility:
    """Compute the reversibility confidence state for one tool.

    Callers only invoke this once a tool's tier is already known to be R3 or
    above — reversibility is not a meaningful question below that, and this
    function does not itself check the tier.
    """
    result = walk_schema(input_schema)
    if result.status is not TraversalStatus.COMPLETE:
        return "unverifiable"

    if has_guarded_write_token(result.properties):
        return "verified"

    if description and _ASSERTED_PATTERN.search(description.lower()):
        return "asserted"

    return "unverifiable"
