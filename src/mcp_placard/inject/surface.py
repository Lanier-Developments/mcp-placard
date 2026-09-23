"""Enumerate every model-facing string in a manifest (Phase 3 §3).

Everything here is text the server hands to the agent's context: tool
descriptions and titles, **property-level descriptions inside input schemas** (a
known poisoning vector — the instruction sits in a parameter description rather
than the tool description — walked with the Rule G schema walker so nothing nested
is missed), server ``instructions``, prompt and prompt-argument descriptions, and
resource and resource-template descriptions.

Resource *contents* are out of scope: reading them needs ``resources/read``, which
fetches live and possibly sensitive data and turns a static scan into a
data-collection step. Recorded as a non-detection in ``docs/THREAT_MODEL.md``.

Each :class:`TextElement` carries the context the class heuristics need to tell a
scope violation from a tool doing its job: this server's own tool names (a
reference to one is in scope; a reference to a tool the server does not have is
``cross_scope``), the owning tool's own parameter names, and whether the owning
tool handles paths or credentials by schema evidence (a filesystem tool mentioning
paths is doing its job; a weather tool mentioning ``~/.ssh`` is not).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from ..classify.schema_walk import TraversalStatus, walk_schema
from ..manifest.models import Manifest, ToolEntry

PATH_HANDLING_FIELDS = frozenset(
    {
        "path",
        "paths",
        "file",
        "files",
        "file_path",
        "filepath",
        "filename",
        "directory",
        "dir",
        "folder",
        "source",
        "destination",
        "dest",
        "target_path",
        "output_path",
        "root",
        "cwd",
        "repo_path",
        "repository",
        "glob",
        "pattern",
    }
)
"""A tool with one of these parameters handles paths; path-like mentions in its
text are in scope for it (``sensitive_target`` does not fire on them)."""

CREDENTIAL_HANDLING_TOKENS = ("key", "token", "secret", "password", "credential", "auth")
"""A tool whose parameter names contain one of these handles credentials."""

FILESYSTEM_SCHEMES = frozenset({"file", "ssh", "sftp", "scp", "smb", "cifs", "nfs", "afp", "ftp"})
"""URI schemes that name a location in a filesystem. A resource served under one of
these handles paths, on the same footing as a tool with a ``path`` parameter: the
scheme is the evidence (ruleset 3.3)."""


@dataclass(frozen=True)
class TextElement:
    """One model-facing string, with the context the heuristics need."""

    element: str
    """Stable identity — see :class:`~mcp_placard.manifest.models.InjectionFinding`."""

    pointer: str
    """JSON Pointer into the manifest document."""

    text: str
    tool: str | None = None
    own_tool_names: frozenset[str] = field(default_factory=frozenset)
    """Every tool name this server exposes, lowercased."""

    own_param_names: frozenset[str] = field(default_factory=frozenset)
    """Every parameter name reachable in the owning tool's schema, lowercased.
    Empty for non-tool elements."""

    handles_paths: bool = False
    handles_credentials: bool = False

    path_family: frozenset[str] = field(default_factory=frozenset)
    """The literal path segments of a resource URI, when it names a concrete location.

    Ruleset 3.3. A tool's ``handles_paths`` is a boolean because a schema names a
    *shape* — a ``path`` parameter says nothing about which path. A resource URI names
    an actual location, which is more specific evidence, and the exemption is narrowed
    to match: a resource at ``file:///home/user/.ssh/config`` may describe itself, but
    one at ``file:///var/log/app.log`` may not mention ``~/.ssh/id_rsa``. Empty means
    no concrete path was available — a tool, or a template whose segments are all
    variables — and ``handles_paths`` then exempts path mentions outright, as before."""

    server_name: str = ""
    """The server's declared ``name`` from ``initialize``, lowercased. A server
    referring to itself by name ("in the Playwright server process") is in scope;
    the cross-scope service-host rule exempts exactly this name."""


def escape_pointer(segment: str) -> str:
    """Escape one JSON Pointer segment (RFC 6901).

    Public because ``corpus`` reconstructs resource element ids with it. The two
    must agree exactly or the held-out scorer selects no findings.
    """
    return segment.replace("~", "~0").replace("/", "~1")


def _tool_params(tool: ToolEntry) -> tuple[frozenset[str], bool, bool]:
    result = walk_schema(tool.input_schema)
    names = frozenset(prop.name.lower() for prop in result.properties)
    if result.status is not TraversalStatus.COMPLETE:
        # Fail closed the *other* way for scoping: an untraversable schema is
        # treated as handling everything, so sensitive_target does not fire on a
        # tool whose parameters we could not read. The tier side already forces R4.
        return names, True, True
    handles_paths = bool(names & PATH_HANDLING_FIELDS)
    handles_credentials = any(tok in name for name in names for tok in CREDENTIAL_HANDLING_TOKENS)
    return names, handles_paths, handles_credentials


def _uri_evidence(uri: str) -> tuple[bool, frozenset[str]]:
    """``(handles_paths, path_family)`` for a resource URI or URI template.

    Ruleset 3.3, Chief's ruling of 2026-09-23. The scheme establishes that the element
    handles paths; the literal segments of the path narrow *which* path mentions are in
    scope for it. Template variables (``{path}``) contribute no segment — a template
    names a family, not a location, so only its literal segments count.
    """
    scheme, separator, remainder = uri.partition("://")
    if not separator:
        scheme, separator, remainder = uri.partition(":")
        if not separator:
            return False, frozenset()
    if scheme.lower() not in FILESYSTEM_SCHEMES:
        return False, frozenset()
    path = remainder.split("?", 1)[0].split("#", 1)[0]
    segments = {
        segment.lower()
        for segment in path.split("/")
        if segment and "{" not in segment and "}" not in segment
    }
    return True, frozenset(segments)


def _prompt_argument_evidence(names: Iterable[str]) -> tuple[bool, bool]:
    """``(handles_paths, handles_credentials)`` from prompt argument names.

    Ruleset 3.3: an argument name is evidence on the same footing as a tool parameter
    name, and by the same test — exact membership for paths, substring for credentials.
    A prompt inherits the evidence of its own arguments, which are the closest thing it
    has to a schema.
    """
    lowered = [name.lower() for name in names]
    handles_paths = any(name in PATH_HANDLING_FIELDS for name in lowered)
    handles_credentials = any(tok in name for name in lowered for tok in CREDENTIAL_HANDLING_TOKENS)
    return handles_paths, handles_credentials


def _schema_descriptions(schema: dict[str, Any]) -> list[tuple[str, str]]:
    """``(pointer-within-schema, description)`` for every property description the
    walker reaches. The walker's pointers are relative to the schema root."""
    result = walk_schema(schema)
    out: list[tuple[str, str]] = []
    for prop in result.properties:
        description = prop.subschema.get("description")
        if isinstance(description, str) and description:
            out.append((f"{prop.pointer}/description", description))
    return out


