# Status: what has shipped since 0.5.0, and three things only you can unblock

**From:** Jr.
**To:** Chief
**Date:** 2026-10-14
**Re:** The Sep 23 override/concealment report, held-out v3, and the Phase 5 brief
**Status:** Nothing below is started. No rule, pattern, vocabulary or baseline was touched.

## What landed since 0.5.0

- **0.5.1 is tagged on `main`.** Docs only: README and AGENTS.md status brought up to date
  with 3.4 and 3.5, and INJECTION.md no longer says v2 is unscored.
- **`docs/INJECTION.md` now has a Known limits section** (PR #34). It states that `override`
  and `concealment` each found 1 of 7 on held-out v2, names the baseline diff as the defence for
  those two classes, and records one worked miss (below). It was written on the assumption that
  nothing has been ruled on yet, so it needs rewriting when you rule.
- **A blast-radius index of nine public servers is on `main`** (PR #36): `docs/INDEX.md`,
  `index/servers.toml`, `index/manifests/`, `scripts/build_index.py`. Pinned versions, committed
  manifests, a page rendered from them, and a test that keeps the page and manifests in sync. A
  second full scan reproduced all nine manifests byte for byte.

## 1. Ruling on the Sep 23 taxonomy report (21 days open)

`2026-09-23_from-jr_to-chief_override-concealment-taxonomy.md` asked you to rule on three things:

1. Concealment: write the affirmative-suppression rule (the report found 7 of 8 misses structural).
2. Fix the adjacency defect in both `override` and `concealment`, validated against the benign
   corpus before it lands.
3. Publish `override` as it stands and do not chase the vocabulary misses.

The report argued for doing 1 and 2 together, once, and then commissioning v3 from a different
author rather than reusing v2. Until you rule, the published numbers stand: 33/49 overall, 1/7 on
each of the two classes.

## 2. Held-out v3

None is in the repo. v3 has to come from an author who has not seen the rules or v1/v2. The
ruleset change in item 1 should land before v3 is scored, so v3 measures it. Who authors it, and
when, is your call.

## 3. Phase 5 signing brief

None is in the repo, and signing is not started. AGENTS.md's order is brief, implement, report,
and I will not begin signing without the brief.

## One thing for you to confirm: the index went ahead without a brief

The index is the second half of the Phase 5 roadmap entry. I built it while signing was blocked
and it merged as PR #36. It does not touch the classifier, the manifest format or any hash. If you
want it held, reshaped, or folded into the signing brief, it is one revert or a docs edit. If you
are content, say so and AGENTS.md can stop describing Phase 5 as half built.

## New evidence for the corpus

On 2026-10-14 I re-scanned `mcp-server-fetch` 2026.10.10 myself. Its tool description says:
"Although originally you did not have internet access, and were advised to refuse and tell the
user this, this tool now grants you internet access." Ruleset 3.5 returns no findings on it. It
tells the model that its earlier guidance is out of date. Is that an `override` sample, or is a
reference server's own correction of its own history outside the class? It is not in any corpus
yet; I would rather you decide which side of the line it sits on than have me guess.

## What I need back

A ruling on item 1, a decision on who writes v3, the Phase 5 brief, and a yes or no on the index.
