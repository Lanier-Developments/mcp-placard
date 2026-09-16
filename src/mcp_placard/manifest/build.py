"""Turn a raw enumeration capture into a canonical, hashed manifest.

This is where the three determinism rules are actually applied:

1. **Stable array ordering.** Collections are sorted by a natural key. A server that
   reorders its own ``tools/list`` response has not changed its surface, and must not
   produce a diff.
2. **Per-tool hashes are computed before the surface hash**, so ``surface_hash``
   covers the per-tool hashes too — tampering with a recorded ``schema_hash`` breaks
   the surface hash as well.
3. **Nothing environment-dependent enters a hashed body.** The scan target and the
   wall clock never reach a manifest at all. The negotiated protocol version and the
   SDK version do reach it, but only inside ``environment`` — the one field this
   module never hashes.

Three independent hashes come out of this module: ``surface_hash`` (tools, resources,
prompts, instructions), ``capabilities_hash`` (the server's declared capabilities,
split out because it can drift on a client SDK upgrade with no server-side change),
and the per-tool ``schema_hash`` / ``description_hash`` pair nested inside
``surface_hash``'s own body.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .. import MANIFEST_VERSION
from ..errors import ManifestValidationError
from .canonical import canonical_text
from .hashing import hash_capabilities, hash_description, hash_schema, hash_value
from .models import (
    UNCLASSIFIED,
    Manifest,
    PromptEntry,
    ResourceEntry,
    ResourceTemplateEntry,
    ServerInfo,
    ServerSurface,
    ToolEntry,
)
from .raw import RawSurface

WireDict = dict[str, Any]


def _sorted_by(entries: list[WireDict], *keys: str) -> list[WireDict]:
    """Sort wire dicts by the named keys, then by their full canonical form.

    The canonical-form tiebreaker matters: the MCP specification does not forbid a
    server from listing two tools under the same name, and sorting on the name alone
    would leave their relative order at the mercy of the server's response order —
    which is exactly the nondeterminism this function exists to remove.
    """
    return sorted(
        entries,
        key=lambda entry: ([str(entry.get(key, "")) for key in keys], canonical_text(entry)),
    )


def _build_tool(raw_tool: WireDict) -> ToolEntry:
    """Validate one wire tool and attach its two independent hashes.

    ``schema_hash`` and ``description_hash`` are computed from separate inputs and
    stay separate forever. Collapsing them would hide a description-only rewrite,
    which is the single event Placard exists to surface.
    """
    payload = dict(raw_tool)
    payload["schema_hash"] = hash_schema(payload.get("inputSchema", {}))
    payload["description_hash"] = hash_description(payload.get("description"))
    payload["tier"] = UNCLASSIFIED
    return ToolEntry.model_validate(payload)


def surface_document(surface: ServerSurface) -> WireDict:
    """Render a surface to the plain-JSON dict that ``surface_hash`` is taken over.

    ``exclude_none`` keeps absent optional fields out of the body entirely, so a
    server that omits a field and a build that models it as ``None`` produce the same
    bytes. ``by_alias`` emits MCP wire spellings for MCP-owned fields.
    """
    return surface.model_dump(by_alias=True, exclude_none=True, mode="json")


def compute_surface_hash(surface: ServerSurface) -> str:
    """SHA-256 over the canonical JSON of the whole surface."""
    return hash_value(surface_document(surface))


def compute_capabilities_hash(capabilities: WireDict) -> str:
    """SHA-256 over the server's ``capabilities`` block alone."""
    return hash_capabilities(capabilities)


def build_surface(raw: RawSurface) -> ServerSurface:
    """Validate and canonically order a raw capture into a :class:`ServerSurface`."""
    try:
        return ServerSurface(
            server=ServerInfo.model_validate(raw.server_info),
            instructions=raw.instructions,
            tools=[_build_tool(tool) for tool in _sorted_by(raw.tools, "name")],
            resources=[
                ResourceEntry.model_validate(entry)
                for entry in _sorted_by(raw.resources, "uri", "name")
            ],
            resource_templates=[
                ResourceTemplateEntry.model_validate(entry)
                for entry in _sorted_by(raw.resource_templates, "uriTemplate", "name")
            ],
            prompts=[
                PromptEntry.model_validate(entry) for entry in _sorted_by(raw.prompts, "name")
            ],
        )
    except ValidationError as exc:
        raise ManifestValidationError(
            f"server surface did not validate against the manifest schema: {exc}"
        ) from exc


def build_manifest(raw: RawSurface) -> Manifest:
    """Build a complete manifest, including every hash, from a raw capture."""
    surface = build_surface(raw)
    return Manifest(
        manifest_version=MANIFEST_VERSION,
        surface_hash=compute_surface_hash(surface),
        capabilities_hash=compute_capabilities_hash(raw.capabilities),
        surface=surface,
        capabilities=raw.capabilities,
        environment=raw.environment,
    )
