"""HTTP transport: connect to a remote MCP server over streamable HTTP and enumerate.

Network egress during a scan goes to the target URL and nowhere else (AGENTS.md,
"Security Posture"). There is no telemetry, no resolution service, and no fetching
of anything a scanned description happens to mention — a description is untrusted
data and is never dereferenced.

Request headers (Phase 4 §1, ``header_env``) are resolved from the environment at
scan time, attached to the HTTP client for the duration of the scan, and never
stored: they reach no manifest, no report, and no stderr line. A server that needs
credentials Placard was not given fails the handshake and surfaces as
:class:`~mcp_placard.errors.ConnectionFailure`.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType
from typing import Any

from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from ..errors import TransportResolutionError
from ..manifest.raw import RawSurface
from .base import DEFAULT_TIMEOUT_SECONDS, connect_and_collect
from .target import HTTP_SCHEMES


def build_http_client(headers: Mapping[str, str] | None) -> Any:
    """The SDK's recommended ``httpx`` client, with this scan's headers attached."""
    return create_mcp_http_client(headers=dict(headers) if headers else None)


class HeaderedStreamableHTTP:
    """A streamable-HTTP transport whose requests carry fixed headers.

    The SDK builds its own client when given a bare URL; to attach headers we
    supply the client ourselves, which also makes us responsible for its
    lifecycle — the SDK only manages a client it created.
    """

    def __init__(self, url: str, headers: Mapping[str, str] | None) -> None:
        self._url = url
        self._headers = dict(headers) if headers else None
        self._client: Any = None
        self._streams: Any = None

    async def __aenter__(self) -> Any:
        self._client = build_http_client(self._headers)
        await self._client.__aenter__()
        self._streams = streamable_http_client(self._url, http_client=self._client)
        return await self._streams.__aenter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        try:
            result: bool | None = await self._streams.__aexit__(exc_type, exc, tb)
        finally:
            await self._client.__aexit__(exc_type, exc, tb)
        return result


def validate_url(target: str) -> str:
    """Confirm ``target`` is an HTTP(S) URL this transport can attempt."""
    if not target.startswith(HTTP_SCHEMES):
        raise TransportResolutionError(
            f"http transport requires an http:// or https:// target, got {target!r}"
        )
    return target


async def enumerate_http(
    target: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    headers: Mapping[str, str] | None = None,
) -> RawSurface:
    """Connect to ``target`` over streamable HTTP, initialize, and enumerate.

    Raises :class:`~mcp_placard.errors.TransportResolutionError` for a target that is
    not a URL, :class:`~mcp_placard.errors.ConnectionFailure` when the endpoint
    cannot be reached or the handshake fails, and
    :class:`~mcp_placard.errors.EnumerationError` when a listing fails afterwards.
    """
    url = validate_url(target)
    return await connect_and_collect(
        lambda: Client(HeaderedStreamableHTTP(url, headers), read_timeout_seconds=timeout),
        description=f"http server {url!r}",
        timeout=timeout,
    )
