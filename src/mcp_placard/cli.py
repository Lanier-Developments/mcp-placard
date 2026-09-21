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

import sys
from pathlib import Path
from typing import Annotated

import typer

from . import MANIFEST_VERSION, __version__
from .analysis import analyze
from .classify.overrides import load_overrides
from .diff import diff_manifests
from .diff.engine import DEFAULT_CEILING
from .errors import (
    EXIT_OK,
    EXIT_USAGE,
    HashMismatchError,
    PlacardError,
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
from .transport import DEFAULT_TIMEOUT_SECONDS, TransportChoice, scan_target

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
            help="A JSON override allowlist. The only way a tier is ever downgraded.",
        ),
    ] = None,
) -> None:
    """Connect to a server, enumerate its surface, classify it, and emit a
    manifest to stdout.

    Enumeration only: initialize, then list tools, resources, resource templates, and
    prompts. No tool is ever invoked and no resource is ever read. Classification is
    a separate, pure pass over the enumerated surface — it reads the schema and
    declared annotations already captured, and never re-contacts the server.
    """
    raw = scan_target(target, transport=transport, timeout=timeout)
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
