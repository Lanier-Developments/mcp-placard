"""Deciding which transport a target string names.

``<target>`` is either an HTTP(S) URL or a stdio command line. Inference is
deliberately narrow — a URL scheme means HTTP, anything else means stdio — because a
clever heuristic that guesses wrong would silently scan the wrong thing.
``--transport`` overrides inference when the caller knows better.
"""

from __future__ import annotations

import shlex
from enum import StrEnum

from ..errors import TransportResolutionError

HTTP_SCHEMES = ("http://", "https://")


class TransportKind(StrEnum):
    """A concrete transport Placard can speak."""

    STDIO = "stdio"
    HTTP = "http"


class TransportChoice(StrEnum):
    """What the caller asked for on the command line."""

    AUTO = "auto"
    STDIO = "stdio"
    HTTP = "http"


def infer_transport(target: str) -> TransportKind:
    """Infer the transport from the shape of ``target``.

    An ``http://`` or ``https://`` prefix means streamable HTTP. Everything else is
    treated as a command line to spawn over stdio.
    """
    if not target.strip():
        raise TransportResolutionError("target is empty; expected a command line or an HTTP(S) URL")
    if target.startswith(HTTP_SCHEMES):
        return TransportKind.HTTP
    return TransportKind.STDIO


def resolve_transport(target: str, choice: TransportChoice) -> TransportKind:
    """Resolve the transport to use, honouring an explicit ``--transport`` override.

    An explicit choice is respected even when it contradicts the target's shape, with
    one exception: ``--transport http`` against something that is not a URL cannot
    work and is rejected as a usage error rather than producing an obscure client
    failure later.
    """
    if choice is TransportChoice.AUTO:
        return infer_transport(target)
    if choice is TransportChoice.HTTP:
        if not target.startswith(HTTP_SCHEMES):
            raise TransportResolutionError(
                f"--transport http requires an http:// or https:// target, got {target!r}"
            )
        return TransportKind.HTTP
    return TransportKind.STDIO


def split_command(target: str) -> tuple[str, list[str]]:
    """Split a stdio target into an executable and its arguments.

    Parsed with :func:`shlex.split` and handed to the MCP SDK as an argument vector.
    No shell is ever involved: the target is untrusted input as far as this tool is
    concerned, and ``shell=True`` would turn a scan target into code execution.
    """
    try:
        parts = shlex.split(target)
    except ValueError as exc:
        raise TransportResolutionError(f"cannot parse stdio command {target!r}: {exc}") from exc
    if not parts:
        raise TransportResolutionError(f"stdio target {target!r} contains no command")
    return parts[0], parts[1:]
