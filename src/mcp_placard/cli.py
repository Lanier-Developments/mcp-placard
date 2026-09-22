"""Command entry points.

This is the only module in Placard that writes to a stream or sets an exit code.
Library code raises typed exceptions from :mod:`mcp_placard.errors` and returns
values; the translation from those into the exit-code table in AGENTS.md happens
here and nowhere else.

Stream discipline matters because ``scan`` is designed to be piped:

* **stdout** carries the manifest, and nothing else.
* **stderr** carries findings, diagnostics, and errors.

So ``placard scan "$SERVER" | jq .`` works, and ``placard diff old.json
new.json`` in CI shows a human why the build went red while the exit code tells the
runner what to do about it.

Exit codes are a per-command contract, pinned in AGENTS.md and in
``tests/test_exit_code_contract.py`` — Phase 4's GitHub Action consumes them, so a
code changing meaning for a command is a breaking change to that interface, not an
implementation detail. ``diff``'s status is a **bitmask of finding categories**, OR'd
together so no category can mask another; the same number can mean different things
for different commands — ``verify``'s ``1`` is an integrity failure, ``diff``'s ``1``
is the escalation bit — so read a code only in the context of the command that
produced it.

======  ============  =================================================================
Code    Command(s)    Condition
======  ============  =================================================================
``0``   all            success / no findings
``1``   ``diff``       bit 0 — escalation: tier increase, new tool at or above the
                       ceiling, capabilities changed
``2``   ``diff``       bit 1 — prompt change: description changed on an existing
                       element. Never silenceable by tier configuration
``4``   ``diff``       bit 2 — tool removed
``8``   ``diff``       bit 3 — injection finding new in this diff
``1``   ``verify``     a recorded hash does not match its content
``3``   ``scan``       server unreachable, or enumeration failed after handshake
``64``  all            usage or configuration error — exclusive, never OR'd
======  ============  =================================================================

``100``-``109`` are reserved for ``report`` (Phase 4, not yet implemented) and
claimed by no other command.
"""

from __future__ import annotations

import json
import os
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from . import MANIFEST_VERSION, __version__
from .analysis import analyze
from .check import CATEGORY_BITS, DEFAULT_FAIL_ON, dump_outputs, run_check, write_baselines
from .classify.overrides import load_overrides
from .config import FindingCategory, load_config, unpinned_target_warnings
from .diff import diff_manifests
from .diff.engine import DEFAULT_CEILING
from .errors import (
    EXIT_OK,
    EXIT_UNREACHABLE,
    EXIT_USAGE,
    HashMismatchError,
    PlacardError,
    UsageError,
)
from .inject.render import stderr_line
from .manifest import (
    Manifest,
    Tier,
    build_manifest,
    load_manifest,
    render_manifest,
    write_manifest,
)
from .manifest.verify import hash_mismatches
from .report import build_report
from .report.findings import decode_bits
from .transport import DEFAULT_TIMEOUT_SECONDS, TransportChoice, scan_target
from .transport.launch import isolated_launch

app = typer.Typer(
    name="placard",
    help=(
        "Enumerate what an MCP server exposes to an agent, hash it, and fail CI when "
        "it changes. Placard never invokes a tool."
    ),
    no_args_is_help=True,
    add_completion=False,
)


def _err(message: str) -> None:
    """Write one diagnostic line to stderr."""
    print(message, file=sys.stderr)


def _passthrough(names: list[str]) -> dict[str, str]:
    """Resolve ``--env`` names against this process's environment. A named variable
    that is not set is a usage error, not a silently different launch."""
    values: dict[str, str] = {}
    for name in names:
        if name not in os.environ:
            raise UsageError(f"--env names {name}, which is not set in the environment")
        values[name] = os.environ[name]
    return values


def _emit_manifest(manifest: Manifest, out: Path | None) -> None:
    """Write the manifest to stdout, and additionally to ``out`` when given.

    stdout is unconditional: a scan that wrote only to a file would break piping, and
    a scan that wrote only to stdout when ``--out`` was requested would silently
    discard the artifact the caller asked for. ``--out`` adds a destination, it does
    not replace one.
    """
    sys.stdout.write(render_manifest(manifest))
    if out is not None:
        write_manifest(manifest, out)
        _err(f"wrote manifest to {out}")


