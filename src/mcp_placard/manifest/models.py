"""Pydantic models for a Placard manifest.

Two naming conventions coexist here on purpose:

* Fields that belong to the **MCP wire format** keep their wire spelling in the
  serialized manifest — ``inputSchema``, ``readOnlyHint``, ``uriTemplate``,
  ``mimeType``, ``_meta``. A reader comparing a manifest against a raw
  ``tools/list`` response should see the same keys in both.
* Fields **Placard itself owns** are ``snake_case`` — ``manifest_version``,
  ``surface_hash``, ``schema_hash``, ``description_hash``, ``resource_templates``,
  ``classification_hash``. The casing tells you at a glance who asserted a field.

Every model sets ``extra="allow"``. That is a fidelity requirement, not laziness: a
server may send fields this build has never heard of, and silently dropping them
would mean the manifest — and therefore ``surface_hash`` — did not actually cover
the surface. Unknown fields survive validation, serialization, and hashing intact.

**Risk classification is not part of ``ToolEntry`` or ``surface_hash``.** A tool's
inferred tier is Placard's own judgment about the surface, not a property of the
surface itself — the same reasoning that split ``capabilities`` out in Pre-work 1
applies one layer up here: a classifier rule fix must never move ``surface_hash``
for a server that did not change. Classification lives in :class:`ToolClassification`
under :attr:`Manifest.classification`, hashed independently as
``classification_hash``. See ``docs/TAXONOMY.md`` for the R0-R5 ladder this data
implements.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RiskTier = Literal["unclassified", "R0", "R1", "R2", "R3", "R4", "R5"]
"""Every tier a manifest's ``classification`` entries may carry. ``unclassified`` is
retained only so a Phase 1 manifest still parses (deliverable 10's backward-compat
fixture) — a build with a classifier never writes it; every tool it scans gets a
real tier. New code should prefer :data:`Tier`, which excludes ``unclassified``."""

Tier = Literal["R0", "R1", "R2", "R3", "R4", "R5"]
"""The R0-R5 ladder `docs/TAXONOMY.md` defines. What a classifier actually assigns."""

TIER_ORDER: tuple[Tier, ...] = ("R0", "R1", "R2", "R3", "R4", "R5")
"""Tiers in ascending severity — the ordering Rule F's monotonic maximum is taken
over. Index in this tuple is the only notion of "higher" or "lower" a tier has."""

UNCLASSIFIED: RiskTier = "unclassified"
"""The literal tier every Phase 1 manifest wrote. Never written by a classifying
build; recognized only when reading an old manifest."""

Reversibility = Literal["verified", "asserted", "unverifiable"]
"""Rule D's confidence state for a tool at R3 or above. See :class:`ToolClassification`."""


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
    """One tool exactly as the server declares it, plus Placard's two per-tool
    hashes. Everything on this model is either server-declared or a deterministic
    hash of server-declared content — nothing here is Placard's own judgment. See
    :class:`ToolClassification` for the inferred tier and the evidence behind it.
    """

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


class Citation(SurfaceModel):
    """One piece of evidence a signal extractor produced in support of a tier.

    ``docs/TAXONOMY.md``: *every assigned tier must cite the signals that produced
    it. A tier without stated reasoning is an opinion, not a finding.* This is that
    citation, structured rather than left as prose.

    Declared annotations are deliberately absent from ``signal``'s allowed values.
    They never independently vote for a tier — the "declared vs inferred" table's
    ``destructiveHint: true`` / inferred R1 row is explicitly "not a finding," which
    is only possible if annotations never enter Rule F's monotonic maximum. Their
    role is comparative evidence for :class:`Disagreement`, not a tier candidate.
    """

    signal: Literal["schema_shape", "tool_name_verb", "description_text"]
    tier: Tier
    """The tier this signal *alone* supports — not necessarily the tool's final
    tier, which is the monotonic maximum over every citation (Rule F)."""

    evidence: str
    """Human-readable specifics: a JSON Pointer into the schema for a schema-shape
    citation, the declared annotation and its value, the matched verb, or the
    description excerpt that matched."""

    rule: str | None = None
    """Which named rule this citation applies, e.g. ``"Rule A"`` — absent for a
    plain tier-table match that cites no amendment rule by name."""


class Disagreement(SurfaceModel):
    """One declared annotation that contradicts the inferred tier.

    ``docs/TAXONOMY.md``, "Declared vs inferred": disagreement is itself a finding,
    and the interesting direction is one-way — a server claiming more safety than
    its schema supports, never the reverse.
    """

    annotation: Literal["readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"]
    declared: bool
    inferred_tier: Tier
    reading: str
    """The human-readable finding text, e.g. "The server claims safety its schema
    does not support.\""""


