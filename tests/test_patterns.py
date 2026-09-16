"""Rule E: host-pinning recognized by form, one fixture per accepted and per
rejected form. `docs/TAXONOMY.md`, Rule E and `classify/patterns.py`.
"""

from __future__ import annotations

import pytest

from mcp_placard.classify.patterns import is_recognized_host_pinning_form

ACCEPTED_FORMS = [
    (
        "the canonical TAXONOMY.md example",
        r"^https://docs\.internal\.example\.com/",
    ),
    ("http scheme, not just https", r"^http://docs\.example\.com/"),
    ("a single-label host", r"^https://localhost/"),
    ("a hyphenated label", r"^https://my-service\.example\.com/"),
    ("host is the entire string, no path allowed", r"^https://docs\.example\.com$"),
]

REJECTED_FORMS = [
    (
        "unescaped dot is a wildcard, not a literal",
        r"^https://docs.internal.example.com/",
    ),
    ("missing the leading anchor", r"https://docs\.example\.com/"),
    ("alternation smuggles an alternate host", r"^https://(docs|evil)\.example\.com/"),
    ("unbounded wildcard subdomain", r"^https://.*\.example\.com/"),
    ("scheme is not a pure literal", r"^https?://docs\.example\.com/"),
    (
        "optional group around a label is not the recognized grammar",
        r"^https://(?:docs\.)?example\.com/",
    ),
    ("character class in the host", r"^https://doc[sz]\.example\.com/"),
    ("no scheme at all", r"^docs\.example\.com/"),
    ("empty pattern", ""),
    ("not a URL pattern in the first place", r"^notes/[A-Za-z0-9_./-]+$"),
]


@pytest.mark.parametrize(
    ("label", "pattern"), ACCEPTED_FORMS, ids=[row[0] for row in ACCEPTED_FORMS]
)
def test_accepted_forms_are_recognized(label: str, pattern: str) -> None:
    assert is_recognized_host_pinning_form(pattern), label


@pytest.mark.parametrize(
    ("label", "pattern"), REJECTED_FORMS, ids=[row[0] for row in REJECTED_FORMS]
)
def test_rejected_forms_are_not_recognized(label: str, pattern: str) -> None:
    assert not is_recognized_host_pinning_form(pattern), label


def test_the_attacker_host_the_amendment_warns_about_does_not_match_the_unescaped_form() -> None:
    """The exact scenario Rule E exists to prevent: an unescaped-dot pattern reads
    as though it pins a host, but the regex it actually compiles to admits an
    attacker-chosen lookalike. This asserts the *rejection*, not the regex match —
    this module never evaluates the pattern as a regex at all."""
    unescaped = r"^https://docs.internal.example.com/"
    assert not is_recognized_host_pinning_form(unescaped)