@app.command()
def scan(
    target: Annotated[
        str,
        typer.Argument(
            help="A stdio command line, or an http(s):// URL. Transport is inferred.",
        ),
    ],
    transport: Annotated[
        TransportChoice,
        typer.Option("--transport", help="Override the inferred transport."),
    ] = TransportChoice.AUTO,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Additionally write the manifest to this path."),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=0.1, help="Seconds allowed for connect and enumeration."),
    ] = DEFAULT_TIMEOUT_SECONDS,
    override: Annotated[
        Path | None,
        typer.Option(
            "--override",
            help="A JSON override allowlist, added to any from --config. The only way a "
            "tier is ever downgraded.",
        ),
    ] = None,
    env: Annotated[
        list[str] | None,
        typer.Option(
            "--env",
            help="Name of an environment variable a stdio server may receive at launch, "
            "read from this process's environment. Repeatable. Everything else is withheld.",
        ),
    ] = None,
) -> None:
    """Connect to a server, enumerate its surface, classify it, and emit a
    manifest to stdout.

    Enumeration only: initialize, then list tools, resources, resource templates, and
    prompts. No tool is ever invoked and no resource is ever read. Classification is
    a separate, pure pass over the enumerated surface — it reads the schema and
    declared annotations already captured, and never re-contacts the server.

    A stdio server is launched with an isolated environment: PATH, a temporary HOME,
    redirected package caches, and only the variables named with --env. It still runs
    as this user with this user's filesystem access — isolation is not a sandbox.
    """
    passthrough = _passthrough(env or [])
    with isolated_launch(passthrough) as launch_env:
        raw = scan_target(target, transport=transport, timeout=timeout, env=launch_env)
    manifest = build_manifest(raw)
    overrides = load_overrides(override) if override is not None else []
    manifest = analyze(manifest, overrides=overrides)
    for finding in manifest.injection_findings:
        _err(f"[injection] {stderr_line(finding)}")
    _emit_manifest(manifest, out)


@app.command(name="diff")
def diff_command(
    old: Annotated[Path, typer.Argument(help="The baseline manifest.")],
    new: Annotated[Path, typer.Argument(help="The manifest to compare against it.")],
    ceiling: Annotated[
        Tier,
        typer.Option(
            "--ceiling",
            help="A tool added at or above this tier escalates; below it, exit 0.",
        ),
    ] = DEFAULT_CEILING,
    escalate_schema_changes: Annotated[
        bool,
        typer.Option(
            "--escalate-schema-changes",
            help="Escalate on every input-schema change, even one that leaves the tier "
            "unchanged (the Phase 1 default, before a classifier existed to grade the delta).",
        ),
    ] = False,
) -> None:
    """Compare two manifests. The exit status is a bitmask of what was found.

    1 = escalation, 2 = description change (a prompt change), 4 = tool removed,
    8 = new injection finding — OR'd together, so an escalation alongside a prompt
    change exits 3 and `(( rc & 2 ))` answers "does this need a prompt review" on
    its own. 0 = nothing above the ceiling. Every finding is listed on stderr.
    """
    result = diff_manifests(
        load_manifest(old),
        load_manifest(new),
        ceiling=ceiling,
        escalate_schema_changes=escalate_schema_changes,
    )

    for note in result.notes:
        _err(f"note: {note}")
    for finding in result.findings:
        _err(f"[{finding.kind.value}] {finding.summary}")

    if not result.findings:
        if result.surface_hash_changed:
            _err(
                "no tool-level findings, but surface_hash changed — a resource, prompt, "
                "or server instruction differs between these manifests"
            )
        else:
            _err("no change")

    raise typer.Exit(code=result.exit_code)


@app.command()
def verify(
    manifest_path: Annotated[
        Path,
        typer.Argument(metavar="MANIFEST", help="The manifest to check."),
    ],
) -> None:
    """Recompute a manifest's hashes and report any that disagree with its content.

    Exits 0 when intact, 1 when any hash does not match. A mismatch means the file
    was edited after it was produced.
    """
    manifest = load_manifest(manifest_path)
    mismatches = hash_mismatches(manifest)
    if mismatches:
        raise HashMismatchError(mismatches)

    tools = len(manifest.surface.tools)
    _err(
        f"{manifest_path}: intact — manifest_version {manifest.manifest_version}, "
        f"surface_hash {manifest.surface_hash}, {tools} tool(s) verified"
    )