@dataclass(frozen=True)
class _ToolContext:
    tool: ToolEntry
    index: int
    own_tools: frozenset[str]
    params: frozenset[str]
    handles_paths: bool
    handles_credentials: bool
    server_name: str

    def element(self, suffix: str, text: str) -> TextElement:
        return TextElement(
            element=f"tool:{self.tool.name}/{suffix}",
            pointer=f"/surface/tools/{self.index}/{suffix}",
            text=text,
            tool=self.tool.name,
            own_tool_names=self.own_tools,
            own_param_names=self.params,
            handles_paths=self.handles_paths,
            handles_credentials=self.handles_credentials,
            server_name=self.server_name,
        )


def enumerate_text(manifest: Manifest) -> list[TextElement]:
    """Every model-facing string in the manifest, in document order."""
    surface = manifest.surface
    own_tools = frozenset(tool.name.lower() for tool in surface.tools)
    server_name = (surface.server.name or "").lower()
    elements: list[TextElement] = []

    if surface.instructions:
        elements.append(
            TextElement(
                element="server:instructions",
                pointer="/surface/instructions",
                text=surface.instructions,
                own_tool_names=own_tools,
                server_name=server_name,
            )
        )

    for index, tool in enumerate(surface.tools):
        params, handles_paths, handles_credentials = _tool_params(tool)
        context = _ToolContext(
            tool=tool,
            index=index,
            own_tools=own_tools,
            params=params,
            handles_paths=handles_paths,
            handles_credentials=handles_credentials,
            server_name=server_name,
        )
        if tool.description:
            elements.append(context.element("description", tool.description))
        if tool.annotations is not None and tool.annotations.title:
            elements.append(context.element("annotations/title", tool.annotations.title))
        for rel_pointer, description in _schema_descriptions(tool.input_schema):
            elements.append(context.element(f"inputSchema{rel_pointer}", description))

    for index, prompt in enumerate(surface.prompts):
        base = f"/surface/prompts/{index}"
        arguments = prompt.arguments or []
        # A prompt inherits the evidence of its own arguments (ruleset 3.3).
        prompt_paths, prompt_credentials = _prompt_argument_evidence(a.name for a in arguments)
        if prompt.description:
            elements.append(
                TextElement(
                    element=f"prompt:{prompt.name}/description",
                    pointer=f"{base}/description",
                    text=prompt.description,
                    own_tool_names=own_tools,
                    handles_paths=prompt_paths,
                    handles_credentials=prompt_credentials,
                    server_name=server_name,
                )
            )
        for arg_index, argument in enumerate(arguments):
            if argument.description:
                arg_paths, arg_credentials = _prompt_argument_evidence([argument.name])
                elements.append(
                    TextElement(
                        element=f"prompt:{prompt.name}/arguments/{argument.name}/description",
                        pointer=f"{base}/arguments/{arg_index}/description",
                        text=argument.description,
                        own_tool_names=own_tools,
                        handles_paths=arg_paths,
                        handles_credentials=arg_credentials,
                        server_name=server_name,
                    )
                )

    for index, resource in enumerate(surface.resources):
        if resource.description:
            handles_paths, path_family = _uri_evidence(resource.uri)
            elements.append(
                TextElement(
                    element=f"resource:{escape_pointer(resource.uri)}/description",
                    pointer=f"/surface/resources/{index}/description",
                    text=resource.description,
                    own_tool_names=own_tools,
                    handles_paths=handles_paths,
                    path_family=path_family,
                    server_name=server_name,
                )
            )

    for index, template in enumerate(surface.resource_templates):
        if template.description:
            handles_paths, path_family = _uri_evidence(template.uri_template)
            elements.append(
                TextElement(
                    element=(
                        f"resource_template:{escape_pointer(template.uri_template)}/description"
                    ),
                    pointer=f"/surface/resource_templates/{index}/description",
                    text=template.description,
                    own_tool_names=own_tools,
                    handles_paths=handles_paths,
                    path_family=path_family,
                    server_name=server_name,
                )
            )

    return elements
