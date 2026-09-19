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

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

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

Kind = Literal["read_sensitive", "egress", "write", "destructive", "code_exec"]
"""The second axis Amendment 2 adds, orthogonal to :data:`Tier`. ``docs/TAXONOMY.md``,
"Kinds": the tier ladder must stay totally ordered to function as a CI ceiling, so
*what a tool does* — reads sensitive data, moves data outward, writes, destroys,
executes caller-supplied code — lives here instead. A tool may carry several kinds
or none. Kinds never affect tier and tier never affects kinds."""

KIND_ORDER: tuple[Kind, ...] = ("read_sensitive", "egress", "write", "destructive", "code_exec")
"""Canonical serialization order for a tool's ``kinds`` list. Not a severity order —
kinds are unordered by meaning; this exists only so two scans agree byte for byte."""


def _drop_empty_kinds(data: dict[str, Any]) -> dict[str, Any]:
    """Omit ``kinds`` from a serialized body when it is empty.

    A ``"2.0"`` manifest predates ``kinds`` entirely, and its recorded
    ``classification_hash`` was computed over bodies with no such key. Serializing
    an absent-or-empty ``kinds`` as *nothing* keeps that hash reproducible under this
    build, so ``verify`` on a stored ``"2.0"`` baseline still passes, and a ``"2.1"``
    entry for a tool with no kind-bearing evidence is byte-identical to what ``"2.0"``
    wrote for it. Absent and empty are the same statement: no kind evidence found.
    """
    if not data.get("kinds"):
        data.pop("kinds", None)
    return data


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

    ``declared_annotations`` is a signal since Amendment 2 §7, in one direction only:
    a server declaring *more* danger than the schema shows (``destructiveHint:
    true``) is a claim against interest and escalates to a floor of R3. A server
    declaring *less* never enters Rule F's maximum; that direction is
    :class:`Disagreement`'s job.
    """

    signal: Literal[
        "schema_shape",
        "tool_name_verb",
        "description_text",
        "declared_annotations",
        "code_execution",
    ]
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

    kinds: list[Kind] = Field(default_factory=list)
    """The kinds this evidence establishes (Amendment 2 §3). A kind on a
    :class:`ToolClassification` always traces back to at least one citation
    carrying it — a kind with no citation is as much a bug as a tier with none."""

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return _drop_empty_kinds(handler(self))


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

    kinds: list[Kind] = Field(default_factory=list)
    """What this tool does, orthogonal to how far it reaches (Amendment 2 §3).
    The union of every citation's ``kinds``, in :data:`KIND_ORDER`. Empty means no
    kind-bearing evidence was found — legal, and serialized as absent."""

    reversibility: Reversibility | None = None
    """Set only when :attr:`tier` is R3 or above (Rule D). ``None`` below R3, where
    reversibility is not a meaningful question."""

    disagreements: list[Disagreement] = Field(default_factory=list)
    override: OverrideApplied | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return _drop_empty_kinds(handler(self))


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
    at least one tool of kind ``read_sensitive`` and at least one of kind ``egress``
    (Amendment 2 §4 — tier is not consulted; one tool carrying both kinds suffices).

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
