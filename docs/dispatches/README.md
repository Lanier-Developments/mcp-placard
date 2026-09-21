# Dispatches

The working record of how Placard's taxonomy was argued into shape. Two roles:

- **Chief** writes a dated brief specifying a phase, and later a decisions memo adjudicating
  what came back.
- **Jr.** implements against the brief and writes a dated report: what landed, what the real
  servers said, and the questions that need a ruling rather than an implementation choice.

Every rule in `docs/TAXONOMY.md` that changed after Phase 1 changed here first, with the
evidence attached — usually a real server's `tools/list`. The amendments themselves
(`../TAXONOMY-amendment-*.md`) are the adopted text; these files are why.

| Date | Direction | Subject |
| --- | --- | --- |
| 2026-09-14 | Chief → Jr. | Phase 1 scaffold brief |
| 2026-09-16 | Chief → Jr. | Phase 2 classifier brief (rev 1, superseded) |
| 2026-09-16 | Chief → Jr. | Phase 2 classifier brief, rev 2 |
| 2026-09-16 | Chief → Jr. | Phase 2 addendum: Rule G, `CHAIN_EXFIL` scope |
| 2026-09-17 | Jr. → Chief | Phase 2 against 11 real servers: three rule ambiguities, four flag-backs |
| 2026-09-18 | Chief → Jr. | Phase 2.1 corrections brief (Amendment 2) |
| 2026-09-18 | Jr. → Chief | Phase 2.1 report with before/after delta; Phase 2.2 addenda appended |
| 2026-09-18 | Chief → Jr. | Phase 2.2 decisions on the three flag-backs (Amendment 3) |
| 2026-09-19 | Chief → Jr. | Phase 2.2 addendum decisions: condition 1, negation guard, exit codes |
| 2026-09-21 | Chief → Jr. | Phase 3 brief: injection surface, and the 0.3.0 bitmask exit-code ruling |
| 2026-09-21 | Jr. → Chief | Phase 3 report: corpus, ratchet, re-analysis, the spurious-escalation confirmation |

These are kept verbatim, including the parts that turned out to be wrong. A taxonomy whose
history is visible is easier to trust than one that only shows its current text.
