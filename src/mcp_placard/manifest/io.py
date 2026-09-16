"""Reading and writing manifest documents.

Rendering goes through ``canonical.render_json`` so that a manifest written twice
from the same surface is byte-identical, and a manifest checked into a repository
produces a readable ``git diff``.

Loading is defensive: a manifest is an input file, and a malformed or
future-versioned one must produce a typed error the CLI can turn into exit code 10,
never a traceback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .. import MANIFEST_VERSION
from ..errors import ManifestValidationError, ManifestVersionError, UsageError
from .build import compute_classification_hash
from .canonical import render_json
from .models import Manifest

SUPPORTED_MANIFEST_VERSIONS = frozenset({"1.0", MANIFEST_VERSION})
"""Versions this build can read. "1.0" is Phase 1's format, added here rather than
rewritten in place — deliverable 10's backward-compatibility requirement."""

_EMPTY_CLASSIFICATION_HASH = compute_classification_hash([])


def _upgrade_legacy_document(document: dict[str, Any], version: str) -> dict[str, Any]:
    """Fill in fields a "1.0" document never had, so it validates against the
    current :class:`~mcp_placard.manifest.models.Manifest`.

    "1.0" manifests predate ``classification`` entirely — every tool in one was
    Phase 1's literal ``unclassified``, carried on the tool itself rather than as a
    separate structure. Reading one back gets an *empty* classification, not a
    reconstructed one: this build does not retroactively classify a manifest it did
    not produce. ``diff`` already treats a tool absent from ``classification`` as
    "cannot be graded" and falls back to its Phase 1 conservative default, so an old
    manifest diffed against a new one still behaves exactly as it did before this
    field existed.
    """
    if version != "1.0" or "classification_hash" in document:
        return document
    upgraded = dict(document)
    upgraded.setdefault("classification", [])
    upgraded.setdefault("classification_hash", _EMPTY_CLASSIFICATION_HASH)
    upgraded.setdefault("findings", [])
    return upgraded


def manifest_document(manifest: Manifest) -> dict[str, Any]:
    """Render a manifest to a plain JSON-compatible dict."""
    return manifest.model_dump(by_alias=True, exclude_none=True, mode="json")


def render_manifest(manifest: Manifest) -> str:
    """Render a manifest as indented canonical JSON text, newline-terminated."""
    return render_json(manifest_document(manifest))


def parse_manifest(text: str, *, source: str) -> Manifest:
    """Parse and validate manifest JSON text.

    ``source`` names the origin in error messages — a path, or ``"<stdin>"``.
    """
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"{source}: not valid JSON: {exc}") from exc

    if not isinstance(document, dict):
        raise ManifestValidationError(f"{source}: expected a JSON object at the top level")

    version = document.get("manifest_version")
    if version not in SUPPORTED_MANIFEST_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_MANIFEST_VERSIONS))
        raise ManifestVersionError(
            f"{source}: unsupported manifest_version {version!r} (this build reads: {supported})"
        )
    document = _upgrade_legacy_document(document, version)

    try:
        return Manifest.model_validate(document)
    except ValidationError as exc:
        raise ManifestValidationError(f"{source}: not a valid manifest: {exc}") from exc


def load_manifest(path: Path) -> Manifest:
    """Read and validate a manifest from disk."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"cannot read manifest {path}: {exc}") from exc
    return parse_manifest(text, source=str(path))


def write_manifest(manifest: Manifest, path: Path) -> None:
    """Write a manifest to ``path``, creating parent directories as needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_manifest(manifest), encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"cannot write manifest {path}: {exc}") from exc
