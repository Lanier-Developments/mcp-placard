"""Canonical serialization, hashing, and the manifest schema.

Public surface of this package:

* :class:`~mcp_placard.manifest.raw.RawSurface` — the capture ``transport`` produces
* :func:`build_manifest` — raw capture to canonical hashed manifest
* :func:`render_manifest` / :func:`parse_manifest` / :func:`load_manifest` /
  :func:`write_manifest` — manifest documents on the wire and on disk
* :func:`hash_mismatches` — integrity check behind ``placard verify``

This package has no dependency on the MCP SDK. ``diff`` and ``verify`` read
manifests without any transport machinery being importable.
"""

from __future__ import annotations

from .build import build_manifest, build_surface, compute_surface_hash, surface_document
from .canonical import canonical_bytes, canonical_text, render_json
from .hashing import hash_description, hash_schema, hash_value
from .io import (
    SUPPORTED_MANIFEST_VERSIONS,
    load_manifest,
    manifest_document,
    parse_manifest,
    render_manifest,
    write_manifest,
)
from .models import (
    UNCLASSIFIED,
    Manifest,
    PromptArgumentEntry,
    PromptEntry,
    ResourceEntry,
    ResourceTemplateEntry,
    RiskTier,
    ServerInfo,
    ServerSurface,
    ToolAnnotations,
    ToolEntry,
)
from .raw import RawSurface
from .verify import hash_mismatches, is_intact

__all__ = [
    "SUPPORTED_MANIFEST_VERSIONS",
    "UNCLASSIFIED",
    "Manifest",
    "PromptArgumentEntry",
    "PromptEntry",
    "RawSurface",
    "ResourceEntry",
    "ResourceTemplateEntry",
    "RiskTier",
    "ServerInfo",
    "ServerSurface",
    "ToolAnnotations",
    "ToolEntry",
    "build_manifest",
    "build_surface",
    "canonical_bytes",
    "canonical_text",
    "compute_surface_hash",
    "hash_description",
    "hash_mismatches",
    "hash_schema",
    "hash_value",
    "is_intact",
    "load_manifest",
    "manifest_document",
    "parse_manifest",
    "render_json",
    "render_manifest",
    "surface_document",
    "write_manifest",
]
