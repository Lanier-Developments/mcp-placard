#!/usr/bin/env python3
"""Build the published blast-radius index (docs/INDEX.md) from pinned public MCP servers.

    python scripts/build_index.py scan      # install pins, scan each server, write manifests, render
    python scripts/build_index.py render    # re-render docs/INDEX.md from stored manifests (no network)
    python scripts/build_index.py check     # exit 1 if docs/INDEX.md is not what the manifests render
    python scripts/build_index.py reanalyze # re-analyse stored surfaces under the current ruleset, render

``scan`` is the only mode that installs or launches anything. It installs each
pinned package into a scratch directory (never the repository), then runs
``placard scan`` against the installed executable, so the scan itself needs no
network: Placard's launch isolation strips proxy settings and a ``uvx`` or
``npx`` launch would not resolve. It launches third-party code as the current
user, exactly as ``placard scan`` documents; run it somewhere you are content to
run those servers.

The index stores manifests under ``index/manifests/`` and renders from them, so
``render`` and ``check`` are deterministic and cheap enough for CI. A re-scan that
changes a ``surface_hash`` shows up as a diff of a committed file — and ``scan``
says so when it happens: a moved hash on an unchanged pin is reported, not
committed; read it before committing (adversary A5 in docs/THREAT_MODEL.md
applies here as it does to the self-gating fixture).

``reanalyze`` exists so the index cannot go stale silently (Chief's ruling of
2026-10-14, ratifying the index): it re-runs classification and injection
analysis over each **stored** surface under the current ruleset — offline, the
same re-analysis ``diff`` performs, so ``surface_hash`` cannot move — and
re-renders the page. A test fails whenever a stored manifest's
``ruleset_version`` is not this build's, so a ruleset bump is red until
``reanalyze`` has been run, the same shape as the fixture-staleness gate.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp_placard.manifest.models import Manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVERS_TOML = REPO_ROOT / "index" / "servers.toml"
MANIFEST_DIR = REPO_ROOT / "index" / "manifests"
INDEX_MD = REPO_ROOT / "docs" / "INDEX.md"

TIER_ORDER = ["R0", "R1", "R2", "R3", "R4", "R5"]
KIND_ORDER = ["read_sensitive", "egress", "write", "destructive", "code_exec"]


def load_servers() -> list[dict[str, Any]]:
    with SERVERS_TOML.open("rb") as handle:
        servers = tomllib.load(handle)["server"]
    ids = [server["id"] for server in servers]
    if len(ids) != len(set(ids)):
        raise SystemExit("index/servers.toml: duplicate server id")
    return list(servers)


# --------------------------------------------------------------------------- scan


def _install(servers: list[dict[str, Any]], cache: Path) -> dict[str, list[str]]:
    """Install every pin under *cache*; return the launch argv (before args) per id."""
    npm_prefix = cache / "npm"
    py_venv = cache / "py"
    launch: dict[str, list[str]] = {}
    npm_specs = [f"{s['package']}@{s['version']}" for s in servers if s["ecosystem"] == "npm"]
    py_specs = [f"{s['package']}=={s['version']}" for s in servers if s["ecosystem"] == "pypi"]
    if npm_specs:
        subprocess.run(
            [
                "npm",
                "install",
                "--silent",
                "--no-audit",
                "--no-fund",
                "--prefix",
                str(npm_prefix),
                *npm_specs,
            ],
            check=True,
        )
    if py_specs:
        # Separate environment: these servers pin mcp<2, which conflicts with Placard.
        subprocess.run(["uv", "venv", "-q", str(py_venv)], check=True)
        subprocess.run(
            ["uv", "pip", "install", "-q", "--python", str(py_venv / "bin" / "python"), *py_specs],
            check=True,
        )
    for server in servers:
        root = (
            npm_prefix / "node_modules" / ".bin"
            if server["ecosystem"] == "npm"
            else py_venv / "bin"
        )
        executable = root / server["bin"]
        if not executable.exists():
            raise SystemExit(f"{server['id']}: {executable} not found after install")
        launch[server["id"]] = [str(executable)]
    return launch


def scan(keep: bool) -> None:
    servers = load_servers()
    placard = shutil.which("placard") or str(Path(sys.executable).parent / "placard")
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    cache = Path(tempfile.mkdtemp(prefix="placard-index-"))
    try:
        launch = _install(servers, cache)
        sandbox = cache / "sandbox"
        sandbox.mkdir()
        # A repository for the git server, and an empty directory for the filesystem one.
        subprocess.run(["git", "init", "-q", str(sandbox)], check=True)
        failures: list[str] = []
        moved: list[str] = []
        for server in servers:
            args = [a.replace("{sandbox}", str(sandbox)) for a in server.get("args", [])]
            command = shlex.join(launch[server["id"]] + args)
            out = MANIFEST_DIR / f"{server['id']}.json"
            previous_hash = _stored_surface_hash(out)
            result = subprocess.run(
                [placard, "scan", command, "--timeout", "60", "--out", str(out)],
                capture_output=True,
                text=True,
                env={**os.environ},
            )
            status = "ok" if result.returncode == 0 else f"exit {result.returncode}"
            if (
                result.returncode == 0
                and previous_hash
                and _stored_surface_hash(out) != previous_hash
            ):
                moved.append(server["id"])
                status += "  surface_hash MOVED on an unchanged pin"
            print(f"{server['id']:<22} {status}")
            if result.returncode != 0:
                failures.append(server["id"])
                out.unlink(missing_ok=True)
                sys.stderr.write(result.stderr[-600:])
        if failures:
            raise SystemExit(f"scan failed for: {', '.join(failures)}")
        if moved:
            sys.stderr.write(
                f"surface_hash moved on an unchanged pin for: {', '.join(moved)}. That is a "
                "finding in its own right, to be reported, not committed: read each manifest "
                "diff before committing it (docs/THREAT_MODEL.md, adversary A5).\n"
            )
    finally:
        if not keep:
            shutil.rmtree(cache, ignore_errors=True)
    render()


def _stored_surface_hash(path: Path) -> str | None:
    """The committed manifest's ``surface_hash``, or None when no manifest is stored.
    Read leniently: a scan must not fail because the previous file is unreadable."""
    try:
        return str(json.loads(path.read_text(encoding="utf-8"))["surface_hash"])
    except (OSError, ValueError, KeyError):
        return None


# ---------------------------------------------------------------------- reanalyze


def reanalyze_manifests() -> None:
    """Re-run the analysis over every stored surface under the current ruleset.

    Offline by construction: the manifest carries the complete surface and analysis is
    static, so this is the same re-analysis ``diff`` performs on a stale side.
    ``surface_hash`` cannot move; ``ruleset_version``, the classification and the
    injection findings may. Run it after any ruleset change, then read the diff —
    judgement changes are reviewable events too, they are just Placard's rather than
    the server's."""
    from mcp_placard import RULESET_VERSION
    from mcp_placard.analysis import reanalyze
    from mcp_placard.manifest.io import load_manifest, write_manifest

    for server in load_servers():
        path = MANIFEST_DIR / f"{server['id']}.json"
        if not path.exists():
            raise SystemExit(f"missing {path.relative_to(REPO_ROOT)}; run `scan` first")
        manifest = load_manifest(path)
        before = manifest.ruleset_version
        write_manifest(reanalyze(manifest), path)
        note = "unchanged" if before == RULESET_VERSION else f"{before} -> {RULESET_VERSION}"
        print(f"{server['id']:<22} ruleset {note}")
    render()


