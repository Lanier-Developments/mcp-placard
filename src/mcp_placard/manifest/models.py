"""Pydantic models for a Placard manifest.

Two naming conventions coexist here on purpose:

* Fields that belong to the **MCP wire format** keep their wire spelling in the
  serialized manifest — ``inputSchema``, ``readOnlyHint``, ``uriTemplate``,
  ``mimeType``, ``_meta``. A reader comparing a manifest against a raw
  ``tools/list`` response should see the same keys in both.
* Fields **Placard itself owns** are ``snake_case`` — ``manifest_version``,
  ``surface_hash``, ``schema_hash``, ``description_hash``, ``resource_templates``,
  ``tier``. The casing tells you at a glance who asserted a given field.

Every model sets ``extra="allow"``. That is a fidelity requirement, not laziness: a
server may send fields this build has never heard of, and silently dropping them
would mean the manifest — and therefore ``surface_hash`` — did not actually cover
the surface. Unknown fields survive validation, serialization, and hashing intact.

Phase 1 performs **no risk classification**. Every tool carries the literal tier
``unclassified``; the raw ``annotations`` block is preserved verbatim so Phase 2's
declared-vs-inferred reconciliation has the server's own claims to work from.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RiskTier = Literal["unclassified"]
"""Phase 1's tier type. Phase 2 widens this to the R0-R5 ladder in docs/TAXONOMY.md."""

UNCLASSIFIED: RiskTier = "unclassified"
"""The only tier Phase 1 emits. Risk inference is Phase 2 (AGENTS.md, "Roadmap")."""


class SurfaceModel(BaseModel):
    """Base for every manifest structure.

    ``extra="allow"`` preserves server fields this build does not model.
    ``populate_by_name=True`` lets tests and builders construct models with readable
    Python names while serialization still emits the MCP wire spelling.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ToolAnnotations(SurfaceModel):
    """A tool's self-declared behavioural hints, recorded verbatim.

    AGENTS.md: *server self-declaration is evidence, not truth.* These values come
    from the party being audited. Placard stores them as reported and never lets
    them influence anything in Phase 1 — Phase 2 will compare them against inferred
    risk and report disagreement as a finding.

    All four hints are tri-state: ``True``, ``False``, or absent. Absent is not the
    same as ``False``, so the distinction is preserved rather than defaulted away.
    """

    title: str | None = None
    read_only_hint: bool | None = Field(default=None, alias="readOnlyHint")
    destructive_hint: bool | None = Field(default=None, alias="destructiveHint")
    idempotent_hint: bool | None = Field(default=None, alias="idempotentHint")
    open_world_hint: bool | None = Field(default=None, alias="openWorldHint")


class ToolEntry(SurfaceModel):
    """One tool as the server declares it, plus Placard' two per-tool hashes."""

    name: str
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] = Field(alias="inputSchema")
    output_schema: dict[str, Any] | None = Field(default=None, alias="outputSchema")
    annotations: ToolAnnotations | None = None
    meta: dict[str, Any] | None = Field(default=None, alias="_meta")

    schema_hash: str
    """SHA-256 over ``input_schema`` alone. Never combined with the description."""

    description_hash: str
    """SHA-256 over ``description`` alone. A change here is a prompt change."""

    tier: RiskTier = UNCLASSIFIED
    """Always ``unclassified`` in Phase 1."""


class ResourceEntry(SurfaceModel):
    """One concrete resource the server exposes.

    Resource ``annotations`` (audience, priority, lastModified) are a different shape
    from tool annotations and carry no blast-radius signal, so they are not modelled
    explicitly — ``extra="allow"`` carries them through unchanged.
    """

    name: str
    title: str | None = None
    uri: str
    description: str | None = None
    mime_type: str | None = Field(default=None, alias="mimeType")
    size: int | None = None
    meta: dict[str, Any] | None = Field(default=None, alias="_meta")


