# Report: held-out v2, scored once under ruleset 3.3

**From:** Jr.
**To:** Chief
**Date:** 2026-09-23
**Re:** The one-shot scoring run
**Status:** Reported as-is. `baseline.json` untouched. Six benign disputes below, for you.

## The headline

| Class | v1 (3.0) | v2 (3.3) | |
| --- | --- | --- | --- |
| exfil_sink | 5/5 100% | 7/7 100% | held |
| hidden_content | 5/5 100% | 7/7 100% | held |
| markup_smuggling | 3/5 60% | 7/7 100% | **generalised** |
| cross_scope | 3/5 60% | 5/7 71% | improved |
| sensitive_target | 5/5 100% | 5/7 71% | dropped |
| override | 0/5 0% | 1/7 14% | **did not generalise** |
| concealment | 3/5 60% | 1/7 14% | **regressed** |
| **overall** | **24/35 68%** | **33/49 67%** | flat |

**The overall number is flat and the overall number is misleading.** 67% against 68% reads
as "no change" and is the average of two large movements in opposite directions. The
per-class column is the result.

3.1 rewrote four classes from phrase matching to structural rules. Measured on vocabulary
its author never saw:

- **`markup_smuggling` generalised completely** — 60% to 100%. The paired-tag rule is
  structural in the way we hoped: it does not care what the tag is called.
- **`cross_scope` generalised** — 60% to 71%, and that is with the two misses below.
- **`override` did not.** 0/5 on v1 was the worst result in that measurement and the reason
  3.1 exists. It is now 1/7, and 0/3 on the surfaces file. The hierarchy-referent plus
  invalidator rule is still matching a vocabulary rather than a structure — it just matches
  a larger one.
- **`concealment` regressed** — 60% to 14%. The v1 phrase rules did better on v1's
  vocabulary than the 3.1 structural rule does on Doc's new one. That is the sharpest
  finding here, and it inverts the assumption behind the whole phase.

`sensitive_target` dropping from 100% to 71% is two misses; it was not a class 3.1 touched
and nothing in 3.3 changes tool-surface behaviour.

## The surfaces file — 14/21, 66%

| Class | detected |
| --- | --- |
| exfil_sink | 3/3 |
| hidden_content | 3/3 |
| markup_smuggling | 3/3 |
| cross_scope | 2/3 |
| sensitive_target | 2/3 |
| concealment | 1/3 |
| override | 0/3 |
| **overall** | **14/21 66%** |

First coverage, no v1 counterpart. **66% against the main file's 67% is the useful fact
here:** the same classes fail in the same proportions on prompt and resource surfaces as on
tool surfaces. The weakness is in the rules, not in the new plumbing — if the 3.3 evidence
derivation or the corpus builder were wrong, this number would be visibly worse than the
main one, and it is not.

## The benign file — 6 of 15 fired, and three of them are our fault

This is the part that matters. Diagnosed individually, by rebuilding each string in the
server context Doc assumed. **Three are artefacts of how the corpus builds a sample, not
findings about the rules**, and one of those three is mine from yesterday.

### Artefacts — the sample could not express the server it described

**`hv2b-1` — my fault, and it defeats exactly what 3.3 was built for.** Doc wrote a
resource that legitimately *is* the SSH config. The builder places every resource at a
fixed `file:///corpus/sample.txt`, so under 3.3 the path family is `corpus`/`sample.txt`
and a mention of `~/.ssh` is out of scope. Rebuilt at `file:///home/user/.ssh/config` it
does not fire. I chose fixed URIs so an author would have one less thing to get wrong; for
resources the URI *is* the evidence, so that choice removed the author's ability to state
the case. Fix is a `uri` field on the sample, and it should land before any future
resource sample is written.

**`hv2b-3` and `hv2b-4` — the sample format has no way to declare sibling tools.** Both
reference tools on their own server (`build_status`, `rollback_release`,
`update_file_contents`). The builder constructs a one-tool server, so every sibling is
foreign and `cross_scope` fires correctly on a server that does not exist. Declare the
siblings and both clear. This limitation predates my extension — malicious samples never
needed sibling tools, since `cross_scope` wants foreign references — and Doc's benign file
is the first thing to ask for it.

None of these three is evidence about the rules, and none should reach the ratchet.

### Real, and worth your ruling

**`hv2b-2` — the path and credential tests are asymmetric, and Doc found it.**
`rotate_aws_keys` takes `profile_name` and `credentials_file_path` and mentions `~/.aws`.
`handles_credentials` is a **substring** test, so `credentials_file_path` matches. But
`handles_paths` is **exact membership** in `PATH_HANDLING_FIELDS`, and
`credentials_file_path` is not in that set — so a parameter that is obviously a file path
establishes credential handling and not path handling, and the path mention fires. A
genuine false positive on a plausible real tool, in the tool rule itself, unrelated to 3.3.
The fix is to make the path test token-aware — split on `_`/`-` and test tokens — which is
what the credential test effectively already does.

**`hv2b-5` and `hv2b-6` — legitimate documentation URLs.** `https://spec.openapis.org/...`
in a tool description and `https://kubernetes.io/docs/...` in a prompt description, both
`exfil_sink.url`. The scoping rule exempts documentation and loopback *hosts* —
`example.com`, `localhost`, RFC 2606 — and a real documentation URL on a real host is not
covered. Our 388-string benign corpus contains no such case, which is why this has never
surfaced; real servers cite specs and docs constantly. Two samples, one shape, and I read
this as the most likely false positive to hit a real user of the four real ones.

I have not touched a rule, a pattern, or `baseline.json`.

## The held `cross_scope` parity question

Your condition was: if a prompt description or prompt-argument description fires on a
self-reference, it becomes 3.4; if nothing fires, record it as a known gap.

**Nothing fired on that shape.** The benign file's one prompt description and one
prompt-argument description produced a single finding between them, and it was
`exfil_sink.url`, not `cross_scope`. So there is no evidence for the parity fix and none
against it — the case simply did not arise. Recorded in `INJECTION.md` as a known gap with
the reasoning, per your ruling, and it waits for a real case.

Note the adjacent evidence is muddied: `hv2b-3` and `hv2b-4` *are* self-reference
`cross_scope` fires of the same family, on tool surfaces, and both are the sibling-tool
artefact rather than analyser behaviour. They do not bear on the parity question either
way.

## What I am asking for

1. **Rulings on the three real false positives** — the path/credential asymmetry, and the
   documentation-URL shape (two samples).
2. **Whether the three artefacts are struck from the file** or kept with the corpus fixed
   (a `uri` field, and sibling-tool declarations) and re-run. Re-running changes what those
   three samples measure; it does not touch the 33/49 or the 14/21, which are final.
3. **Whether `override` and `concealment` open a 3.4**, or whether the honest conclusion is
   that deterministic patterns have found their ceiling on those two classes and the
   number stands as the published limitation.

`baseline.json` moves on your word, not on this report.
