"""Manifest models, canonical ordering, and document I/O."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_placard import MANIFEST_VERSION
from mcp_placard.errors import ManifestValidationError, ManifestVersionError, UsageError
from mcp_placard.manifest import (
    build_manifest,
    load_manifest,
    manifest_document,
    parse_manifest,
    render_manifest,
    write_manifest,
)
from mcp_placard.manifest.models import ToolEntry

from .conftest import make_manifest, make_raw, tool_wire


def test_build_manifest_alone_never_classifies() -> None:
    """``build_manifest`` is structural only — ``manifest/`` does not classify risk
    (see the package boundary note). Classification is ``classify.classify_manifest``,
    a deliberate separate pass."""
    manifest = make_manifest([tool_wire("a"), tool_wire("b")])
    assert manifest.classification == []
    assert manifest.classification_hash


def test_manifest_version_is_stamped() -> None:
    assert make_manifest([tool_wire("a")]).manifest_version == MANIFEST_VERSION


def test_tools_are_sorted_by_name_regardless_of_server_order() -> None:
    manifest = make_manifest([tool_wire("zulu"), tool_wire("alpha"), tool_wire("mike")])
    assert [tool.name for tool in manifest.surface.tools] == ["alpha", "mike", "zulu"]


def test_server_reordering_does_not_change_the_surface_hash() -> None:
    forwards = make_manifest([tool_wire("a"), tool_wire("b"), tool_wire("c")])
    backwards = make_manifest([tool_wire("c"), tool_wire("b"), tool_wire("a")])
    assert forwards.surface_hash == backwards.surface_hash


def test_duplicate_tool_names_still_order_deterministically() -> None:
    """The specification does not forbid duplicate names, so the canonical form of
    the entry is the tiebreaker rather than the server's response order."""
    first = make_manifest(
        [tool_wire("dup", description="one"), tool_wire("dup", description="two")]
    )
    second = make_manifest(
        [tool_wire("dup", description="two"), tool_wire("dup", description="one")]
    )
    assert first.surface_hash == second.surface_hash


def test_resources_and_prompts_are_sorted() -> None:
    manifest = build_manifest(
        make_raw(
            resources=[
                {"name": "z", "uri": "file:///z"},
                {"name": "a", "uri": "file:///a"},
            ],
            prompts=[{"name": "second"}, {"name": "first"}],
        )
    )
    assert [r.uri for r in manifest.surface.resources] == ["file:///a", "file:///z"]
    assert [p.name for p in manifest.surface.prompts] == ["first", "second"]


def test_wire_spellings_survive_into_the_document() -> None:
    """MCP-owned fields keep camelCase; Placard-owned fields stay snake_case."""
    manifest = make_manifest(
        [
            tool_wire(
                "t",
                annotations={"readOnlyHint": True, "openWorldHint": False},
                outputSchema={"type": "object"},
            )
        ]
    )
    tool = manifest_document(manifest)["surface"]["tools"][0]

    assert set(tool["annotations"]) == {"readOnlyHint", "openWorldHint"}
    assert "inputSchema" in tool
    assert "outputSchema" in tool
    assert {"schema_hash", "description_hash"} <= set(tool)


def test_all_four_annotation_hints_round_trip() -> None:
    """Phase 2's declared-vs-inferred split depends on these arriving intact."""
    declared = {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    }
    manifest = make_manifest([tool_wire("t", annotations=declared)])
    assert manifest_document(manifest)["surface"]["tools"][0]["annotations"] == declared


def test_absent_annotations_stay_absent() -> None:
    """Absent is not ``false``. A server that declared nothing must not be recorded
    as having declared safety."""
    manifest = make_manifest([tool_wire("t", annotations={"readOnlyHint": True})])
    annotations = manifest_document(manifest)["surface"]["tools"][0]["annotations"]
    assert annotations == {"readOnlyHint": True}


def test_unknown_fields_are_preserved_not_dropped() -> None:
    """``surface_hash`` claims to cover the surface; dropping unknown fields would
    make that claim false."""
    manifest = make_manifest(
        [
            tool_wire(
                "t",
                annotations={"readOnlyHint": True, "futureHint": "unknown-to-this-build"},
                someFutureField={"nested": [1, 2]},
            )
        ]
    )
    tool = manifest_document(manifest)["surface"]["tools"][0]
    assert tool["someFutureField"] == {"nested": [1, 2]}
    assert tool["annotations"]["futureHint"] == "unknown-to-this-build"


def test_no_timestamp_or_target_anywhere_in_the_document() -> None:
    """Nothing environment-dependent may enter the body, or byte-identity across
    machines is lost and every self-gating CI run becomes a false positive."""
    text = render_manifest(make_manifest([tool_wire("t")]))
    lowered = text.lower()
    for forbidden in ("timestamp", "scanned_at", "generated", "target", "hostname"):
        assert forbidden not in lowered


