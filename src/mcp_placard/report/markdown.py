"""The Markdown report — for ``$GITHUB_STEP_SUMMARY`` and for humans (Phase 4 §2).

Lead with the bitmask decoded into words, then findings grouped by category, then a
per-tool table. A reviewer should be able to approve or reject from the summary
alone. Every scanned string is escaped before it is placed: the step summary
renders Markdown, so this is the first place an unescaped excerpt would become live.
"""

from __future__ import annotations

from ..diff.models import DiffResult
from ..inject.render import escape_excerpt
from ..manifest.models import Manifest
from .findings import CATEGORY_TITLES, ReportFinding, decode_bits

CATEGORY_ORDER = ("incomplete", "injection", "escalation", "prompt", "removal", "chain")


def _e(text: str | None) -> str:
    return escape_excerpt(text or "", limit=200)


def render_status(status: int | None, *, incomplete: bool = False) -> str:
    if status is None:
        return "_Full manifest report — no baseline to compare against._"
    categories = decode_bits(status)
    if not categories:
        return f"**Exit status {status}** — no findings above the configured ceiling. ✅"
    words = " | ".join(CATEGORY_TITLES[c] for c in categories)
    return f"**Exit status {status}** = {words}"


def _tool_table(manifest: Manifest) -> list[str]:
    rows = [
        "| Tool | Tier | Kinds | Reversibility | Disagreements |",
        "| --- | --- | --- | --- | --- |",
    ]
    by_tool = manifest.classification_by_tool()
    for tool in manifest.surface.tools:
        entry = by_tool.get(tool.name)
        if entry is None:
            rows.append(f"| {_e(tool.name)} | unclassified | | | |")
            continue
        kinds = ", ".join(entry.kinds) or "—"
        reversibility = entry.reversibility or "—"
        disagreements = ", ".join(d.annotation for d in entry.disagreements) or "—"
        override = f" (override: {_e(entry.override.entry)})" if entry.override else ""
        rows.append(
            f"| {_e(tool.name)} | {entry.tier}{override} | {kinds} | {reversibility} | "
            f"{disagreements} |"
        )
    return rows


def render_markdown(
    *,
    server: str,
    manifest: Manifest,
    findings: list[ReportFinding],
    diff: DiffResult | None,
    status: int | None,
    baseline_path: str | None = None,
) -> str:
    """The whole report as Markdown text."""
    lines: list[str] = [f"## Placard — {_e(server)}", ""]
    lines.append(render_status(status))
    if baseline_path:
        lines.append(f"Baseline: `{_e(baseline_path)}`")
    lines.append("")

    if diff is not None:
        for note in diff.notes:
            lines.append(f"> note: {_e(note)}")
        if diff.notes:
            lines.append("")
        if not diff.findings:
            lines.append(
                "No tool-level findings; surface hash changed."
                if diff.surface_hash_changed
                else "No change."
            )
            lines.append("")

    grouped: dict[str, list[ReportFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.category, []).append(finding)
    for category in CATEGORY_ORDER:
        items = grouped.get(category)
        if not items:
            continue
        lines.append(f"### {CATEGORY_TITLES[category]}")  # type: ignore[index]
        lines.append("")
        for item in items:
            gate = "" if item.gated else " _(below ceiling — reported, not failed)_"
            where = f" — `{_e(item.pointer)}`" + (f" line {item.line}" if item.line else "")
            lines.append(f"- **{item.rule_id}**{gate}: {item.message}{where}")
        lines.append("")

    lines.append("### Tools")
    lines.append("")
    lines.extend(_tool_table(manifest))
    lines.append("")
    lines.append(
        f"_manifest {manifest.manifest_version}, ruleset {manifest.ruleset_version or 'none'}, "
        f"surface `{manifest.surface_hash[:12]}`_"
    )
    lines.append("")
    return "\n".join(lines)
