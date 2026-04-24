"""Unit tests for MCP dependency injection."""

import pytest

from ontology_engine.mcp import (
    init_mcp_dependencies,
    get_service,
    mcp_response,
)


class TestMCPDependencies:
    """Test MCP dependency injection container."""

    def setup_method(self):
        """Reset global state before each test."""
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    def test_init_mcp_dependencies_sets_services(self):
        services = {"dataset": object(), "query": object()}
        init_mcp_dependencies(services)
        import ontology_engine.mcp as mcp_mod
        assert mcp_mod._services is services

    def test_get_service_returns_initialized_service(self):
        mock_service = object()
        init_mcp_dependencies(services={"analysis": mock_service})
        assert get_service("analysis") is mock_service

    def test_get_service_raises_runtime_error_when_not_initialized(self):
        with pytest.raises(RuntimeError, match="MCP dependencies not initialized"):
            get_service("analysis")

    def test_get_service_raises_key_error_for_unknown_service(self):
        init_mcp_dependencies(services={"dataset": object()})
        with pytest.raises(KeyError, match="Service 'unknown' not found"):
            get_service("unknown")

    def test_get_service_key_error_lists_available_services(self):
        init_mcp_dependencies(services={"dataset": object(), "query": object()})
        with pytest.raises(KeyError) as exc_info:
            get_service("nonexistent")
        error_msg = str(exc_info.value)
        assert "dataset" in error_msg
        assert "query" in error_msg

    def test_init_mcp_dependencies_can_be_called_multiple_times(self):
        svc1 = object()
        svc2 = object()
        init_mcp_dependencies(services={"a": svc1})
        assert get_service("a") is svc1
        init_mcp_dependencies(services={"b": svc2})
        with pytest.raises(KeyError):
            get_service("a")
        assert get_service("b") is svc2


class TestMCPResponse:
    """Test mcp_response utility."""

    def test_success_response(self):
        result = mcp_response(success=True, data={"id": "123"})
        assert result == {"success": True, "data": {"id": "123"}, "error": None}

    def test_error_response_with_string(self):
        result = mcp_response(success=False, error="Not found")
        assert result == {"success": False, "data": None, "error": "Not found"}

    def test_error_response_with_structured_dict(self):
        error = {
            "code": "SPACE_NOT_FOUND",
            "message": "Space 'space_xxx' not found",
            "suggestion": "Use oe_list_spaces to find available spaces",
        }
        result = mcp_response(success=False, error=error)
        assert result["success"] is False
        assert result["error"]["code"] == "SPACE_NOT_FOUND"
        assert result["error"]["suggestion"] == "Use oe_list_spaces to find available spaces"

    def test_success_response_no_data(self):
        result = mcp_response(success=True)
        assert result == {"success": True, "data": None, "error": None}

    def test_error_response_no_data(self):
        result = mcp_response(success=False, error={"code": "INTERNAL_ERROR", "message": "fail"})
        assert result["data"] is None
        assert result["error"]["code"] == "INTERNAL_ERROR"
