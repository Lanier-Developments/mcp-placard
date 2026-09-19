# Contributing

Thanks for looking. Placard is small, opinionated, and tested against real MCP servers, and
the easiest contributions are the ones that keep it that way.

**Read [`AGENTS.md`](AGENTS.md) first.** It is the operating spec: the two principles every
design decision follows, the hard non-goal, the exit-code contract, and the testing rules.
This file only tells you how to get set up and what a good pull request looks like.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
pytest
```

Python 3.11 or newer. The test suite needs no network; every server interaction runs against
fixtures and the bundled mock server.

## The most useful contribution: a misclassification with a schema

Placard's classifier is written against real `tools/list` responses. If a tool lands at the
wrong tier, the schema and description are the whole argument. Open an issue with the
*Misclassification* template and paste them in. If you want to go further, capture the
server's surface as a fixture:

```bash
placard scan "<how you start the server>" --out capture.json
```

and lift the `surface.tools` entries into `tests/fixtures/real_servers/<server>.json` in the
same shape as the existing files. A test in `tests/test_classify_real_servers.py` that pins the
correct tier turns the argument into a regression guard.

## Rules that will come up in review

- **No `tools/call`, ever.** A PR that adds one is rejected on sight. The AST guard will catch
  it before a reviewer does.
- **Classifier changes need a fixture pair.** A tool that belongs in the tier, and a near-miss
  that does not. AGENTS.md: a classifier change without one is incomplete.
- **Every tier and every kind must cite evidence.** Two global tests enforce this; a change
  that produces an uncited tier or kind fails them.
- **Field-name lists are closed.** Rule C's communication targets, Rule D's content and
  destination names, Rule H's code parameters — these are explicit allowlists, not
  heuristics. Adding a name is a deliberate, argued change to `docs/TAXONOMY.md`, not a
  one-line edit to a set.
- **Exit codes are an interface.** Add a row to `tests/test_diff_table.py` or
  `tests/test_exit_code_contract.py` before changing a code's meaning. Categories, not a
  severity ladder.
- **The self-gating fixture is regenerated deliberately, never to make CI green.** If
  `tests/fixtures/mock_server_manifest.json` needs to change, say why in the PR.
- **Coverage floor is 85% on `src/`.** Do not lower it.

## Taxonomy changes

The R0-R5 ladder, the kind axis, and Rules A-H live in `docs/TAXONOMY.md`. Changes to the
rules are made by amendment: a short document stating the defect, the evidence (ideally a
real server schema), the replacement text, and the residual risk accepted. Amendments 1
through 3 in `docs/` are the pattern. Code follows the taxonomy, not the other way round.

## Pull requests

- Branches: `feature/<short-description>` or `fix/<short-description>`.
- Conventional commits. One logical change per PR.
- The PR description states what changed, which fixtures were added, and any exit-code
  semantics affected. The template asks for exactly these.
- CI must pass lint, types, tests, coverage, the no-invocation guard, and the self-gate.
