"""Placard gates itself.

AGENTS.md: *CI also runs Placard against its own mock server and diffs the result
against a checked-in manifest — the tool gates itself.* This module is the local
form of that CI job, so drift is caught by ``pytest`` before it reaches a runner.

If this fails, the mock server's surface changed. Regenerate the fixture **only**
after reading the diff and agreeing with it:

    placard scan "python -m tests.mock_server" --out tests/fixtures/mock_server_manifest.json

Regenerating to make a red build green is the failure mode described as adversary A5
in ``docs/THREAT_MODEL.md``.
"""

from __future__ import annotations

import pytest

from mcp_placard.analysis import analyze
from mcp_placard.diff import diff_manifests
from mcp_placard.errors import EXIT_OK
from mcp_placard.manifest import build_manifest, hash_mismatches, load_manifest, render_manifest
from mcp_placard.transport import scan_target

from .conftest import MOCK_MANIFEST_FIXTURE, mock_server_target

pytestmark = pytest.mark.slow


def _fresh_scan():  # type: ignore[no-untyped-def]
    """The same two-step pipeline ``placard scan`` runs — build, then classify —
    since that is the command the fixture-regeneration instructions below use."""
    return analyze(build_manifest(scan_target(mock_server_target(), timeout=60)))


def test_the_checked_in_fixture_exists() -> None:
    assert MOCK_MANIFEST_FIXTURE.is_file(), (
        f"{MOCK_MANIFEST_FIXTURE} is missing — the self-gating CI job has nothing to "
        "compare against"
    )


def test_the_checked_in_fixture_verifies() -> None:
    assert hash_mismatches(load_manifest(MOCK_MANIFEST_FIXTURE)) == []


def test_a_fresh_scan_does_not_drift_from_the_fixture() -> None:
    fresh = _fresh_scan()
    recorded = load_manifest(MOCK_MANIFEST_FIXTURE)

    result = diff_manifests(recorded, fresh)
    assert result.exit_code == EXIT_OK, [finding.summary for finding in result.findings]
    assert not result.surface_hash_changed


def test_a_fresh_scan_is_byte_identical_to_the_fixture_file() -> None:
    """Stronger than the diff: the rendered bytes match too, which is what proves
    the checked-in file is reproducible rather than merely equivalent."""
    fresh = _fresh_scan()
    assert render_manifest(fresh) == MOCK_MANIFEST_FIXTURE.read_text(encoding="utf-8")
