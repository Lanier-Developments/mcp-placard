"""Shared fixtures and builders for the Placard test suite.

Two kinds of test live here:

* **Unit tests** build manifests synthetically with :func:`make_manifest`. They are
  fast, they run everywhere, and they are how the diff table is exercised.
* **Integration tests** spawn ``tests.mock_server`` over real stdio and are marked
  ``slow``. They are the only place the MCP SDK, the subprocess, and the wire format
  are actually involved, and they are what proves the manifest is faithful to a real
  server response rather than to a hand-written fixture.
"""

from __future__ import annotations

import os
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from mcp_placard.manifest import Manifest, RawSurface, build_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
MOCK_MANIFEST_FIXTURE = FIXTURES / "mock_server_manifest.json"


@pytest.fixture(scope="session", autouse=True)
def _placard_cache_in_tmp(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Every launched server's package cache goes under pytest's temp root, never
    under the real home — the suite must not write outside its own sandbox."""
    previous = os.environ.get("PLACARD_CACHE_DIR")
    os.environ["PLACARD_CACHE_DIR"] = str(tmp_path_factory.mktemp("placard-cache"))
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PLACARD_CACHE_DIR", None)
        else:
            os.environ["PLACARD_CACHE_DIR"] = previous


@pytest.fixture(scope="session", autouse=True)
def _run_from_repo_root() -> Iterator[None]:
    """Run the whole suite from the repo root.

    ``python -m tests.mock_server`` has to resolve for the integration tests and for
    the CLI tests, which pass a target string through argv and so have no way to
    inject a ``PYTHONPATH``. Pinning the working directory once is less fragile than
    threading an environment through every call site.
    """
    previous = Path.cwd()
    os.chdir(REPO_ROOT)
    try:
        yield
    finally:
        os.chdir(previous)


def mock_server_target(*args: str) -> str:
    """Build a stdio target string that launches the mock server.

    ``sys.executable`` is quoted because a virtualenv path may contain spaces, and
    the target is parsed with :func:`shlex.split` exactly as a real one would be.
    """
    parts = [shlex.quote(sys.executable), "-m", "tests.mock_server", *args]
    return " ".join(parts)


@pytest.fixture
def mock_target() -> str:
    """The default, unmutated mock server target."""
    return mock_server_target()


def tool_wire(
    name: str,
    *,
    description: str | None = "A tool.",
    input_schema: dict[str, Any] | None = None,
    annotations: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build one tool in MCP wire form, as a server would send it."""
    payload: dict[str, Any] = {
        "name": name,
        "inputSchema": input_schema
        if input_schema is not None
        else {"type": "object", "properties": {}},
    }
    if description is not None:
        payload["description"] = description
    if annotations is not None:
        payload["annotations"] = annotations
    payload.update(extra)
    return payload


def make_raw(
    tools: list[dict[str, Any]] | None = None,
    *,
    server_name: str = "synthetic",
    instructions: str | None = None,
    resources: list[dict[str, Any]] | None = None,
    prompts: list[dict[str, Any]] | None = None,
    capabilities: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
) -> RawSurface:
    """Build a synthetic :class:`RawSurface` without touching a server."""
    return RawSurface(
        server_info={"name": server_name, "version": "0.0.1"},
        capabilities=capabilities
        if capabilities is not None
        else {"tools": {"listChanged": False}},
        environment=environment or {},
        instructions=instructions,
        tools=tools or [],
        resources=resources or [],
        prompts=prompts or [],
    )


def make_manifest(
    tools: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> Manifest:
    """Build a synthetic manifest — the fast path for unit tests."""
    return build_manifest(make_raw(tools, **kwargs))


@pytest.fixture
def baseline_manifest() -> Manifest:
    """A two-tool baseline that the diff table mutates."""
    return make_manifest(
        [
            tool_wire(
                "search_documents",
                description="Search the workspace index.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                annotations={"readOnlyHint": True, "openWorldHint": False},
            ),
            tool_wire(
                "write_note",
                description="Write a note into the workspace.",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "body": {"type": "string"}},
                    "required": ["path", "body"],
                },
                annotations={"readOnlyHint": False, "destructiveHint": False},
            ),
        ]
    )
