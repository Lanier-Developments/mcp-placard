"""The three hash levels, and the independence between them.

AGENTS.md forbids collapsing ``schema_hash`` and ``description_hash``. These tests
are what makes that prohibition mechanical: they fail the moment the two stop being
computed from independent inputs.
"""

from __future__ import annotations

from mcp_placard.manifest import build_manifest
from mcp_placard.manifest.hashing import hash_description, hash_schema, hash_value, sha256_hex

from .conftest import make_raw, tool_wire

SCHEMA = {"type": "object", "properties": {"query": {"type": "string"}}}


def test_sha256_hex_is_lowercase_64_chars() -> None:
    digest = sha256_hex(b"placard")
    assert len(digest) == 64
    assert digest == digest.lower()


def test_hash_is_stable_across_key_order() -> None:
    assert hash_schema({"a": 1, "b": 2}) == hash_schema({"b": 2, "a": 1})


def test_absent_and_empty_descriptions_hash_differently() -> None:
    """Removing a description and blanking it are different events, and a manifest
    that cannot tell them apart cannot report either one honestly."""
    assert hash_description(None) != hash_description("")


def test_description_hash_tracks_only_the_text() -> None:
    assert hash_description("one") != hash_description("two")
    assert hash_description("one") == hash_value("one")


def test_schema_hash_ignores_the_description_entirely() -> None:
    """The load-bearing property: rewriting the prompt must not move the API hash."""
    before = build_manifest(make_raw([tool_wire("t", description="original", input_schema=SCHEMA)]))
    after = build_manifest(
        make_raw([tool_wire("t", description="rewritten entirely", input_schema=SCHEMA)])
    )

    assert before.surface.tools[0].schema_hash == after.surface.tools[0].schema_hash
    assert before.surface.tools[0].description_hash != after.surface.tools[0].description_hash
    assert before.surface_hash != after.surface_hash


def test_description_hash_ignores_the_schema_entirely() -> None:
    """And the converse: changing the API must not move the prompt hash."""
    before = build_manifest(make_raw([tool_wire("t", description="same", input_schema=SCHEMA)]))
    after = build_manifest(
        make_raw(
            [
                tool_wire(
                    "t",
                    description="same",
                    input_schema={**SCHEMA, "required": ["query"]},
                )
            ]
        )
    )

    assert before.surface.tools[0].description_hash == after.surface.tools[0].description_hash
    assert before.surface.tools[0].schema_hash != after.surface.tools[0].schema_hash


def test_the_two_per_tool_hashes_are_not_the_same_value() -> None:
    """A cheap guard against a future refactor that points both at one helper."""
    manifest = build_manifest(
        make_raw([tool_wire("t", description="A tool.", input_schema=SCHEMA)])
    )
    tool = manifest.surface.tools[0]
    assert tool.schema_hash != tool.description_hash


def test_surface_hash_covers_the_per_tool_hashes() -> None:
    """Tampering with a recorded per-tool hash must break the surface hash too."""
    manifest = build_manifest(
        make_raw([tool_wire("t", description="A tool.", input_schema=SCHEMA)])
    )
    original = manifest.surface_hash

    from mcp_placard.manifest.build import compute_surface_hash

    manifest.surface.tools[0].schema_hash = "0" * 64
    assert compute_surface_hash(manifest.surface) != original


def test_surface_hash_changes_when_only_instructions_change() -> None:
    """Server instructions are model-facing text and belong inside the hashed body."""
    without = build_manifest(make_raw([tool_wire("t")], instructions=None))
    with_text = build_manifest(make_raw([tool_wire("t")], instructions="Be careful."))
    assert without.surface_hash != with_text.surface_hash
