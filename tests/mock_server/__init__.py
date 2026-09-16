"""Local MCP server fixture used by Placard integration tests.

See :mod:`tests.mock_server.surface` for the declared surface and
:mod:`tests.mock_server.server` for the stdio wiring.
"""

from __future__ import annotations

from .surface import (
    DESCRIPTIONS,
    EXTRA_TOOL_NAME,
    MUTABLE_TOOL_NAME,
    SERVER_NAME,
    SERVER_VERSION,
    MockConfig,
)

__all__ = [
    "DESCRIPTIONS",
    "EXTRA_TOOL_NAME",
    "MUTABLE_TOOL_NAME",
    "SERVER_NAME",
    "SERVER_VERSION",
    "MockConfig",
]
