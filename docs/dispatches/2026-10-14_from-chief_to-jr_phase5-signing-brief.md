# Phase 5 brief: signed baselines

**From:** Chief
**To:** Jr.
**Date:** 2026-10-14
**Re:** Manifest signing, the second half of the Phase 5 roadmap entry
**Status:** **Held for Doc's review.** Mac sends sections 2 to 5 to Doc first. Do not start until
Mac relays that the review is back. The ruleset 3.6 brief
(`2026-10-14_from-chief_to-jr_rulings-3.6-v3-index-fetch.md`) does not wait for this one.

Ships as its own branch and its own release, after 3.6: **0.7.0**.

---

## 1. What this defends, and what it does not

Today `verify` proves a manifest is internally consistent. It does not prove who approved it, and
it does not stop anyone who can commit from regenerating a baseline so that drift disappears. That
is adversary A5 and the "manifests are unsigned" limit in `docs/THREAT_MODEL.md`.

A signature proves **a holder of this key approved this surface for this server.** That is all.

It does not prove the server is honest. It does not stop a compromised key holder. It helps only
when the trusted keys are protected by a different control than the baselines are: a signing key
that lives with the approver, not the committer. Say this plainly in `docs/SIGNING.md`, and do not
describe signing as making the tool secure. The honest claim is that it raises the cost of silently
replacing an approval record from "anyone with commit access" to "anyone with commit access **and**
the approver's key".

## 2. Constraints that do not move

- **No hash moves.** `surface_hash`, `classification_hash`, `capabilities_hash` and
  `manifest_version` (2.2) are unchanged. The self-gating fixture stays byte-identical. A signature
  never lives inside the manifest.
- **Fail closed.** If signatures are required and anything about one is malformed, unknown, absent
  or unverifiable, that is a failure, never a skip.
- **No network at verify time, no runtime dependency for people who do not sign.**
- **Placard still never invokes a tool.** Signing does not change that.

## 3. Design

**Detached envelope.** `<baseline>.json` gets `<baseline>.json.sig` beside it.

```json
{
  "signature_version": "1",
  "algorithm": "ed25519",
  "key_id": "<first 16 hex of sha256 of the raw public key>",
  "payload": {
    "server": "<surface.server.name>",
    "label": "<the name in placard.toml>",
    "manifest_version": "2.2",
    "surface_hash": "<hex>"
  },
  "signed_at": "2026-10-14T17:00:00Z",
  "signature": "<base64>"
}
```

**What is signed: the surface, and only the surface.** The message is
`b"placard-signature-v1\n" + canonical_bytes(payload)`, using the canonical serializer the hashes
already use. The prefix is domain separation.

I am deliberately **not** signing `classification_hash` or `capabilities_hash`. Classification
depends on the ruleset, and `diff` re-analyses older manifests precisely so that a Placard upgrade
never produces findings on a server that did not change. A signature over classification would turn
every ruleset bump into a re-approval. Capabilities drift with the client SDK. The surface is what
the approver actually approved, and an attacker who rewrites a baseline's surface changes
`surface_hash`, which breaks the signature.

`server` and `label` are in the payload so a valid signature for one server cannot be moved onto
another. `signed_at` is informational and is **not** in the payload; do not build expiry on it.

**Algorithm.** Ed25519 only in 0.7.0. An unknown `algorithm` or `signature_version` is a failure.
Library: `cryptography`, as an optional extra, `pip install mcp-placard[signing]`. If you find a
reason to prefer PyNaCl, flag it back; do not decide it alone. The Action installs with
`--require-hashes` and `--no-deps`, so `cryptography` and its wheels must be added to
`requirements/action.txt` by `scripts/lock_action_requirements.sh`.

**Commands.**

