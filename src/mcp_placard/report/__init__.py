"""``placard report`` — Markdown and SARIF renderers (Phase 4 §2).

Reads a manifest, or a manifest and the baseline it is compared against, and
produces text. It performs no analysis of its own: ``diff`` decides what changed,
``inject`` decides what looks hostile, and this package formats. A renderer that
decides what is interesting is a classifier wearing a disguise, and its judgements
would be untestable through the diff table.

Everything rendered here is attacker-controlled — tool names, descriptions,
excerpts — and is escaped at construction (``findings.py``), not as a pass
afterwards. ``report`` refuses a manifest that fails ``verify``: a report of tampered
data is worse than no report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import ReportLevel
from ..diff import diff_manifests
from ..diff.models import DiffResult
from ..errors import (
    EXIT_REPORT_BASELINE_VERIFY_FAILED,
    EXIT_REPORT_VERIFY_FAILED,
    PlacardError,
)
from ..manifest import hash_mismatches, render_manifest
from ..manifest.models import Manifest, Tier
from .findings import ReportContext, ReportFinding, findings_from_diff, findings_from_manifest
from .markdown import render_markdown
from .sarif import render_sarif

__all__ = [
    "Report",
    "ReportRefused",
    "build_report",
    "render_markdown",
    "render_sarif",
]


class ReportRefused(PlacardError):
    """The manifest (or its baseline) fails ``verify``; nothing is rendered."""

    def __init__(self, message: str, *, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class Report:
    server: str
    manifest: Manifest
    baseline: Manifest | None
    diff: DiffResult | None
    findings: list[ReportFinding]
    status: int | None
    baseline_path: str | None

    def markdown(self) -> str:
        return render_markdown(
            server=self.server,
            manifest=self.manifest,
            findings=self.findings,
            diff=self.diff,
            status=self.status,
            baseline_path=self.baseline_path,
        )

    def sarif(self) -> dict[str, Any]:
        return render_sarif(
            server=self.server,
            findings=self.findings,
            artifact_uri=self.baseline_path,
            status=self.status,
        )

    def sarif_text(self) -> str:
        return json.dumps(self.sarif(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_report(
    manifest: Manifest,
    *,
    server: str,
    baseline: Manifest | None = None,
    baseline_path: Path | str | None = None,
    levels: ReportLevel | None = None,
    ceiling: Tier = "R4",
    escalate_schema_changes: bool = False,
) -> Report:
    """Assemble a report. With ``baseline`` the report covers the diff; without, the
    full manifest. ``baseline_path`` is the repository-relative path SARIF locations
    point at; it is used verbatim as the artifact URI."""
    mismatches = hash_mismatches(manifest)
    if mismatches:
        raise ReportRefused(
            "refusing to report a manifest whose hashes do not match its content: "
            + "; ".join(mismatches),
            exit_code=EXIT_REPORT_VERIFY_FAILED,
        )
    levels = levels or ReportLevel()

    if baseline is None:
        context = ReportContext(
            server=server,
            levels=levels,
            located_text=render_manifest(manifest),
            located_manifest=manifest,
        )
        findings = findings_from_manifest(manifest, context=context)
        return Report(server, manifest, None, None, findings, None, None)

    baseline_mismatches = hash_mismatches(baseline)
    if baseline_mismatches:
        raise ReportRefused(
            "refusing to report against a baseline whose hashes do not match its content: "
            + "; ".join(baseline_mismatches),
            exit_code=EXIT_REPORT_BASELINE_VERIFY_FAILED,
        )
    result = diff_manifests(
        baseline, manifest, ceiling=ceiling, escalate_schema_changes=escalate_schema_changes
    )
    context = ReportContext(
        server=server,
        levels=levels,
        located_text=render_manifest(baseline),
        located_manifest=baseline,
    )
    findings = findings_from_diff(result, new=manifest, context=context)
    path_text = str(baseline_path) if baseline_path is not None else None
    return Report(server, manifest, baseline, result, findings, result.exit_code, path_text)
