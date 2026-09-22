# `report/` — Markdown and SARIF renderers

## Status: implemented (Phase 4)

`placard report` renders a manifest, or a diff against a baseline, as Markdown (for
humans and `$GITHUB_STEP_SUMMARY`) or SARIF 2.1.0 (for GitHub code scanning). Findings
are unified in `findings.py`; `locate.py` maps a JSON Pointer to a real line in the
indented baseline so SARIF regions point at something; `sarif.py` emits the rule
catalog, text-only messages, physical and logical locations, and partial fingerprints
derived from server, element, rule, and excerpt hash — never from position.

## Responsibility (Phase 4)

Render a manifest, or a diff between two manifests, as something a human reads in a
pull request (Markdown) or a machine ingests into a code-scanning dashboard (SARIF).

## Boundary (Phase 4)

Reads manifests and diff results. Produces text. It performs no analysis of its own —
a renderer that decides what is interesting is a classifier wearing a disguise, and
its judgements would be untestable through the diff table.

## The constraint that governs this package

**Everything rendered here is attacker-controlled.** Tool descriptions, resource
text, and server names come from the audited party. AGENTS.md is explicit: report
renderers escape scanned content, and an injection string must not become live markup
in the Markdown or SARIF output.

Concretely, that means:

- Escape at construction, not as a pass afterwards. A renderer that builds a string
  and sanitizes it later will eventually grow a path that skips the sanitizer.
- Markdown: no raw interpolation into link targets, image sources, HTML blocks, or
  code fences that scanned content could close.
- SARIF: scanned text belongs in message *arguments*, never in a format string.
- A description that reads as an instruction to whoever is reviewing the report is
  itself the payload. Rendering it verbatim inside a fenced, escaped block is the
  goal; rendering it as prose in the reviewer's reading flow is not.

## Refusal

`report` refuses a manifest (101) or a baseline (102) whose hashes do not match. A
report of tampered data is worse than no report.

## Phase 1 note

`diff` findings report **hashes, not description text**, for exactly this reason. The
text is reviewed via `git diff` on the manifests, where it is already quoted and
escaped as JSON data.
