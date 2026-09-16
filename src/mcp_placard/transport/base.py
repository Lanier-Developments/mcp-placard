"""Enumeration logic shared by the stdio and HTTP transports.

The one rule that governs this module: **enumerate, never invoke**. The only
requests issued are ``initialize``, ``tools/list``, ``resources/list``,
``resources/templates/list`` and ``prompts/list``. ``tools/call`` is a hard non-goal
(AGENTS.md, "Security Posture") and ``scripts/check_no_tool_invocation.py`` fails the
build if a call site for it ever appears under ``src/``.

Listings are paginated, capability-gated, and bounded:

* **Paginated** — a server may return a cursor; every page is followed.
* **Capability-gated** — a listing is only requested when the server declared the
  matching capability during initialize. Asking a server for something it never
  advertised produces a protocol error, not an empty list.
* **Bounded** — a page budget stops a server that returns a cursor forever from
  hanging the scan. Exceeding it raises rather than returning a partial surface: a
  truncated surface hashed as though it were complete is worse than no manifest.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from typing import Any, Protocol, TypeVar

import anyio

from ..errors import ConnectionFailure, EnumerationError, PlacardError
from ..manifest.raw import RawSurface

MAX_PAGES = 1000
"""Per-listing page budget. High enough for any honest server, finite by design."""

DEFAULT_TIMEOUT_SECONDS = 30.0
"""Wall-clock budget for a whole scan: connect, handshake, and every listing."""

WireDict = dict[str, Any]


class _WireModel(Protocol):
    """Anything the MCP SDK returns that can be dumped back to wire JSON."""

    def model_dump(self, **kwargs: Any) -> dict[str, Any]: ...


ItemT = TypeVar("ItemT", bound=_WireModel)


def _sdk_version() -> str | None:
    """The installed ``mcp`` package version, for ``environment`` — never for a hash.

    Best-effort: an unresolvable distribution (an editable checkout with unusual
    packaging, say) omits the field rather than failing a scan over metadata.
    """
    try:
        return _package_version("mcp")
    except PackageNotFoundError:  # pragma: no cover - depends on install layout
        return None


def _environment(client: Any) -> dict[str, str]:
    """Scan-circumstance metadata: SDK version and the negotiated protocol version.

    Both are properties of *this scan* — which SDK build did the talking, which
    protocol revision it and the server settled on — not of the server's surface.
    They belong in ``environment`` precisely so they never influence a hash.
    """
    environment: dict[str, str] = {}
    if (sdk_version := _sdk_version()) is not None:
        environment["sdk_version"] = sdk_version
    if (protocol_version := getattr(client, "protocol_version", None)) is not None:
        environment["protocol_version"] = protocol_version
    return environment


def to_wire(model: _WireModel | None) -> WireDict:
    """Convert an SDK model back into the wire JSON the server sent.

    ``by_alias`` restores MCP's camelCase spellings (``inputSchema``,
    ``readOnlyHint``, ``_meta``); ``exclude_none`` drops fields the server never sent
    so that "absent" and "present but null" do not collapse into the same manifest;
    ``mode="json"`` renders URLs, enums, and dates as the JSON scalars they were.

    The SDK's models allow unknown fields, so anything this build does not model
    still round-trips through here untouched.
    """
    if model is None:
        return {}
    return model.model_dump(by_alias=True, exclude_none=True, mode="json")


async def _paginate(
    fetch: Any,
    *,
    items_of: Any,
    what: str,
) -> list[WireDict]:
    """Follow a paginated MCP listing to exhaustion and return wire dicts.

    ``fetch`` is called with a cursor and returns a paginated result; ``items_of``
    extracts the page's items from it.
    """
    collected: list[WireDict] = []
    cursor: str | None = None
    for _ in range(MAX_PAGES):
        result = await fetch(cursor)
        collected.extend(to_wire(item) for item in items_of(result))
        cursor = getattr(result, "next_cursor", None)
        if cursor is None:
            return collected
    raise EnumerationError(
        f"{what} listing did not terminate after {MAX_PAGES} pages; refusing to "
        "serialize a partial surface"
    )


async def collect_surface(client: Any) -> RawSurface:
    """Enumerate a connected client's full surface into a :class:`RawSurface`.

    ``client`` is an already-initialized MCP SDK client. Only listing requests are
    issued. Any failure after a successful handshake is an
    :class:`~mcp_placard.errors.EnumerationError`: the connection worked, the
    enumeration did not, and a half-read surface is not a manifest.
    """
    capabilities = client.server_capabilities

    try:
        tools = (
            await _paginate(
                lambda cursor: client.list_tools(cursor=cursor),
                items_of=lambda result: result.tools,
                what="tools",
            )
            if getattr(capabilities, "tools", None) is not None
            else []
        )

        resources: list[WireDict] = []
        resource_templates: list[WireDict] = []
        if getattr(capabilities, "resources", None) is not None:
            resources = await _paginate(
                lambda cursor: client.list_resources(cursor=cursor),
                items_of=lambda result: result.resources,
                what="resources",
            )
            resource_templates = await _paginate(
                lambda cursor: client.list_resource_templates(cursor=cursor),
                items_of=lambda result: result.resource_templates,
                what="resource templates",
            )

        prompts = (
            await _paginate(
                lambda cursor: client.list_prompts(cursor=cursor),
                items_of=lambda result: result.prompts,
                what="prompts",
            )
            if getattr(capabilities, "prompts", None) is not None
            else []
        )
    except EnumerationError:
        raise
    except Exception as exc:
        raise EnumerationError(f"failed to enumerate server surface: {exc}") from exc

    return RawSurface(
        server_info=to_wire(client.server_info),
        capabilities=to_wire(capabilities),
        environment=_environment(client),
        instructions=client.instructions,
        tools=tools,
        resources=resources,
        resource_templates=resource_templates,
        prompts=prompts,
    )


async def connect_and_collect(
    build_client: Callable[[], Any],
    *,
    description: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> RawSurface:
    """Connect a client, complete the handshake, and enumerate — under one deadline.

    ``build_client`` is a zero-argument factory so that constructing the client (which
    for stdio spawns a process) happens inside the timeout scope.

    Failure mapping is deliberate. A failure to reach, spawn, or initialize the target
    becomes :class:`~mcp_placard.errors.ConnectionFailure`, which the CLI reports as
    exit code 3 — "tool removed or server unreachable". A consumer cannot distinguish
    a server that vanished from a server that withdrew everything it offered, and both
    need the same attention. Nothing leaves this function as a bare exception.
    """
    try:
        with anyio.fail_after(timeout):
            async with build_client() as client:
                return await collect_surface(client)
    except TimeoutError as exc:
        raise ConnectionFailure(
            f"timed out after {timeout:g}s connecting to or enumerating {description}"
        ) from exc
    except PlacardError:
        raise
    except Exception as exc:
        raise ConnectionFailure(f"cannot connect to {description}: {exc}") from exc
