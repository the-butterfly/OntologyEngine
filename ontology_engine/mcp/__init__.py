"""OntologyEngine MCP Server."""

from typing import Any

__version__ = "0.1.0"


def mcp_response(success: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    """统一 MCP 工具返回格式."""
    return {
        "success": success,
        "data": data,
        "error": error,
    }