class ReportFormat(StrEnum):
    MARKDOWN = "markdown"
    SARIF = "sarif"


@app.command()
def report(
    manifest_path: Annotated[
        Path, typer.Argument(metavar="MANIFEST", help="The manifest to report on.")
    ],
    against: Annotated[
        Path | None,
        typer.Option(
            "--against",
            help="A baseline manifest. With it the report covers the diff; without, the "
            "full manifest. SARIF locations point at this file.",
        ),
    ] = None,
    fmt: Annotated[
        ReportFormat,
        typer.Option(
            "--format",
            help="markdown for humans and step summaries; sarif for GitHub code scanning.",
        ),
    ] = ReportFormat.MARKDOWN,
    server_name: Annotated[
        str | None,
        typer.Option(
            "--server-name",
            help="Name used in the report title and SARIF fingerprints. Defaults to the "
            "server's declared name.",
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="placard.toml, for the [report.level] mapping and ceiling."),
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", help="Also write the report here.")] = None,
) -> None:
    """Render a manifest, or a diff against a baseline, as Markdown or SARIF.

    Refuses a manifest (101) or a baseline (102) whose hashes do not match: a
    report of tampered data is worse than no report. Every scanned string is escaped
    before it is placed; SARIF messages are text only, never Markdown.
    """
    manifest = load_manifest(manifest_path)
    baseline = load_manifest(against) if against is not None else None
    levels = None
    ceiling: Tier = DEFAULT_CEILING
    if config is not None:
        loaded = load_config(config)
        levels = loaded.report.level
        ceiling = loaded.defaults.ceiling
    name = server_name or manifest.surface.server.name
    built = build_report(
        manifest,
        server=name,
        baseline=baseline,
        baseline_path=str(against) if against is not None else None,
        levels=levels,
        ceiling=ceiling,
    )
    text = built.markdown() if fmt is ReportFormat.MARKDOWN else built.sarif_text()
    sys.stdout.write(text)
    if out is not None:
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise UsageError(f"cannot write report {out}: {exc}") from exc
        _err(f"wrote report to {out}")


def _config_root(config: Path) -> Path:
    return config.resolve().parent


def _server_filter(server: list[str] | None) -> list[str] | None:
    return list(server) if server else None


@app.command()
def baseline(
    config: Annotated[Path, typer.Option("--config", help="placard.toml")] = Path("placard.toml"),
    server: Annotated[
        list[str] | None, typer.Option("--server", help="Only this server. Repeatable.")
    ] = None,
) -> None:
    """Scan every configured server and write its manifest to its baseline path.

    This is how a repository adopts Placard and how an approved change gets
    committed: the committed baseline is the approval record. Never run this in
    CI — approving a capability change is a human commit, by design.

    Exits 0 when every baseline was written, 3 when any server could not be
    scanned, 64 on a configuration error.
    """
    loaded = load_config(config)
    for warning in unpinned_target_warnings(loaded):
        _err(f"warning: {warning}")
    results = write_baselines(loaded, root=_config_root(config), only=_server_filter(server))
    failed = False
    for name, path, error in results:
        if error is None:
            _err(f"{name}: wrote {path}")
        else:
            failed = True
            _err(f"{name}: not written — {error}")
    if failed:
        raise typer.Exit(code=EXIT_UNREACHABLE)


@app.command()
def check(
    config: Annotated[Path, typer.Option("--config", help="placard.toml")] = Path("placard.toml"),
    server: Annotated[
        list[str] | None, typer.Option("--server", help="Only this server. Repeatable.")
    ] = None,
    sarif: Annotated[Path | None, typer.Option("--sarif", help="Write the SARIF log here.")] = None,
    summary: Annotated[
        Path | None, typer.Option("--summary", help="Write the Markdown summary here.")
    ] = None,
    outputs: Annotated[
        Path | None,
        typer.Option(
            "--outputs",
            help="Write a JSON file of the bitmask, one boolean per "
            "category, and the gate decision — what the GitHub Action turns into outputs.",
        ),
    ] = None,
    fail_on: Annotated[
        str,
        typer.Option(
            "--fail-on",
            help="Comma-separated categories that fail the gate; recorded in --outputs as "
            "'fail'. The exit status is always the full bitmask.",
        ),
    ] = ",".join(DEFAULT_FAIL_ON),
) -> None:
    """Scan every configured server, diff each against its baseline, and exit with
    the OR of every finding bit — plus 16 when a server could not be scanned.

    A server with no baseline yet is reported, not failed. The exit status is the
    contract; --fail-on only decides the 'fail' value in --outputs, which is what
    the GitHub Action gates on.
    """
    loaded = load_config(config)
    for warning in unpinned_target_warnings(loaded):
        _err(f"warning: {warning}")
    categories = _parse_fail_on(fail_on)
    result = run_check(loaded, root=_config_root(config), only=_server_filter(server))

    for outcome in result.outcomes:
        if not outcome.scanned:
            _err(f"[incomplete] {outcome.name}: {outcome.error}")
        elif not outcome.baseline_present:
            _err(f"[no-baseline] {outcome.name}: reported, not failed ({outcome.baseline_path})")
        else:
            bits = ", ".join(decode_bits(outcome.status)) or "no change"
            _err(f"[{outcome.status}] {outcome.name}: {bits}")
            if outcome.report is not None and outcome.report.diff is not None:
                for note in outcome.report.diff.notes:
                    _err(f"note: {note}")
                for finding in outcome.report.diff.findings:
                    _err(f"[{finding.kind.value}] {finding.summary}")

    if summary is not None:
        _write_text(summary, result.markdown())
    if sarif is not None:
        _write_text(sarif, json.dumps(result.sarif(), indent=2, sort_keys=True) + "\n")
    if outputs is not None:
        dump_outputs(result, categories, outputs)
    raise typer.Exit(code=result.status)


def _parse_fail_on(value: str) -> list[FindingCategory]:
    categories: list[FindingCategory] = []
    for raw in value.split(","):
        name = raw.strip()
        if not name:
            continue
        if name not in CATEGORY_BITS:
            raise UsageError(
                f"--fail-on: unknown category {name!r}; expected any of " + ", ".join(CATEGORY_BITS)
            )
        categories.append(name)
    return categories


def _write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"cannot write {path}: {exc}") from exc
    _err(f"wrote {path}")


