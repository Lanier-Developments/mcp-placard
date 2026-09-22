"""``placard baseline`` and ``placard check``: the routing case, the no-baseline
case, the incomplete bit, header/env redaction with a sentinel, and outputs."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest

from mcp_placard.check import DEFAULT_FAIL_ON, CheckResult, run_check, write_baselines
from mcp_placard.cli import main
from mcp_placard.config import load_config
from mcp_placard.errors import (
    EXIT_DESCRIPTION_CHANGE,
    EXIT_ESCALATION,
    EXIT_INCOMPLETE,
    EXIT_OK,
    EXIT_UNREACHABLE,
    EXIT_USAGE,
)
from mcp_placard.manifest import load_manifest

pytestmark = pytest.mark.slow

PY = shlex.quote(sys.executable)


def _config(tmp_path: Path, *servers: str, extra: str = "") -> Path:
    body = '[defaults]\nbaseline_dir = "baselines"\n' + extra + "\n".join(servers)
    path = tmp_path / "placard.toml"
    path.write_text(body, encoding="utf-8")
    return path


def _mock(name: str, *args: str, env: str = "") -> str:
    target = " ".join([PY, "-m", "tests.mock_server", *args])
    env_line = f"\nenv = {env}" if env else ""
    return f'\n[[server]]\nname = "{name}"\ntarget = "{target}"{env_line}\n'


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    def _run(*argv: str) -> int:
        monkeypatch.setattr("sys.argv", ["placard", *argv])
        return main()

    return _run


# ---------------------------------------------------------------- baseline


def test_baseline_writes_one_manifest_per_server(tmp_path: Path, run) -> None:  # type: ignore[no-untyped-def]
    config = _config(tmp_path, _mock("a"), _mock("b", "--add-tool"))
    assert run("baseline", "--config", str(config)) == EXIT_OK
    a = load_manifest(tmp_path / "baselines" / "a.json")
    b = load_manifest(tmp_path / "baselines" / "b.json")
    assert len(b.surface.tools) == len(a.surface.tools) + 1
    assert a.ruleset_version is not None


def test_baseline_reports_an_unscannable_server_and_exits_3(tmp_path: Path, run) -> None:  # type: ignore[no-untyped-def]
    config = _config(
        tmp_path,
        _mock("ok"),
        '\n[[server]]\nname = "gone"\ntarget = "placard-no-such-binary-xyz"\n',
    )
    assert run("baseline", "--config", str(config)) == EXIT_UNREACHABLE
    assert (tmp_path / "baselines" / "ok.json").is_file()
    assert not (tmp_path / "baselines" / "gone.json").exists()


# ------------------------------------------------------------------- check


def test_check_with_matching_baselines_is_zero(tmp_path: Path, run) -> None:  # type: ignore[no-untyped-def]
    config = _config(tmp_path, _mock("a"))
    assert run("baseline", "--config", str(config)) == EXIT_OK
    assert run("check", "--config", str(config)) == EXIT_OK


def test_the_routing_case_prompt_change_passes_a_gate_that_does_not_fail_on_prompt(
    tmp_path: Path,
) -> None:
    """Acceptance, verbatim: an action run with a prompt change and
    ``fail-on: escalation,injection`` passes, and ``prompt`` output is true. The
    test that proves the bitmask was worth it."""
    config_path = _config(tmp_path, _mock("a"))
    config = load_config(config_path)
    write_baselines(config, root=tmp_path)
    # Now the server rewrites a description.
    changed = _config(tmp_path, _mock("a", "--description-variant", "b"))
    result = run_check(load_config(changed), root=tmp_path)
    assert result.status == EXIT_DESCRIPTION_CHANGE
    outputs = result.outputs(["escalation", "injection"])
    assert outputs["prompt"] is True
    assert outputs["escalation"] is False
    assert outputs["fail"] is False  # the gate passes
    assert result.outputs(list(DEFAULT_FAIL_ON))["fail"] is True  # the default would not


def test_bits_accumulate_across_servers_by_or(tmp_path: Path) -> None:
    config = load_config(_config(tmp_path, _mock("a"), _mock("b")))
    write_baselines(config, root=tmp_path)
    changed = load_config(
        _config(tmp_path, _mock("a", "--description-variant", "b"), _mock("b", "--add-tool"))
    )
    result = run_check(changed, root=tmp_path)
    by_name = {o.name: o.status for o in result.outcomes}
    assert by_name["a"] == EXIT_DESCRIPTION_CHANGE
    assert by_name["b"] == EXIT_ESCALATION
    assert result.status == EXIT_DESCRIPTION_CHANGE | EXIT_ESCALATION


def test_a_server_with_no_baseline_is_reported_not_failed(tmp_path: Path) -> None:
    result = run_check(load_config(_config(tmp_path, _mock("fresh"))), root=tmp_path)
    [outcome] = result.outcomes
    assert outcome.scanned and not outcome.baseline_present
    assert result.status == EXIT_OK
    assert "no baseline yet" in result.markdown()
    assert outcome.report is not None  # a full-manifest report still appears


def test_an_unscannable_server_sets_bit_16_and_fails_by_default(tmp_path: Path) -> None:
    config = load_config(
        _config(
            tmp_path,
            _mock("ok"),
            '\n[[server]]\nname = "gone"\ntarget = "placard-no-such-binary-xyz"\n',
        )
    )
    write_baselines(config, root=tmp_path)
    result = run_check(config, root=tmp_path)
    assert result.status & EXIT_INCOMPLETE
    assert result.outputs(list(DEFAULT_FAIL_ON))["incomplete"] is True
    assert result.outputs(list(DEFAULT_FAIL_ON))["fail"] is True
    assert result.outputs(["escalation"])["fail"] is False
    assert "could not be scanned" in result.markdown()


def test_check_exit_status_is_the_bitmask_and_outputs_carry_the_gate(
    tmp_path: Path, run, capsys
) -> None:  # type: ignore[no-untyped-def]
    config = _config(tmp_path, _mock("a"))
    run("baseline", "--config", str(config))
    changed = _config(tmp_path, _mock("a", "--description-variant", "b"))
    outputs = tmp_path / "out.json"
    rc = run(
        "check",
        "--config",
        str(changed),
        "--fail-on",
        "escalation,injection",
        "--sarif",
        str(tmp_path / "p.sarif"),
        "--summary",
        str(tmp_path / "s.md"),
        "--outputs",
        str(outputs),
    )
    assert rc == EXIT_DESCRIPTION_CHANGE
    data = json.loads(outputs.read_text())
    assert data["exit_code"] == EXIT_DESCRIPTION_CHANGE and data["prompt"] is True
    assert data["fail"] is False
    sarif = json.loads((tmp_path / "p.sarif").read_text())
    assert sarif["version"] == "2.1.0" and len(sarif["runs"]) == 1
    assert "Exit status 2" in (tmp_path / "s.md").read_text()
    assert "[tool_description_changed]" in capsys.readouterr().err


def test_an_unknown_fail_on_category_is_a_usage_error(tmp_path: Path, run) -> None:  # type: ignore[no-untyped-def]
    config = _config(tmp_path, _mock("a"))
    assert run("check", "--config", str(config), "--fail-on", "escalation,bogus") == EXIT_USAGE


# --------------------------------------------------------------- redaction


def test_a_sentinel_credential_appears_in_no_output_anywhere(
    tmp_path: Path, run, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    """Phase 4 §5: header/env values never appear in manifests, SARIF, the
    summary, or stderr. The mock server dumps its environment so we know it
    *received* the value; then every output is grepped for it."""
    sentinel = "SENTINEL-4f1c9e2b-do-not-leak"
    monkeypatch.setenv("PLACARD_TEST_TOKEN", sentinel)
    dump = tmp_path / "env.json"
    config = _config(
        tmp_path,
        _mock("a", "--dump-env", str(dump), env='["PLACARD_TEST_TOKEN"]'),
    )
    assert run("baseline", "--config", str(config)) == EXIT_OK
    assert json.loads(dump.read_text())["PLACARD_TEST_TOKEN"] == sentinel  # it was delivered
    rc = run(
        "check",
        "--config",
        str(config),
        "--sarif",
        str(tmp_path / "p.sarif"),
        "--summary",
        str(tmp_path / "s.md"),
        "--outputs",
        str(tmp_path / "o.json"),
    )
    assert rc == EXIT_OK
    captured = capsys.readouterr()
    for name in ("baselines/a.json", "p.sarif", "s.md", "o.json"):
        assert sentinel not in (tmp_path / name).read_text(), name
    assert sentinel not in captured.err and sentinel not in captured.out


def test_check_result_markdown_and_sarif_are_well_formed_when_empty() -> None:
    result = CheckResult()
    assert result.status == EXIT_OK
    assert "nothing to review" in result.markdown()
    assert result.sarif()["runs"] == []
