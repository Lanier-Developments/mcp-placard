"""``placard.toml`` — loading, validation, overrides, and the unpinned-target warning."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_placard.classify.overrides import OverrideEntry
from mcp_placard.config import (
    PlacardConfig,
    load_config,
    merge_overrides,
    unpinned_target_warnings,
)
from mcp_placard.errors import EXIT_USAGE, UsageError

MINIMAL = """
[[server]]
name = "mock"
target = "python -m tests.mock_server"
"""

FULL = """
[defaults]
ceiling = "R5"
baseline_dir = "baselines"
timeout = 12.5

[[server]]
name = "github"
target = "npx -y @modelcontextprotocol/server-github@2025.4.8"
env = ["GITHUB_PERSONAL_ACCESS_TOKEN"]

[[server]]
name = "docs"
target = "https://mcp.example.com/mcp"
header_env = ["Authorization=PLACARD_DOCS_TOKEN"]
baseline = "approved/docs.json"

[[override]]
server = "github"
tool = "create_pull_request_review"
tier = "R3"
reason = "Review comments reference a file; nothing is written to it."

[report.level]
prompt = "note"
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "placard.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_minimal_config_loads_with_defaults(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, MINIMAL))
    assert config.defaults.ceiling == "R4"
    assert config.defaults.baseline_dir == ".placard/baselines"
    assert [s.name for s in config.server] == ["mock"]
    assert config.report.level.injection == "error"
    assert (
        config.baseline_path(config.server[0], root=tmp_path)
        == (tmp_path / ".placard/baselines/mock.json").resolve()
    )


def test_full_config_loads(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, FULL))
    assert config.defaults.ceiling == "R5"
    docs = config.server_named("docs")
    assert config.baseline_path(docs, root=tmp_path) == (tmp_path / "approved/docs.json").resolve()
    assert config.report.level.prompt == "note"
    assert config.report.level.for_category("injection") == "error"
    [override] = config.overrides_for("github")
    assert override == OverrideEntry(
        entry_id="placard.toml:github/create_pull_request_review",
        tool="create_pull_request_review",
        tier="R3",
        reason="Review comments reference a file; nothing is written to it.",
    )
    assert config.overrides_for("docs") == []


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        (MINIMAL + '\n[defaults]\nceilng = "R4"\n', "ceilng"),
        (MINIMAL + '\n[[server]]\nname = "mock"\ntarget = "x"\n', "duplicate server name"),
        (MINIMAL + '\n[[override]]\nserver = "nope"\ntool = "t"\ntier = "R1"\n', "not configured"),
        (
            MINIMAL
            + '\n[[override]]\nserver = "mock"\ntool = "t"\ntier = "R1"\n'
            + '\n[[override]]\nserver = "mock"\ntool = "t"\ntier = "R2"\n',
            "conflicting overrides",
        ),
        (
            MINIMAL + '\n[[server]]\nname = "h"\ntarget = "https://x"\nheader_env = ["nope"]\n',
            "Header-Name=ENV_VAR",
        ),
        (MINIMAL + '\n[[server]]\nname = "bad name!"\ntarget = "x"\n', "name"),
        ("this is not toml = = =", "not valid TOML"),
    ],
)
def test_invalid_config_is_a_usage_error_with_a_readable_message(
    tmp_path: Path, text: str, fragment: str
) -> None:
    with pytest.raises(UsageError) as info:
        load_config(_write(tmp_path, text))
    assert info.value.exit_code == EXIT_USAGE
    assert fragment in str(info.value)


def test_a_missing_config_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(UsageError):
        load_config(tmp_path / "absent.toml")


# ------------------------------------------------------------- credentials


def test_headers_and_env_are_resolved_from_the_environment_not_the_file(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, FULL))
    docs = config.server_named("docs")
    assert docs.resolve_headers({"PLACARD_DOCS_TOKEN": "sentinel"}) == {"Authorization": "sentinel"}
    github = config.server_named("github")
    assert github.resolve_env({"GITHUB_PERSONAL_ACCESS_TOKEN": "s", "OTHER": "x"}) == {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "s"
    }
    assert "sentinel" not in (tmp_path / "placard.toml").read_text()


def test_a_missing_named_variable_is_a_usage_error_not_an_unauthenticated_scan(
    tmp_path: Path,
) -> None:
    config = load_config(_write(tmp_path, FULL))
    with pytest.raises(UsageError, match="PLACARD_DOCS_TOKEN"):
        config.server_named("docs").resolve_headers({})
    with pytest.raises(UsageError, match="GITHUB_PERSONAL_ACCESS_TOKEN"):
        config.server_named("github").resolve_env({})


# --------------------------------------------------------------- overrides


def test_cli_overrides_add_to_config_overrides() -> None:
    a = OverrideEntry(entry_id="cfg", tool="x", tier="R1")
    b = OverrideEntry(entry_id="cli", tool="y", tier="R2")
    assert merge_overrides([a], [b]) == [a, b]


def test_conflicting_overrides_are_a_usage_error_never_a_precedence() -> None:
    a = OverrideEntry(entry_id="cfg", tool="x", tier="R1")
    b = OverrideEntry(entry_id="cli", tool="x", tier="R3")
    with pytest.raises(UsageError, match="conflicting overrides"):
        merge_overrides([a], [b])
    # Same tool, same tier, from two sources: an agreement, not a conflict.
    assert merge_overrides([a], [OverrideEntry(entry_id="cli", tool="x", tier="R1")]) == [a]


# ------------------------------------------------------- unpinned targets


@pytest.mark.parametrize(
    ("target", "warns"),
    [
        ("npx -y @modelcontextprotocol/server-github", True),
        ("npx -y @modelcontextprotocol/server-github@latest", True),
        ("npx -y @modelcontextprotocol/server-github@2025.4.8", False),
        ("npx -y @playwright/mcp@0.0.41 --headless", False),
        ("npx some-package", True),
        ("npx some-package@1.2.3", False),
        ("uvx mcp-server-fetch", True),
        ("uvx mcp-server-fetch==0.6.3", False),
        ("uvx mcp-server-git@0.6.2 --repository .", False),
        ("python -m tests.mock_server", False),
        ("https://mcp.example.com/mcp", False),
    ],
)
def test_unpinned_npx_and_uvx_targets_warn(target: str, warns: bool) -> None:
    config = PlacardConfig.model_validate({"server": [{"name": "s", "target": target}]})
    warnings = unpinned_target_warnings(config)
    assert bool(warnings) is warns, warnings
    if warns:
        assert "drift" in warnings[0]
