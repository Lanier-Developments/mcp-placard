"""Phase 4 §5: a launched server sees an explicitly constructed environment and a
temporary ``HOME`` — nothing inherited, nothing shared between servers.

The env-dump mock server writes what it actually received; these tests read it back.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcp_placard.transport import scan_target
from mcp_placard.transport.launch import (
    ISOLATED_VARIABLES,
    build_launch_environment,
    isolated_launch,
    shared_cache_dir,
)

from .conftest import mock_server_target

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def _cache_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the shared package cache out of the real home during tests."""
    monkeypatch.setenv("PLACARD_CACHE_DIR", str(tmp_path / "cache"))


def _launch_and_dump(tmp_path: Path, passthrough: dict[str, str] | None = None) -> dict[str, str]:
    dump = tmp_path / f"env-{os.getpid()}-{len(list(tmp_path.iterdir()))}.json"
    with isolated_launch(passthrough) as env:
        scan_target(mock_server_target("--dump-env", str(dump)), env=env, timeout=60)
        home_during = env["HOME"]
    received: dict[str, str] = json.loads(dump.read_text(encoding="utf-8"))
    received["__home_during__"] = home_during
    return received


def test_the_server_sees_only_the_permitted_variables(tmp_path: Path) -> None:
    received = _launch_and_dump(tmp_path)
    home_during = received.pop("__home_during__")
    # Platform loaders may add a couple of their own (e.g. macOS adds __CF_USER_TEXT_ENCODING);
    # everything Placard controls is exactly the isolated set, and nothing ambient leaks.
    controlled = {k for k in received if not k.startswith("__")}
    assert controlled <= ISOLATED_VARIABLES | _platform_noise(), sorted(controlled)
    assert received["HOME"] == home_during
    for ambient in ("USER", "LOGNAME", "SHELL", "TERM", "SSH_AUTH_SOCK", "AWS_PROFILE"):
        assert ambient not in received


def test_home_is_temporary_and_not_the_runners(tmp_path: Path) -> None:
    received = _launch_and_dump(tmp_path)
    assert received["HOME"] != str(Path.home())
    assert "placard-home-" in received["HOME"]
    assert not Path(received["HOME"]).exists()  # removed after the launch


def test_home_is_not_shared_between_launches(tmp_path: Path) -> None:
    first = _launch_and_dump(tmp_path)["HOME"]
    second = _launch_and_dump(tmp_path)["HOME"]
    assert first != second


def test_a_named_variable_passes_through_and_an_unnamed_one_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLACARD_TEST_SENTINEL", "sentinel-value")
    monkeypatch.setenv("PLACARD_TEST_OTHER", "other-value")
    received = _launch_and_dump(tmp_path, {"PLACARD_TEST_SENTINEL": "sentinel-value"})
    assert received["PLACARD_TEST_SENTINEL"] == "sentinel-value"
    assert "PLACARD_TEST_OTHER" not in received


def test_caches_are_redirected_so_npx_and_uvx_work_without_the_real_home() -> None:
    env = build_launch_environment(
        {}, home=Path("/srv/h"), cache=Path("/srv/c"), environ={"PATH": "/bin"}
    )
    assert env == {
        "PATH": "/bin",
        "HOME": "/srv/h",
        "npm_config_cache": "/srv/c/npm",
        "UV_CACHE_DIR": "/srv/c/uv",
    }


def test_a_passthrough_cannot_override_the_isolation_itself() -> None:
    env = build_launch_environment(
        {"HOME": "/root", "PATH": "/evil", "X": "1"},
        home=Path("/srv/h"),
        cache=Path("/srv/c"),
        environ={"PATH": "/bin"},
    )
    assert env["HOME"] == "/srv/h" and env["PATH"] == "/bin" and env["X"] == "1"


def test_the_shared_cache_honours_the_override_variable() -> None:
    assert shared_cache_dir({"PLACARD_CACHE_DIR": "/x/cache"}) == Path("/x/cache")
    assert shared_cache_dir({"XDG_CACHE_HOME": "/y"}) == Path("/y/placard")


def _platform_noise() -> frozenset[str]:
    """Variables the OS process loader injects regardless of what the parent passes.
    Not secrets, not inherited from the parent's environment, not under Placard's
    control."""
    return frozenset({"__CF_USER_TEXT_ENCODING", "__PYVENV_LAUNCHER__", "PWD", "LC_CTYPE"})
