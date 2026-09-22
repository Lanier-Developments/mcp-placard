"""The environment a stdio server is launched with (Phase 4 §5, and the go memo).

Placard never calls ``tools/call``. But scanning a stdio server means *launching*
it, and launching an ``npx`` package executes that package's code, as the runner's
user, with whatever the runner's environment holds. "Placard never invokes a tool"
is true and is not the same as "scanning is safe." A malicious server does not need
a tool call to read the runner's environment; it needs to be started.

So every launch gets an explicitly constructed environment:

* ``PATH`` — the runner's, so the command resolves.
* ``HOME`` — a **fresh temporary directory per launch**, removed afterwards. Passing
  the real ``HOME`` would hand the server ``~/.npmrc``, ``~/.docker/config.json``,
  git credential helpers, and cloud CLI profiles: the secrets there are files, not
  variables, and scrubbing the environment alone would leave that door open.
* ``npm_config_cache`` and ``UV_CACHE_DIR`` — redirected to a shared cache directory
  so ``npx`` and ``uvx`` keep working without seeing the real home.
* The variables the configuration names for that server, and nothing else. A
  server scanned for GitHub never sees the token configured for Slack.

What this is **not**: a sandbox. The launched process still runs as the runner's
user with the runner's filesystem access. ``docs/THREAT_MODEL.md`` says so, and the
action's documentation recommends a dedicated job with no deploy credentials.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from ..errors import UsageError

CACHE_DIR_VARIABLE = "PLACARD_CACHE_DIR"
"""Set to relocate the shared package cache (default: ``$XDG_CACHE_HOME/placard`` or
``~/.cache/placard``). The cache is the one path under the real home a launched
server can reach, and it holds package downloads, not credentials."""

ISOLATED_VARIABLES = frozenset({"PATH", "HOME", "npm_config_cache", "UV_CACHE_DIR"})
"""The complete set a launched server receives beyond what its configuration names."""


def shared_cache_dir(environ: Mapping[str, str] | None = None) -> Path:
    environ = os.environ if environ is None else environ
    if CACHE_DIR_VARIABLE in environ:
        return Path(environ[CACHE_DIR_VARIABLE])
    base = environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "placard"


def build_launch_environment(
    passthrough: Mapping[str, str],
    *,
    home: Path,
    cache: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """The exact environment for one launch. Pure; see :func:`isolated_launch`."""
    environ = os.environ if environ is None else environ
    env = {
        "PATH": environ.get("PATH", ""),
        "HOME": str(home),
        "npm_config_cache": str(cache / "npm"),
        "UV_CACHE_DIR": str(cache / "uv"),
    }
    for name, value in passthrough.items():
        if name in ISOLATED_VARIABLES:
            # A configured passthrough may not override the isolation itself.
            continue
        env[name] = value
    return env


@contextmanager
def isolated_launch(passthrough: Mapping[str, str] | None = None) -> Iterator[dict[str, str]]:
    """A launch environment with a fresh temporary ``HOME``, removed on exit."""
    cache = shared_cache_dir()
    try:
        (cache / "npm").mkdir(parents=True, exist_ok=True)
        (cache / "uv").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UsageError(
            f"cannot create the shared package cache at {cache}: {exc} "
            f"(set {CACHE_DIR_VARIABLE} to a writable directory)"
        ) from exc
    home = Path(tempfile.mkdtemp(prefix="placard-home-"))
    try:
        yield build_launch_environment(passthrough or {}, home=home, cache=cache)
    finally:
        shutil.rmtree(home, ignore_errors=True)
