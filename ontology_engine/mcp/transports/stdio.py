"""STDIO transport for MCP server.

This module re-exports the stdio_server from mcp.server.stdio
for use as a module import path.
"""

from mcp.server.stdio import stdio_server

__all__ = ["stdio_server"]
