"""SHA-256 hashing over canonical JSON.

AGENTS.md mandates independent hash levels, all required, and forbids collapsing them:

``surface_hash``
    The tool, resource, and prompt surface. Answers "did anything at all change?".

``schema_hash`` (per tool)
    The tool's input schema and nothing else. Answers "did the callable API change?".

``description_hash`` (per tool)
    The tool's description text and nothing else. Answers "did the prompt change?".

``capabilities_hash``
    The server's self-declared MCP capabilities block and nothing else. Split out of
    ``surface_hash`` because some capability flags are SDK-derived and can drift on a
    client SDK upgrade with no server-side change at all.

The split is the entire point. A server that rewrites a tool description while
leaving the API byte-identical has injected new instructions into every agent that
connects to it, and a single combined hash would render that indistinguishable from
a harmless refactor. Do not merge these for convenience.

Descriptions are hashed via their canonical JSON form rather than their raw text so
that an absent description (``null``) and an empty description (``""``) hash
differently. "The server removed the description" and "the server blanked the
description" are different events.
"""

from __future__ import annotations

import hashlib

from .canonical import JsonValue, canonical_bytes

HASH_ALGORITHM = "sha256"
"""Named here so manifests and docs cannot drift from the implementation."""


def sha256_hex(payload: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of ``payload``."""
    return hashlib.sha256(payload).hexdigest()


def hash_value(value: JsonValue) -> str:
    """Hash any JSON-serializable value through its canonical rendering."""
    return sha256_hex(canonical_bytes(value))


def hash_schema(input_schema: dict[str, JsonValue]) -> str:
    """Hash a tool's input schema — the schema only, never the description.

    The schema is hashed exactly as the server sent it, with no normalization beyond
    canonical JSON. Rewriting ``{"type": "string"}`` into an equivalent-but-different
    schema is a real change to the surface and must be visible as one.
    """
    return hash_value(input_schema)


def hash_description(description: str | None) -> str:
    """Hash a tool's description text — the description only, never the schema."""
    return hash_value(description)


def hash_capabilities(capabilities: dict[str, JsonValue]) -> str:
    """Hash the server's ``capabilities`` block — split out of ``surface_hash``.

    Some capability flags are derived by the server's SDK from the negotiated
    protocol version, so a client SDK upgrade can shift this hash even though the
    server did not change. Keeping it independent of ``surface_hash`` means that
    drift produces its own finding instead of masquerading as a surface change.
    """
    return hash_value(capabilities)
