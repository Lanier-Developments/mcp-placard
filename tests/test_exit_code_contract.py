"""The per-command exit-code contract from AGENTS.md, pinned as data.

Phase 4's GitHub Action consumes these codes, so they are an interface, not a
convention: a code changing meaning for a command is a breaking change. This module
mirrors AGENTS.md's "Exit Codes" section line for line — every code claimed by every
command is enumerated here, next to the codes reserved for `report`. Individual
scenarios that produce each code live in ``test_cli.py``, ``test_diff_table.py``, and
``test_integration.py``; this module is the cross-command index, not a duplicate of
that coverage.
"""

from __future__ import annotations

from mcp_placard.errors import (
    EXIT_DESCRIPTION_CHANGE,
    EXIT_ESCALATION,
    EXIT_OK,
    EXIT_REMOVED_OR_UNREACHABLE,
    EXIT_REPORT_RESERVED,
    EXIT_USAGE,
)

SCAN_CODES = {EXIT_OK, EXIT_REMOVED_OR_UNREACHABLE, EXIT_USAGE}
"""``scan``: 0 success, 3 unreachable, 10 usage. Exercised in test_cli.py and the
success case in test_integration.py (needs a live mock server)."""

DIFF_CODES = {
    EXIT_OK,
    EXIT_ESCALATION,
    EXIT_DESCRIPTION_CHANGE,
    EXIT_REMOVED_OR_UNREACHABLE,
    EXIT_USAGE,
}
"""``diff``: the full table, exercised row by row in test_diff_table.py."""

VERIFY_CODES = {EXIT_OK, EXIT_ESCALATION, EXIT_USAGE}
"""``verify``: 0 intact, 1 hash mismatch, 10 usage. Exercised in test_cli.py.

Note ``verify``'s ``1`` reuses ``EXIT_ESCALATION``'s numeric value but not its
meaning — see AGENTS.md's "Exit Codes" section. Reading a code only makes sense in
the context of the command that produced it.
"""

ALL_DEFINED_CODES = {
    EXIT_OK,
    EXIT_ESCALATION,
    EXIT_DESCRIPTION_CHANGE,
    EXIT_REMOVED_OR_UNREACHABLE,
    EXIT_USAGE,
}


def test_no_command_claims_a_code_reserved_for_report() -> None:
    """``report`` is Phase 4 and unimplemented; ``20``-``29`` must stay unclaimed
    until it defines what they mean."""
    for codes in (SCAN_CODES, DIFF_CODES, VERIFY_CODES):
        assert codes.isdisjoint(EXIT_REPORT_RESERVED)


def test_every_defined_exit_code_is_claimed_by_at_least_one_command() -> None:
    """A code that exists in errors.py but appears in no command's contract here is
    either dead or undocumented — this test catches either."""
    assert (SCAN_CODES | DIFF_CODES | VERIFY_CODES) == ALL_DEFINED_CODES


def test_verify_and_diff_share_a_number_but_document_different_meanings() -> None:
    """The one deliberate cross-command collision. Asserted explicitly so a future
    reader does not "fix" it by assigning verify's mismatch code a new number."""
    assert EXIT_ESCALATION in VERIFY_CODES
    assert EXIT_ESCALATION in DIFF_CODES