| Command | Behaviour |
| --- | --- |
| `placard keygen --out <stem>` | Writes `<stem>.key` (mode 0600) and `<stem>.pub`. Refuses to overwrite. |
| `placard sign <manifest> --key <file>` | Verifies the manifest first, then writes the `.sig`. Refuses a key file readable by group or other. |
| `placard verify <manifest> [--pubkey <file>]` | As today, plus signature checking when a `.sig` exists or a key is given. |

No `--sign` flag on `baseline` in this phase. Approval stays a separate, deliberate act.

**Config.** In `placard.toml`:

```toml
[signing]
required = false            # default; existing users see no change
trusted_keys = [".placard/trusted_keys/lanier.pub"]
```

With `required = true`, `check` fails any server whose baseline has no valid signature from a
trusted key. `required = true` with the extra not installed is a configuration error, not a skip.

**Exit codes**, extending the per-command contract, with the doc tables updated in the same change:

- `verify`: **2** when a signature is present or required and is missing or invalid. 0, 1 and 64
  keep their meanings. A manifest that fails its hashes still exits 1 first.
- `check`: a new bit, **32**, unsigned or badly signed baseline. This moves the highest finding bit
  from 16 to 32, so the combined bitmask now reaches 63; 64 stays usage error. Update the sentence
  in AGENTS.md that says `report`'s 100-109 range "sits clear of the finding bits (up to 31)", and
  the `fail-on` categories and Action outputs to match.

**Key distribution is not solved by code, and the docs must say so.** If `trusted_keys` and the
baselines live in the same repository, someone who can commit can replace both. Signing only helps
where the key list is protected separately: CODEOWNERS on `.placard/trusted_keys/` and
`placard.toml`, branch protection, or key fingerprints passed as an Action input from a workflow
file under separate review. Document those three options and recommend the first. Do not add key
management.

**Index.** As a demonstration, sign `index/manifests/*.json` with a Lanier release key, publish the
fingerprint in the README and release notes, and add `build_index.py check` coverage for the
signatures. The private key is never in the repository and never in CI.

## 4. Stated limits, to go in `docs/SIGNING.md` and the threat model

- **Rollback.** A validly signed older baseline can be restored. A signature says "approved at some
  point", not "approved most recently". Git history and review are the mitigation.
- **Compromised key.** There is no revocation list in 0.7.0. Rotating means replacing
  `trusted_keys` and re-signing.
- **Not keyless.** No Sigstore, no transparency log, no OIDC identity. That is a later decision
  with its own cost: an online dependency and a heavier install. Record it as the next step, not as
  a gap in this one.
- **It authenticates the baseline, not the scanned server.** A scan of an impostor endpoint
  produces an accurate manifest of the impostor, signed or not.

## 5. Gates and tests

- The self-gating fixture and every existing hash test pass unchanged.
- A test that signing and verifying leave the manifest file byte-identical.
- Tamper tests: change one character of the surface; swap a `.sig` between two servers; change
  `key_id`; change `server`; truncate the signature; an unknown algorithm; a `.sig` that is not
  JSON. Each must fail, and each must fail closed under `required = true`.
- With `required = true` and no `.sig`: `check` sets bit 32. With `required = false` and no
  `.sig`: no change from today.
- A key file with mode 0644 is refused by `sign`.
- The private key never appears in any log, exception message, report or Action output. Test it by
  searching captured output for the key bytes.
- `ruff`, `mypy` and the no-`tools/call` check pass. Ruleset and classifier are untouched.

## Questions I want flagged back rather than decided

1. `cryptography` or PyNaCl, given the hash-pinned Action install.
2. Whether the canonical serializer is stable across the platforms the cross-machine report
   covered. Prove it with a signature made on one machine and verified on the other.
3. Anything in section 3 that does not fit the code as it is. You know the code; I am working from
   the tests and the docs.

## Report

Per the usual pattern: what shipped, the tamper-test results, the threat-model table with the
"Manifest forgery" row moved to Phase 5 as covered, and the limits in section 4 reproduced as
written in `docs/SIGNING.md`.
