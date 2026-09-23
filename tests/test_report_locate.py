"""SARIF line regions are real: a JSON Pointer maps to the line in the rendered
baseline where its value begins."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_placard.manifest import load_manifest, render_manifest
from mcp_placard.report.locate import pointer_line

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mock_server_manifest.json"


@pytest.fixture(scope="module")
def rendered() -> str:
    return render_manifest(load_manifest(FIXTURE))


def _value_at(document: object, pointer: str) -> object:
    node = document
    for segment in pointer[1:].split("/"):
        segment = segment.replace("~1", "/").replace("~0", "~")
        node = node[int(segment)] if isinstance(node, list) else node[segment]  # type: ignore[index]
    return node


@pytest.mark.parametrize(
    "pointer",
    [
        "/manifest_version",
        "/surface/instructions",
        "/surface/tools/0/description",
        "/surface/tools/0/name",
        "/surface/tools/6/inputSchema/properties/path/pattern",
        "/surface/prompts/1/arguments/1/description",
        "/surface/resources/1/uri",
        "/classification/2/tier",
        "/capabilities/tools/listChanged",
    ],
)
def test_the_line_holds_the_key_and_the_scalar_value(rendered: str, pointer: str) -> None:
    line = pointer_line(rendered, pointer)
    assert line is not None
    text = rendered.splitlines()[line - 1]
    key = pointer.rsplit("/", 1)[1]
    assert f'"{key}":' in text
    value = _value_at(json.loads(rendered), pointer)
    assert json.dumps(value, ensure_ascii=False) in text


def test_a_container_pointer_lands_on_its_opening_line(rendered: str) -> None:
    line = pointer_line(rendered, "/surface/tools/3")
    assert line is not None
    assert rendered.splitlines()[line - 1].strip() == "{"
    line = pointer_line(rendered, "/surface/tools")
    assert line is not None
    assert rendered.splitlines()[line - 1].strip().startswith('"tools": [')


def test_an_unresolvable_pointer_is_none(rendered: str) -> None:
    assert pointer_line(rendered, "/surface/tools/99/name") is None
    assert pointer_line(rendered, "/nope") is None
    assert pointer_line(rendered, "no-leading-slash") is None
    assert pointer_line(rendered, "") == 1


def test_escaped_segments_resolve() -> None:
    text = render_manifest(load_manifest(FIXTURE))
    # A key containing "/" would be escaped as ~1 in a pointer; the mock has none, so
    # synthesise one and check the walker unescapes.
    document = json.loads(text)
    document["a/b"] = {"c": 1}
    rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    line = pointer_line(rendered, "/a~1b/c")
    assert line is not None and '"c": 1' in rendered.splitlines()[line - 1]
