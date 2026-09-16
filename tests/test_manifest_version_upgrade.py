"""Deliverable 10: a Phase 1 ("1.0") manifest still parses and diffs against a
Phase 2 ("2.0") manifest without crashing.

``tests/fixtures/legacy_manifest_1_0.json`` is a genuine "1.0"-shaped document —
built the same way any pre-classification manifest was, then stripped of the
fields "1.0" never had (``classification``, ``classification_hash``, ``findings``)
rather than hand-written, so its ``surface_hash``/``capabilities_hash`` are real.
"""

from __future__ import annotations

from pathlib import Path

from mcp_placard.classify import classify_manifest
from mcp_placard.diff import diff_manifests
from mcp_placard.errors import EXIT_ESCALATION, EXIT_OK
from mcp_placard.manifest import build_manifest, hash_mismatches, load_manifest
from mcp_placard.manifest.build import compute_classification_hash

from .conftest import make_raw, tool_wire

LEGACY_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "legacy_manifest_1_0.json"


def test_the_legacy_fixture_exists() -> None:
    assert LEGACY_FIXTURE.is_file()


def test_a_1_0_manifest_parses_under_the_2_0_build() -> None:
    manifest = load_manifest(LEGACY_FIXTURE)
    assert manifest.manifest_version == "1.0"
    assert manifest.classification == []
    assert manifest.classification_hash == compute_classification_hash([])
    assert manifest.findings == []
    assert {tool.name for tool in manifest.surface.tools} == {"search_documents", "send_email"}


def test_a_1_0_manifest_verifies_cleanly() -> None:
    """The upgrade fills in defaults consistently with what verify recomputes —
    reading an old file must not itself look like tampering."""
    manifest = load_manifest(LEGACY_FIXTURE)
    assert hash_mismatches(manifest) == []


def test_a_1_0_manifest_diffs_against_a_fresh_2_0_manifest_without_crashing() -> None:
    """The headline deliverable-10 claim. The old manifest has no classification
    data for either tool, so both get the Phase 1 conservative default rather than
    a crash or a silently-accepted "no finding.\""""
    old = load_manifest(LEGACY_FIXTURE)
    new = classify_manifest(
        build_manifest(
            make_raw(
                [
                    tool_wire(
                        "search_documents",
                        description="Search workspace documents.",
                        input_schema={
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    ),
                    tool_wire(
                        "send_email",
                        description="Send an email.",
                        input_schema={
                            "type": "object",
                            "properties": {"to": {"type": "string"}},
                            "required": ["to"],
                        },
                    ),
                ],
                server_name="legacy-fixture-server",
            )
        )
    )

    result = diff_manifests(old, new)
    # Same surface, same schemas/descriptions — no tool_added/removed/changed
    # findings. Nothing crashed getting here, which is the point.
    assert result.findings == []
    assert result.exit_code == EXIT_OK


def test_a_1_0_manifest_diffed_against_a_2_0_manifest_with_a_new_tool_still_escalates() -> None:
    """An added tool with no classification data on the old side still falls back
    to the Phase 1 conservative default — the "1.0" side contributes nothing, but
    the comparison still runs and still protects the operator."""
    old = load_manifest(LEGACY_FIXTURE)
    new = classify_manifest(
        build_manifest(
            make_raw(
                [
                    tool_wire(
                        "search_documents",
                        description="Search workspace documents.",
                        input_schema={
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    ),
                    tool_wire(
                        "send_email",
                        description="Send an email.",
                        input_schema={
                            "type": "object",
                            "properties": {"to": {"type": "string"}},
                            "required": ["to"],
                        },
                    ),
                    tool_wire(
                        "delete_everything",
                        description="Delete the whole workspace.",
                        input_schema={
                            "type": "object",
                            "properties": {"force": {"type": "boolean"}},
                        },
                    ),
                ],
                server_name="legacy-fixture-server",
            )
        )
    )

    result = diff_manifests(old, new)
    assert result.exit_code == EXIT_ESCALATION
