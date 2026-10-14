# Phase 5: signed baselines — shipped as briefed, three answers flagged back

**From:** Jr.
**To:** Chief
**Date:** 2026-10-14
**Re:** `2026-10-14_from-chief_to-jr_phase5-signing-brief.md`. Doc's review came back with
no objections; Mac relayed it and said go.
**Status:** Implemented on `feature/phase-5-signing`. Ships as 0.7.0, after 0.6.0.

## What shipped

Section 3 as written, with nothing moved:

- **Envelope** exactly as specified: detached `<baseline>.json.sig`, `signature_version`
  "1", Ed25519 only, `key_id` = first 16 hex of SHA-256 over the raw public key, payload =
  `{server, label, manifest_version, surface_hash}`, message =
  `b"placard-signature-v1\n" + canonical_bytes(payload)` through the same canonical
  serializer the hashes use. `signed_at` is written and **not** signed — a test rewrites it
  and the signature still verifies, so no one can later build expiry on it by accident.
- **No hash moves.** The self-gating fixture is untouched; a test pins that sign + verify
  leave the manifest byte-identical.
- **Commands:** `keygen` (0600, refuses overwrite), `sign` (verifies first; refuses a
  group/other-readable key; `--label` binds the placard.toml name, defaulting to the
  declared server name), `verify --pubkey` (signature required and checked; exit 2).
  `verify` with a `.sig` and **no** key checks shape and payload binding only — that
  needs no cryptography, catches a moved or stale `.sig`, and says plainly that
  authentication needs a key. No `--sign` on `baseline`.
- **Config:** `[signing] required = false` default; `required = true` fails any baseline
  without a valid signature from a trusted key (bit **32**; mask now 63; the
  AGENTS.md "up to 31" sentence, the fail-on categories, and the Action outputs are all
  updated). The signature is checked against the **committed baseline**, the approval
  record — never the fresh scan. `required = true` with no trusted keys or without the
  extra is a usage error before any server is scanned.
- **Extra:** `pip install 'mcp-placard[signing]'`, `cryptography`, imported lazily;
  nothing for people who do not sign.
- **Docs:** `docs/SIGNING.md` opens with the honest claim — a holder of this key approved
  this surface for this server, and it helps only when the trusted keys are protected by
  a different control than the baselines — and reproduces section 4's limits as written
  (rollback, no revocation, not keyless, authenticates the baseline not the server). The
  threat model's "Manifest forgery" row is moved to covered (5) with those caveats; A5's
  regenerate-to-go-green is priced, not prevented, and says so. Key distribution options
  documented, CODEOWNERS recommended, no key management added.
- **Index demonstration:** all nine `index/manifests/*.json` signed with the Lanier
  release key, label-bound to their server ids; public key committed at
  `.placard/trusted_keys/lanier-release.pub`, key id **48e31e7790c21fca** published in the
  README; `build_index.py check` and a test verify the nine signatures. The private key
  was generated outside the repository and handed to Mac; it has never been in the repo
  or CI. A pleasant property worth noting: `reanalyze` cannot break these signatures —
  only the surface is signed — while a rescan that changes a surface invalidates its
  signature until the key holder re-signs, which is the point.

## Tamper tests — all fail, all fail closed

Pinned in `tests/test_signing.py` and `tests/test_check.py`:

| Case | Result |
| --- | --- |
| One character of the surface changed | `verify` exits **1** first (integrity before authenticity); with hashes recomputed, the payload binding breaks |
| `.sig` swapped between two servers | payload `server`/`surface_hash` mismatch |
| `key_id` rewritten | "not in the trusted keys" |
| `server` in the payload rewritten | payload mismatch |
| Signature truncated | does not verify |
| Unknown `algorithm` / `signature_version` | refused, never a fallback |
| `.sig` that is not JSON | refused at parse |
| Signature from an untrusted key | `check` bit 32 |
| Signature bound to another label | `check` bit 32 |
| No `.sig` under `required = true` | `check` bit 32 |
| No `.sig` under `required = false` | no change from today |
| Key file mode 0644 | `sign` refuses, nothing written |
| Private key bytes in any output | grepped across stdout, stderr and the `.sig`: absent |

Full suite green; ruff, mypy, no-`tools/call` pass; ratchet, fixture and hash tests
unchanged.

## The three questions you wanted flagged back, not decided

1. **`cryptography`, not PyNaCl.** Decisive fact: `cryptography` was **already in
   `requirements/action.txt`** — pyjwt pulls it transitively — so the hash-pinned Action
   install gains zero new packages; the lock now lists it as a direct requirement so it
   survives pyjwt ever dropping it. PyNaCl would add a new wheel set for no capability we
   use. (Found while doing this: `scripts/lock_action_requirements.sh` had backticks
   inside double-quoted sed text, which the shell executed as command substitution and
   blanked two header lines on any regeneration; rewritten with a quoted heredoc.)
2. **Canonical serializer stability across platforms: yes, with one artifact left to
   close.** The Oct 13 cross-machine report already proves `canonical_bytes` stable —
   byte-identical rendered manifests across macOS arm64 and Ubuntu x86_64 imply identical
   canonical bytes, and the signed payload is a four-string JSON object, the easy case.
   The committed index signatures are the cross-machine artifact: verifying them on
   cloudmac-1 (`placard verify index/manifests/fetch.json --pubkey
   .placard/trusted_keys/lanier-release.pub`) completes the proof with a signature made
   on one machine and verified on the other. Mac can run that in a minute; I did not
   claim it done.
   *(Closed same day: Mac ran it on cloudmac-1 — Ubuntu x86_64, py3.12, placard 0.7.0
   installed editable from the merged checkout with the signing extra. Result:
   `index/manifests/fetch.json: intact — surface_hash 8eb8d596…` and
   `index/manifests/fetch.json.sig: signature verifies under trusted key
   48e31e7790c21fca`, exit 0. The signature was produced on macOS arm64 (py3.14); the
   canonical serializer is proven stable across the same pair of machines as the
   Oct 13 report, now for the signed payload specifically.)*
3. **One thing in section 3 that did not fit the code as written, resolved in its
   spirit:** standalone `verify` cannot know which placard.toml label to expect — the
   manifest does not carry it. So `verify` binds `server`, `manifest_version` and
   `surface_hash` and takes the envelope's own `label` at face value, while `check`,
   which knows the configured name, additionally requires `label` to equal it (tested:
   a signature bound to another label sets bit 32). Everything else fit.

## Key custody, for the record

The release private key lives with Mac, outside the repository. If it is ever lost,
rotation is: `keygen`, replace `.placard/trusted_keys/lanier-release.pub`, re-sign the
nine manifests, commit past the separate control — exactly the §4 procedure.
