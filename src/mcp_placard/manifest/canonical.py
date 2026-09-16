"""Canonical JSON serialization.

Everything Placard hashes or compares passes through this module, so that two
scans of an unchanged server produce byte-identical output on any machine.

The rules, from AGENTS.md ("Manifest Format"):

* **Sorted keys.** Python dict order reflects insertion order, which reflects the
  order a server happened to serialize its response — not a property of the surface.
* **Stable array ordering.** Callers sort collections by a natural key before
  handing them here; see ``manifest.build``.
* **No environment-dependent values in the hashed body.** No timestamps, no scan
  target, no negotiated protocol version, no hostname. A manifest describes a
  server's surface, not the circumstances of one scan.

Two renderings exist and they are deliberately different:

``canonical_bytes``
    Compact (no whitespace), sorted, UTF-8. This is the *only* input to a hash.

``render_json``
    Indented, sorted, newline-terminated. This is what ``scan`` writes to stdout and
    to ``--out``. It is equally deterministic, just readable, so a checked-in
    manifest produces a legible ``git diff``.

Hash stability depends on ``canonical_bytes`` alone, so changing the presentation
format can never change a hash.
"""

from __future__ import annotations

import json
from typing import Any

JsonValue = Any
"""Arbitrary decoded JSON. Tool input schemas are unconstrained JSON Schema, so this
cannot be narrowed further without losing fidelity to what the server actually sent."""


def canonical_text(value: JsonValue) -> str:
    """Render ``value`` as canonical JSON text: sorted keys, no insignificant space.

    ``ensure_ascii`` is off so non-ASCII description text is emitted as real UTF-8
    rather than ``\\uXXXX`` escapes. That keeps the hashed bytes identical to what a
    reader sees, and keeps the form independent of the JSON encoder's escaping taste.
    """
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_bytes(value: JsonValue) -> bytes:
    """Render ``value`` as canonical JSON encoded UTF-8. The sole input to hashing."""
    return canonical_text(value).encode("utf-8")


def render_json(value: JsonValue) -> str:
    """Render ``value`` as human-readable canonical JSON, newline-terminated.

    Used for manifest output. Deterministic for the same reasons ``canonical_text``
    is, but indented so checked-in manifests diff legibly in review.
    """
    text = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
        separators=(",", ": "),
        allow_nan=False,
    )
    return f"{text}\n"
