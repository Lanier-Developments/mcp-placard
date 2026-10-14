# Signed baselines

A signature proves **a holder of this key approved this surface for this server.**
That is all it proves.

It does not prove the server is honest: a scan of an impostor endpoint produces an
accurate manifest of the impostor, and signing it authenticates the approval, not the
server. It does not stop a compromised key holder. And it helps only when the trusted
keys are protected by a **different control** than the baselines are — a signing key
that lives with the approver, not the committer. Signing does not make Placard, or
your configuration, "secure". The honest claim is narrower: it raises the cost of
silently replacing an approval record from *anyone with commit access* to *anyone with
commit access **and** the approver's key*.

That is adversary A5's regenerate-to-go-green move (`docs/THREAT_MODEL.md`), priced
rather than prevented.

## What is signed

A detached envelope, `<baseline>.json.sig` beside `<baseline>.json`:

```json
{
  "signature_version": "1",
  "algorithm": "ed25519",
  "key_id": "<first 16 hex of sha256 of the raw public key>",
  "payload": {
    "server": "<the manifest's declared server name>",
    "label": "<the name in placard.toml>",
    "manifest_version": "2.2",
    "surface_hash": "<hex>"
  },
  "signed_at": "2026-10-14T17:00:00Z",
  "signature": "<base64>"
}
```

The message is `b"placard-signature-v1\n" + canonical_bytes(payload)` — the same
canonical serializer every hash already uses, with a domain-separation prefix.

**The surface, and only the surface, is signed.** `classification_hash` is
deliberately left out: classification depends on the ruleset, and `diff` re-analyses
older manifests precisely so a Placard upgrade never produces findings on a server
that did not change — a signature over classification would turn every ruleset bump
into a re-approval. `capabilities_hash` drifts with the client SDK. The surface is
what the approver actually approved, and an attacker who rewrites a baseline's
surface changes `surface_hash`, which breaks the signature. `server` and `label` are
in the payload so a valid signature for one server cannot be moved onto another.
`signed_at` is informational and is **not** in the payload; nothing may build expiry
on it.

Nothing about the manifest or its hashes changes: a signature never lives inside the
manifest, and signing then verifying leaves the manifest byte-identical.

## Commands

Signing needs the optional extra: `pip install 'mcp-placard[signing]'` (Ed25519 via
`cryptography`; an unknown `algorithm` or `signature_version` is a failure, never a
fallback). There is no runtime dependency for people who do not sign, and no network
at verify time.

| Command | Behaviour |
| --- | --- |
| `placard keygen --out <stem>` | Writes `<stem>.key` (mode 0600) and `<stem>.pub`. Refuses to overwrite. |
| `placard sign <manifest> --key <file> [--label <name>]` | Verifies the manifest first, then writes the `.sig`. Refuses a key file readable by group or other. |
| `placard verify <manifest> [--pubkey <file>]` | As today, plus signature checking when a `.sig` exists or a key is given. |

There is no `--sign` flag on `baseline`: approval stays a separate, deliberate act.

## Configuration and exit codes

```toml
[signing]
required = false            # default; existing users see no change
trusted_keys = [".placard/trusted_keys/lanier.pub"]
```

With `required = true`, `check` fails any server whose baseline has no valid
signature from a trusted key — **fail closed**: missing, malformed, unverifiable,
unknown key, and wrong label are all the same failure. `required = true` with the
extra not installed, or with no trusted keys listed, is a configuration error (64),
not a skip.

- `verify` exits **2** when a signature is present or required and is missing or
  invalid. 0, 1 and 64 keep their meanings; a manifest that fails its hashes still
  exits 1 first.
- `check` sets a new bit, **32** (`signature`), taking the combined bitmask to 63.
  The bit is in the default `fail-on` set, which changes nothing while it can never
  be set. The Action exposes a `signature` output like every other category.

## Key distribution is not solved by code

If `trusted_keys` and the baselines live in the same repository under the same
review, someone who can commit can replace both, and signing bought nothing. The key
list must be protected separately. Three options, in order of preference:

1. **CODEOWNERS** on `.placard/trusted_keys/` and `placard.toml`, with branch
   protection requiring that review — the key list then changes only past a named
   human. **Recommended.**
2. Branch protection rules that gate the key paths specifically.
3. Key fingerprints passed as an Action input from a workflow file under separate
   review, so the trusted set is pinned outside the scanned repository's main tree.

Placard adds no key management beyond `keygen`. Rotation is: replace the entry in
`trusted_keys`, re-sign the baselines, commit both past the same separate control.

## Stated limits

- **Rollback.** A validly signed older baseline can be restored and verifies. A
  signature says "approved at some point", not "approved most recently". Git history
  and review are the mitigation.
- **Compromised key.** There is no revocation list in 0.7.0. Rotating means replacing
  `trusted_keys` and re-signing.
- **Not keyless.** No Sigstore, no transparency log, no OIDC identity. That is a
  later decision with its own cost — an online dependency and a heavier install —
  recorded as the next step, not as a gap in this one.
- **It authenticates the baseline, not the scanned server.** A scan of an impostor
  endpoint produces an accurate manifest of the impostor, signed or not.

## The index demonstration

The nine manifests under `index/manifests/` are signed with the Lanier release key;
the public key is committed at `.placard/trusted_keys/lanier-release.pub` and its
fingerprint is published in the README and in release notes. The private key is never
in the repository and never in CI. `scripts/build_index.py check` verifies the nine
signatures along with the page.
