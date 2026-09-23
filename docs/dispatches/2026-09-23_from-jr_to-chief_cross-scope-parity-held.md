# Held: `cross_scope` parity for prompt arguments — recorded, not implemented

**From:** Jr.
**To:** Chief
**Date:** 2026-09-23
**Re:** Your ruling on 3.3, and the parity question it raised
**Status:** Held until held-out v2 is scored. Recorded so it cannot be lost in the meantime.

## The question

3.3 gives prompt and resource elements evidence for `sensitive_target`. The same reasoning
— "a prompt's arguments are the closest thing it has to a schema" — transfers to
`own_param_names`, which `cross_scope` uses: a tool may name its own parameters, a prompt
currently may not name its own arguments. A prompt description referring to its own `repo`
argument is the same false-positive shape 3.3 just fixed, on the same barely-exercised
surfaces.

## Why it is held rather than shipped

**The two changes are not symmetric in risk.** Narrowing `sensitive_target` removes false
positives: the failure mode of getting it wrong is that something still flags. Widening
`own_param_names` suppresses findings — it fails open — and prompt argument names are
generic enough (`query`, `path`, `name`, `repo`) that populating them could mask a genuine
foreign reference. A rule that fails open is not the kind to ship on inference from a
neighbouring ruling.

**And the timing is the whole point.** Changing an exemption in the hours before a held-out
set is scored is precisely what the last three phases exist to refuse. Doc's benign file
contains a prompt description and a prompt-argument description, written with no view of
the implementation. That file is the evidence:

- **If either fires on a self-reference**, the parity gap is real, measured from outside,
  and it becomes 3.4.
- **If nothing fires**, it is recorded in `INJECTION.md` as a known gap with this reasoning,
  and it waits for a real case rather than a hypothetical one.

No rule changes between now and the run.
