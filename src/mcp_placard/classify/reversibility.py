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
support the inference; Amendment 3 §3.3 tightened ``asserted`` again after the only
match in the corrected batch was ``browser_navigate_back``'s "previous page in
history":

* ``verified`` gains ``sha`` with a content-carrying sibling (GitHub's Contents API
  optimistic-concurrency idiom). ``dryRun`` and ``commitId`` were considered and
  rejected.
* ``asserted`` no longer comes from ``idempotentHint: true`` — an idempotent delete
  is not a reversible one. It comes from a closed list of *phrases* claiming
  recoverable state; bare ``history`` and bare ``version`` are not on it.
* ``unverifiable`` becoming the common case is the honest outcome. It is what the
  scanner actually knows. Standing decision (Amendment 3 §3.3): if ``asserted`` is
  still empty after a document-management server has been scanned, the state is
  deleted then — not before.
"""

from __future__ import annotations

import re
from typing import Any

from ..manifest.models import Reversibility
from .schema_walk import TraversalStatus, walk_schema
from .signals.schema_shape import has_guarded_write_token

JsonSchema = dict[str, Any]

ASSERTED_PHRASES = (
    "version history",
    "revision history",
    "previous version",
    "restore",
    "undo",
    "trash",
    "recycle bin",
    "soft delete",
    "recoverable",
)
"""Amendment 3 §3.3: the closed phrase list. Matched at a word start, so
``restored``, ``undoable``, and ``previous versions`` count and ``diversion`` does
not."""

NEGATIONS = ("cannot be", "can't be", "can not be", "not", "no", "without", "never", "irreversibly")
"""Amendment 3 §3.3's negation guard, as ratified: a phrase directly preceded —
within two words — by one of these is a claim *against* recoverability ("this
cannot be undone", the standing ``delete_workspace`` example) and is not evidence.
A guard against the obvious inversion, not a negation parser. Do not extend the
window, this list, or the matching without a real false positive from a real server
to point at; ``unverifiable`` is the fail-closed value and already the common case."""

_PHRASE = re.compile(r"\b(" + "|".join(re.escape(p) for p in ASSERTED_PHRASES) + r")")
_NEGATED = re.compile(
    r"\b(?:" + "|".join(re.escape(n) for n in NEGATIONS) + r")\s+(?:\w+\s+){0,2}$"
)


def _claims_recoverable_state(description: str) -> bool:
    lowered = description.lower()
    for match in _PHRASE.finditer(lowered):
        preceding = lowered[: match.start()]
        if not _NEGATED.search(preceding):
            return True
    return False


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

    if description and _claims_recoverable_state(description):
        return "asserted"

    return "unverifiable"
