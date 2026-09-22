"""stdio transport: spawn a local MCP server and enumerate what it offers.

The target is a command line. It is split with :func:`shlex.split` and handed to the
SDK as an argument vector — no shell is ever interposed, so a scan target cannot
become shell injection.

**Environment isolation (Phase 4 §5).** The SDK merges its own allowlist of
inherited variables (``HOME``, ``USER``, ``SHELL``, ``TERM``, …) *under* whatever
``env`` it is given, so passing an environment to it cannot withhold those. Placard
therefore launches the command through ``env -i``, which clears the environment
entirely and sets exactly the variables it is handed — the ones
``transport/launch.py`` constructed: ``PATH``, a temporary ``HOME``, redirected
package caches, and the variables the configuration names for that server. Nothing
else reaches the child. POSIX only; there is no ``env -i`` on Windows and the
isolation there is the SDK's allowlist.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from mcp import StdioServerParameters
from mcp.client.client import Client

from ..manifest.raw import RawSurface
from .base import DEFAULT_TIMEOUT_SECONDS, connect_and_collect
from .target import split_command

ENV_COMMAND = "/usr/bin/env"


def stdio_parameters(target: str, env: Mapping[str, str] | None = None) -> StdioServerParameters:
    """Build SDK stdio parameters from a command-line target.

    With ``env`` given on POSIX, the command is wrapped as
    ``/usr/bin/env -i VAR=value … command args``, so the child's environment is
    exactly ``env`` and not the SDK's inherited allowlist merged under it.
    """
    command, args = split_command(target)
    if env is None or os.name == "nt":
        return StdioServerParameters(command=command, args=args, env=dict(env) if env else None)
    assignments = [f"{name}={value}" for name, value in env.items()]
    return StdioServerParameters(
        command=ENV_COMMAND, args=["-i", *assignments, command, *args], env=dict(env)
    )


async def enumerate_stdio(
    target: str,
    *,
    env: Mapping[str, str] | None = None,
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
