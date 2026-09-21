# Held-out malicious set

Authored by Doc, against the pattern-class table in `docs/INJECTION.md`, and **not opened
during development** (Phase 3 brief §5). Drop files here in the same encoded format as
`../malicious/synthetic.json` — `samples[].{id, class, expected_classes, element, tool,
property?, payload_b64}` — and score once with:

    python scripts/score_heldout.py

The score is reported as-is. Nothing in this directory is read by the test suite.
