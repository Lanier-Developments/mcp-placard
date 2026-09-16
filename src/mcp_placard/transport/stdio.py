"""stdio transport: spawn a local MCP server and enumerate what it offers.

The target is a command line. It is split with :func:`shlex.split` and handed to the
SDK as an argument vector — no shell is ever interposed, so a scan target cannot
become shell injection.

Environment handling is restrictive by default. The SDK passes only a small
allowlist of variables to the child unless told otherwise, which keeps ambient
credentials in the operator's shell out of the scanned process. ``env`` exists for
servers that genuinely need a variable to start; Placard passes it through and
stores none of it (AGENTS.md: no credential storage).
"""

from __future__ import annotations

from mcp import StdioServerParameters
from mcp.client.client import Client

from ..manifest.raw import RawSurface
from .base import DEFAULT_TIMEOUT_SECONDS, connect_and_collect
from .target import split_command


def stdio_parameters(target: str, env: dict[str, str] | None = None) -> StdioServerParameters:
    """Build SDK stdio parameters from a command-line target."""
    command, args = split_command(target)
    return StdioServerParameters(command=command, args=args, env=env)


async def enumerate_stdio(
    target: str,
    *,
    env: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> RawSurface:
    """Spawn ``target`` over stdio, initialize, and enumerate its surface.

    Raises :class:`~mcp_placard.errors.TransportResolutionError` when the command
    line cannot be parsed, :class:`~mcp_placard.errors.ConnectionFailure` when the
    process cannot be spawned or the handshake fails, and
    :class:`~mcp_placard.errors.EnumerationError` when a listing fails after a
    successful handshake.
    """
    parameters = stdio_parameters(target, env)
    return await connect_and_collect(
        lambda: Client(parameters, read_timeout_seconds=timeout),
        description=f"stdio server {target!r}",
        timeout=timeout,
    )
