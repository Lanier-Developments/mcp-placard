"""The override allowlist — deliverable 7. Downgrades come only from an explicit
config entry; the manifest records that one applied, which entry, and the tier it
would have been without it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_placard.classify import classify_tool
from mcp_placard.classify.overrides import OverrideEntry, apply, load_overrides
from mcp_placard.errors import UsageError
from mcp_placard.manifest.models import ToolEntry


def test_a_matching_entry_downgrades_and_records_itself() -> None:
    entry = OverrideEntry(entry_id="ok-1", tool="send_email", tier="R1", reason="reviewed")
    tier, applied = apply("send_email", "R4", [entry])
    assert tier == "R1"
    assert applied is not None
    assert applied.entry == "ok-1"
    assert applied.without_override_tier == "R4"


def test_a_non_matching_tool_name_is_inert() -> None:
    entry = OverrideEntry(entry_id="ok-1", tool="other_tool", tier="R1", reason="")
    tier, applied = apply("send_email", "R4", [entry])
    assert tier == "R4"
    assert applied is None


def test_an_entry_that_would_raise_the_tier_is_inert() -> None:
    """An override may only ever lower a tier — AGENTS.md forbids automatic
    downgrades, and an "override" that raises a tier isn't a downgrade at all."""
    entry = OverrideEntry(entry_id="ok-1", tool="search_documents", tier="R4", reason="")
    tier, applied = apply("search_documents", "R1", [entry])
    assert tier == "R1"
    assert applied is None


def test_an_entry_at_the_same_tier_is_inert() -> None:
    entry = OverrideEntry(entry_id="ok-1", tool="t", tier="R3", reason="")
    tier, applied = apply("t", "R3", [entry])
    assert tier == "R3"
    assert applied is None


def test_the_first_matching_entry_wins() -> None:
    entries = [
        OverrideEntry(entry_id="first", tool="t", tier="R2", reason=""),
        OverrideEntry(entry_id="second", tool="t", tier="R0", reason=""),
    ]
    tier, applied = apply("t", "R4", entries)
    assert tier == "R2"
    assert applied is not None
    assert applied.entry == "first"


def test_classify_tool_applies_an_override_end_to_end() -> None:
    tool = ToolEntry(
        name="send_email",
        input_schema={"type": "object", "properties": {"to": {"type": "string"}}},
        schema_hash="0" * 64,
        description_hash="0" * 64,
    )
    entry = OverrideEntry(
        entry_id="reviewed-1", tool="send_email", tier="R1", reason="internal only"
    )
    result = classify_tool(tool, [entry])
    assert result.tier == "R1"
    assert result.override is not None
    assert result.override.entry == "reviewed-1"
    assert result.override.without_override_tier == "R4"
    # The citations still show what was actually inferred, undisturbed by the override.
    assert any(c.tier == "R4" for c in result.citations)


# ------------------------------------------------------------------- load_overrides


def test_load_overrides_reads_a_valid_config(tmp_path: Path) -> None:
    path = tmp_path / "overrides.json"
    path.write_text(
        json.dumps([{"entry_id": "e1", "tool": "t", "tier": "R2", "reason": "reviewed"}]),
        encoding="utf-8",
    )
    entries = load_overrides(path)
    assert len(entries) == 1
    assert entries[0].entry_id == "e1"
    assert entries[0].tool == "t"
    assert entries[0].tier == "R2"
    assert entries[0].reason == "reviewed"


def test_load_overrides_defaults_reason_to_empty(tmp_path: Path) -> None:
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps([{"entry_id": "e1", "tool": "t", "tier": "R2"}]), encoding="utf-8")
    assert load_overrides(path)[0].reason == ""


def test_load_overrides_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="cannot read override config"):
        load_overrides(tmp_path / "absent.json")


def test_load_overrides_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "overrides.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(UsageError, match="not valid JSON"):
        load_overrides(path)


def test_load_overrides_rejects_a_non_array_top_level(tmp_path: Path) -> None:
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps({"tool": "t"}), encoding="utf-8")
    with pytest.raises(UsageError, match="expected a JSON array"):
        load_overrides(path)


def test_load_overrides_rejects_a_non_object_entry(tmp_path: Path) -> None:
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps(["not an object"]), encoding="utf-8")
    with pytest.raises(UsageError, match="expected an object"):
        load_overrides(path)


def test_load_overrides_rejects_a_missing_required_field(tmp_path: Path) -> None:
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps([{"entry_id": "e1", "tool": "t"}]), encoding="utf-8")
    with pytest.raises(UsageError, match="missing required field"):
        load_overrides(path)


def test_load_overrides_rejects_an_invalid_tier(tmp_path: Path) -> None:
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps([{"entry_id": "e1", "tool": "t", "tier": "R9"}]), encoding="utf-8")
    with pytest.raises(UsageError, match="not one of"):
        load_overrides(path)
