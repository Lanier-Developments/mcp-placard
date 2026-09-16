"""Canonical JSON must be deterministic, or every hash below it is meaningless."""

from __future__ import annotations

import json

import pytest

from mcp_placard.manifest.canonical import canonical_bytes, canonical_text, render_json


def test_keys_are_sorted_regardless_of_insertion_order() -> None:
    first = {"b": 1, "a": 2, "c": 3}
    second = {"c": 3, "a": 2, "b": 1}
    assert canonical_text(first) == canonical_text(second) == '{"a":2,"b":1,"c":3}'


def test_nested_keys_are_sorted_too() -> None:
    value = {"outer": {"z": 1, "a": {"y": 2, "b": 3}}}
    assert canonical_text(value) == '{"outer":{"a":{"b":3,"y":2},"z":1}}'


def test_array_order_is_preserved() -> None:
    """Sorting arrays is the *caller's* job. Canonical JSON must not reorder them —
    a JSON Schema ``required`` list or an ``enum`` is order-bearing data."""
    assert canonical_text({"required": ["b", "a"]}) == '{"required":["b","a"]}'


def test_output_has_no_insignificant_whitespace() -> None:
    assert canonical_text({"a": [1, 2], "b": {"c": 3}}) == '{"a":[1,2],"b":{"c":3}}'


def test_non_ascii_is_emitted_as_utf8_not_escaped() -> None:
    """Escaping style must not be a hash input. Real UTF-8 keeps the hashed bytes
    identical to what a reader sees in the manifest."""
    text = canonical_text({"description": "Café — naïve"})
    assert "\\u" not in text
    assert canonical_bytes({"description": "Café"}) == '{"description":"Café"}'.encode()


def test_canonical_bytes_are_utf8_of_canonical_text() -> None:
    value = {"z": "Ω", "a": 1}
    assert canonical_bytes(value) == canonical_text(value).encode("utf-8")


def test_render_json_is_readable_sorted_and_newline_terminated() -> None:
    rendered = render_json({"b": 1, "a": {"d": 2, "c": 3}})
    assert rendered.endswith("\n")
    assert rendered.splitlines()[1].startswith("  ")
    assert list(json.loads(rendered)) == ["a", "b"]


def test_render_json_and_canonical_text_agree_on_content() -> None:
    """The two renderings differ only in presentation. If they ever disagreed on
    content, a manifest's hash would not describe the manifest's body."""
    value = {"b": [3, 1], "a": {"x": None, "y": "Ω"}}
    assert json.loads(render_json(value)) == json.loads(canonical_text(value))


def test_repeated_rendering_is_byte_identical() -> None:
    value = {f"key{index}": {"nested": index} for index in range(50)}
    assert canonical_bytes(value) == canonical_bytes(dict(reversed(list(value.items()))))


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_numbers_are_rejected(bad: float) -> None:
    """``NaN`` is not JSON, and Python's encoder emits it happily by default. A
    manifest containing it would not round-trip through another JSON reader."""
    with pytest.raises(ValueError):
        canonical_text({"value": bad})
