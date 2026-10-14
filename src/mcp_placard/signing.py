"""Detached Ed25519 signatures over a manifest's surface (Phase 5).

A signature proves **a holder of this key approved this surface for this server** —
that is all. It does not prove the server is honest, and it does not stop a
compromised key holder. It helps only when the trusted keys are protected by a
different control than the baselines are; ``docs/SIGNING.md`` says so plainly, with
the stated limits (rollback, no revocation, no transparency log).

The constraints that do not move (Phase 5 brief, 2026-10-14):

* **No hash moves.** ``surface_hash``, ``classification_hash``, ``capabilities_hash``
  and ``manifest_version`` are untouched; a signature never lives inside the
  manifest. The envelope is a separate ``<baseline>.json.sig`` file beside it.
* **What is signed is the surface, and only the surface.** The message is
  ``b"placard-signature-v1\\n" + canonical_bytes(payload)`` where the payload is
  ``{server, label, manifest_version, surface_hash}``, canonicalised by the same
  serializer every hash already uses. ``classification_hash`` is deliberately not
  signed: classification depends on the ruleset, and ``diff`` re-analyses older
  manifests precisely so a Placard upgrade never produces findings on a server that
  did not change — a signature over classification would turn every ruleset bump
  into a re-approval. ``capabilities_hash`` drifts with the client SDK. An attacker
  who rewrites a baseline's surface changes ``surface_hash``, which breaks the
  signature; ``server`` and ``label`` are in the payload so a valid signature for
  one server cannot be moved onto another.
* **Fail closed.** When signatures are required, anything malformed, unknown,
  absent or unverifiable is a failure, never a skip.
* **No network at verify time, and no runtime dependency for people who do not
  sign.** ``cryptography`` is an optional extra (``pip install mcp-placard[signing]``)
  imported lazily; every entry point raises a configuration error, not an
  ImportError, when it is missing.

``signed_at`` is informational and is **not** part of the signed payload; nothing
may build expiry on it.
"""

from __future__ import annotations

import base64
import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import SignatureError, SigningUnavailableError, UsageError
from .manifest.canonical import canonical_bytes, render_json
from .manifest.models import Manifest

__all__ = [
    "ALGORITHM",
    "DOMAIN_PREFIX",
    "SIGNATURE_VERSION",
    "Envelope",
    "generate_keypair",
    "key_fingerprint",
    "load_public_key_raw",
    "load_signature",
    "sig_path",
    "sign_manifest",
    "verify_manifest_signature",
    "write_signature",
]

SIGNATURE_VERSION = "1"
ALGORITHM = "ed25519"
DOMAIN_PREFIX = b"placard-signature-v1\n"
"""Domain separation: a Placard signature verifies nothing but a Placard payload."""

_ENVELOPE_FIELDS = frozenset(
    {"signature_version", "algorithm", "key_id", "payload", "signed_at", "signature"}
)
_PAYLOAD_FIELDS = frozenset({"server", "label", "manifest_version", "surface_hash"})


def _crypto() -> Any:
    """The ``cryptography`` Ed25519 primitives, imported only when signing is used.

    ``required = true`` with the extra not installed is a configuration error, not a
    skip — hence :class:`SigningUnavailableError` is a usage error, exit 64.
    """
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:  # pragma: no cover - exercised via the error path test
        raise SigningUnavailableError(
            "signature support needs the optional extra: pip install 'mcp-placard[signing]'"
        ) from exc
    return ed25519, serialization


def key_fingerprint(raw_public_key: bytes) -> str:
    """The key id: the first 16 hex characters of SHA-256 over the raw public key."""
    import hashlib

    return hashlib.sha256(raw_public_key).hexdigest()[:16]


