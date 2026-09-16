"""The raw capture handed from ``transport`` to ``manifest``.

``RawSurface`` is the contract between the two packages: transport produces it,
``manifest.build`` consumes it. It holds MCP wire JSON exactly as the server sent it
— no sorting, no hashing, no normalization, nothing dropped.

It lives in ``manifest`` rather than ``transport`` so that ``diff`` and ``verify``,
which only ever read manifests off disk, can import the manifest package without
pulling in the MCP SDK and its transport dependencies.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RawSurface(BaseModel):
    """Unprocessed enumeration output for a single server.

    Every field holds decoded MCP wire JSON with its original camelCase keys. This
    model is never written to disk; it is the intermediate that ``build_manifest``
    turns into a canonical, sorted, hashed :class:`~mcp_placard.manifest.models.Manifest`.
    """

    model_config = ConfigDict(extra="forbid")

    server_info: dict[str, Any] = Field(default_factory=dict)
    """The ``serverInfo`` block from the initialize response."""

    capabilities: dict[str, Any] = Field(default_factory=dict)
    """The ``capabilities`` block from the initialize response."""

    environment: dict[str, Any] = Field(default_factory=dict)
    """Scan-circumstance metadata — SDK version, negotiated protocol version. A
    property of this scan, never of the server; never hashed."""

    instructions: str | None = None
    """Server instructions from initialize — model-facing text, part of the prompt surface."""

    tools: list[dict[str, Any]] = Field(default_factory=list)
    resources: list[dict[str, Any]] = Field(default_factory=list)
    resource_templates: list[dict[str, Any]] = Field(default_factory=list)
    prompts: list[dict[str, Any]] = Field(default_factory=list)
