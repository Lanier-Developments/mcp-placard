"""``CHAIN_EXFIL`` — the one server-level finding Phase 2 implements.

Acceptance criteria, verbatim: two server surfaces differing by one tool produce
``CHAIN_EXFIL`` and no ``CHAIN_EXFIL``; the finding states its own tools-only scope.
"""

from __future__ import annotations

from mcp_placard.classify import classify_manifest
from mcp_placard.manifest import build_manifest

from .conftest import make_raw, tool_wire

READ_SCHEMA = {"type": "object", "properties": {"folder": {"type": "string"}}}
"""Unconstrained free text alone would be R1; paired with a mail-domain
description it reaches R2 — the read half of the chain."""

EGRESS_SCHEMA = {
    "type": "object",
    "properties": {"to": {"type": "string"}},
    "required": ["to"],
}
"""Rule C: `to` is a recognized communication-target field — R4, the egress half."""


def _manifest(tools: list[dict]):  # type: ignore[no-untyped-def]
    return classify_manifest(build_manifest(make_raw(tools)))


def test_a_read_and_egress_tool_together_raise_chain_exfil() -> None:
    manifest = _manifest(
        [
            tool_wire(
                "read_inbox",
                description="Read messages from the mail inbox.",
                input_schema=READ_SCHEMA,
            ),
            tool_wire("notify", description="Send a notification.", input_schema=EGRESS_SCHEMA),
        ]
    )
    findings = [f for f in manifest.findings if f.kind == "chain_exfil"]
    assert len(findings) == 1
    assert set(findings[0].tools) == {"read_inbox", "notify"}
    assert "tools only" in findings[0].scope.lower()


def test_removing_the_egress_tool_clears_the_finding() -> None:
    """The same two surfaces, differing by exactly one tool — the acceptance
    criterion's "and no CHAIN_EXFIL" half."""
    manifest = _manifest(
        [
            tool_wire(
                "read_inbox",
                description="Read messages from the mail inbox.",
                input_schema=READ_SCHEMA,
            ),
        ]
    )
    assert manifest.findings == []


def test_removing_the_read_tool_also_clears_the_finding() -> None:
    manifest = _manifest(
        [tool_wire("notify", description="Send a notification.", input_schema=EGRESS_SCHEMA)]
    )
    assert manifest.findings == []


def test_an_r4_tool_alone_does_not_self_trigger_the_chain() -> None:
    """A single R4 tool satisfies neither half's tier set on its own — the read
    and egress tiers are disjoint by construction, so a chain always names at
    least two distinct tools rather than firing on one dangerous tool alone."""
    manifest = _manifest(
        [tool_wire("send_email", description="Send an email.", input_schema=EGRESS_SCHEMA)]
    )
    assert manifest.findings == []
