# Note: prompt and resource elements carry no tool context — `sensitive_target` cannot be exempted there

**From:** Jr.
**To:** Chief
**Date:** 2026-09-23
**Re:** The held-out v2 surfaces file, and a latent false positive it exposed
**Status:** Ruling wanted before the second file is commissioned from Doc.

## Summary

Reviewing the draft commission for a second held-out file — the one aimed at prompt and
resource descriptions — turned up a gap in the analyzer that the file would have measured
dishonestly. It is worth a ruling on its own terms, separately from the commission.

`enumerate_text` builds prompt, prompt-argument, resource, and resource-template elements
without `handles_paths`, `handles_credentials`, or `own_param_names`
(`inject/surface.py:184-221`; the fields default `False` and empty at `surface.py:77-82`).
`detect_sensitive_target` is guarded by exactly those two booleans
(`inject/patterns.py:589-594`). So on any non-tool surface the credential exemption — "a
tool that handles paths or credentials may mention them", the scoping rule in
`INJECTION.md` — **cannot apply at all**.

The same sentence, `"The agent's SSH configuration at ~/.ssh/config, for reference."`:

| Element | Result |
| --- | --- |
| tool description, tool has a `path` parameter | no finding (exemption applies) |
| resource description | `sensitive_target.credential_path` |
| resource template description | `sensitive_target.credential_path` |
| prompt description | `sensitive_target.credential_path` |
| prompt argument description | `sensitive_target.credential_path` |

## Two consequences

**1. It would have corrupted the v2 measurement.** Every `sensitive_target` sample Doc
placed on those surfaces is a guaranteed hit before it is written. Two of fourteen samples
in the draft commission were that case: not a measurement, an identity. Held-out v2 is
meant to replace 24/35 as the published number, and a number with tautologies folded into
it is worth less than no number.

**2. It is a live false-positive risk on real servers.** A resource that legitimately *is*
the SSH config, described accurately, flags — and there is no schema evidence available on
that element to exempt it with. This is the crying-wolf outcome the zero-tolerance rule
exists to prevent, on a surface where we have almost no evidence either way: of the 388
benign elements, **364 are tool-owned and only 21 are prompt, resource, or template**
(prompt 11, resource 8, template 2). Zero false positives there is a real result, but it
is drawn from a thin sample, and none of those 21 happens to mention a credential path.
We have not shown the rule is clean on these surfaces; we have shown it has not yet been
asked.

## Options

**A. Document and accept.** Add it to the scoping rules in `INJECTION.md` and as a stated
limitation in `THREAT_MODEL.md`, the same treatment resource contents and the `CHAIN_EXFIL`
resource gap already get. Costs nothing, keeps the ruleset frozen, and leaves a known FP
shape in the product.

**B. Derive the context from what these elements do have.** A resource has a URI and a
template has a URI template; a prompt argument has a name. The tool rule is "decided by
schema evidence" — the analogue is URI evidence and argument-name evidence. A resource at
`file:///…` or `ssh://…` handles paths; a prompt argument named `token` or `api_key`
handles credentials. Same principle, different evidence, and it keeps the exemption
earned rather than granted.

**C. Fall back to the server.** If any tool on the server handles paths or credentials,
exempt its prompt and resource elements too. Cheapest to implement and the weakest: a
filesystem server's entirely unrelated prompt would be exempt for a reason that has
nothing to do with that prompt.

I recommend **B**. It is a ruleset change — 3.3 — and it has to be measured against the
benign corpus before it lands, per the zero-tolerance rule.

## The ordering question, which is the actual ask

Whichever option you pick, it has to be settled **before** Doc's second file is scored.
Changing the exemption after we have seen which samples missed is tuning to the test, and
it would forfeit the only thing a held-out set buys.

So, concretely:

- **If B (or C) now:** ship the fix first, then commission all seven classes on the new
  surfaces — `sensitive_target` included, because by then the exemption is real there.
- **If A, or if you want v2 to go out first:** commission six classes and tell Doc
  `sensitive_target` is excluded and why. Eighteen samples, three per class. The gap gets
  documented, and the number stays honest.

Either way, the second commission does not go out until this is ruled.

## Also done, unrelated to the ruling

`inject/corpus.py` now builds the four non-tool element kinds (`prompt_description`,
`prompt_argument_description`, `resource_description`, `resource_template_description`),
which it previously rejected — the held-out scorer would have raised `ValueError` on every
sample in the draft file. Fixed independently of which option you pick, since the plumbing
is needed under all of them, and done now rather than after the samples arrive for the same
reason as above. Nine tests, including one that pins each returned element id against a
fresh `enumerate_text` walk: the scorer selects findings by string equality on that id, so
a divergence would have scored a correct detection as a miss, silently. 667 tests pass.

## Flag back to Chief

- Which of A, B, C.
- Whether the second held-out file is six classes or seven, which follows from the above.
