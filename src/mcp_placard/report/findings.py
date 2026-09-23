"""One finding shape for every renderer (Phase 4 §2).

A report covers either a full manifest or a diff against a baseline. Both produce
:class:`ReportFinding` records: a stable hierarchical rule id, a category (the
bitmask category the finding belongs to, which is also what selects its SARIF
``level``), an escaped one-line message, and enough location data to point at the
committed baseline file. Renderers format; they never decide what is interesting —
a renderer that decides is a classifier wearing a disguise (``report/README.md``).

Everything that came from a server passes through :func:`escape_excerpt` before it
is placed in a message. Tool names are server-controlled text too.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ..config import FindingCategory, ReportLevel, SarifLevel
from ..diff.models import ChangeKind, DiffResult, Finding
from ..inject.render import escape_excerpt
from ..manifest.models import Manifest
from .locate import pointer_line

RULE_PREFIX = "placard"

DIFF_RULES: dict[ChangeKind, tuple[str, FindingCategory]] = {
    ChangeKind.TIER_ESCALATED: ("escalation/tier_increase", "escalation"),
    ChangeKind.TOOL_ADDED: ("escalation/tool_added", "escalation"),
    ChangeKind.TOOL_SCHEMA_CHANGED: ("escalation/schema_changed", "escalation"),
    ChangeKind.SERVER_CAPABILITIES_CHANGED: ("escalation/capabilities_changed", "escalation"),
    ChangeKind.TOOL_DESCRIPTION_CHANGED: ("prompt/description_changed", "prompt"),
    ChangeKind.TOOL_REMOVED: ("removal/tool_removed", "removal"),
}
"""Stable rule ids per diff kind. ``INJECTION_FINDING`` is keyed by its own rule."""

CATEGORY_TITLES: dict[FindingCategory, str] = {
    "escalation": "Escalation (bit 1)",
    "prompt": "Prompt change (bit 2)",
    "removal": "Tool removed (bit 4)",
    "injection": "Injection finding (bit 8)",
    "incomplete": "Incomplete (bit 16)",
    "chain": "Exfiltration chain",
}


@dataclass(frozen=True)
class ReportFinding:
    rule_id: str
    """``placard/<category>/<name>``, stable across runs and releases."""

    category: FindingCategory
    level: SarifLevel
    message: str
    """Already escaped. Safe for Markdown, a terminal, and SARIF ``message.text``."""

    tool: str | None
    pointer: str
    """JSON Pointer into the committed baseline manifest (or, for a full-manifest
    report, into the manifest itself) — the SARIF logical location."""

    line: int | None
    """1-based line in the located file, when the pointer resolves there."""

    fingerprint: str
    """``partialFingerprints["placard/v1"]``: what lets code scanning track the
    alert across runs and keep a dismissal. Derived from server name, element
    pointer, rule, and a hash of the excerpt — never from list position or line."""

    gated: bool = True
    """False for a finding that is reported but sets no bit (a tool added below the
    ceiling): rendered at ``note`` level whatever the category's level is."""

    extra: dict[str, str] = field(default_factory=dict)


def _fingerprint(server: str, element: str, rule_id: str, excerpt: str) -> str:
    excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:16]
    digest = hashlib.sha256(f"{server}\x1f{element}\x1f{rule_id}\x1f{excerpt_hash}".encode())
    return digest.hexdigest()[:40]


def _tool_index(manifest: Manifest | None, tool: str | None) -> int | None:
    if manifest is None or tool is None:
        return None
    for index, entry in enumerate(manifest.surface.tools):
        if entry.name == tool:
            return index
    return None


def _tool_pointer(manifest: Manifest | None, tool: str | None, suffix: str = "") -> str:
    index = _tool_index(manifest, tool)
    if index is None:
        return "/surface/tools"
    return f"/surface/tools/{index}{suffix}"


@dataclass(frozen=True)
class ReportContext:
    server: str
    """The configured server name — the fingerprint namespace and the report title."""

    levels: ReportLevel
    located_text: str | None = None
    """Rendered text of the file locations point into (the baseline when diffing,
    else the manifest), for line lookup."""

    located_manifest: Manifest | None = None

    def locate(self, pointer: str) -> int | None:
        if self.located_text is None:
            return None
        return pointer_line(self.located_text, pointer)

    def level_for(self, category: FindingCategory, *, gated: bool = True) -> SarifLevel:
        return self.levels.for_category(category) if gated else "note"


