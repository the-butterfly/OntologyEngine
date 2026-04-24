"""OntologyEngine MCP Server."""

from typing import Any

__version__ = "0.1.0"

_services: dict[str, Any] | None = None


def init_mcp_dependencies(services: dict[str, Any]) -> None:
    """Initialize MCP dependencies with service instances.

    Args:
        services: Service instances dict (same as API dependencies)
    """
    global _services
    _services = services


def get_service(name: str) -> Any:
    """Get a service instance by name.

    Args:
        name: Service name (e.g. 'schema', 'entity', 'analysis', 'query', 'dataset', 'space')

    Returns:
        Service instance

    Raises:
        RuntimeError: If MCP dependencies not initialized
        KeyError: If service not found
    """
    if _services is None:
        raise RuntimeError(
            "MCP dependencies not initialized. "
            "Call init_mcp_dependencies() before using MCP tools."
        )
    if name not in _services:
        raise KeyError(
            f"Service '{name}' not found. "
            f"Available services: {list(_services.keys())}"
        )
    return _services[name]


def mcp_response(
    success: bool,
    data: Any = None,
    error: str | dict[str, str] | None = None,
) -> dict[str, Any]:
    """Unified MCP tool response format.

    Args:
        success: Whether the operation succeeded
        data: Response data on success
        error: Error message (string) or structured error dict with
               code/message/suggestion keys

    Returns:
        Standardized response dict
    """
    return {
        "success": success,
        "data": data,
        "error": error,
    }
