# Held-out malicious set

Authored by Doc, against the pattern-class table in `docs/INJECTION.md`, and **not opened
during development** (Phase 3 brief §5). Drop files here in the same encoded format as
`../malicious/synthetic.json` — `samples[].{id, class, expected_classes, element, tool,
property?, uri?, siblings?, payload_b64}` — and score once with:

    python scripts/score_heldout.py

The score is reported as-is. Once a set here is scored and gated (Chief's ruling of
2026-09-23), the ratchet in `tests/test_inject_corpus.py` reads its file directly —
currently `heldout_v2.json` and `heldout_v2_surfaces.json` — so a scored file is live
regression data, not an inert record. Scratch files do not belong in this directory.

Two fields are optional and matter only for the case each was added for:

- `uri` — on a `resource_description` or `resource_template_description` sample, the URI
  the resource is served at. Under ruleset 3.3 the URI is the evidence a resource may
  describe its own path family, so a sample about a credential file must be able to say
  where it lives. Absent, a fixed `file:///corpus/…` is synthesized.
- `siblings` — other tool names on the fictional server. Absent, the server exposes only
  the tool the sample names, so any other identifier is foreign and `cross_scope` fires.
  A sample describing a same-server workflow needs to declare the tools it mentions.

An `expected_classes` of `[]` marks a **benign** sample: it passes when nothing fires on
its element, of any class, and is reported as a false-positive count rather than a
detection count.
