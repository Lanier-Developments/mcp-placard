"""Recompute a manifest's hashes and report any that do not match its content.

This is the integrity check behind ``placard verify``. It answers one question:
*does this file's recorded hashes actually describe the content sitting next to
them?* A mismatch means the manifest was edited after it was produced — by hand, by
a merge, or by someone trying to make a surface change look like it never happened.

The check runs in layers so a tamper cannot pass by being internally consistent at
only one level:

1. Each tool's ``schema_hash`` and ``description_hash`` are recomputed from that
   tool's own ``input_schema`` and ``description``.
2. ``surface_hash`` is recomputed over the surface *exactly as stored*, including
   the per-tool hashes that layer 1 just checked.
3. ``capabilities_hash`` is recomputed over ``capabilities`` independently — it does
   not feed ``surface_hash`` and ``surface_hash`` does not feed it, so this layer
   catches a capabilities tamper that layer 2 cannot see.
4. ``classification_hash`` is recomputed over ``classification`` independently, for
   the identical reason: a hand-edited tier must not pass just because the surface
   underneath it is untouched.

Editing a schema breaks layers 1 and 2. Editing a schema *and* its ``schema_hash``
still breaks layer 2. Every mismatch is collected rather than raised on first sight,
so one run reports the full extent of the damage.
"""

from __future__ import annotations

from .build import compute_capabilities_hash, compute_classification_hash, compute_surface_hash
from .hashing import hash_description, hash_schema
from .models import Manifest


def hash_mismatches(manifest: Manifest) -> list[str]:
    """Return one human-readable line per hash that does not match its content.

    An empty list means the manifest is internally consistent.
    """
    mismatches: list[str] = []

    for tool in manifest.surface.tools:
        expected_schema = hash_schema(tool.input_schema)
        if tool.schema_hash != expected_schema:
            mismatches.append(
                f"tool {tool.name!r}: schema_hash recorded {tool.schema_hash} "
                f"but input schema hashes to {expected_schema}"
            )

        expected_description = hash_description(tool.description)
        if tool.description_hash != expected_description:
            mismatches.append(
                f"tool {tool.name!r}: description_hash recorded {tool.description_hash} "
                f"but description hashes to {expected_description}"
            )

    expected_surface = compute_surface_hash(manifest.surface)
    if manifest.surface_hash != expected_surface:
        mismatches.append(
            f"surface_hash recorded {manifest.surface_hash} "
            f"but surface hashes to {expected_surface}"
        )

    expected_capabilities = compute_capabilities_hash(manifest.capabilities)
    if manifest.capabilities_hash != expected_capabilities:
        mismatches.append(
            f"capabilities_hash recorded {manifest.capabilities_hash} "
            f"but capabilities hashes to {expected_capabilities}"
        )

    expected_classification = compute_classification_hash(manifest.classification)
    if manifest.classification_hash != expected_classification:
        mismatches.append(
            f"classification_hash recorded {manifest.classification_hash} "
            f"but classification hashes to {expected_classification}"
        )

    return mismatches


def is_intact(manifest: Manifest) -> bool:
    """True when every recorded hash matches the content it covers."""
    return not hash_mismatches(manifest)
