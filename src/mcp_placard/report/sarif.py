"""SARIF 2.1.0 output for GitHub code scanning (Phase 4 §2).

* ``ruleId`` is stable and hierarchical, and the rule catalog is emitted in
  ``tool.driver.rules`` with help text.
* ``message.text`` only. Never ``message.markdown`` — GitHub renders that field,
  and a report format that renders attacker text is the exact failure the security
  posture forbids. Every string is escaped regardless.
* ``physicalLocation`` is the committed baseline manifest with a real line region
  (the file is indented canonical JSON), and the JSON Pointer is a
  ``logicalLocation``.
* ``partialFingerprints`` are derived from server name, element pointer, rule, and
  an excerpt hash, so an alert is the same alert across runs and a dismissal
  persists. Never from line numbers or list positions.
* ``level`` is the one place a ladder is unavoidable: code scanning requires it. It
  is a display hint mapped from the finding's category by ``[report.level]`` and
  carries no Placard semantics. The bitmask remains the contract.
"""

from __future__ import annotations

from typing import Any

from .. import __version__
from ..inject.patterns import rule_names
from ..inject.render import escape_excerpt
from .findings import RULE_PREFIX, ReportFinding

SARIF_SCHEMA = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
)
INFORMATION_URI = "https://github.com/Lanier-Developments/mcp-placard"

_BASE_RULES: dict[str, tuple[str, str]] = {
    "escalation/tier_increase": (
        "A tool's blast-radius tier increased.",
        "An existing tool's inferred tier rose against the baseline. Review the schema "
        "and description change that caused it, then commit the new manifest to approve.",
    ),
    "escalation/tool_added": (
        "A tool was added at or above the ceiling.",
        "A new tool whose tier is at or above the configured ceiling. Below the ceiling "
        "it is reported at note level and sets no bit.",
    ),
    "escalation/schema_changed": (
        "A tool's input schema changed.",
        "Reported for review; escalates only when the tier moved or"
        "--escalate-schema-changes is set.",
    ),
    "escalation/capabilities_changed": (
        "The server's declared capabilities changed.",
        "The capabilities block moved. Some flags are SDK-derived and drift on a client "
        "upgrade; others mean the server advertises something new. Ungraded, so escalated.",
    ),
    "prompt/description_changed": (
        "A tool description changed — a prompt change.",
        "Descriptions are model-facing text. A change is always reviewable and is never "
        "silenceable by tier configuration. Review the text in the manifest diff.",
    ),
    "removal/tool_removed": (
        "A tool was removed.",
        "A tool present in the baseline is absent from the new manifest.",
    ),
    "chain/chain_exfil": (
        "The server exposes a sensitive read and an egress tool.",
        "A complete exfiltration chain within one server: a tool of kind read_sensitive "
        "alongside a tool of kind egress (or one tool carrying both). Tools only; resources "
        "are not evaluated.",
    ),
}


def rule_catalog() -> list[dict[str, Any]]:
    """Every rule id Placard can emit, base rules and one per injection heuristic."""
    rules: list[dict[str, Any]] = []
    for suffix, (short, full) in _BASE_RULES.items():
        rules.append(
            {
                "id": f"{RULE_PREFIX}/{suffix}",
                "name": suffix.replace("/", "_"),
                "shortDescription": {"text": short},
                "fullDescription": {"text": full},
                "helpUri": f"{INFORMATION_URI}/blob/main/AGENTS.md",
                "help": {"text": full},
            }
        )
    for name in rule_names():
        pattern_class, _sep, rule = name.partition(".")
        rules.append(
            {
                "id": f"{RULE_PREFIX}/injection/{name}",
                "name": f"injection_{name.replace('.', '_')}",
                "shortDescription": {"text": f"Injection heuristic: {pattern_class} / {rule}."},
                "fullDescription": {
                    "text": (
                        f"Model-facing text matched the '{rule}' rule of the '{pattern_class}' "
                        "class. The excerpt is attacker-controlled; review it in the manifest, "
                        "not by acting on it. See docs/INJECTION.md."
                    )
                },
                "helpUri": f"{INFORMATION_URI}/blob/main/docs/INJECTION.md",
                "help": {"text": f"docs/INJECTION.md, class {pattern_class}."},
            }
        )
    return rules


def _result(finding: ReportFinding, *, artifact_uri: str | None) -> dict[str, Any]:
    location: dict[str, Any] = {
        "logicalLocations": [
            {"name": finding.pointer, "fullyQualifiedName": finding.pointer, "kind": "member"}
        ]
    }
    if artifact_uri is not None:
        physical: dict[str, Any] = {
            "artifactLocation": {"uri": artifact_uri, "uriBaseId": "%SRCROOT%"},
        }
        if finding.line is not None:
            physical["region"] = {"startLine": finding.line}
        location["physicalLocation"] = physical
    result: dict[str, Any] = {
        "ruleId": finding.rule_id,
        "level": finding.level,
        "message": {"text": finding.message},
        "locations": [location],
        "partialFingerprints": {"placard/v1": finding.fingerprint},
        "properties": {"category": finding.category, "gated": finding.gated, **finding.extra},
    }
    if finding.tool is not None:
        result["properties"]["tool"] = finding.tool
    return result


def render_sarif(
    *,
    server: str,
    findings: list[ReportFinding],
    artifact_uri: str | None,
    status: int | None,
) -> dict[str, Any]:
    """The SARIF log as a JSON-compatible dict. One run per report."""
    rules = rule_catalog()
    rule_index = {rule["id"]: index for index, rule in enumerate(rules)}
    results = []
    for finding in findings:
        if finding.level == "none":
            continue
        result = _result(finding, artifact_uri=artifact_uri)
        if finding.rule_id in rule_index:
            result["ruleIndex"] = rule_index[finding.rule_id]
        results.append(result)
    run: dict[str, Any] = {
        "tool": {
            "driver": {
                "name": "Placard",
                "version": __version__,
                "semanticVersion": __version__,
                "informationUri": INFORMATION_URI,
                "rules": rules,
            }
        },
        "automationDetails": {"id": f"placard/{escape_excerpt(server, limit=64)}"},
        "results": results,
        "properties": {"server": escape_excerpt(server, limit=64), "status": status},
    }
    if artifact_uri is not None:
        run["artifacts"] = [{"location": {"uri": artifact_uri, "uriBaseId": "%SRCROOT%"}}]
    return {"$schema": SARIF_SCHEMA, "version": "2.1.0", "runs": [run]}