def _refuse_lax_permissions(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise UsageError(
            f"{path}: private key is readable by group or other (mode {mode:03o}); "
            "chmod 600 it — a shared key signs nothing"
        )


def generate_keypair(stem: Path) -> tuple[Path, Path]:
    """Write ``<stem>.key`` (mode 0600) and ``<stem>.pub``. Refuses to overwrite:
    silently replacing a signing key is exactly the event signing exists to make
    loud."""
    ed25519, serialization = _crypto()
    key_path = stem.with_suffix(stem.suffix + ".key")
    pub_path = stem.with_suffix(stem.suffix + ".pub")
    for existing in (key_path, pub_path):
        if existing.exists():
            raise UsageError(f"{existing} already exists; refusing to overwrite a key")
    private = ed25519.Ed25519PrivateKey.generate()
    key_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(key_pem)
    pub_path.write_bytes(pub_pem)
    return key_path, pub_path


def _load_private_key(path: Path) -> Any:
    ed25519, serialization = _crypto()
    _refuse_lax_permissions(path)
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (ValueError, OSError) as exc:
        raise UsageError(f"{path}: not a readable PEM private key: {exc}") from exc
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise UsageError(f"{path}: not an Ed25519 key; 0.7.0 signs with Ed25519 only")
    return key


def load_public_key_raw(path: Path) -> bytes:
    """The raw 32 public-key bytes from a PEM ``.pub`` file."""
    ed25519, serialization = _crypto()
    try:
        key = serialization.load_pem_public_key(path.read_bytes())
    except (ValueError, OSError) as exc:
        raise UsageError(f"{path}: not a readable PEM public key: {exc}") from exc
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise UsageError(f"{path}: not an Ed25519 key; 0.7.0 verifies Ed25519 only")
    raw: bytes = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return raw


def sig_path(manifest_path: Path) -> Path:
    """``<baseline>.json`` gets ``<baseline>.json.sig`` beside it."""
    return manifest_path.with_suffix(manifest_path.suffix + ".sig")


def _payload(manifest: Manifest, label: str) -> dict[str, str]:
    return {
        "server": manifest.surface.server.name,
        "label": label,
        "manifest_version": manifest.manifest_version,
        "surface_hash": manifest.surface_hash,
    }


def _message(payload: dict[str, str]) -> bytes:
    return DOMAIN_PREFIX + canonical_bytes(payload)


def sign_manifest(manifest: Manifest, *, key_path: Path, label: str) -> dict[str, Any]:
    """Build the signature envelope for a manifest's surface.

    The caller verifies the manifest first (``sign`` in the CLI does); signing a
    manifest whose hashes do not match would authenticate tampered data.
    """
    _ed25519, serialization = _crypto()
    private = _load_private_key(key_path)
    raw_public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    payload = _payload(manifest, label)
    return {
        "signature_version": SIGNATURE_VERSION,
        "algorithm": ALGORITHM,
        "key_id": key_fingerprint(raw_public),
        "payload": payload,
        "signed_at": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "signature": base64.b64encode(private.sign(_message(payload))).decode("ascii"),
    }


def write_signature(envelope: dict[str, Any], path: Path) -> None:
    path.write_text(render_json(envelope), encoding="utf-8")


@dataclass(frozen=True)
class Envelope:
    """A parsed, shape-checked signature file. Parsing does not authenticate."""

    key_id: str
    payload: dict[str, str]
    signature: bytes
    signed_at: str


def load_signature(path: Path) -> Envelope:
    """Parse a ``.sig`` file, failing closed on anything unexpected: bad JSON, an
    unknown ``signature_version`` or ``algorithm``, missing or extra fields, or a
    signature that is not base64."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SignatureError(f"{path}: not a readable signature file: {exc}") from exc
    if not isinstance(document, dict) or set(document) != _ENVELOPE_FIELDS:
        raise SignatureError(f"{path}: signature envelope fields are wrong")
    if document["signature_version"] != SIGNATURE_VERSION:
        raise SignatureError(f"{path}: unknown signature_version {document['signature_version']!r}")
    if document["algorithm"] != ALGORITHM:
        raise SignatureError(f"{path}: unknown algorithm {document['algorithm']!r}")
    payload = document["payload"]
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_FIELDS:
        raise SignatureError(f"{path}: signature payload fields are wrong")
    if not all(isinstance(value, str) for value in payload.values()):
        raise SignatureError(f"{path}: signature payload values must be strings")
    try:
        signature = base64.b64decode(document["signature"], validate=True)
    except (TypeError, ValueError) as exc:
        raise SignatureError(f"{path}: signature is not valid base64") from exc
    return Envelope(
        key_id=str(document["key_id"]),
        payload=dict(payload),
        signature=signature,
        signed_at=str(document["signed_at"]),
    )


def payload_binds(manifest: Manifest, envelope: Envelope, *, source: str) -> None:
    """Check the envelope's payload names this manifest — no cryptography involved,
    so a reader without the extra still catches a ``.sig`` moved between servers or a
    baseline whose surface changed after signing. Binding is not authenticity: only
    :func:`verify_manifest_signature` proves who signed."""
    expected = _payload(manifest, envelope.payload["label"])
    for field in sorted(_PAYLOAD_FIELDS):
        if envelope.payload.get(field) != expected[field]:
            raise SignatureError(
                f"{source}: signature payload {field} is "
                f"{envelope.payload.get(field)!r}, manifest says {expected[field]!r}"
            )


def verify_manifest_signature(
    manifest: Manifest,
    envelope: Envelope,
    trusted_raw_keys: list[bytes],
    *,
    source: str,
    label: str | None = None,
) -> str:
    """Authenticate *envelope* against *manifest* under the trusted keys.

    Checks, in order and all required: the payload binds this manifest (``server``,
    ``manifest_version``, ``surface_hash``, and ``label`` when the caller knows which
    label it expects); the ``key_id`` names a trusted key; and that key verifies the
    signature over the domain-separated canonical payload. Returns the key id that
    verified. Every failure raises :class:`SignatureError` — fail closed.
    """
    ed25519, _serialization = _crypto()
    expected = _payload(manifest, label if label is not None else envelope.payload["label"])
    if envelope.payload != expected:
        for field in sorted(_PAYLOAD_FIELDS):
            if envelope.payload.get(field) != expected[field]:
                raise SignatureError(
                    f"{source}: signature payload {field} is "
                    f"{envelope.payload.get(field)!r}, manifest says {expected[field]!r}"
                )
    by_id = {key_fingerprint(raw): raw for raw in trusted_raw_keys}
    raw = by_id.get(envelope.key_id)
    if raw is None:
        raise SignatureError(f"{source}: key_id {envelope.key_id} is not in the trusted keys")
    public = ed25519.Ed25519PublicKey.from_public_bytes(raw)
    try:
        public.verify(envelope.signature, _message(envelope.payload))
    except Exception as exc:
        raise SignatureError(f"{source}: signature does not verify") from exc
    return envelope.key_id
