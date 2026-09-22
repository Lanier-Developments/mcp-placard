"""MCP client wrappers — connect and enumerate only.

This package is the only part of Placard that talks to a server, and the only
requests it issues are ``initialize`` and the four listing methods. It never calls a
tool, never reads a resource, never writes anything.

:func:`scan_target` is the entry point: it resolves the transport, runs the async
enumeration on a fresh event loop, and returns a
:class:`~mcp_placard.manifest.raw.RawSurface` for ``manifest.build`` to canonicalize.
"""

from __future__ import annotations

from collections.abc import Mapping

import anyio

from ..manifest.raw import RawSurface
from .base import DEFAULT_TIMEOUT_SECONDS, MAX_PAGES, collect_surface, connect_and_collect, to_wire
from .http import enumerate_http
from .stdio import enumerate_stdio
from .target import (
    TransportChoice,
    TransportKind,
    infer_transport,
    resolve_transport,
    split_command,
)

__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_PAGES",
    "TransportChoice",
    "TransportKind",
    "collect_surface",
    "connect_and_collect",
    "enumerate_http",
    "enumerate_stdio",
    "enumerate_target",
    "infer_transport",
    "resolve_transport",
    "scan_target",
    "split_command",
    "to_wire",
]


async def enumerate_target(
    target: str,
    *,
    transport: TransportChoice = TransportChoice.AUTO,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
) -> RawSurface:
    """Resolve the transport for ``target`` and enumerate its surface.

    ``env`` is the complete launch environment for a stdio target (see
    ``transport/launch.py``); ``headers`` are request headers for an HTTP target.
    Neither is stored anywhere.
    """
    kind = resolve_transport(target, transport)
    if kind is TransportKind.HTTP:
        return await enumerate_http(target, timeout=timeout, headers=headers)
    return await enumerate_stdio(target, env=env, timeout=timeout)


def scan_target(
    target: str,
    *,
    transport: TransportChoice = TransportChoice.AUTO,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
) -> RawSurface:
    """Synchronous wrapper around :func:`enumerate_target` for the CLI.

    The MCP SDK is async; the CLI is not. One event loop is created per scan and torn
    down with it, so no transport state outlives a command.
    """
    return anyio.run(
        lambda: enumerate_target(
            target, transport=transport, timeout=timeout, env=env, headers=headers
        )
    )
