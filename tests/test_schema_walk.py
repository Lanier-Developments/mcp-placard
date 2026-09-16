"""The shared schema-traversal utility (Rule G).

Every schema-shape signal consumes :func:`walk_schema` rather than reimplementing
field matching, so correctness here is load-bearing for every rule that reads the
schema — Rule A, C, D, and the R0/R1 near-misses in `docs/TAXONOMY.md` all depend on
traversal reaching the same properties a signal extractor expects.
"""

from __future__ import annotations

from mcp_placard.classify.schema_walk import TraversalStatus, walk_schema


def _names(result) -> set[str]:  # type: ignore[no-untyped-def]
    return {prop.name for prop in result.properties}


def test_a_flat_schema_yields_its_top_level_properties() -> None:
    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE
    assert _names(result) == {"query", "limit"}


def test_pointers_are_real_json_pointers() -> None:
    schema = {"type": "object", "properties": {"url": {"type": "string"}}}
    result = walk_schema(schema)
    assert result.properties[0].pointer == "/properties/url"


def test_a_property_named_with_a_slash_or_tilde_is_escaped_in_its_pointer() -> None:
    """RFC 6901: ``~`` becomes ``~0`` and ``/`` becomes ``~1`` in a reference token."""
    schema = {"type": "object", "properties": {"a/b~c": {"type": "string"}}}
    result = walk_schema(schema)
    assert result.properties[0].pointer == "/properties/a~1b~0c"


def test_nested_objects_are_traversed() -> None:
    schema = {
        "type": "object",
        "properties": {
            "notification": {
                "type": "object",
                "properties": {"webhook_url": {"type": "string", "format": "uri"}},
            }
        },
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE
    assert "webhook_url" in _names(result)
    webhook = next(p for p in result.properties if p.name == "webhook_url")
    assert webhook.pointer == "/properties/notification/properties/webhook_url"


def test_arrays_of_objects_are_traversed_through_items() -> None:
    schema = {
        "type": "object",
        "properties": {
            "targets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"webhook_url": {"type": "string"}},
                },
            }
        },
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE
    webhook = next(p for p in result.properties if p.name == "webhook_url")
    assert webhook.pointer == "/properties/targets/items/properties/webhook_url"


def test_tuple_form_items_are_each_traversed() -> None:
    schema = {
        "type": "array",
        "items": [
            {"type": "object", "properties": {"a": {"type": "string"}}},
            {"type": "object", "properties": {"b": {"type": "string"}}},
        ],
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE
    assert _names(result) == {"a", "b"}


def test_allof_branches_are_traversed() -> None:
    schema = {
        "allOf": [
            {"type": "object", "properties": {"a": {"type": "string"}}},
            {"type": "object", "properties": {"to": {"type": "string", "format": "email"}}},
        ]
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE
    to_prop = next(p for p in result.properties if p.name == "to")
    assert to_prop.pointer == "/allOf/1/properties/to"


def test_a_field_three_levels_deep_inside_an_allof_branch_is_found() -> None:
    schema = {
        "allOf": [
            {
                "type": "object",
                "properties": {
                    "notification": {
                        "type": "object",
                        "properties": {
                            "targets": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"webhook_url": {"type": "string"}},
                                },
                            }
                        },
                    }
                },
            }
        ]
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE
    webhook = next(p for p in result.properties if p.name == "webhook_url")
    assert webhook.pointer == (
        "/allOf/0/properties/notification/properties/targets/items/properties/webhook_url"
    )


