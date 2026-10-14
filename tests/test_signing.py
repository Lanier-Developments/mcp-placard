"""Phase 5: detached Ed25519 signatures over the surface — the §5 gates.

Every tamper case must fail, and must fail *closed*: under ``required = true`` a
signature problem is never a skip. The manifest file is byte-identical through
signing and verifying, the private key never appears in any output, and a key file
readable by group or other is refused.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import pytest

from mcp_placard.cli import main
from mcp_placard.errors import (
    EXIT_HASH_MISMATCH,
    EXIT_OK,
    EXIT_SIGNATURE_INVALID,
    EXIT_USAGE,
    SignatureError,
)
from mcp_placard.manifest import load_manifest, render_manifest
from mcp_placard.signing import (
    generate_keypair,
    key_fingerprint,
    load_public_key_raw,
    load_signature,
    sig_path,
    sign_manifest,
    verify_manifest_signature,
    write_signature,
)

from .conftest import make_manifest, tool_wire


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    def _run(*argv: str) -> int:
        monkeypatch.setattr("sys.argv", ["placard", *argv])
        return main()

    return _run


@pytest.fixture
def keypair(tmp_path: Path) -> tuple[Path, Path]:
    return generate_keypair(tmp_path / "approver")


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    manifest = make_manifest([tool_wire("read_file", description="Reads a file.")])
    path = tmp_path / "baseline.json"
    path.write_text(render_manifest(manifest), encoding="utf-8")
    return path


def _signed(manifest_path: Path, key: Path, label: str = "synthetic") -> Path:
    manifest = load_manifest(manifest_path)
    write_signature(sign_manifest(manifest, key_path=key, label=label), sig_path(manifest_path))
    return sig_path(manifest_path)


# ------------------------------------------------------------------ round trip


def test_sign_then_verify_round_trips_and_names_the_key(
    keypair: tuple[Path, Path], manifest_path: Path
) -> None:
    key, pub = keypair
    signature_file = _signed(manifest_path, key)
    manifest = load_manifest(manifest_path)
    envelope = load_signature(signature_file)
    raw = load_public_key_raw(pub)
    assert envelope.key_id == key_fingerprint(raw)
    assert (
        verify_manifest_signature(manifest, envelope, [raw], source="t", label="synthetic")
        == envelope.key_id
    )


def test_signing_and_verifying_leave_the_manifest_byte_identical(
    keypair: tuple[Path, Path], manifest_path: Path, run
) -> None:
    key, pub = keypair
    before = manifest_path.read_bytes()
    _signed(manifest_path, key)
    assert run("verify", str(manifest_path), "--pubkey", str(pub)) == EXIT_OK
    assert manifest_path.read_bytes() == before


def test_signed_at_is_informational_and_outside_the_signed_payload(
    keypair: tuple[Path, Path], manifest_path: Path
) -> None:
    """No expiry may ever be built on ``signed_at``: rewriting it does not break
    the signature, which proves it is not signed."""
    key, pub = keypair
    signature_file = _signed(manifest_path, key)
    document = json.loads(signature_file.read_text(encoding="utf-8"))
    document["signed_at"] = "1999-01-01T00:00:00Z"
    signature_file.write_text(json.dumps(document), encoding="utf-8")
    manifest = load_manifest(manifest_path)
    verify_manifest_signature(
        manifest, load_signature(signature_file), [load_public_key_raw(pub)], source="t"
    )


# ------------------------------------------------------------------ CLI codes


def test_verify_without_key_or_signature_is_unchanged(manifest_path: Path, run) -> None:
    assert run("verify", str(manifest_path)) == EXIT_OK


def test_verify_exits_two_when_a_key_is_given_and_no_signature_exists(
    keypair: tuple[Path, Path], manifest_path: Path, run
) -> None:
    _key, pub = keypair
    assert run("verify", str(manifest_path), "--pubkey", str(pub)) == EXIT_SIGNATURE_INVALID


def test_a_hash_failure_still_exits_one_first(
    keypair: tuple[Path, Path], manifest_path: Path, run
) -> None:
    """Integrity before authenticity: a tampered manifest is reported as tampered,
    not as badly signed."""
    key, pub = keypair
    _signed(manifest_path, key)
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["surface"]["tools"][0]["description"] = "Reads a file!"
    manifest_path.write_text(json.dumps(document), encoding="utf-8")
    assert run("verify", str(manifest_path), "--pubkey", str(pub)) == EXIT_HASH_MISMATCH


def test_sign_refuses_a_manifest_whose_hashes_do_not_match(
    keypair: tuple[Path, Path], manifest_path: Path, run
) -> None:
    key, _pub = keypair
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["surface"]["tools"][0]["description"] = "Reads a file!"
    manifest_path.write_text(json.dumps(document), encoding="utf-8")
    assert run("sign", str(manifest_path), "--key", str(key)) == EXIT_HASH_MISMATCH
    assert not sig_path(manifest_path).exists()


def test_keygen_refuses_to_overwrite(tmp_path: Path, run) -> None:
    stem = tmp_path / "release"
    assert run("keygen", "--out", str(stem)) == EXIT_OK
    assert run("keygen", "--out", str(stem)) == EXIT_USAGE


def test_a_group_readable_key_is_refused(
    keypair: tuple[Path, Path], manifest_path: Path, run
) -> None:
    key, _pub = keypair
    os.chmod(key, 0o644)
    assert run("sign", str(manifest_path), "--key", str(key)) == EXIT_USAGE
    assert not sig_path(manifest_path).exists()


# ---------------------------------------------------------------- tamper suite


def _tamper(signature_file: Path, **changes: object) -> None:
    document = json.loads(signature_file.read_text(encoding="utf-8"))
    for dotted, value in changes.items():
        target = document
        *parents, leaf = dotted.split("__")
        for part in parents:
            target = target[part]
        target[leaf] = value
    signature_file.write_text(json.dumps(document), encoding="utf-8")


def test_every_tamper_case_fails(
    keypair: tuple[Path, Path], manifest_path: Path, tmp_path: Path
) -> None:
    key, pub = keypair
    raw = load_public_key_raw(pub)
    manifest = load_manifest(manifest_path)

    def failing(**changes: object) -> str:
        signature_file = _signed(manifest_path, key)
        _tamper(signature_file, **changes)
        with pytest.raises(SignatureError) as caught:
            envelope = load_signature(signature_file)
            verify_manifest_signature(manifest, envelope, [raw], source="t")
        return str(caught.value)

    # A surface edit (with recomputed-looking hashes) breaks the payload binding.
    assert "surface_hash" in failing(payload__surface_hash="0" * 64)
    # A .sig moved from another server.
    assert "server" in failing(payload__server="someone-else")
    # A rewritten key id.
    assert "not in the trusted keys" in failing(key_id="deadbeefdeadbeef")
    # A truncated signature still decodes as base64 but cannot verify.
    truncated = base64.b64encode(b"short").decode("ascii")
    assert "does not verify" in failing(signature=truncated)
    # Unknown algorithm and unknown version are refusals, not fallbacks.
    assert "algorithm" in failing(algorithm="rsa-pss")
    assert "signature_version" in failing(signature_version="2")
    # A signature file that is not JSON at all.
    signature_file = _signed(manifest_path, key)
    signature_file.write_text("not json", encoding="utf-8")
    with pytest.raises(SignatureError, match="not a readable signature"):
        load_signature(signature_file)
    # One manifest's signature does not verify another manifest.
    other = make_manifest([tool_wire("write_file")])
    other_path = tmp_path / "other.json"
    other_path.write_text(render_manifest(other), encoding="utf-8")
    envelope = load_signature(_signed(manifest_path, key))
    with pytest.raises(SignatureError):
        verify_manifest_signature(other, envelope, [raw], source="t")


def test_a_wrong_label_breaks_the_binding(keypair: tuple[Path, Path], manifest_path: Path) -> None:
    """``label`` pins the signature to the placard.toml entry it approves, so a
    valid signature for one configured server cannot vouch for another that happens
    to declare the same server name."""
    key, pub = keypair
    envelope = load_signature(_signed(manifest_path, key, label="prod"))
    manifest = load_manifest(manifest_path)
    raw = load_public_key_raw(pub)
    verify_manifest_signature(manifest, envelope, [raw], source="t", label="prod")
    with pytest.raises(SignatureError, match="label"):
        verify_manifest_signature(manifest, envelope, [raw], source="t", label="staging")


# --------------------------------------------------------- the key never leaks


def test_private_key_bytes_never_appear_in_any_output(
    keypair: tuple[Path, Path],
    manifest_path: Path,
    run,
    capsys: pytest.CaptureFixture[str],
) -> None:
    key, pub = keypair
    key_body = "".join(
        line for line in key.read_text(encoding="utf-8").splitlines() if "PRIVATE KEY" not in line
    ).strip()
    assert key_body  # the sentinel exists
    assert run("sign", str(manifest_path), "--key", str(key)) == EXIT_OK
    assert run("verify", str(manifest_path), "--pubkey", str(pub)) == EXIT_OK
    run("verify", str(manifest_path))
    captured = capsys.readouterr()
    for stream in (captured.out, captured.err):
        assert key_body not in stream
    assert key_body not in sig_path(manifest_path).read_text(encoding="utf-8")
