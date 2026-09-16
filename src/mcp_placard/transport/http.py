"""HTTP transport: connect to a remote MCP server over streamable HTTP and enumerate.

Network egress during a scan goes to the target URL and nowhere else (AGENTS.md,
"Security Posture"). There is no telemetry, no resolution service, and no fetching
of anything a scanned description happens to mention — a description is untrusted
data and is never dereferenced.

Authentication is out of scope for Phase 1. A server that requires credentials will
fail the handshake and surface as :class:`~mcp_placard.errors.ConnectionFailure`,
which is the honest outcome: Placard stores no credentials.
"""

from __future__ import annotations

from mcp.client.client import Client

from ..errors import TransportResolutionError
from ..manifest.raw import RawSurface
from .base import DEFAULT_TIMEOUT_SECONDS, connect_and_collect
from .target import HTTP_SCHEMES


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
) -> RawSurface:
    """Connect to ``target`` over streamable HTTP, initialize, and enumerate.

    Raises :class:`~mcp_placard.errors.TransportResolutionError` for a target that is
    not a URL, :class:`~mcp_placard.errors.ConnectionFailure` when the endpoint
    cannot be reached or the handshake fails, and
    :class:`~mcp_placard.errors.EnumerationError` when a listing fails afterwards.
    """
    url = validate_url(target)
    return await connect_and_collect(
        lambda: Client(url, read_timeout_seconds=timeout),
        description=f"http server {url!r}",
        timeout=timeout,
    )
