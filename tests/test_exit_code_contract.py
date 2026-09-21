"""The per-command exit-code contract from AGENTS.md, pinned as data.

Phase 4's GitHub Action consumes these codes, so they are an interface, not a
convention: a code changing meaning for a command is a breaking change. This module
mirrors AGENTS.md's "Exit Codes" section — every code claimed by every command is
enumerated here, next to the codes reserved for `report`. Individual scenarios that
produce each code live in ``test_cli.py``, ``test_diff_table.py``,
``test_inject_diff.py``, and ``test_integration.py``; this module is the
cross-command index, not a duplicate of that coverage.

0.3.0 contract: ``diff`` is a bitmask of finding categories (0-15); ``scan`` is 0, 3,
64; ``verify`` is 0, 1, 64; usage error is 64 everywhere and exclusive; 100-109 are
reserved for ``report``.
"""

from __future__ import annotations

from itertools import combinations

from mcp_placard.errors import (
    DIFF_FINDING_BITS,
    EXIT_DESCRIPTION_CHANGE,
    EXIT_ESCALATION,
    EXIT_HASH_MISMATCH,
    EXIT_INJECTION,
    EXIT_OK,
    EXIT_REMOVED,
    EXIT_REPORT_RESERVED,
    EXIT_UNREACHABLE,
    EXIT_USAGE,
)

SCAN_CODES = {EXIT_OK, EXIT_UNREACHABLE, EXIT_USAGE}
"""``scan``: 0 success, 3 unreachable or enumeration failed, 64 usage."""

DIFF_BITMASK_VALUES = {
    sum(subset)
    for n in range(len(DIFF_FINDING_BITS) + 1)
    for subset in combinations(DIFF_FINDING_BITS, n)
}
"""Every OR of a subset of the four finding bits: 0 through 15."""

DIFF_CODES = DIFF_BITMASK_VALUES | {EXIT_USAGE}
"""``diff``: the bitmask, plus the exclusive usage error."""

VERIFY_CODES = {EXIT_OK, EXIT_HASH_MISMATCH, EXIT_USAGE}
"""``verify``: 0 intact, 1 hash mismatch, 64 usage."""


def test_the_finding_bits_are_distinct_powers_of_two() -> None:
    assert DIFF_FINDING_BITS == (
        EXIT_ESCALATION,
        EXIT_DESCRIPTION_CHANGE,
        EXIT_REMOVED,
        EXIT_INJECTION,
    )
    assert DIFF_FINDING_BITS == (1, 2, 4, 8)
    for bit in DIFF_FINDING_BITS:
        assert bit & (bit - 1) == 0


def test_the_bitmask_covers_exactly_zero_through_fifteen() -> None:
    assert set(range(16)) == DIFF_BITMASK_VALUES


def test_usage_error_is_exclusive_and_clear_of_every_bit_combination() -> None:
    """64 is not a subset of bits (it is bit 6, which no category owns), so a
    consumer can never mistake a usage error for a set of findings. 10, the old
    value, collided with ``8 | 2`` — the reason it moved."""
    assert EXIT_USAGE == 64
    assert EXIT_USAGE not in DIFF_BITMASK_VALUES
    assert EXIT_USAGE & sum(DIFF_FINDING_BITS) == 0
    assert 10 in DIFF_BITMASK_VALUES  # the collision that forced the move


def test_no_command_claims_a_code_reserved_for_report() -> None:
    """``report`` is Phase 4 and unimplemented; 100-109 must stay unclaimed until it
    defines what they mean, and clear of any future fifth finding bit."""
    assert range(100, 110) == EXIT_REPORT_RESERVED
    for codes in (SCAN_CODES, DIFF_CODES, VERIFY_CODES):
        assert codes.isdisjoint(EXIT_REPORT_RESERVED)
    assert 16 not in EXIT_REPORT_RESERVED and 32 not in EXIT_REPORT_RESERVED


def test_scan_keeps_three_and_it_is_not_a_diff_category() -> None:
    """``scan``'s codes are its own. 3 there means unreachable; in ``diff`` 3 is
    ``1 | 2`` — escalation plus prompt change. Read a code only in the context of
    the command that produced it."""
    assert EXIT_UNREACHABLE == 3
    assert EXIT_UNREACHABLE not in DIFF_FINDING_BITS
    assert EXIT_UNREACHABLE == EXIT_ESCALATION | EXIT_DESCRIPTION_CHANGE


def test_verify_and_diff_share_a_number_but_document_different_meanings() -> None:
    """The one deliberate cross-command collision. Asserted explicitly so a future
    reader does not "fix" it by assigning verify's mismatch code a new number."""
    assert EXIT_HASH_MISMATCH == EXIT_ESCALATION == 1
    assert EXIT_HASH_MISMATCH in VERIFY_CODES
    assert EXIT_ESCALATION in DIFF_CODES
