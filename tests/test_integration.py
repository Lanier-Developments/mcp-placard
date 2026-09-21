"""Integration tests against the real mock MCP server over real stdio.

These are the only tests where the MCP SDK, a subprocess, and the wire format are
actually involved. Everything else in the suite works from synthetic manifests, so
this module is what proves the manifest is faithful to a genuine server response
rather than to a hand-written fixture.

Marked ``slow`` — ``pytest -m "not slow"`` skips the subprocess round trips.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_placard.classify import classify_manifest
from mcp_placard.cli import main
from mcp_placard.diff import ChangeKind, diff_manifests
from mcp_placard.errors import (
    EXIT_DESCRIPTION_CHANGE,
    EXIT_ESCALATION,
    EXIT_OK,
    EXIT_REMOVED,
)
from mcp_placard.manifest import (
    build_manifest,
    hash_mismatches,
    manifest_document,
    render_manifest,
)
from mcp_placard.manifest.hashing import hash_description
from mcp_placard.transport import scan_target

from .conftest import mock_server_target
from .mock_server.surface import EXTRA_TOOL_NAME, MUTABLE_TOOL_NAME

pytestmark = pytest.mark.slow


def scan(*args: str):  # type: ignore[no-untyped-def]
    """Scan the mock server, optionally with mutation flags, and build a classified
    manifest — the same two-step pipeline the real ``placard scan`` runs."""
    return classify_manifest(build_manifest(scan_target(mock_server_target(*args), timeout=60)))


@pytest.fixture(scope="module")
def baseline():  # type: ignore[no-untyped-def]
    return scan()


# ------------------------------------------------------------------ enumeration


def test_the_full_surface_is_enumerated(baseline) -> None:  # type: ignore[no-untyped-def]
    names = {tool.name for tool in baseline.surface.tools}
    assert {
        "describe_server",
        "search_documents",
        "fetch_url",
        "send_email",
        "write_note",
        "delete_workspace",
        "ping",
    } <= names
    assert len(baseline.surface.resources) == 2
    assert len(baseline.surface.resource_templates) == 1
    assert len(baseline.surface.prompts) == 2
    assert baseline.surface.server.name == "placard-mock"
    assert baseline.surface.instructions


def test_every_tool_is_classified_against_a_live_server(baseline) -> None:  # type: ignore[no-untyped-def]
    """Asserted against a live server response, not a synthetic fixture — proves
    the classifier pipeline actually runs end to end through ``scan``."""
    tiers = {entry.tool: entry.tier for entry in baseline.classification}
    assert tiers == {
        "send_email": "R4",
        "search_documents": "R1",
        "describe_server": "R0",
        "fetch_url": "R4",
        "write_note": "R3",
        "delete_workspace": "R5",
        "ping": "R0",
    }
    assert baseline.classification_hash


def test_all_four_declared_annotations_reach_the_manifest(baseline) -> None:  # type: ignore[no-untyped-def]
    """Phase 2's declared-vs-inferred reconciliation depends on the raw hints
    surviving Phase 1 intact, so this is asserted against a live server response and
    not against a synthetic dict."""
    tools = baseline.tools_by_name()

    email = tools["send_email"].annotations
    assert email is not None
    assert email.read_only_hint is False
    assert email.destructive_hint is False
    assert email.idempotent_hint is False
    assert email.open_world_hint is True

    delete = tools["delete_workspace"].annotations
    assert delete is not None and delete.destructive_hint is True

    fetch = tools["fetch_url"].annotations
    assert fetch is not None and fetch.open_world_hint is True


def test_annotations_use_wire_spellings_in_the_document(baseline) -> None:  # type: ignore[no-untyped-def]
    document = manifest_document(baseline)
    annotations = next(
        tool["annotations"] for tool in document["surface"]["tools"] if tool["name"] == "send_email"
    )
    assert set(annotations) == {
        "readOnlyHint",
        "destructiveHint",
        "idempotentHint",
        "openWorldHint",
    }


def test_a_tool_that_declares_nothing_is_recorded_as_declaring_nothing(baseline) -> None:  # type: ignore[no-untyped-def]
    """Absent is not ``false``. Defaulting here would invent a declaration the
    server never made, and Phase 2 would then reconcile against a fiction."""
    ping = baseline.tools_by_name()["ping"]
    assert ping.annotations is None
    assert ping.description is None
    assert ping.description_hash == hash_description(None)

    document = manifest_document(baseline)
    entry = next(t for t in document["surface"]["tools"] if t["name"] == "ping")
    assert "annotations" not in entry
    assert "description" not in entry


def test_optional_wire_fields_round_trip(baseline) -> None:  # type: ignore[no-untyped-def]
    tools = baseline.tools_by_name()
    assert tools["search_documents"].output_schema is not None
    assert tools["write_note"].meta is not None


def test_non_ascii_descriptions_survive(baseline) -> None:  # type: ignore[no-untyped-def]
    assert "Café" in (baseline.tools_by_name()["write_note"].description or "")


def test_the_scan_is_internally_consistent(baseline) -> None:  # type: ignore[no-untyped-def]
    assert hash_mismatches(baseline) == []


# ----------------------------------------------------------------- determinism


def test_two_scans_of_an_unchanged_server_are_byte_identical() -> None:
    """The headline acceptance criterion. Any nondeterminism — dict ordering, a
    timestamp, a recorded target — breaks this and makes the whole tool cry wolf."""
    first = render_manifest(scan())
    second = render_manifest(scan())
    assert first == second


def test_two_scans_agree_on_every_hash() -> None:
    first, second = scan(), scan()
    assert first.surface_hash == second.surface_hash
    assert [(t.name, t.schema_hash, t.description_hash) for t in first.surface.tools] == [
        (t.name, t.schema_hash, t.description_hash) for t in second.surface.tools
    ]


def test_tools_arrive_sorted_even_though_the_server_declares_them_unsorted(baseline) -> None:  # type: ignore[no-untyped-def]
    names = [tool.name for tool in baseline.surface.tools]
    assert names == sorted(names)


# -------------------------------------------------------------------- fidelity


def test_the_manifest_is_a_lossless_record_of_the_wire_response() -> None:
    """Canonical serialization must not drop a field a real server sent. If this
    fails, ``surface_hash`` no longer covers the surface it claims to."""
    raw = scan_target(mock_server_target(), timeout=60)
    document = manifest_document(build_manifest(raw))
    added = {"schema_hash", "description_hash", "tier"}

    recorded = {tool["name"]: tool for tool in document["surface"]["tools"]}
    for wire_tool in raw.tools:
        stored = {k: v for k, v in recorded[wire_tool["name"]].items() if k not in added}
        assert stored == wire_tool, f"lossy round trip for tool {wire_tool['name']}"

    assert document["surface"]["server"] == raw.server_info
    assert document["capabilities"] == raw.capabilities
    assert document["surface"]["instructions"] == raw.instructions
    assert {r["uri"] for r in document["surface"]["resources"]} == {r["uri"] for r in raw.resources}
    assert {p["name"] for p in document["surface"]["prompts"]} == {p["name"] for p in raw.prompts}


def test_a_real_scan_populates_environment_outside_every_hashed_body() -> None:
    """``environment`` is scan-circumstance metadata from the real SDK connection —
    this is the one test that proves the wiring actually reaches it, not just a
    synthetic fixture."""
    manifest = scan()
    assert "sdk_version" in manifest.environment
    assert manifest.environment["sdk_version"]


# ------------------------------------------------------- the three drift cases


def test_a_description_only_rewrite_moves_one_hash_and_not_the_other() -> None:
    """The event Placard exists to surface: identical API, rewritten prompt."""
    before = scan().tools_by_name()[MUTABLE_TOOL_NAME]
    after = scan("--description-variant", "b").tools_by_name()[MUTABLE_TOOL_NAME]

    assert before.schema_hash == after.schema_hash
    assert before.description_hash != after.description_hash
    assert before.input_schema == after.input_schema
    assert before.description != after.description


def test_a_description_only_rewrite_diffs_to_exit_code_two() -> None:
    result = diff_manifests(scan(), scan("--description-variant", "b"))
    assert result.exit_code == EXIT_DESCRIPTION_CHANGE
    assert [f.kind for f in result.findings] == [ChangeKind.TOOL_DESCRIPTION_CHANGED]
    assert result.findings[0].tool == MUTABLE_TOOL_NAME


def test_an_added_tool_diffs_to_exit_code_one() -> None:
    result = diff_manifests(scan(), scan("--add-tool"))
    assert result.exit_code == EXIT_ESCALATION
    assert [f.tool for f in result.findings_of(ChangeKind.TOOL_ADDED)] == [EXTRA_TOOL_NAME]


def test_a_removed_tool_diffs_to_exit_code_three() -> None:
    result = diff_manifests(scan(), scan("--drop-tool", "delete_workspace"))
    assert result.exit_code == EXIT_REMOVED
    assert [f.tool for f in result.findings_of(ChangeKind.TOOL_REMOVED)] == ["delete_workspace"]


# --------------------------------------------------------------- through the CLI


def _cli(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr("sys.argv", ["placard", *argv])
    return main()


def test_scan_emits_to_stdout_and_also_writes_the_out_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:  # type: ignore[no-untyped-def]
    """``--out`` *adds* a destination; it does not replace stdout. A scan that wrote
    only to a file would break piping."""
    out = tmp_path / "manifest.json"
    assert _cli(monkeypatch, "scan", mock_server_target(), "--out", str(out)) == EXIT_OK

    captured = capsys.readouterr()
    assert out.read_text(encoding="utf-8") == captured.out
    assert captured.out.endswith("}\n")
    assert str(out) in captured.err


def test_the_full_scan_diff_cycle_through_the_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:  # type: ignore[no-untyped-def]
    """The exact loop CI runs: scan, scan again after a change, diff, read the code."""
    baseline_path = tmp_path / "baseline.json"
    mutated_path = tmp_path / "mutated.json"

    assert _cli(monkeypatch, "scan", mock_server_target(), "--out", str(baseline_path)) == EXIT_OK
    assert (
        _cli(
            monkeypatch,
            "scan",
            mock_server_target("--description-variant", "b"),
            "--out",
            str(mutated_path),
        )
        == EXIT_OK
    )
    capsys.readouterr()

    assert _cli(monkeypatch, "verify", str(baseline_path)) == EXIT_OK
    assert _cli(monkeypatch, "diff", str(baseline_path), str(baseline_path)) == EXIT_OK
    assert (
        _cli(monkeypatch, "diff", str(baseline_path), str(mutated_path)) == EXIT_DESCRIPTION_CHANGE
    )


def test_scanning_twice_through_the_cli_produces_identical_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:  # type: ignore[no-untyped-def]
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    _cli(monkeypatch, "scan", mock_server_target(), "--out", str(first))
    _cli(monkeypatch, "scan", mock_server_target(), "--out", str(second))
    capsys.readouterr()
    assert first.read_bytes() == second.read_bytes()
