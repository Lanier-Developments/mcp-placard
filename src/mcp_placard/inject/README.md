# `inject/` — injection surface heuristics

## Status: implemented (Phase 3)

Deterministic pattern matching over every model-facing string a manifest carries,
producing `injection_findings` (manifest format 2.2). Seven classes, each a closed set
of named rules; every finding cites its rule, its element, its JSON Pointer, its
character span, and the matched excerpt. `docs/INJECTION.md` is the specification.

## Responsibility

Make a description *suspicious on first sight*, without a baseline. Phase 1 made a
description change visible through `description_hash`; this package says whether the
text is trying to reach outside its own scope — other tools, other servers, the user
relationship, the agent's standing instructions.

## Boundary

Reads text out of a manifest and returns findings. It never fetches a URL a description
mentions, never expands a reference, never reads a resource (resource *descriptions*
are in scope; resource *contents* are a stated non-detection in `docs/THREAT_MODEL.md`),
and never passes scanned text to a model. Scanned content is untrusted data;
dereferencing it would make the scanner a delivery mechanism for the thing it is
scanning for.

## Layout

| Module | Role |
| --- | --- |
| `surface.py` | Enumerate every model-facing string with the context the heuristics need (own tool names, own parameter names, whether the tool handles paths or credentials) |
| `patterns.py` | The seven classes as named rules; the scoping decisions that keep the benign corpus at zero |
| `render.py` | Escape an excerpt for Markdown or a terminal — the one place scanned text is ever printed |
| `corpus.py` | Decode an encoded corpus sample into a manifest; shared by the tests and the held-out scorer |
| `__init__.py` | `analyze_manifest` / `analyze_elements` |

## Constraints fixed in advance by AGENTS.md

- **The corpus lives in `tests/fixtures/injection/`** and holds malicious samples *and*
  benign descriptions that superficially resemble them. A tool description that
  legitimately says "use `read_text_file` instead" is not an attack.
- **The false-positive rate on the benign set is a tracked metric, not an
  afterthought.** It is a ratchet against `baseline.json`; the annotated hard cases
  never flag, with zero tolerance.
- **Renderers escape scanned content.** An injection string must never become live
  markup in Markdown or SARIF output — `render.py`, tested in `test_inject_render.py`.
- **Malicious samples are stored encoded** and decoded only at the moment of test.
  Their contents are data under test, never instructions.