# ------------------------------------------------------------------------- render


def _summarise(
    server: dict[str, Any],
) -> tuple[
    Manifest,
    collections.Counter[str],
    collections.Counter[str],
    list[Any],
    collections.Counter[str],
]:
    from mcp_placard.manifest.io import load_manifest

    path = MANIFEST_DIR / f"{server['id']}.json"
    if not path.exists():
        raise SystemExit(f"missing {path.relative_to(REPO_ROOT)}; run `scan` first")
    manifest = load_manifest(path)
    tiers = collections.Counter(entry.tier for entry in manifest.classification)
    kinds = collections.Counter(kind for entry in manifest.classification for kind in entry.kinds)
    chains = [f for f in manifest.findings if f.kind == "chain_exfil"]
    classes = collections.Counter(f.pattern_class for f in manifest.injection_findings)
    return manifest, tiers, kinds, chains, classes


def _safe(text: str) -> str:
    return "".join(ch for ch in text if ch.isalnum() or ch in "_-.")[:64]


def _histogram(counter: collections.Counter[str], order: list[str]) -> str:
    parts = [f"{key}:{counter[key]}" for key in order if counter.get(key)]
    return " ".join(parts) or "—"


def render_text() -> str:
    servers = load_servers()
    rows: list[str] = []
    notes: list[str] = []
    rulesets: set[str] = set()
    for server in servers:
        manifest, tiers, kinds, chains, classes = _summarise(server)
        rulesets.add(str(manifest.ruleset_version))
        top = max((t for t in tiers), key=TIER_ORDER.index, default="—")
        chain = "**yes**" if chains else "no"
        inj = ", ".join(f"{k} {v}" for k, v in sorted(classes.items())) or "0"
        rows.append(
            f"| `{server['id']}` | `{server['package']}` | {server['version']} "
            f"| {len(manifest.surface.tools)} | {_histogram(tiers, TIER_ORDER)} | {top} "
            f"| {_histogram(kinds, KIND_ORDER)} | {chain} | {inj} | `{manifest.surface_hash[:16]}` |"
        )
        for finding in chains:
            # Tool names come from the scanned server: keep only identifier characters so
            # a hostile name cannot inject markup into a published page.
            names = ", ".join(f"`{_safe(name)}`" for name in sorted(finding.tools))
            notes.append(
                f"- **{server['id']}** exposes a sensitive read and an egress path "
                f"({len(finding.tools)} tools involved): {names}."
            )
    if len(rulesets) != 1:
        raise SystemExit(f"manifests were produced under mixed rulesets: {sorted(rulesets)}")
    ruleset = rulesets.pop()
    lines = [
        "# Blast-radius index",
        "",
        "What the agent gains by connecting to each of these widely used public MCP servers, as",
        "Placard classifies it. Every row is a scan of an exact pinned version; the manifests are",
        "committed under [`index/manifests/`](../index/manifests/) and this page is rendered from",
        "them by `scripts/build_index.py`, so anyone can re-run the scan and compare `surface_hash`.",
        "",
        f"Ruleset **{ruleset}**. Tiers: R0 inert, R1 read-scoped, R2 read-sensitive, R3 write-scoped, R4 egress, R5 irreversible; see",
        "[`TAXONOMY.md`](TAXONOMY.md). Kinds: `read_sensitive`, `egress`, `write`, `destructive`,",
        "`code_exec`. Counts are tools, not risk scores.",
        "",
        "| Server | Package | Version | Tools | Tiers | Max | Kinds | `CHAIN_EXFIL` | Injection findings | `surface_hash` |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
    ]
    if notes:
        lines += ["## Exfiltration chains", "", *notes, ""]
    lines += [
        "## How to read this",
        "",
        "- **A tier is the worst thing a tool's declared surface lets an agent do**, inferred from its",
        "  schema, name, description and annotations, and reconciled with what the server claims about",
        "  itself. It is a statement about capability, not about whether the server is trustworthy.",
        "- **`CHAIN_EXFIL: yes` means a single server exposes both a sensitive read and an egress**",
        "  path. It is the property worth a second look before connecting that server to an agent that",
        "  also holds credentials.",
        "- **Injection findings are first-sight heuristics with known gaps.** A `0` here does not mean a",
        "  description is safe: on held-out v2 (the published measurement, ruleset 3.3) `override` and",
        "  `concealment` detected 1 of 7 each; ruleset 3.6 addressed the structural misses and its",
        "  generalisation is unmeasured until held-out v3 is scored. See",
        "  [Known limits](INJECTION.md#known-limits).",
        "- **Only the servers' own enumerations are scanned.** No tool was invoked. Servers that need",
        "  credentials or a hosted endpoint (GitHub, DeepWiki) are not in this index.",
        "",
        "## Reproducing",
        "",
        "```",
        "pip install -e '.[dev]'",
        "python scripts/build_index.py scan      # installs pins in a scratch dir, rewrites the manifests",
        "python scripts/build_index.py check     # fails if this page is not what the manifests render",
        "python scripts/build_index.py reanalyze # after a ruleset change: re-analyse stored surfaces",
        "```",
        "",
        "Scanning launches each pinned server as your user. A moved `surface_hash` on an unchanged pin",
        "is a finding in its own right; read the manifest diff before committing it.",
        "",
    ]
    return "\n".join(lines)


def render() -> None:
    INDEX_MD.write_text(render_text(), encoding="utf-8")
    print(f"wrote {INDEX_MD.relative_to(REPO_ROOT)}")


def check() -> int:
    expected = render_text()
    actual = INDEX_MD.read_text(encoding="utf-8") if INDEX_MD.exists() else ""
    if expected == actual:
        print("docs/INDEX.md is current")
        return 0
    sys.stderr.write("docs/INDEX.md is stale; run `python scripts/build_index.py render`\n")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    scan_parser = sub.add_parser("scan", help="install pins, scan, write manifests, render")
    scan_parser.add_argument("--keep", action="store_true", help="keep the scratch install dir")
    sub.add_parser("render", help="render docs/INDEX.md from stored manifests")
    sub.add_parser("check", help="exit 1 if docs/INDEX.md is stale")
    sub.add_parser(
        "reanalyze", help="re-analyse stored surfaces under the current ruleset, then render"
    )
    args = parser.parse_args()
    if args.mode == "scan":
        scan(args.keep)
        return 0
    if args.mode == "render":
        render()
        return 0
    if args.mode == "reanalyze":
        reanalyze_manifests()
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
