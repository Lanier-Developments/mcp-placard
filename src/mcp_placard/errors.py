"""Typed exceptions for Placard.

Library code raises these and never prints, never calls ``sys.exit``. ``cli.py`` is
the only module allowed to translate an exception into an exit code — see
``mcp_placard.cli.EXIT_CODES`` and the exit-code table in AGENTS.md.

Each exception carries ``exit_code`` so the translation is a property of the error,
not a chain of ``isinstance`` checks scattered through the CLI.
"""

from __future__ import annotations

EXIT_OK = 0
EXIT_ESCALATION = 1
EXIT_DESCRIPTION_CHANGE = 2
EXIT_REMOVED_OR_UNREACHABLE = 3
EXIT_USAGE = 10

# 20-29 are reserved for `report` (Phase 4, not yet implemented). AGENTS.md: exit
# codes are a per-command interface Phase 4's GitHub Action consumes, not a
# convention — nothing in `scan`, `diff`, or `verify` may claim a code in this range.
EXIT_REPORT_RESERVED = range(20, 30)


class PlacardError(Exception):
    """Base class for every error Placard raises deliberately.

    Anything that is not a subclass of this escaping to ``cli.py`` is a bug, and the
    CLI reports it as such rather than mapping it onto a documented exit code.
    """

    exit_code: int = EXIT_USAGE


class UsageError(PlacardError):
    """The invocation or configuration is wrong — bad flag, unreadable path."""

    exit_code = EXIT_USAGE


class TransportError(PlacardError):
    """Base class for failures in reaching or speaking to a target server."""

    exit_code = EXIT_REMOVED_OR_UNREACHABLE


class TransportResolutionError(UsageError):
    """The target string could not be resolved to a transport.

    This is a usage error, not a connection failure: nothing was contacted. An empty
    target, or ``--transport http`` against a shell command, lands here.
    """


class ConnectionFailure(TransportError):
    """The target server could not be reached, spawned, or initialized.

    Maps to exit code 3 — "tool removed or server unreachable". A server that has
    become unreachable is indistinguishable, from the consumer's point of view, from
    a server that withdrew its entire surface.
    """


class EnumerationError(TransportError):
    """The server was reached but its surface could not be enumerated.

    A capability was advertised and then errored, or a listing paginated without
    terminating. Treated as unreachable: an incomplete surface must never be
    serialized as though it were the whole surface.
    """


class ManifestError(PlacardError):
    """Base class for manifest parsing, validation, and integrity failures."""

    exit_code = EXIT_USAGE


class ManifestValidationError(ManifestError):
    """A file did not parse as JSON, or did not validate as a manifest."""


class ManifestVersionError(ManifestError):
    """The manifest declares a ``manifest_version`` this build cannot read."""


class HashMismatchError(ManifestError):
    """A recorded hash does not match the content it claims to cover.

    Raised by ``placard verify``. The ``mismatches`` list names each offending
    field so the CLI can report all of them, not just the first.
    """

    exit_code = EXIT_ESCALATION

    def __init__(self, mismatches: list[str]) -> None:
        self.mismatches = list(mismatches)
        joined = "; ".join(self.mismatches)
        super().__init__(f"manifest hash verification failed: {joined}")
