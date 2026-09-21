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

    server_name: str = ""
    """The server's declared ``name`` from ``initialize``, lowercased. A server
    referring to itself by name ("in the Playwright server process") is in scope;
    the cross-scope service-host rule exempts exactly this name."""


def _escape_pointer(segment: str) -> str:
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
        if prompt.description:
            elements.append(
                TextElement(
                    element=f"prompt:{prompt.name}/description",
                    pointer=f"{base}/description",
                    text=prompt.description,
                    own_tool_names=own_tools,
                    server_name=server_name,
                )
            )
        for arg_index, argument in enumerate(prompt.arguments or []):
            if argument.description:
                elements.append(
                    TextElement(
                        element=f"prompt:{prompt.name}/arguments/{argument.name}/description",
                        pointer=f"{base}/arguments/{arg_index}/description",
                        text=argument.description,
                        own_tool_names=own_tools,
                        server_name=server_name,
                    )
                )

    for index, resource in enumerate(surface.resources):
        if resource.description:
            elements.append(
                TextElement(
                    element=f"resource:{_escape_pointer(resource.uri)}/description",
                    pointer=f"/surface/resources/{index}/description",
                    text=resource.description,
                    own_tool_names=own_tools,
                    server_name=server_name,
                )
            )

    for index, template in enumerate(surface.resource_templates):
        if template.description:
            elements.append(
                TextElement(
                    element=(
                        f"resource_template:{_escape_pointer(template.uri_template)}/description"
                    ),
                    pointer=f"/surface/resource_templates/{index}/description",
                    text=template.description,
                    own_tool_names=own_tools,
                    server_name=server_name,
                )
            )

    return elements
