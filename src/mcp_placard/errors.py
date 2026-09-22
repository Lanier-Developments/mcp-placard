"""Typed exceptions for Placard.

Library code raises these and never prints, never calls ``sys.exit``. ``cli.py`` is
the only module allowed to translate an exception into an exit code — see the
exit-code table in AGENTS.md.

Each exception carries ``exit_code`` so the translation is a property of the error,
not a chain of ``isinstance`` checks scattered through the CLI.

Exit codes are a **per-command contract** (AGENTS.md, "Exit Codes"). ``diff``'s codes
are a bitmask of finding categories, OR'd together, so no category can mask another;
``scan``'s and ``verify``'s are plain values. Usage error is ``64`` on every command
and is exclusive — a usage error means no comparison happened, so it is never OR'd
with a finding bit.
"""

from __future__ import annotations

EXIT_OK = 0

# ---- diff: finding-category bits (Phase 3 ruling, 0.3.0) -----------------------
EXIT_ESCALATION = 1
"""Bit 0 — tier increase, new tool at or above ``--ceiling``, capabilities changed."""
EXIT_DESCRIPTION_CHANGE = 2
"""Bit 1 — description changed on an existing element. A prompt change; never
silenceable by tier configuration."""
EXIT_REMOVED = 4
"""Bit 2 — tool removed."""
EXIT_INJECTION = 8
"""Bit 3 — an injection finding new in this diff (Phase 3)."""

DIFF_FINDING_BITS: tuple[int, ...] = (
    EXIT_ESCALATION,
    EXIT_DESCRIPTION_CHANGE,
    EXIT_REMOVED,
    EXIT_INJECTION,
)
"""Every bit ``diff`` may set. A ``diff`` exit status is the OR of a subset of these,
so it ranges over 0-15; ``64`` is the only other value it can produce."""

EXIT_INCOMPLETE = 16
"""Bit 4 — ``check`` only: one or more configured servers could not be scanned
(Phase 4 go memo). ``check`` scans before it diffs, and a server that cannot be
scanned has no representation in ``diff``'s bits; reporting nothing would pass the
gate on a server it never looked at — fail-open, in a security gate. ``diff`` never
sets this bit: it compares two files and cannot be incomplete."""

CHECK_FINDING_BITS: tuple[int, ...] = (*DIFF_FINDING_BITS, EXIT_INCOMPLETE)
"""Every bit ``check`` may set: ``diff``'s four plus incomplete, 0-31."""

# ---- report ------------------------------------------------------------------------
EXIT_REPORT_VERIFY_FAILED = 101
"""``report``: the manifest fails ``verify``. A report of tampered data is worse than
no report, so ``report`` refuses to render it."""
EXIT_REPORT_BASELINE_VERIFY_FAILED = 102
"""``report``: the ``--against`` baseline fails ``verify``."""

# ---- scan --------------------------------------------------------------------------
EXIT_UNREACHABLE = 3
"""``scan``: server unreachable, or enumeration failed after a successful handshake.
``scan``'s codes are its own — 3 here has never meant a ``diff`` category."""

# ---- verify ------------------------------------------------------------------------
EXIT_HASH_MISMATCH = 1
"""``verify``: at least one recorded hash does not match its content. Shares a number
with ``EXIT_ESCALATION`` and nothing else — read a code only in the context of the
command that produced it."""

# ---- all commands ------------------------------------------------------------------
EXIT_USAGE = 64
"""Usage or configuration error, every command. Exclusive: never combined with a
finding bit. Moved from 10 in 0.3.0 because 10 collides with ``8 | 2``."""

EXIT_REPORT_RESERVED = range(100, 110)
"""Reserved for ``report``. Nothing in ``scan``, ``diff``, ``verify``, ``baseline``, or
``check`` may claim a code in this range; it sits clear of the finding bits (up to
31) and of ``64``. ``report`` claims 101 and 102 so far."""


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

    exit_code = EXIT_UNREACHABLE


class TransportResolutionError(UsageError):
    """The target string could not be resolved to a transport.

    This is a usage error, not a connection failure: nothing was contacted. An empty
    target, or ``--transport http`` against a shell command, lands here.
    """


class ConnectionFailure(TransportError):
    """The target server could not be reached, spawned, or initialized.

    Maps to ``scan`` exit code 3. Nothing derived from a scan that never happened can
    be trusted, and the code says so before any manifest is written.
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

    exit_code = EXIT_HASH_MISMATCH

    def __init__(self, mismatches: list[str]) -> None:
        self.mismatches = list(mismatches)
        joined = "; ".join(self.mismatches)
        super().__init__(f"manifest hash verification failed: {joined}")
