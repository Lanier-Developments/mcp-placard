"""The hard non-goal, enforced mechanically.

AGENTS.md: *Placard never invokes a tool. No code path may call ``tools/call``.
A PR that adds one is rejected on sight.*

"Rejected on sight" needs something that actually looks. These tests run the same
AST check that pre-commit and CI run, and additionally prove the check is capable of
catching a violation — a guard that always passes is not a guard.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from .conftest import REPO_ROOT

CHECKER = REPO_ROOT / "scripts" / "check_no_tool_invocation.py"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_no_tool_invocation", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_library_contains_no_tool_invocation() -> None:
    module = _load_checker()
    assert module.scan(REPO_ROOT) == []


def test_the_checker_runs_clean_as_a_subprocess() -> None:
    """The exact invocation pre-commit uses."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(CHECKER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_the_checker_catches_a_method_call() -> None:
    module = _load_checker()
    source = "async def go(client):\n    return await client.call_tool('x', {})\n"
    found = list(module.violations_in_source(source, Path("fake.py")))
    assert found and "call_tool" in found[0]


def test_the_checker_catches_the_raw_method_string() -> None:
    """Bypassing the typed client and hand-rolling the JSON-RPC call is still a
    tool invocation."""
    module = _load_checker()
    source = 'METHOD = "tools/call"\n'
    found = list(module.violations_in_source(source, Path("fake.py")))
    assert found and "tools/call" in found[0]


def test_the_checker_accepts_enumeration_calls() -> None:
    """The four listing methods and initialize are the whole permitted vocabulary."""
    module = _load_checker()
    source = (
        "async def go(client):\n"
        "    await client.list_tools()\n"
        "    await client.list_resources()\n"
        "    await client.list_resource_templates()\n"
        "    await client.list_prompts()\n"
    )
    assert list(module.violations_in_source(source, Path("fake.py"))) == []


def test_the_mock_server_cannot_be_invoked() -> None:
    """The fixture for an enumeration-only scanner registers no ``tools/call``
    handler at all, so the guarantee is structural on both sides of the wire."""
    from .mock_server.server import build_server
    from .mock_server.surface import MockConfig

    server = build_server(MockConfig())
    capabilities = server.get_capabilities()
    assert capabilities.tools is not None
    assert "tools/call" not in server._request_handlers
