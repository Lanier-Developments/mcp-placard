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
implementation detail. They are **categories, not a severity ladder**: ``2`` is a
different review path from ``1``, not a worse outcome than it. The same number can
mean different things for different commands — ``verify``'s ``1`` is an integrity
failure, ``diff``'s ``1`` is a risk escalation — so read a code only in the context
of the command that produced it.

======  ============  =================================================================
Code    Command(s)    Condition
======  ============  =================================================================
``0``   all            success / no change
``1``   ``diff``       escalation — new tool, schema change, or capabilities change
``1``   ``verify``     a recorded hash does not match its content
``2``   ``diff``       description change on an existing tool — always reviewable,
                       never silenceable by tier configuration
``3``   ``scan``       server unreachable, or enumeration failed after handshake
``3``   ``diff``       tool removed
``10``  all            usage or configuration error
======  ============  =================================================================

``20``-``29`` are reserved for ``report`` (Phase 4, not yet implemented) and claimed
by no other command.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from . import MANIFEST_VERSION, __version__
from .diff import diff_manifests
from .errors import (
    EXIT_OK,
    EXIT_USAGE,
    HashMismatchError,
    PlacardError,
)
from .manifest import (
    Manifest,
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
) -> None:
    """Connect to a server, enumerate its surface, and emit a manifest to stdout.

    Enumeration only: initialize, then list tools, resources, resource templates, and
    prompts. No tool is ever invoked and no resource is ever read.
    """
    raw = scan_target(target, transport=transport, timeout=timeout)
    manifest = build_manifest(raw)
    _emit_manifest(manifest, out)


@app.command(name="diff")
def diff_command(
    old: Annotated[Path, typer.Argument(help="The baseline manifest.")],
    new: Annotated[Path, typer.Argument(help="The manifest to compare against it.")],
) -> None:
    """Compare two manifests. The exit code is the result.

    0 = no change, 1 = escalation, 2 = description change on an existing tool,
    3 = tool removed. When several apply, the highest precedence (3 > 1 > 2) is
    reported; every finding is still listed on stderr.
    """
    result = diff_manifests(load_manifest(old), load_manifest(new))

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
