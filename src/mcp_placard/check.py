"""``placard baseline`` and ``placard check`` — the configured-servers workflow.

The model (Phase 4 brief): **the committed baseline manifest is the approval
record.** ``baseline`` scans every configured server and writes the manifests to
``baseline_dir``; a repository commits them. ``check`` scans again, diffs each server
against its baseline, ORs the resulting bitmasks together, and writes the Markdown
summary and the SARIF log. Approving a change means committing the new manifest —
a pull request, which is a code review of exactly what changed. ``baseline`` never
runs in CI; approving a capability change is a human commit, by design.

``check`` adds one bit ``diff`` cannot: **incomplete**, 16, when a configured server
could not be scanned. ``check`` scans before it diffs, and a server that cannot be
scanned has no representation in ``diff``'s bits; reporting nothing would pass the
gate on a server it never looked at. A server with no baseline yet is reported, not
failed, and sets no bit — first adoption should not be a red build.

Credentials named in the configuration are resolved from the environment here,
handed to the transport, and dropped. They reach no manifest, no report, no output
file, and no stderr line (Phase 4 §5); ``tests/test_check.py`` proves it with a
sentinel value.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .analysis import analyze
from .config import FindingCategory, PlacardConfig, ServerConfig
from .errors import (
    EXIT_DESCRIPTION_CHANGE,
    EXIT_ESCALATION,
    EXIT_INCOMPLETE,
    EXIT_INJECTION,
    EXIT_REMOVED,
    PlacardError,
)
from .manifest import build_manifest, load_manifest, write_manifest
from .manifest.models import Manifest
from .report import Report, ReportRefused, build_report
from .report.findings import decode_bits
from .transport import scan_target
from .transport.launch import isolated_launch

CATEGORY_BITS: dict[FindingCategory, int] = {
    "escalation": EXIT_ESCALATION,
    "prompt": EXIT_DESCRIPTION_CHANGE,
    "removal": EXIT_REMOVED,
    "injection": EXIT_INJECTION,
    "incomplete": EXIT_INCOMPLETE,
}
DEFAULT_FAIL_ON: tuple[FindingCategory, ...] = ("escalation", "prompt", "injection", "incomplete")
"""What fails the gate unless configured otherwise: everything but removal."""


def scan_server(
    server: ServerConfig, config: PlacardConfig, *, environ: Mapping[str, str] | None = None
) -> Manifest:
    """Scan one configured server and analyse it with its overrides.

    Headers and pass-through variables are resolved from ``environ`` into memory
    for the duration of the scan only.
    """
    environ = os.environ if environ is None else environ
    headers = server.resolve_headers(environ)
    passthrough = server.resolve_env(environ)
    timeout = server.timeout or config.defaults.timeout
    with isolated_launch(passthrough) as launch_env:
        raw = scan_target(
            server.target,
            transport=server.transport,
            timeout=timeout,
            env=launch_env,
            headers=headers or None,
        )
    return analyze(build_manifest(raw), overrides=config.overrides_for(server.name))


@dataclass
class ServerOutcome:
    name: str
    baseline_path: Path
    scanned: bool = False
    baseline_present: bool = False
    status: int = 0
    error: str | None = None
    manifest: Manifest | None = None
    report: Report | None = None

    @property
    def incomplete(self) -> bool:
        return not self.scanned


@dataclass
class CheckResult:
    outcomes: list[ServerOutcome] = field(default_factory=list)

    @property
    def status(self) -> int:
        status = 0
        for outcome in self.outcomes:
            status |= outcome.status
            if outcome.incomplete:
                status |= EXIT_INCOMPLETE
        return status

    def categories(self) -> list[FindingCategory]:
        return decode_bits(self.status)

    def fails(self, fail_on: tuple[FindingCategory, ...] | list[FindingCategory]) -> bool:
        mask = 0
        for category in fail_on:
            mask |= CATEGORY_BITS[category]
        return bool(self.status & mask)

    def outputs(
        self, fail_on: tuple[FindingCategory, ...] | list[FindingCategory]
    ) -> dict[str, Any]:
        """What the action exposes as step outputs: the raw bitmask, one boolean per
        category, and the gate decision for the configured ``fail-on``."""
        categories = set(self.categories())
        return {
            "exit_code": self.status,
            **{name: (name in categories) for name in CATEGORY_BITS},
            "fail": self.fails(fail_on),
            "fail_on": list(fail_on),
            "servers": [
                {
                    "name": o.name,
                    "status": o.status,
                    "scanned": o.scanned,
                    "baseline_present": o.baseline_present,
                    "baseline": str(o.baseline_path),
                    "error": o.error,
                }
                for o in self.outcomes
            ],
        }

    def markdown(self) -> str:
        lines = ["# Placard check", ""]
        categories = self.categories()
        if categories:
            words = " | ".join(categories)
            lines.append(f"**Exit status {self.status}** = {words}")
        else:
            lines.append(f"**Exit status {self.status}** — nothing to review. ✅")
        lines.append("")
        lines.append("| Server | Status | Baseline | Result |")
        lines.append("| --- | --- | --- | --- |")
        for o in self.outcomes:
            if not o.scanned:
                result = f"⚠️ could not be scanned: {_e(o.error or 'unknown error')}"
                status = f"{EXIT_INCOMPLETE} (incomplete)"
            elif not o.baseline_present:
                result = "no baseline yet — reported, not failed; run `placard baseline` and commit"
                status = "0"
            else:
                bits = ", ".join(decode_bits(o.status)) or "no findings"
                result = bits
                status = str(o.status)
            lines.append(f"| {_e(o.name)} | {status} | `{_e(str(o.baseline_path))}` | {result} |")
        lines.append("")
        for o in self.outcomes:
            if o.report is not None:
                lines.append(o.report.markdown())
        return "\n".join(lines)

    def sarif(self) -> dict[str, Any]:
        """One SARIF log with one run per server that produced a report."""
        runs = [o.report.sarif()["runs"][0] for o in self.outcomes if o.report is not None]
        from .report.sarif import SARIF_SCHEMA

        return {"$schema": SARIF_SCHEMA, "version": "2.1.0", "runs": runs}


def _e(text: str) -> str:
    from .inject.render import escape_excerpt

    return escape_excerpt(text, limit=200)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def run_check(
    config: PlacardConfig,
    *,
    root: Path,
    only: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> CheckResult:
    """Scan and diff every configured server (or the named subset)."""
    result = CheckResult()
    servers = [s for s in config.server if not only or s.name in only]
    for server in servers:
        baseline_path = config.baseline_path(server, root=root)
        outcome = ServerOutcome(name=server.name, baseline_path=baseline_path)
        result.outcomes.append(outcome)
        try:
            manifest = scan_server(server, config, environ=environ)
        except PlacardError as exc:
            outcome.error = str(exc)
            continue
        outcome.scanned = True
        outcome.manifest = manifest
        if not baseline_path.is_file():
            outcome.report = build_report(manifest, server=server.name, levels=config.report.level)
            continue
        outcome.baseline_present = True
        try:
            baseline = load_manifest(baseline_path)
            outcome.report = build_report(
                manifest,
                server=server.name,
                baseline=baseline,
                baseline_path=_relative(baseline_path, root),
                levels=config.report.level,
                ceiling=config.defaults.ceiling,
            )
        except ReportRefused as exc:
            outcome.scanned = False  # a tampered baseline is a gate that cannot be trusted
            outcome.error = str(exc)
            continue
        outcome.status = outcome.report.status or 0
    return result


def write_baselines(
    config: PlacardConfig,
    *,
    root: Path,
    only: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[tuple[str, Path, str | None]]:
    """Scan each configured server and write its manifest to its baseline path.
    Returns ``(name, path, error)`` per server; ``error`` is ``None`` on success."""
    written: list[tuple[str, Path, str | None]] = []
    servers = [s for s in config.server if not only or s.name in only]
    for server in servers:
        path = config.baseline_path(server, root=root)
        try:
            manifest = scan_server(server, config, environ=environ)
            write_manifest(manifest, path)
            written.append((server.name, path, None))
        except PlacardError as exc:
            written.append((server.name, path, str(exc)))
    return written


def dump_outputs(result: CheckResult, fail_on: list[FindingCategory], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.outputs(fail_on), indent=2) + "\n", encoding="utf-8")