@app.command()
def version() -> None:
    """Print the Placard version and the manifest version it writes."""
    print(f"placard {__version__} (manifest_version {MANIFEST_VERSION})")


def main() -> int:
    """Console-script entry point: run the app and map typed errors to exit codes.

    ``standalone_mode=False`` stops Click from calling ``sys.exit`` itself, so every
    outcome funnels through this one translation table. A ``PlacardError``
    carries its own ``exit_code``, so adding an error type does not mean editing a
    chain of ``isinstance`` checks here.

    Anything that is *not* a ``PlacardError`` is a bug, not a documented
    condition, and is allowed to propagate with its traceback intact rather than
    being flattened into a plausible-looking exit code.

    Typer vendors its own copy of Click, so argument-parsing failures arrive as
    ``typer.TyperException`` rather than as ``click.ClickException``. Catching the
    vendored base is what keeps a mistyped command landing on exit code 10 instead
    of on a traceback.
    """
    try:
        result = app(standalone_mode=False)
    except HashMismatchError as exc:
        for mismatch in exc.mismatches:
            _err(f"[hash_mismatch] {mismatch}")
        return exc.exit_code
    except PlacardError as exc:
        _err(f"error: {exc}")
        return exc.exit_code
    except typer.Exit as exc:
        return exc.exit_code
    except typer.Abort:
        _err("aborted")
        return EXIT_USAGE
    except typer.TyperException as exc:
        show = getattr(exc, "show", None)
        if callable(show):
            show()
        else:  # pragma: no cover - every parsing error in Typer carries show()
            _err(f"error: {exc}")
        return EXIT_USAGE
    return result if isinstance(result, int) else EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
