"""CLI behaviour: stream discipline and the exit-code table.

``cli.py`` is the only module allowed to print or set an exit code, so this is where
the AGENTS.md exit-code table is asserted end to end.

Stream discipline is tested as carefully as the codes. ``scan`` is designed to be
piped, so stdout must carry the manifest and *only* the manifest — a diagnostic line
leaking into it would break every consumer downstream.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_placard import MANIFEST_VERSION
from mcp_placard.cli import main
from mcp_placard.errors import (
    EXIT_DESCRIPTION_CHANGE,
    EXIT_ESCALATION,
    EXIT_OK,
    EXIT_REMOVED_OR_UNREACHABLE,
    EXIT_USAGE,
)
from mcp_placard.manifest import render_manifest

from .conftest import make_manifest, tool_wire


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Invoke the CLI exactly as the console script does, and return its exit code."""

    def _run(*argv: str) -> int:
        monkeypatch.setattr("sys.argv", ["placard", *argv])
        return main()

    return _run


def _write(path: Path, *tools: dict[str, object]) -> Path:
    path.write_text(render_manifest(make_manifest(list(tools))), encoding="utf-8")  # type: ignore[arg-type]
    return path


# --------------------------------------------------------------------------- diff


def test_diff_identical_exits_zero(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    old = _write(tmp_path / "old.json", tool_wire("a"))
    new = _write(tmp_path / "new.json", tool_wire("a"))
    assert run("diff", str(old), str(new)) == EXIT_OK
    assert "no change" in capsys.readouterr().err


def test_diff_added_tool_exits_one(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    old = _write(tmp_path / "old.json", tool_wire("a"))
    new = _write(tmp_path / "new.json", tool_wire("a"), tool_wire("b"))
    assert run("diff", str(old), str(new)) == EXIT_ESCALATION
    assert "tool_added" in capsys.readouterr().err


def test_diff_description_change_exits_two(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    old = _write(tmp_path / "old.json", tool_wire("a", description="before"))
    new = _write(tmp_path / "new.json", tool_wire("a", description="after"))
    assert run("diff", str(old), str(new)) == EXIT_DESCRIPTION_CHANGE
    assert "tool_description_changed" in capsys.readouterr().err


def test_diff_removed_tool_exits_three(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    old = _write(tmp_path / "old.json", tool_wire("a"), tool_wire("b"))
    new = _write(tmp_path / "new.json", tool_wire("a"))
    assert run("diff", str(old), str(new)) == EXIT_REMOVED_OR_UNREACHABLE
    assert "tool_removed" in capsys.readouterr().err


def test_diff_reports_a_surface_only_change_without_failing(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from mcp_placard.manifest import build_manifest

    from .conftest import make_raw

    old = _write(tmp_path / "old.json", tool_wire("a"))
    manifest = build_manifest(
        make_raw([tool_wire("a")], resources=[{"name": "r", "uri": "file:///r"}])
    )
    new = tmp_path / "new.json"
    new.write_text(render_manifest(manifest), encoding="utf-8")

    assert run("diff", str(old), str(new)) == EXIT_OK
    assert "surface_hash changed" in capsys.readouterr().err


def test_diff_writes_findings_to_stderr_not_stdout(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    old = _write(tmp_path / "old.json", tool_wire("a", description="before"))
    new = _write(tmp_path / "new.json", tool_wire("a", description="after"))
    run("diff", str(old), str(new))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err


def test_diff_on_a_missing_file_exits_ten(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    old = _write(tmp_path / "old.json", tool_wire("a"))
    assert run("diff", str(old), str(tmp_path / "absent.json")) == EXIT_USAGE
    assert "cannot read manifest" in capsys.readouterr().err


def test_diff_on_malformed_json_exits_ten(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    old = _write(tmp_path / "old.json", tool_wire("a"))
    bad = tmp_path / "bad.json"
    bad.write_text("{oh no", encoding="utf-8")
    assert run("diff", str(old), str(bad)) == EXIT_USAGE
    assert "not valid JSON" in capsys.readouterr().err


def test_diff_on_an_unsupported_version_exits_ten(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    old = _write(tmp_path / "old.json", tool_wire("a"))
    document = json.loads(render_manifest(make_manifest([tool_wire("a")])))
    document["manifest_version"] = "0.1-ancient"
    future = tmp_path / "future.json"
    future.write_text(json.dumps(document), encoding="utf-8")

    assert run("diff", str(old), str(future)) == EXIT_USAGE
    assert "unsupported manifest_version" in capsys.readouterr().err


# ------------------------------------------------------------------------- verify


def test_verify_intact_exits_zero(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    path = _write(tmp_path / "m.json", tool_wire("a"))
    assert run("verify", str(path)) == EXIT_OK
    captured = capsys.readouterr()
    assert "intact" in captured.err
    assert captured.out == ""


def test_verify_detects_tampering_and_exits_one(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    document = json.loads(render_manifest(make_manifest([tool_wire("a", description="before")])))
    document["surface"]["tools"][0]["description"] = "quietly rewritten"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    assert run("verify", str(path)) == EXIT_ESCALATION
    err = capsys.readouterr().err
    assert "hash_mismatch" in err
    assert "description_hash" in err


def test_verify_on_a_missing_file_exits_ten(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    assert run("verify", str(tmp_path / "absent.json")) == EXIT_USAGE
    assert "cannot read manifest" in capsys.readouterr().err


def test_verify_reports_every_mismatch(run, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    document = json.loads(render_manifest(make_manifest([tool_wire("a"), tool_wire("b")])))
    document["surface"]["tools"][0]["schema_hash"] = "0" * 64
    document["surface"]["tools"][1]["description_hash"] = "1" * 64
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    run("verify", str(path))
    assert capsys.readouterr().err.count("[hash_mismatch]") == 3


# --------------------------------------------------------------------------- scan


def test_scan_on_an_unreachable_server_exits_three(run, capsys) -> None:  # type: ignore[no-untyped-def]
    assert run("scan", "placard-no-such-binary-xyz") == EXIT_REMOVED_OR_UNREACHABLE
    assert "error:" in capsys.readouterr().err


def test_scan_with_http_transport_against_a_command_exits_ten(run, capsys) -> None:  # type: ignore[no-untyped-def]
    assert run("scan", "some-command", "--transport", "http") == EXIT_USAGE
    assert "requires an http" in capsys.readouterr().err


def test_scan_with_an_empty_target_exits_ten(run) -> None:  # type: ignore[no-untyped-def]
    assert run("scan", "") == EXIT_USAGE


# -------------------------------------------------------------------------- misc


def test_version_prints_both_versions(run, capsys) -> None:  # type: ignore[no-untyped-def]
    assert run("version") == EXIT_OK
    assert MANIFEST_VERSION in capsys.readouterr().out


def test_an_unknown_command_exits_ten(run) -> None:  # type: ignore[no-untyped-def]
    assert run("nonsense-command") == EXIT_USAGE


def test_no_arguments_shows_help_and_exits_ten(run, capsys) -> None:  # type: ignore[no-untyped-def]
    """A bare invocation is a usage error, not a crash and not a success. The help
    text is printed, and the code is the one AGENTS.md reserves for usage errors."""
    assert run() == EXIT_USAGE
    assert "Usage:" in capsys.readouterr().out


def test_help_exits_zero(run) -> None:  # type: ignore[no-untyped-def]
    """Asking for help is not an error."""
    assert run("--help") == EXIT_OK