def test_anyof_branches_are_all_traversed_even_when_only_one_is_dangerous() -> None:
    """A single tool presenting two call shapes via anyOf; only one carries the
    dangerous field. Both branches must be visible to the caller."""
    schema = {
        "anyOf": [
            {"type": "object", "properties": {"path": {"type": "string"}}},
            {"type": "object", "properties": {"url": {"type": "string", "format": "uri"}}},
        ]
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE
    assert _names(result) == {"path", "url"}


def test_oneof_branches_are_traversed() -> None:
    schema = {"oneOf": [{"type": "object", "properties": {"x": {"type": "string"}}}]}
    result = walk_schema(schema)
    assert "x" in _names(result)


def test_a_ref_resolves_against_the_schemas_own_defs() -> None:
    schema = {
        "type": "object",
        "properties": {"target": {"$ref": "#/$defs/Target"}},
        "$defs": {"Target": {"type": "object", "properties": {"webhook_url": {"type": "string"}}}},
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE
    assert "webhook_url" in _names(result)


def test_a_ref_reused_by_two_siblings_is_not_a_false_cycle() -> None:
    schema = {
        "type": "object",
        "properties": {
            "a": {"$ref": "#/$defs/Shared"},
            "b": {"$ref": "#/$defs/Shared"},
        },
        "$defs": {"Shared": {"type": "object", "properties": {"x": {"type": "string"}}}},
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE


def test_a_ref_cycle_is_detected_and_traversal_terminates() -> None:
    schema = {
        "type": "object",
        "properties": {"a": {"$ref": "#/$defs/A"}},
        "$defs": {
            "A": {"type": "object", "properties": {"b": {"$ref": "#/$defs/B"}}},
            "B": {"type": "object", "properties": {"a_again": {"$ref": "#/$defs/A"}}},
        },
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.CYCLE_DETECTED
    assert result.detail is not None


def test_a_self_referencing_ref_is_a_cycle() -> None:
    schema = {
        "type": "object",
        "properties": {"child": {"$ref": "#/$defs/Node"}},
        "$defs": {"Node": {"type": "object", "properties": {"child": {"$ref": "#/$defs/Node"}}}},
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.CYCLE_DETECTED


def test_an_unresolvable_ref_is_reported_and_never_fetched() -> None:
    schema = {"type": "object", "properties": {"target": {"$ref": "#/$defs/Missing"}}}
    result = walk_schema(schema)
    assert result.status is TraversalStatus.UNRESOLVABLE_REF
    assert result.detail is not None


def test_an_external_ref_is_treated_as_unresolvable_never_fetched() -> None:
    """AGENTS.md: scanned content is never dereferenced. An external $ref is exactly
    the kind of external reference this scanner must not follow."""
    schema = {
        "type": "object",
        "properties": {"target": {"$ref": "https://attacker.example/schema"}},
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.UNRESOLVABLE_REF


def test_a_schema_exceeding_the_depth_cap_is_reported() -> None:
    schema: dict = {"type": "string"}
    for _ in range(30):
        schema = {"type": "object", "properties": {"nested": schema}}
    result = walk_schema(schema, max_depth=5)
    assert result.status is TraversalStatus.DEPTH_EXCEEDED
    assert result.detail is not None


def test_a_schema_within_the_depth_cap_completes() -> None:
    schema: dict = {"type": "string"}
    for _ in range(3):
        schema = {"type": "object", "properties": {"nested": schema}}
    result = walk_schema(schema, max_depth=10)
    assert result.status is TraversalStatus.COMPLETE


def test_a_non_complete_status_stops_traversal_rather_than_collecting_a_partial_list() -> None:
    """Fail-closed: once a status other than complete is decided, the caller must
    not be handed a partial property list that looks like a safe, full one."""
    schema = {
        "type": "object",
        "properties": {
            "before": {"type": "string"},
            "broken": {"$ref": "#/$defs/Missing"},
        },
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.UNRESOLVABLE_REF


def test_an_if_match_token_nested_only_inside_an_object_is_found() -> None:
    """Proves the walker is shared across signal classes: Rule D's concurrency
    tokens are found by the same traversal as Rule A/C's communication targets."""
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "options": {
                "type": "object",
                "properties": {"if_match": {"type": "string"}},
            },
        },
    }
    result = walk_schema(schema)
    assert result.status is TraversalStatus.COMPLETE
    assert "if_match" in _names(result)


def test_an_empty_schema_completes_with_no_properties() -> None:
    result = walk_schema({})
    assert result.status is TraversalStatus.COMPLETE
    assert result.properties == []


def test_a_non_dict_schema_completes_without_error() -> None:
    """A boolean JSON Schema (``true``/``false``) or any other non-object value is
    valid JSON Schema and must not crash the walker."""
    result = walk_schema(True)  # type: ignore[arg-type]
    assert result.status is TraversalStatus.COMPLETE
