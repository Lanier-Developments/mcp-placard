"""Phase 3's compatibility fixture: a Phase 2.1 ("2.1") manifest still parses,
verifies, and diffs under the "2.2" build.

``tests/fixtures/legacy_manifest_2_1.json`` is the mock server's checked-in manifest
exactly as the last "2.1" build wrote it. "2.1" differs from "2.2" by the absence of
``injection_findings`` and ``ruleset_version``; a missing ``ruleset_version``
selects the pre-2.2 ``classification_hash`` shape, so the stored hash reproduces,
and ``diff`` re-analyses the document under the current ruleset before comparing.
"""

from __future__ import annotations

from pathlib import Path

from mcp_placard import MANIFEST_VERSION
from mcp_placard.diff import diff_manifests
from mcp_placard.errors import EXIT_OK
from mcp_placard.manifest import hash_mismatches, load_manifest, parse_manifest, render_manifest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LEGACY_2_1 = FIXTURES / "legacy_manifest_2_1.json"
CURRENT = FIXTURES / "mock_server_manifest.json"


def test_this_build_writes_2_2() -> None:
    assert MANIFEST_VERSION == "2.2"
    assert load_manifest(CURRENT).manifest_version == "2.2"


def test_a_2_1_manifest_parses_without_ruleset_or_findings() -> None:
    manifest = load_manifest(LEGACY_2_1)
    assert manifest.manifest_version == "2.1"
    assert manifest.ruleset_version is None
    assert manifest.injection_findings == []
    assert any(entry.kinds for entry in manifest.classification)


def test_a_2_1_manifest_still_verifies() -> None:
    assert hash_mismatches(load_manifest(LEGACY_2_1)) == []


def test_every_earlier_baseline_still_verifies() -> None:
    for name in (
        "legacy_manifest_1_0.json",
        "legacy_manifest_2_0.json",
        "legacy_manifest_2_1.json",
    ):
        assert hash_mismatches(load_manifest(FIXTURES / name)) == [], name


def test_a_2_1_manifest_diffs_clean_against_the_2_2_scan_of_the_same_server() -> None:
    result = diff_manifests(load_manifest(LEGACY_2_1), load_manifest(CURRENT))
    assert result.exit_code == EXIT_OK, [f.summary for f in result.findings]
    assert result.notes


def test_a_2_1_document_round_trips_byte_for_byte() -> None:
    text = LEGACY_2_1.read_text(encoding="utf-8")
    manifest = parse_manifest(text, source="<fixture>")
    assert render_manifest(manifest) == text