def findings_from_diff(
    result: DiffResult, *, new: Manifest, context: ReportContext
) -> list[ReportFinding]:
    """Every diff finding as a report finding. Locations point into the baseline
    (the committed file); a tool that only exists in the new manifest points at
    the baseline's tool list."""
    out: list[ReportFinding] = []
    baseline = context.located_manifest
    for finding in result.findings:
        if finding.kind is ChangeKind.INJECTION_FINDING and finding.injection is not None:
            inj = finding.injection
            rule_id = f"{RULE_PREFIX}/injection/{inj.rule}"
            baseline_index = _tool_index(baseline, inj.tool)
            if inj.tool is not None and baseline_index is not None:
                pointer = inj.pointer.replace(
                    f"/surface/tools/{_tool_index(new, inj.tool)}/",
                    f"/surface/tools/{baseline_index}/",
                    1,
                )
            elif inj.tool is None:
                pointer = inj.pointer
            else:
                pointer = "/surface/tools"
            out.append(
                ReportFinding(
                    rule_id=rule_id,
                    category="injection",
                    level=context.level_for("injection"),
                    message=(
                        f"{inj.pattern_class} ({inj.rule}) at {inj.pointer} "
                        f"[{inj.start}:{inj.end}]: {escape_excerpt(inj.excerpt)}"
                    ),
                    tool=inj.tool,
                    pointer=pointer,
                    line=context.locate(pointer),
                    fingerprint=_fingerprint(context.server, inj.element, rule_id, inj.excerpt),
                    extra={"class": inj.pattern_class, "element": inj.element},
                )
            )
            continue

        rule_suffix, category = DIFF_RULES[finding.kind]
        rule_id = f"{RULE_PREFIX}/{rule_suffix}"
        gated = finding.exit_code != 0
        suffix = {
            ChangeKind.TOOL_DESCRIPTION_CHANGED: "/description",
            ChangeKind.TOOL_SCHEMA_CHANGED: "/inputSchema",
        }.get(finding.kind, "")
        if finding.kind is ChangeKind.SERVER_CAPABILITIES_CHANGED:
            pointer = "/capabilities"
        else:
            pointer = _tool_pointer(baseline, finding.tool, suffix)
        element = finding.tool or "server"
        out.append(
            ReportFinding(
                rule_id=rule_id,
                category=category,
                level=context.level_for(category, gated=gated),
                message=_escape_summary(finding),
                tool=finding.tool,
                pointer=pointer,
                line=context.locate(pointer),
                fingerprint=_fingerprint(context.server, element, rule_id, finding.summary),
                gated=gated,
            )
        )
    return out


def findings_from_manifest(manifest: Manifest, *, context: ReportContext) -> list[ReportFinding]:
    """A full-manifest report: injection findings and server-level findings.
    Per-tool tiers are a table in the Markdown report, not alerts."""
    out: list[ReportFinding] = []
    for inj in manifest.injection_findings:
        rule_id = f"{RULE_PREFIX}/injection/{inj.rule}"
        out.append(
            ReportFinding(
                rule_id=rule_id,
                category="injection",
                level=context.level_for("injection"),
                message=(
                    f"{inj.pattern_class} ({inj.rule}) at {inj.pointer} "
                    f"[{inj.start}:{inj.end}]: {escape_excerpt(inj.excerpt)}"
                ),
                tool=inj.tool,
                pointer=inj.pointer,
                line=context.locate(inj.pointer),
                fingerprint=_fingerprint(context.server, inj.element, rule_id, inj.excerpt),
                extra={"class": inj.pattern_class, "element": inj.element},
            )
        )
    for server_finding in manifest.findings:
        rule_id = f"{RULE_PREFIX}/chain/{server_finding.kind}"
        tools = ", ".join(escape_excerpt(t) for t in server_finding.tools)
        out.append(
            ReportFinding(
                rule_id=rule_id,
                category="chain",
                level=context.level_for("chain"),
                message=f"{server_finding.kind}: {escape_excerpt(server_finding.summary)} "
                f"(tools: {tools})",
                tool=None,
                pointer="/surface/tools",
                line=context.locate("/surface/tools"),
                fingerprint=_fingerprint(
                    context.server, "server", rule_id, "|".join(server_finding.tools)
                ),
            )
        )
    return out


def _escape_summary(finding: Finding) -> str:
    """Diff summaries embed tool names, which are server-controlled text."""
    return escape_excerpt(finding.summary, limit=400)


def decode_bits(status: int) -> list[FindingCategory]:
    """The categories a ``diff``/``check`` status carries, in bit order."""
    from ..errors import (
        EXIT_DESCRIPTION_CHANGE,
        EXIT_ESCALATION,
        EXIT_INCOMPLETE,
        EXIT_INJECTION,
        EXIT_REMOVED,
    )

    bits: list[tuple[int, FindingCategory]] = [
        (EXIT_ESCALATION, "escalation"),
        (EXIT_DESCRIPTION_CHANGE, "prompt"),
        (EXIT_REMOVED, "removal"),
        (EXIT_INJECTION, "injection"),
        (EXIT_INCOMPLETE, "incomplete"),
    ]
    return [category for bit, category in bits if status & bit]
