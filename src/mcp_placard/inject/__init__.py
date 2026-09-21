"""Injection surface heuristics over every model-facing string (Phase 3).

Phase 1 made a description change *visible* through ``description_hash``. This
package makes a description *suspicious* on first sight, without a baseline to
compare against, by matching deterministic patterns for the seven classes in
``docs/INJECTION.md``: ``override``, ``concealment``, ``cross_scope``,
``sensitive_target``, ``exfil_sink``, ``hidden_content``, ``markup_smuggling``.

Boundary: reads text out of a manifest and returns findings. It never fetches a
URL a description mentions, never expands a reference, never reads a resource, and
never passes scanned text to a model. Scanned content is untrusted data;
dereferencing it would make the scanner a delivery mechanism for the thing it is
scanning for.

The false-positive rate on the benign corpus is a tracked, ratcheted metric
(``tests/test_inject_ratchet.py``): a scanner that cries wolf gets turned off, and a
scanner that is turned off has a detection rate of zero.
"""

from __future__ import annotations

from ..manifest.models import InjectionFinding, Manifest
from .patterns import DETECTORS
from .render import MAX_EXCERPT, escape_excerpt, markdown_line, stderr_line
from .surface import TextElement, enumerate_text

__all__ = [
    "MAX_EXCERPT",
    "InjectionFinding",
    "TextElement",
    "analyze_elements",
    "analyze_manifest",
    "enumerate_text",
    "escape_excerpt",
    "markdown_line",
    "stderr_line",
]

EXCERPT_STORED = 200
"""Characters of matched text stored on a finding. Longer matches (a whole HTML
comment, a long base64 run) are cut here; the span still records the full extent."""


def analyze_elements(elements: list[TextElement]) -> list[InjectionFinding]:
    """Run every detector over every element. Deterministic: same input, same
    findings, same order (document order, then detector order, then position)."""
    findings: list[InjectionFinding] = []
    for element in elements:
        for detector in DETECTORS:
            for match in detector(element):
                findings.append(
                    InjectionFinding(
                        element=element.element,
                        pointer=element.pointer,
                        tool=element.tool,
                        pattern_class=match.pattern_class,
                        rule=match.rule,
                        start=match.start,
                        end=match.end,
                        excerpt=element.text[match.start : match.end][:EXCERPT_STORED],
                    )
                )
    findings.sort(key=lambda f: (f.pointer, f.start, f.pattern_class, f.rule))
    return findings


def analyze_manifest(manifest: Manifest) -> list[InjectionFinding]:
    """Every injection finding across the manifest's model-facing strings."""
    return analyze_elements(enumerate_text(manifest))