class ResourceTemplateEntry(SurfaceModel):
    """One parameterized resource URI template the server exposes."""

    name: str
    title: str | None = None
    uri_template: str = Field(alias="uriTemplate")
    description: str | None = None
    mime_type: str | None = Field(default=None, alias="mimeType")
    meta: dict[str, Any] | None = Field(default=None, alias="_meta")


class PromptArgumentEntry(SurfaceModel):
    """One argument accepted by a server-supplied prompt."""

    name: str
    title: str | None = None
    description: str | None = None
    required: bool | None = None


class PromptEntry(SurfaceModel):
    """One prompt template the server offers to the agent."""

    name: str
    title: str | None = None
    description: str | None = None
    arguments: list[PromptArgumentEntry] | None = None
    meta: dict[str, Any] | None = Field(default=None, alias="_meta")


class ServerInfo(SurfaceModel):
    """The server's self-reported identity from the initialize response.

    Only server-asserted values live here. The *negotiated* protocol version is
    deliberately absent: it is a property of the client/server pair, not of the
    surface, and including it would make ``surface_hash`` change when the client SDK
    is upgraded. See ``manifest/README.md``.
    """

    name: str
    title: str | None = None
    version: str | None = None
    description: str | None = None
    website_url: str | None = Field(default=None, alias="websiteUrl")


class ServerSurface(SurfaceModel):
    """Everything the server exposes to an agent — the body that ``surface_hash`` covers.

    Collections are stored sorted by a stable natural key (see ``manifest.build``) so
    that a server reordering its own listing does not register as a change.

    ``capabilities`` is deliberately *not* a field here. Some capability flags are
    derived by the server's SDK from the negotiated protocol version, so a client SDK
    upgrade can shift them even though the server did not change — see
    :class:`Manifest`. Mixing that into ``surface_hash`` would make a tool-surface
    change and an SDK-driven capability change indistinguishable.
    """

    server: ServerInfo
    instructions: str | None = None
    """Server instructions are model-facing text, and therefore part of the prompt
    surface. Included in ``surface_hash`` for exactly that reason."""

    tools: list[ToolEntry] = Field(default_factory=list)
    resources: list[ResourceEntry] = Field(default_factory=list)
    resource_templates: list[ResourceTemplateEntry] = Field(default_factory=list)
    prompts: list[PromptEntry] = Field(default_factory=list)


class Manifest(SurfaceModel):
    """A complete Placard manifest.

    ``manifest_version``, ``surface_hash``, and ``capabilities_hash`` sit *outside*
    the bodies they hash: a hash cannot cover itself, and bumping the manifest schema
    version must not invalidate every previously recorded hash.

    Three bodies, three independent hashes, deliberately not collapsed:

    * ``surface`` / ``surface_hash`` — the tool, resource, and prompt surface.
    * ``capabilities`` / ``capabilities_hash`` — the server's self-declared MCP
      capabilities block, split out so its own drift (see above) produces its own
      finding instead of masquerading as a surface change.
    * ``environment`` — SDK version, negotiated protocol version, and anything else
      that is a property of *this scan* rather than of the server. Never hashed by
      anything: two scans differing only in ``environment`` must agree on every hash.
    """

    manifest_version: str
    surface_hash: str
    capabilities_hash: str
    surface: ServerSurface
    capabilities: dict[str, Any] = Field(default_factory=dict)
    """The raw ``capabilities`` block from initialize, recorded but not part of
    ``surface_hash``. Open-ended by specification (``experimental``, ``extensions``),
    so it is carried as received."""

    environment: dict[str, Any] = Field(default_factory=dict)
    """Scan-circumstance metadata — SDK version, negotiated protocol version. Never
    an input to any hash in this manifest."""

    def tools_by_name(self) -> dict[str, ToolEntry]:
        """Index this manifest's tools by name — the key ``diff`` pairs them on."""
        return {tool.name: tool for tool in self.surface.tools}