class OverrideApplied(SurfaceModel):
    """Records that an explicit allowlist entry downgraded a tier.

    AGENTS.md: *never silently downgrade a tier because a server declares itself
    safe.* A downgrade is only ever this — an explicit, recorded, attributable
    override — never an automatic effect of a declared annotation.
    """

    entry: str
    """Which allowlist entry applied — an identifier from the consuming repo's
    override configuration, not a free-text explanation."""

    without_override_tier: Tier
    """The tier this tool would carry with no override applied. Always higher than
    :attr:`ToolClassification.tier` in the tier ordering — an override only lowers."""


class ToolClassification(SurfaceModel):
    """Placard's own judgment about one tool — never a hash input for
    ``surface_hash``. See :attr:`Manifest.classification_hash`.
    """

    tool: str
    """The :attr:`ToolEntry.name` this classification is about."""

    tier: Tier
    citations: list[Citation] = Field(default_factory=list)
    """Every signal that produced a candidate tier, not only the winning one — an
    R1 candidate sits alongside the R4 candidate that decided the tier, because
    ordering governs citation, not exclusion (Rule F)."""

    reversibility: Reversibility | None = None
    """Set only when :attr:`tier` is R3 or above (Rule D). ``None`` below R3, where
    reversibility is not a meaningful question."""

    disagreements: list[Disagreement] = Field(default_factory=list)
    override: OverrideApplied | None = None


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


class ServerFinding(SurfaceModel):
    """A server-level finding — a property of the whole surface's *composition*,
    not of any single tool. ``docs/TAXONOMY.md``, "Server-level findings":
    ``CHAIN_EXFIL`` is the one Phase 2 implements, raised when the surface exposes
    at least one R2-or-above read alongside at least one R4 egress tool.

    Carried on the manifest itself (produced at scan time), unlike a diff
    :class:`~mcp_placard.diff.models.Finding`, which only exists when comparing two
    manifests.
    """

    kind: Literal["chain_exfil"]
    summary: str
    tools: list[str]
    """The specific tools forming this chain — naming them, per the brief, rather
    than leaving a reader to infer which ones triggered it."""

    scope: str
    """States this finding's own boundary in its output, not only in the taxonomy —
    e.g. that it evaluates tools only and resources/prompts are not evaluated."""


class Manifest(SurfaceModel):
    """A complete Placard manifest.

    ``manifest_version``, ``surface_hash``, ``capabilities_hash``, and
    ``classification_hash`` sit *outside* the bodies they hash: a hash cannot cover
    itself, and bumping the manifest schema version must not invalidate every
    previously recorded hash.

    Four bodies, four independent hashes, deliberately not collapsed:

    * ``surface`` / ``surface_hash`` — the tool, resource, and prompt surface.
    * ``capabilities`` / ``capabilities_hash`` — the server's self-declared MCP
      capabilities block, split out so its own drift produces its own finding
      instead of masquerading as a surface change.
    * ``classification`` / ``classification_hash`` — Placard's own tier judgment,
      split out for the identical reason one layer up: a classifier rule change
      must not move ``surface_hash`` for a server that did not change (see
      ``manifest/models.py``'s module docstring).
    * ``environment`` — SDK version, negotiated protocol version, and anything else
      that is a property of *this scan* rather than of the server. Never hashed by
      anything: two scans differing only in ``environment`` must agree on every hash.
    """

    manifest_version: str
    surface_hash: str
    capabilities_hash: str
    classification_hash: str
    surface: ServerSurface
    capabilities: dict[str, Any] = Field(default_factory=dict)
    """The raw ``capabilities`` block from initialize, recorded but not part of
    ``surface_hash``. Open-ended by specification (``experimental``, ``extensions``),
    so it is carried as received."""

    classification: list[ToolClassification] = Field(default_factory=list)
    """One entry per tool in ``surface.tools`` once a classifier has run; empty on a
    manifest nothing has classified yet (a freshly built, pre-classification
    manifest, or an old Phase 1 manifest read back)."""

    findings: list[ServerFinding] = Field(default_factory=list)
    """Server-level findings computed at scan time, e.g. ``CHAIN_EXFIL``. Distinct
    from ``diff``'s findings, which only exist when comparing two manifests."""

    environment: dict[str, Any] = Field(default_factory=dict)
    """Scan-circumstance metadata — SDK version, negotiated protocol version. Never
    an input to any hash in this manifest."""

    def tools_by_name(self) -> dict[str, ToolEntry]:
        """Index this manifest's tools by name — the key ``diff`` pairs them on."""
        return {tool.name: tool for tool in self.surface.tools}

    def classification_by_tool(self) -> dict[str, ToolClassification]:
        """Index this manifest's classification entries by tool name."""
        return {entry.tool: entry for entry in self.classification}
