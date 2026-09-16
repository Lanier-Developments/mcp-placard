#!/usr/bin/env python3
"""Fail if library code acquires the ability to invoke an MCP tool.

AGENTS.md states the hard non-goal plainly: *Placard never invokes a tool.*
No code path may call ``tools/call``. This check is the mechanical enforcement of
that rule so the guarantee does not rely on review attention alone.

It walks the AST of every module under ``src/`` and rejects:

* a call to anything named ``call_tool`` / ``callTool`` / ``call_tool_sync``
* a string literal equal to the ``tools/call`` JSON-RPC method name

Run standalone (``python scripts/check_no_tool_invocation.py``) or via pre-commit.
Exit status 0 means clean, 1 means at least one violation was found.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCANNED_ROOTS = ("src",)

FORBIDDEN_CALL_NAMES = frozenset({"call_tool", "callTool", "call_tool_sync"})
FORBIDDEN_METHOD_STRINGS = frozenset({"tools/call"})


def _called_name(node: ast.Call) -> str | None:
    """Return the simple name being called, if the call target has one."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def violations_in_source(source: str, path: Path) -> Iterator[str]:
    """Yield a human-readable violation line for each tool-invocation site."""
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _called_name(node)
            if name in FORBIDDEN_CALL_NAMES:
                yield f"{path}:{node.lineno}: call to {name}() — tool invocation is forbidden"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in FORBIDDEN_METHOD_STRINGS:
                yield (
                    f"{path}:{node.lineno}: literal {node.value!r} — "
                    "the tools/call method must never appear in library code"
                )


def scan(root: Path) -> list[str]:
    """Collect every violation under ``root``."""
    found: list[str] = []
    for source_root in SCANNED_ROOTS:
        for path in sorted((root / source_root).rglob("*.py")):
            found.extend(violations_in_source(path.read_text(encoding="utf-8"), path))
    return found


def main() -> int:
    found = scan(REPO_ROOT)
    if found:
        print("Placard must never invoke a tool. Offending sites:", file=sys.stderr)
        for line in found:
            print(f"  {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
