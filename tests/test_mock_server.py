"""The mock server fixture itself.

Fast, in-process checks on the fixture's own configuration surface. The whole test
suite and the self-gating CI job rest on this server, so its mutation switches are
tested directly rather than only through the manifests they produce.
"""

from __future__ import annotations

import pytest

from .mock_server.surface import (
    DESCRIPTIONS,
    EXTRA_TOOL_NAME,
    MUTABLE_TOOL_NAME,
    MockConfig,
    build_prompts,
    build_resource_templates,
    build_resources,
    build_tools,
    config_from_args,
    surface_summary,
)


def test_the_default_surface_is_the_baseline() -> None:
    names = {tool.name for tool in build_tools(MockConfig())}
    assert EXTRA_TOOL_NAME not in names
    assert MUTABLE_TOOL_NAME in names


def test_tools_are_declared_unsorted() -> None:
    """Deliberate: a fixture that arrived pre-sorted would never prove that
    canonical serialization imposes the ordering."""
    names = [tool.name for tool in build_tools(MockConfig())]
    assert names != sorted(names)


def test_the_description_variant_changes_only_the_description() -> None:
    def find(variant: str):  # type: ignore[no-untyped-def]
        config = MockConfig(description_variant=variant)
        return next(t for t in build_tools(config) if t.name == MUTABLE_TOOL_NAME)

    first, second = find("a"), find("b")
    assert first.description != second.description
    assert first.input_schema == second.input_schema
    assert first.annotations == second.annotations


def test_add_tool_appends_exactly_one_tool() -> None:
    base = build_tools(MockConfig())
    extended = build_tools(MockConfig(include_extra_tool=True))
    assert len(extended) == len(base) + 1
    assert EXTRA_TOOL_NAME in {tool.name for tool in extended}


def test_drop_tool_withholds_exactly_that_tool() -> None:
    reduced = build_tools(MockConfig(omit_tools=frozenset({"delete_workspace"})))
    assert "delete_workspace" not in {tool.name for tool in reduced}
    assert len(reduced) == len(build_tools(MockConfig())) - 1


def test_the_fixture_covers_the_annotation_shapes_that_matter() -> None:
    tools = {tool.name: tool for tool in build_tools(MockConfig(include_extra_tool=True))}

    assert tools["ping"].annotations is None
    assert tools["ping"].description is None

    declared = [t.annotations for t in tools.values() if t.annotations is not None]
    assert any(a.read_only_hint is True for a in declared)
    assert any(a.read_only_hint is False for a in declared)
    assert any(a.destructive_hint is True for a in declared)
    assert any(a.idempotent_hint is True for a in declared)
    assert any(a.open_world_hint is True for a in declared)
    assert any(a.open_world_hint is False for a in declared)


def test_the_fixture_covers_varied_schema_shapes() -> None:
    schemas = {tool.name: tool.input_schema for tool in build_tools(MockConfig())}
    assert schemas["describe_server"]["properties"] == {}
    assert schemas["send_email"]["properties"]["attachments"]["items"]["type"] == "object"
    assert "enum" in schemas["write_note"]["properties"]["mode"]
    assert "pattern" in schemas["write_note"]["properties"]["path"]
    assert "const" in schemas["delete_workspace"]["properties"]["confirm_phrase"]


def test_resources_templates_and_prompts_are_declared() -> None:
    assert len(build_resources()) == 2
    assert len(build_resource_templates()) == 1
    assert all(prompt.arguments for prompt in build_prompts())


def test_argument_parsing_covers_every_switch() -> None:
    config = config_from_args(["--description-variant", "b", "--add-tool", "--drop-tool", "ping"])
    assert config == MockConfig(
        description_variant="b", include_extra_tool=True, omit_tools=frozenset({"ping"})
    )


def test_the_default_config_needs_no_arguments() -> None:
    assert config_from_args([]) == MockConfig()


@pytest.mark.parametrize("argv", [["--nonsense"], ["--description-variant", "z"]])
def test_bad_arguments_are_rejected(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        config_from_args(argv)


def test_both_description_variants_are_defined() -> None:
    assert set(DESCRIPTIONS) == {"a", "b"}


def test_surface_summary_reports_the_configured_surface() -> None:
    summary = surface_summary(MockConfig(include_extra_tool=True))
    assert EXTRA_TOOL_NAME in summary["tools"]
    assert summary["tools"] == sorted(summary["tools"])
