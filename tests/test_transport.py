"""Transport resolution, command splitting, and typed failure behaviour.

No test here reaches a real server; that is ``test_integration.py``. These cover the
decisions made before a connection is attempted, and the guarantee that every
failure leaves the package as a typed error rather than a bare exception.
"""

from __future__ import annotations

import anyio
import pytest

from mcp_placard.errors import ConnectionFailure, PlacardError, TransportResolutionError
from mcp_placard.transport import (
    TransportChoice,
    TransportKind,
    enumerate_http,
    enumerate_stdio,
    enumerate_target,
    infer_transport,
    resolve_transport,
    scan_target,
    split_command,
)
from mcp_placard.transport.base import to_wire
from mcp_placard.transport.http import validate_url
from mcp_placard.transport.stdio import stdio_parameters


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("http://localhost:8000/mcp", TransportKind.HTTP),
        ("https://mcp.example.com/mcp", TransportKind.HTTP),
        ("python -m tests.mock_server", TransportKind.STDIO),
        ("/usr/local/bin/some-server", TransportKind.STDIO),
        ("npx -y @scope/mcp-server", TransportKind.STDIO),
    ],
)
def test_transport_is_inferred_from_the_target_shape(target: str, expected: TransportKind) -> None:
    assert infer_transport(target) is expected


@pytest.mark.parametrize("target", ["", "   ", "\t"])
def test_an_empty_target_is_a_usage_error(target: str) -> None:
    with pytest.raises(TransportResolutionError, match="target is empty"):
        infer_transport(target)


def test_explicit_stdio_overrides_a_url_shaped_target() -> None:
    """An override is an override. A command may legitimately be named like a URL."""
    assert resolve_transport("https://x/y", TransportChoice.STDIO) is TransportKind.STDIO


def test_explicit_http_against_a_command_is_rejected() -> None:
    """The one override that cannot possibly work is refused up front rather than
    producing an obscure client error later."""
    with pytest.raises(TransportResolutionError, match="requires an http"):
        resolve_transport("python -m server", TransportChoice.HTTP)


def test_explicit_http_against_a_url_is_accepted() -> None:
    assert resolve_transport("https://x/y", TransportChoice.HTTP) is TransportKind.HTTP


def test_auto_defers_to_inference() -> None:
    assert resolve_transport("https://x/y", TransportChoice.AUTO) is TransportKind.HTTP


def test_command_splitting_respects_quoting() -> None:
    command, args = split_command('"/opt/my server/bin/mcp" --config "a b.json"')
    assert command == "/opt/my server/bin/mcp"
    assert args == ["--config", "a b.json"]


def test_unbalanced_quotes_are_a_usage_error() -> None:
    with pytest.raises(TransportResolutionError, match="cannot parse stdio command"):
        split_command('server --flag "unterminated')


def test_a_whitespace_only_command_is_rejected() -> None:
    with pytest.raises(TransportResolutionError, match="no command"):
        split_command("   ")


def test_shell_metacharacters_are_arguments_not_operators() -> None:
    """A scan target must never become shell injection. ``;`` is a literal argument,
    not a command separator, because no shell is ever interposed."""
    command, args = split_command("server; rm -rf /")
    assert command == "server;"
    assert args == ["rm", "-rf", "/"]


def test_stdio_parameters_without_env_pass_the_command_through() -> None:
    params = stdio_parameters("server --flag value")
    assert params.command == "server"
    assert params.args == ["--flag", "value"]
    assert params.env is None


def test_stdio_parameters_with_env_launch_through_env_i_for_exact_isolation() -> None:
    """Phase 4 §5: the SDK merges its inherited allowlist *under* the env it is
    given, so exactness needs ``env -i``, which clears everything first."""
    params = stdio_parameters("server --flag value", {"PATH": "/bin", "TOKEN": "x"})
    assert params.command == "/usr/bin/env"
    assert params.args == ["-i", "PATH=/bin", "TOKEN=x", "server", "--flag", "value"]
    assert params.env == {"PATH": "/bin", "TOKEN": "x"}


def test_validate_url_rejects_a_non_url() -> None:
    with pytest.raises(TransportResolutionError, match="http transport requires"):
        validate_url("not-a-url")


def test_validate_url_accepts_a_url() -> None:
    assert validate_url("https://example.com/mcp") == "https://example.com/mcp"


def test_to_wire_of_none_is_an_empty_dict() -> None:
    assert to_wire(None) == {}


def test_a_missing_executable_is_a_connection_failure() -> None:
    """Exit code 3 territory: unreachable, not a crash."""
    with pytest.raises(ConnectionFailure, match="cannot connect to stdio server"):
        anyio.run(lambda: enumerate_stdio("placard-no-such-binary-xyz", timeout=10))


def test_an_unreachable_http_endpoint_is_a_connection_failure() -> None:
    with pytest.raises(ConnectionFailure, match="cannot connect to http server"):
        anyio.run(lambda: enumerate_http("http://127.0.0.1:1/mcp", timeout=5))


def test_http_enumeration_rejects_a_non_url_before_connecting() -> None:
    with pytest.raises(TransportResolutionError):
        anyio.run(lambda: enumerate_http("python -m server", timeout=5))


def test_enumerate_target_routes_http_by_inference() -> None:
    with pytest.raises(ConnectionFailure, match="http server"):
        anyio.run(lambda: enumerate_target("http://127.0.0.1:1/mcp", timeout=5))


def test_scan_target_surfaces_typed_errors_through_the_sync_wrapper() -> None:
    """The CLI calls the sync wrapper; the exception type must survive the event
    loop boundary or ``cli.py`` cannot map it to an exit code."""
    with pytest.raises(PlacardError):
        scan_target("placard-no-such-binary-xyz", timeout=10)


@pytest.mark.slow
def test_a_hung_server_times_out_as_a_connection_failure() -> None:
    """A server that never speaks must bound the scan rather than hang CI."""
    import sys

    target = f"{sys.executable} -c 'import time; time.sleep(60)'"
    with pytest.raises(ConnectionFailure, match="timed out"):
        anyio.run(lambda: enumerate_stdio(target, timeout=2))
