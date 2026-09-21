"""The one place a manifest is analysed: classification, injection, ruleset stamp.

``scan`` calls :func:`analyze` once. ``diff`` calls :func:`reanalyze` on any side
whose recorded ``ruleset_version`` is not the current one (Phase 3 §4), so that two
manifests are only ever compared under the same rules:

> Classification records the analyzer ruleset version. When ``diff`` compares
> manifests produced under different ruleset versions, it re-runs classification
> and injection analysis on the old manifest's surface with the current rules
> before comparing. Only surface changes can produce findings; ruleset changes
> never do.

This is possible because of a property held since Phase 1: the manifest carries the
complete surface, and analysis is static. Nothing here contacts a server.
"""

from __future__ import annotations

from . import RULESET_VERSION
from .classify import classify_manifest
from .classify.overrides import OverrideEntry
from .inject import analyze_manifest as inject_findings
from .manifest.build import compute_classification_hash
from .manifest.models import Manifest

__all__ = ["analyze", "needs_reanalysis", "reanalyze", "recorded_overrides"]


def analyze(manifest: Manifest, *, overrides: list[OverrideEntry] | None = None) -> Manifest:
    """Classify every tool, run the injection heuristics over every model-facing
    string, stamp the ruleset, and recompute ``classification_hash`` over all of it.

    Pure: returns a new manifest, never mutates the input.
    """
    classified = classify_manifest(manifest, overrides=overrides)
    findings = inject_findings(classified)
    return classified.model_copy(
        update={
            "injection_findings": findings,
            "ruleset_version": RULESET_VERSION,
            "classification_hash": compute_classification_hash(
                classified.classification, findings, RULESET_VERSION
            ),
        }
    )


def needs_reanalysis(manifest: Manifest) -> bool:
    """True when the manifest was analysed under a different ruleset than this
    build's, or under none at all (a ``1.0``/``2.0``/``2.1`` document, or a
    manifest built but never analysed)."""
    return manifest.ruleset_version != RULESET_VERSION


def recorded_overrides(manifest: Manifest) -> list[OverrideEntry]:
    """Reconstruct the override allowlist a manifest was analysed with, from the
    ``override`` record each downgraded tool carries.

    Re-analysing without them would make every operator-downgraded tool reappear
    at its inferred tier and read as an escalation against the stored baseline.
    The manifest records which entry applied to which tool and the tier it
    produced; that is enough to re-apply it. The entry's free-text reason is not
    recorded and is not needed.
    """
    entries: list[OverrideEntry] = []
    for entry in manifest.classification:
        if entry.override is not None:
            entries.append(
                OverrideEntry(
                    entry_id=entry.override.entry,
                    tool=entry.tool,
                    tier=entry.tier,
                    reason="re-applied from the manifest's own override record",
                )
            )
    return entries


def reanalyze(manifest: Manifest) -> Manifest:
    """Re-run the full analysis on a manifest's stored surface under the current
    ruleset, re-applying the overrides it records. ``surface_hash`` and
    ``capabilities_hash`` are untouched — nothing about the server changes, only
    Placard's judgement of it."""
    return analyze(manifest, overrides=recorded_overrides(manifest))