def test_no_scan_circumstance_data_enters_a_hashed_body() -> None:
    """``environment`` is the one field explicitly designed to hold SDK/protocol
    metadata — it must never appear inside ``surface`` or ``capabilities``, the two
    bodies that feed a hash."""
    document = manifest_document(
        make_manifest(
            [tool_wire("t")],
            environment={"sdk_version": "9.9.9", "protocol_version": "2099-01-01"},
        )
    )
    hashed_body = json.dumps(
        {"surface": document["surface"], "capabilities": document["capabilities"]}
    )
    assert "protocol" not in hashed_body.lower()
    assert "9.9.9" not in hashed_body
    assert document["environment"] == {"sdk_version": "9.9.9", "protocol_version": "2099-01-01"}


def test_surface_hash_is_unaffected_by_environment() -> None:
    """``environment`` holds SDK version and anything client-negotiated — properties
    of the scan, not the server. It must never move ``surface_hash``."""
    without = build_manifest(make_raw([tool_wire("t")]))
    with_env = build_manifest(
        make_raw(
            [tool_wire("t")],
            environment={"sdk_version": "9.9.9", "protocol_version": "2099-01-01"},
        )
    )
    assert without.surface_hash == with_env.surface_hash
    assert without.environment != with_env.environment


def test_surface_hash_is_unaffected_by_capabilities() -> None:
    """``capabilities`` was split out of the hashed surface body — only
    ``capabilities_hash`` tracks it, so ``surface_hash`` must not move when only
    capabilities changes."""
    without = build_manifest(make_raw([tool_wire("t")], capabilities={}))
    with_caps = build_manifest(
        make_raw([tool_wire("t")], capabilities={"tools": {"listChanged": True}})
    )
    assert without.surface_hash == with_caps.surface_hash
    assert without.capabilities_hash != with_caps.capabilities_hash


def test_rendered_manifest_round_trips_byte_identically() -> None:
    manifest = make_manifest([tool_wire("b"), tool_wire("a")])
    text = render_manifest(manifest)
    assert render_manifest(parse_manifest(text, source="<mem>")) == text


def test_reloading_preserves_the_surface_hash() -> None:
    manifest = make_manifest([tool_wire("a", description="Café — ünïcödé")])
    reloaded = parse_manifest(render_manifest(manifest), source="<mem>")
    assert reloaded.surface_hash == manifest.surface_hash


def test_tools_by_name_indexes_the_surface() -> None:
    manifest = make_manifest([tool_wire("a"), tool_wire("b")])
    assert set(manifest.tools_by_name()) == {"a", "b"}


def test_write_and_load_round_trip(tmp_path: Path) -> None:
    manifest = make_manifest([tool_wire("a")])
    path = tmp_path / "nested" / "manifest.json"
    write_manifest(manifest, path)
    assert load_manifest(path).surface_hash == manifest.surface_hash


def test_parse_rejects_non_json() -> None:
    with pytest.raises(ManifestValidationError, match="not valid JSON"):
        parse_manifest("{not json", source="<mem>")


def test_parse_rejects_a_json_array() -> None:
    with pytest.raises(ManifestValidationError, match="JSON object"):
        parse_manifest("[]", source="<mem>")


def test_parse_rejects_an_unsupported_version() -> None:
    document = json.loads(render_manifest(make_manifest([tool_wire("a")])))
    document["manifest_version"] = "99.0"
    with pytest.raises(ManifestVersionError, match="unsupported manifest_version"):
        parse_manifest(json.dumps(document), source="<mem>")


def test_parse_rejects_a_missing_version() -> None:
    with pytest.raises(ManifestVersionError):
        parse_manifest('{"surface_hash": "x"}', source="<mem>")


def test_parse_rejects_a_structurally_invalid_manifest() -> None:
    document = {"manifest_version": MANIFEST_VERSION, "surface_hash": "x"}
    with pytest.raises(ManifestValidationError, match="not a valid manifest"):
        parse_manifest(json.dumps(document), source="<mem>")


def test_load_reports_a_missing_file_as_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="cannot read manifest"):
        load_manifest(tmp_path / "absent.json")


def test_write_reports_an_unwritable_path_as_a_usage_error(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    with pytest.raises(UsageError, match="cannot write manifest"):
        write_manifest(make_manifest([tool_wire("a")]), blocker / "sub" / "m.json")


def test_a_tool_without_an_input_schema_is_a_validation_error() -> None:
    """``inputSchema`` is required by the MCP specification. A server omitting it has
    produced something this build refuses to hash as though it were complete."""
    with pytest.raises(ManifestValidationError, match="did not validate"):
        build_manifest(make_raw([{"name": "broken"}]))


def test_tool_entry_can_be_constructed_by_python_name() -> None:
    """``populate_by_name`` keeps test and builder code readable."""
    entry = ToolEntry(
        name="t",
        input_schema={"type": "object"},
        schema_hash="0" * 64,
        description_hash="1" * 64,
    )
    assert entry.model_dump(by_alias=True)["inputSchema"] == {"type": "object"}
