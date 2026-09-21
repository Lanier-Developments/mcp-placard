"""Phase 2.1's compatibility fixture: a Phase 2 ("2.0") manifest still parses,
verifies, and diffs under the "2.1" build.

``tests/fixtures/legacy_manifest_2_0.json`` is the mock server's checked-in
manifest exactly as the last "2.0" build wrote it — a genuine document, not a
hand-written approximation. "2.0" differs from "2.1" only by the absence of per-tool
``kinds``, so the interesting property is that a stored "2.0" *baseline still
verifies*: ``classification_hash`` was recorded over bodies with no ``kinds`` key,
and this build must reproduce it rather than fail an operator's baseline on upgrade.
"""

from __future__ import annotations

from pathlib import Path

from mcp_placard import MANIFEST_VERSION
from mcp_placard.diff import diff_manifests
from mcp_placard.errors import EXIT_OK
from mcp_placard.manifest import hash_mismatches, load_manifest, parse_manifest, render_manifest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LEGACY_2_0 = FIXTURES / "legacy_manifest_2_0.json"
CURRENT = FIXTURES / "mock_server_manifest.json"


def test_this_build_writes_a_version_after_2_0() -> None:
    assert MANIFEST_VERSION >= "2.1"
    assert load_manifest(CURRENT).manifest_version == MANIFEST_VERSION


def test_a_2_0_manifest_parses_with_empty_kinds() -> None:
    manifest = load_manifest(LEGACY_2_0)
    assert manifest.manifest_version == "2.0"
    assert manifest.classification
    assert all(entry.kinds == [] for entry in manifest.classification)


def test_a_2_0_manifest_still_verifies() -> None:
    """The load-bearing claim: the recorded hash reproduces under this build."""
    assert hash_mismatches(load_manifest(LEGACY_2_0)) == []


def test_a_2_0_manifest_diffs_against_the_2_1_scan_of_the_same_server() -> None:
    old = load_manifest(LEGACY_2_0)
    new = load_manifest(CURRENT)
    result = diff_manifests(old, new)
    assert result.exit_code == EXIT_OK, [f.kind for f in result.findings]


def test_a_2_1_manifest_round_trips_with_and_without_kinds() -> None:
    manifest = load_manifest(CURRENT)
    again = parse_manifest(render_manifest(manifest), source="<round-trip>")
    assert again == manifest
    assert render_manifest(again) == render_manifest(manifest)
    assert any(entry.kinds for entry in again.classification)
    assert any(not entry.kinds for entry in again.classification)
