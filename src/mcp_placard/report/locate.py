"""Map a JSON Pointer to a line in a rendered manifest.

SARIF's ``physicalLocation`` needs a file in the repository and, ideally, a line
region, so code scanning can attach an alert to the committed baseline. Placard's
manifests are rendered as indented canonical JSON (``manifest/canonical.py``: sorted
keys, two-space indent, one key or element per line), which makes line regions real
rather than fabricated: every pointer segment sits on its own line.

The walker reads the rendered text line by line, tracking a stack of open containers
by indentation, and stops at the line where the requested pointer's value begins. It
is written against the one format Placard writes and makes no attempt at general
JSON parsing — a manifest that was hand-reformatted is not a file this tool
produced, and ``report`` refuses anything that fails ``verify`` before it gets here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_KEY_LINE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*:\s*(.*?),?\s*$')
_CLOSER = re.compile(r"^\s*[\]}],?\s*$")


@dataclass
class _Frame:
    indent: int
    kind: str  # "object" | "array"
    next_index: int = 0


def _unescape_pointer_segment(segment: str) -> str:
    return segment.replace("~1", "/").replace("~0", "~")


def pointer_line(text: str, pointer: str) -> int | None:
    """The 1-based line on which the value at ``pointer`` begins in ``text``, or
    ``None`` if the pointer does not resolve. ``""`` is the document root."""
    if pointer == "":
        return 1
    if not pointer.startswith("/"):
        return None
    wanted = [_unescape_pointer_segment(s) for s in pointer[1:].split("/")]

    stack: list[_Frame] = []
    path: list[str] = []

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip(" "))

        # Any line at or left of an open container's own indent means that
        # container has closed (its closer sits at the same indent as its opener).
        while stack and indent <= stack[-1].indent:
            stack.pop()
            if path:
                path.pop()
        if _CLOSER.match(line):
            continue

        if not stack:
            if stripped in ("{", "["):
                stack.append(_Frame(indent, "object" if stripped == "{" else "array"))
                # The root has no path segment; keep ``path`` aligned by pushing a
                # sentinel that the pop above removes with the root frame.
                path.append("")
            continue

        top = stack[-1]
        if top.kind == "object":
            match = _KEY_LINE.match(line)
            if match is None:
                continue
            key = json.loads(f'"{match.group(1)}"')
            value = match.group(2).strip()
            current = [*path[1:], key]
            if current == wanted:
                return number
            if value in ("{", "["):
                stack.append(_Frame(indent, "object" if value == "{" else "array"))
                path.append(key)
        else:
            index = top.next_index
            top.next_index += 1
            value = stripped.rstrip(",")
            current = [*path[1:], str(index)]
            if current == wanted:
                return number
            if value in ("{", "["):
                stack.append(_Frame(indent, "object" if value == "{" else "array"))
                path.append(str(index))

    return None
