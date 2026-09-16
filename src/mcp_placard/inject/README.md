# `inject/` — injection surface heuristics

## Status: empty. Phase 3.

This directory exists because AGENTS.md's structure names it. Nothing is implemented,
and **nothing should be added here before Phase 2's fixtures are green** — AGENTS.md
forbids beginning a phase before the prior phase's fixtures pass.

## Responsibility (Phase 3)

Score tool descriptions and resource text for the patterns that turn model-facing
metadata into an instruction channel: imperatives aimed at the agent rather than the
user, references to other tools, embedded URLs to fetch, claims of authority, and
attempts to suppress disclosure to the user.

This is the mechanical half of the principle behind the whole tool: **a tool
description is a prompt.** Phase 1 makes a description change *visible* through
`description_hash`. Phase 3 makes a description *suspicious* on first sight, without
a baseline to compare against.

## Boundary (Phase 3)

Reads text out of a manifest and returns findings. It never fetches a URL a
description mentions, never expands a reference, and never passes scanned text to a
model. Scanned content is untrusted data; dereferencing it would make the scanner a
delivery mechanism for the thing it is scanning for.

## Constraints fixed in advance by AGENTS.md

- **The corpus lives in `tests/fixtures/injection/`** and holds malicious samples
  *and* benign descriptions that superficially resemble them. A tool description that
  legitimately says "always call `search_documents` first" is not an attack.
- **The false-positive rate on the benign set is a tracked metric, not an
  afterthought.** A scanner that cries wolf gets turned off, and a scanner that is
  turned off has a detection rate of zero.
- **Renderers escape scanned content.** An injection string must never become live
  markup in Markdown or SARIF output — see `report/`.
