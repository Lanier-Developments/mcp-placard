"""Rule D's reversibility confidence state: ``verified`` / ``asserted`` /
``unverifiable``. One fixture per state, per the Phase 2 brief's additional
fixture requirement, revised for Amendment 2 §6: ``sha`` with a content sibling is
``verified``; ``asserted`` comes from description evidence of retained state, no
longer from ``idempotentHint``.
"""

from __future__ import annotations

from mcp_placard.classify.reversibility import compute


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


def test_a_description_claiming_retained_state_is_asserted() -> None:
    schema = {"type": "object", "properties": {"id": {"type": "string"}}}
    assert compute(schema, "Update the record. Previous versions are kept in history.") == (
        "asserted"
    )


def test_an_idempotent_hint_no_longer_asserts_anything() -> None:
    """Amendment 2 §6: an idempotent delete is not a reversible one. The annotation
    is not consulted at all — the signature no longer takes it."""
    schema = {"type": "object", "properties": {"id": {"type": "string"}}}
    assert compute(schema, "Delete multiple entities from the graph.") == "unverifiable"


def test_sha_with_a_content_sibling_is_verified() -> None:
    """GitHub's Contents API idiom: ``sha`` of the file being replaced, next to
    ``content``."""
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "sha": {"type": "string"},
        },
    }
    assert compute(schema, "Create or update a single file.") == "verified"


def test_sha_without_a_content_sibling_is_not_a_token() -> None:
    """``sha`` alone is a plain commit reference on read tools."""
    schema = {"type": "object", "properties": {"sha": {"type": "string"}}}
    assert compute(schema, "Show the commit.") == "unverifiable"


def test_sha_and_content_in_different_objects_do_not_pair() -> None:
    schema = {
        "type": "object",
        "properties": {
            "sha": {"type": "string"},
            "file": {"type": "object", "properties": {"content": {"type": "string"}}},
        },
    }
    assert compute(schema, None) == "unverifiable"


def test_no_token_and_no_claim_is_unverifiable() -> None:
    schema = {"type": "object", "properties": {"path": {"type": "string"}}}
    assert compute(schema, None) == "unverifiable"


def test_a_keyword_inside_another_word_does_not_assert() -> None:
    """Word-start matching: ``diversion`` is not ``version``."""
    schema = {"type": "object", "properties": {"path": {"type": "string"}}}
    assert compute(schema, "Create a diversion for the traffic.") == "unverifiable"


def test_a_traversal_failure_is_unverifiable_not_a_guess() -> None:
    """Rule G's fail-closed clause applies here too: a schema too indirect to
    traverse cannot evidence *either* `verified` or `asserted`."""
    schema = {"type": "object", "properties": {"target": {"$ref": "#/$defs/Missing"}}}
    assert compute(schema, None) == "unverifiable"
