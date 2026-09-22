"""``placard.toml`` — the one file a repository reads to know what it has accepted.

Phase 4 brief §1: one configuration file at the repository root, Pydantic-validated,
unknown keys an error. It names the servers a repository depends on, where their
approved baseline manifests live, the override allowlist (folded in here rather than
given a second home), and how findings map to SARIF display levels.

Credentials are named by environment variable, never written into the file, and are
resolved at scan time into memory only — ``header_env`` for HTTP request headers,
``env`` for variables a stdio server needs to start. Neither value ever reaches a
manifest, a report, or stderr (Phase 4 §5).

```toml
[defaults]
ceiling = "R4"
baseline_dir = ".placard/baselines"

[[server]]
name = "github"
target = "npx -y @modelcontextprotocol/server-github@2025.4.8"
env = ["GITHUB_PERSONAL_ACCESS_TOKEN"]

[[server]]
name = "docs"
target = "https://mcp.example.com/mcp"
header_env = ["Authorization=PLACARD_DOCS_TOKEN"]

[[override]]
server = "github"
tool = "create_pull_request_review"
tier = "R3"
reason = "Review comments reference a file; nothing is written to it."

[report.level]
injection = "error"
```
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .classify.overrides import OverrideEntry
from .errors import UsageError
from .manifest.models import Tier
from .transport.target import TransportChoice

SarifLevel = Literal["error", "warning", "note", "none"]

FindingCategory = Literal["escalation", "prompt", "removal", "injection", "incomplete", "chain"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Defaults(_Strict):
    ceiling: Tier = "R4"
    """A tool added at or above this tier escalates (``diff --ceiling``)."""

    baseline_dir: str = ".placard/baselines"
    """Where ``placard baseline`` writes and ``placard check`` reads ``<name>.json``,
    unless a server names its own ``baseline`` path."""

    timeout: float = Field(default=30.0, gt=0)


class ServerConfig(_Strict):
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    """Used as the baseline file name and as the SARIF fingerprint namespace."""

    target: str = Field(min_length=1)
    transport: TransportChoice = TransportChoice.AUTO
    header_env: list[str] = Field(default_factory=list)
    """``"Header-Name=ENV_VAR"`` entries for an HTTP target. The header value is read
    from ``ENV_VAR`` at scan time and never stored."""

    env: list[str] = Field(default_factory=list)
    """Environment variable *names* a stdio server may receive at launch, on top of
    the isolated minimum (Phase 4 §5). Values are read at scan time and never stored."""

    baseline: str | None = None
    """Override the baseline path for this server; relative to the config file."""

    timeout: float | None = Field(default=None, gt=0)

    @field_validator("header_env")
    @classmethod
    def _header_form(cls, value: list[str]) -> list[str]:
        for entry in value:
            if not re.fullmatch(r"[A-Za-z0-9-]+=[A-Za-z_][A-Za-z0-9_]*", entry):
                raise ValueError(f"header_env entry {entry!r} must be 'Header-Name=ENV_VAR'")
        return value

    @field_validator("env")
    @classmethod
    def _env_form(cls, value: list[str]) -> list[str]:
        for entry in value:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", entry):
                raise ValueError(f"env entry {entry!r} must be an environment variable name")
        return value

    def resolve_headers(self, environ: Mapping[str, str]) -> dict[str, str]:
        """HTTP headers for this server, values read from ``environ``. A named
        variable that is missing is a usage error, not a silently unauthenticated
        scan."""
        headers: dict[str, str] = {}
        for entry in self.header_env:
            header, variable = entry.split("=", 1)
            if variable not in environ:
                raise UsageError(
                    f"server {self.name!r}: header_env names {variable}, which is not set"
                )
            headers[header] = environ[variable]
        return headers

    def resolve_env(self, environ: Mapping[str, str]) -> dict[str, str]:
        """Variables to pass through to a stdio launch, values read from ``environ``."""
        passthrough: dict[str, str] = {}
        for variable in self.env:
            if variable not in environ:
                raise UsageError(f"server {self.name!r}: env names {variable}, which is not set")
            passthrough[variable] = environ[variable]
        return passthrough


class OverrideConfig(_Strict):
    server: str
    tool: str
    tier: Tier
    reason: str = ""
    entry_id: str | None = None
    """Recorded on the manifest so a reader can trace the downgrade to this entry.
    Defaults to ``placard.toml:<server>/<tool>``."""

    def entry(self) -> OverrideEntry:
        return OverrideEntry(
            entry_id=self.entry_id or f"placard.toml:{self.server}/{self.tool}",
            tool=self.tool,
            tier=self.tier,
            reason=self.reason,
        )


class ReportLevel(_Strict):
    """SARIF ``level`` per finding category — a *display hint* for code scanning,
    carrying no Placard semantics (Phase 4 §2). The bitmask remains the contract."""

    injection: SarifLevel = "error"
    escalation: SarifLevel = "error"
    prompt: SarifLevel = "warning"
    removal: SarifLevel = "note"
    chain: SarifLevel = "error"
    incomplete: SarifLevel = "warning"

    def for_category(self, category: FindingCategory) -> SarifLevel:
        value: SarifLevel = getattr(self, category)
        return value


class ReportConfig(_Strict):
    level: ReportLevel = Field(default_factory=ReportLevel)


class PlacardConfig(_Strict):
    defaults: Defaults = Field(default_factory=Defaults)
    server: list[ServerConfig] = Field(default_factory=list)
    override: list[OverrideConfig] = Field(default_factory=list)
    report: ReportConfig = Field(default_factory=ReportConfig)

    @model_validator(mode="after")
    def _consistent(self) -> PlacardConfig:
        names = [s.name for s in self.server]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"duplicate server name(s): {', '.join(duplicates)}")
        for override in self.override:
            if override.server not in names:
                raise ValueError(
                    f"override for {override.tool!r} names server {override.server!r}, "
                    "which is not configured"
                )
        seen: dict[tuple[str, str], Tier] = {}
        for override in self.override:
            key = (override.server, override.tool)
            if key in seen and seen[key] != override.tier:
                raise ValueError(
                    f"conflicting overrides for {override.server}/{override.tool}: "
                    f"{seen[key]} and {override.tier} — overrides are approvals, and "
                    "approvals are never resolved by precedence"
                )
            seen[key] = override.tier
        return self

    def server_named(self, name: str) -> ServerConfig:
        for server in self.server:
            if server.name == name:
                return server
        raise UsageError(f"no server named {name!r} in the configuration")

    def baseline_path(self, server: ServerConfig, *, root: Path) -> Path:
        """Where this server's approved manifest lives, resolved against the
        directory the config file sits in."""
        if server.baseline is not None:
            return (root / server.baseline).resolve()
        return (root / self.defaults.baseline_dir / f"{server.name}.json").resolve()

    def overrides_for(self, server_name: str) -> list[OverrideEntry]:
        return [o.entry() for o in self.override if o.server == server_name]


def merge_overrides(
    config_entries: list[OverrideEntry], cli_entries: list[OverrideEntry]
) -> list[OverrideEntry]:
    """CLI overrides add to the config's (Phase 4 go memo, ruling 4). Two entries for
    the same tool with different tiers is a usage error — never a silent precedence."""
    by_tool: dict[str, OverrideEntry] = {}
    for entry in [*config_entries, *cli_entries]:
        if entry.tool in by_tool and by_tool[entry.tool].tier != entry.tier:
            raise UsageError(
                f"conflicting overrides for tool {entry.tool!r}: "
                f"{by_tool[entry.tool].entry_id} says {by_tool[entry.tool].tier}, "
                f"{entry.entry_id} says {entry.tier}"
            )
        by_tool.setdefault(entry.tool, entry)
    return list(by_tool.values())


_NPX_UNPINNED = re.compile(r"^\s*npx\b(?:\s+-{1,2}[\w-]+(?:=\S+)?)*\s+(?:-y\s+)?(\S+)")
_UVX_UNPINNED = re.compile(r"^\s*uvx\b(?:\s+-{1,2}[\w-]+(?:=\S+)?)*\s+(\S+)")


def unpinned_target_warnings(config: PlacardConfig) -> list[str]:
    """Targets that would drift under the scanner.

    ``@latest`` targets are correct behaviour for monitoring and wrong behaviour for
    a gate: the Playwright ``@latest`` package shipped a release between two runs of
    the reference batch and the diff caught it, unprompted. A gate that compares
    against a committed baseline should compare the same server version the baseline
    was approved for. Warn on an ``npx`` package with no ``@<version>`` (or ``@latest``)
    and a ``uvx`` package with no ``==``/``@`` pin.
    """
    warnings: list[str] = []
    for server in config.server:
        target = server.target
        m = _NPX_UNPINNED.match(target)
        if m:
            spec = m.group(1)
            name_part = spec[1:] if spec.startswith("@") else spec
            unpinned = "@" not in name_part or name_part.endswith("@latest")
            if unpinned:
                warnings.append(
                    f"server {server.name!r}: npx target {spec!r} is not pinned to a version; "
                    "it will drift under the scanner (pin with @<version>)"
                )
            continue
        m = _UVX_UNPINNED.match(target)
        if m:
            spec = m.group(1)
            if "==" not in spec and "@" not in spec:
                warnings.append(
                    f"server {server.name!r}: uvx target {spec!r} is not pinned to a version; "
                    "it will drift under the scanner (pin with ==<version>)"
                )
    return warnings


def load_config(path: Path) -> PlacardConfig:
    """Read and validate ``placard.toml``. Every failure is a usage error (64) with a
    message a human can act on; an unreadable or invalid config must never be
    mistaken for an empty one."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"cannot read config {path}: {exc}") from exc
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise UsageError(f"{path}: not valid TOML: {exc}") from exc
    try:
        return PlacardConfig.model_validate(document)
    except ValidationError as exc:
        lines = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "<root>"
            lines.append(f"  {location}: {error['msg']}")
        raise UsageError(f"{path}: invalid configuration\n" + "\n".join(lines)) from exc
