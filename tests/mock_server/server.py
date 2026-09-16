"""A local MCP server used as the fixture for every Placard integration test.

Run it over stdio:

    python -m tests.mock_server
    python -m tests.mock_server --description-variant b
    python -m tests.mock_server --add-tool
    python -m tests.mock_server --drop-tool delete_workspace

The surface itself lives in :mod:`tests.mock_server.surface`. This module only wires
that surface to the low-level MCP server and the stdio transport.

Note what is *not* registered: there is no ``tools/call`` handler. The fixture for a
scanner that must never invoke a tool is a server that cannot be invoked.
"""

from __future__ import annotations

import sys

import anyio
import mcp.types as types
from mcp.server import Server
from mcp.server.context import ServerRequestContext
from mcp.server.stdio import stdio_server

from .surface import (
    SERVER_INSTRUCTIONS,
    SERVER_NAME,
    SERVER_TITLE,
    SERVER_VERSION,
    MockConfig,
    build_prompts,
    build_resource_templates,
    build_resources,
    build_tools,
    config_from_args,
)


def build_server(config: MockConfig) -> Server[None]:
    """Construct the mock server for a given surface configuration."""

    async def on_list_tools(
        _context: ServerRequestContext[None],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=build_tools(config))

    async def on_list_resources(
        _context: ServerRequestContext[None],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListResourcesResult:
        return types.ListResourcesResult(resources=build_resources())

    async def on_list_resource_templates(
        _context: ServerRequestContext[None],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListResourceTemplatesResult:
        return types.ListResourceTemplatesResult(resource_templates=build_resource_templates())

    async def on_list_prompts(
        _context: ServerRequestContext[None],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListPromptsResult:
        return types.ListPromptsResult(prompts=build_prompts())

    return Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        title=SERVER_TITLE,
        instructions=SERVER_INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_list_resources=on_list_resources,
        on_list_resource_templates=on_list_resource_templates,
        on_list_prompts=on_list_prompts,
    )


async def serve_stdio(config: MockConfig) -> None:
    """Serve the configured surface over stdio until the client disconnects."""
    server = build_server(config)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``python -m tests.mock_server``."""
    config = config_from_args(list(sys.argv[1:] if argv is None else argv))
    anyio.run(serve_stdio, config)


if __name__ == "__main__":
    main()
