"""Host-pinning pattern forms (Rule E) — recognized by shape, never by regex analysis.

`docs/TAXONOMY.md`, Rule E: a naive classifier that reads any ``pattern`` as a host
constraint can be defeated by an unescaped dot or a permissive wildcard, so that
``^https://docs.internal.example.com`` *looks* like it pins a host while actually
admitting ``https://docsXinternalYexampleZcom.attacker.com`` — the unescaped ``.``
matches any character, not a literal dot.

This module does not analyze whether an arbitrary regex is safe. That is deliberate:
a classifier that reasons about regex anchoring incorrectly is more dangerous than
one that declines to reason about it at all. Instead it recognizes a short, explicit
allowlist of pattern *forms* — read the grammar in :data:`_HOST_PATTERN`, not a
general regex analyzer — and treats every pattern that does not match one of those
forms as unconstrained, which routes it to Rule A as a caller-influenced outbound
target rather than granting it the benefit of the doubt.

The accepted shape, in full: anchored at the start (``^``), a literal ``http://`` or
``https://`` scheme, one or more DNS labels joined by a literal escaped dot
(``\\.``) — never a bare ``.``, which is a wildcard — and a terminator that closes
the host: either ``/`` (a path may follow) or ``$`` (the host is the whole string).
Nothing about a label itself may be a regex metacharacter, so alternation (``|``),
quantifiers (``*``, ``+``, ``?``), character classes (``[...]``), and groups
(``(...)``) are all rejected by construction — none of those characters appear in
the label grammar, so a pattern containing them simply fails to match and falls
through to "unconstrained."
"""

from __future__ import annotations

import re

_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
"""One DNS label: alphanumeric, optionally hyphenated, 1-63 characters — the same
shape RFC 1035 gives a label. No regex metacharacter is a valid label character, so
alternation, quantifiers, and groups are excluded by construction, not by a separate
denylist check."""

_ESCAPED_DOT = r"\\\."
r"""Matches a literal backslash followed by a literal dot in the pattern *under
test* — i.e. this recognizes the two source characters ``\.``, an escaped dot, in
whatever schema ``pattern`` string is being validated. Not to be confused with the
bare ``.`` this module rejects, which is a regex wildcard matching any character."""

_HOST_PATTERN = re.compile(
    r"^\^https?://" + _LABEL + f"(?:{_ESCAPED_DOT}" + _LABEL + r")*" + r"[/$]"
)
"""The one recognized host-pinning form. A pattern must match this from its very
first character; anything after the terminating ``/`` or ``$`` is the path portion
and is not evaluated here, because by the time the host is fully matched, nothing
that follows can change which host was pinned."""


def is_recognized_host_pinning_form(pattern: str) -> bool:
    """True when ``pattern`` matches the one recognized host-pinning form.

    ``pattern`` is the raw JSON Schema ``pattern`` string, exactly as declared —
    never modified, never partially interpreted. A pattern this returns ``False``
    for is treated as unconstrained by Rule A, regardless of how host-like it looks;
    there is no partial credit.
    """
    return _HOST_PATTERN.match(pattern) is not None
