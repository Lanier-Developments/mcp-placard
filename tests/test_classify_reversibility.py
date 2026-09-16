"""Rule D's reversibility confidence state: ``verified`` / ``asserted`` /
``unverifiable``. One fixture per state, per the Phase 2 brief's additional
fixture requirement.
"""

from __future__ import annotations

from mcp_placard.classify.reversibility import compute
from mcp_placard.manifest.models import ToolAnnotations


def test_a_concurrency_token_anywhere_is_verified() -> None:
    schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}, "if_match": {"type": "string"}},
    }
    assert compute(schema, None) == "verified"


def test_a_nested_concurrency_token_is_still_verified() -> None:
    """Proves the walker is shared across signal classes: Rule D's evidence is
    found by the same traversal Rule A/C use, not reimplemented."""
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "options": {"type": "object", "properties": {"if_match": {"type": "string"}}},
        },
    }
    assert compute(schema, None) == "verified"


def test_a_declared_idempotent_hint_with_no_token_is_asserted() -> None:
    schema = {"type": "object", "properties": {"id": {"type": "string"}}}
    annotations = ToolAnnotations(idempotent_hint=True)
    assert compute(schema, annotations) == "asserted"


def test_no_token_and_no_claim_is_unverifiable() -> None:
    schema = {"type": "object", "properties": {"path": {"type": "string"}}}
    assert compute(schema, None) == "unverifiable"


def test_idempotent_hint_false_is_not_an_assertion() -> None:
    schema = {"type": "object", "properties": {"path": {"type": "string"}}}
    annotations = ToolAnnotations(idempotent_hint=False)
    assert compute(schema, annotations) == "unverifiable"


def test_a_traversal_failure_is_unverifiable_not_a_guess() -> None:
    """Rule G's fail-closed clause applies here too: a schema too indirect to
    traverse cannot evidence *either* `verified` or `asserted`."""
    schema = {"type": "object", "properties": {"target": {"$ref": "#/$defs/Missing"}}}
    assert compute(schema, None) == "unverifiable"
