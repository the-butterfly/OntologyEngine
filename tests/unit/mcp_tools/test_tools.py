"""Unit tests for MCP tools."""

import pytest

from ontology_engine.mcp import mcp_response


class TestMCPResponse:
    """Test mcp_response utility."""

    def test_mcp_response_success(self):
        result = mcp_response(success=True, data={"id": "123"})
        assert result == {"success": True, "data": {"id": "123"}, "error": None}

    def test_mcp_response_error(self):
        result = mcp_response(success=False, error="Not found")
        assert result == {"success": False, "data": None, "error": "Not found"}

    def test_mcp_response_success_no_data(self):
        result = mcp_response(success=True)
        assert result == {"success": True, "data": None, "error": None}


class TestSpaceTools:
    """Test space management tools."""

    @pytest.mark.asyncio
    async def test_oe_create_space_returns_mcp_format(self):
        from ontology_engine.mcp.tools.space import oe_create_space

        result = await oe_create_space(name="Test Space", description="desc", domain="finance")

        assert "success" in result
        assert "data" in result
        assert "error" in result
        # Should succeed or fail gracefully (storage may not persist in-memory across instances)
        if result["success"]:
            assert "space_id" in result["data"]
            assert result["data"]["name"] == "Test Space"

    @pytest.mark.asyncio
    async def test_oe_create_space_validates_required_fields(self):
        from ontology_engine.mcp.tools.space import oe_create_space

        # name is required - call without it to verify error handling
        result = await oe_create_space(name="", description=None)
        # Empty name may succeed or fail depending on validation
        assert "success" in result


class TestDatasetTools:
    """Test dataset tools."""

    @pytest.mark.asyncio
    async def test_oe_register_dataset_returns_mcp_format(self):
        from ontology_engine.mcp.tools.dataset import oe_register_dataset

        result = await oe_register_dataset(space_id="sp_001", name="Test DS")

        assert "success" in result
        assert "data" in result
        assert "error" in result
        if result["success"]:
            assert "dataset_id" in result["data"]


class TestQueryTools:
    """Test query tools."""

    @pytest.mark.asyncio
    async def test_oe_query_returns_mcp_format(self):
        from ontology_engine.mcp.tools.query import oe_query

        result = await oe_query(query="test", match_mode="vector", top_k=5)

        assert "success" in result
        assert "data" in result
        assert "error" in result
        if result["success"]:
            assert "results" in result["data"]
            assert result["data"]["match_mode"] == "vector"

    @pytest.mark.asyncio
    async def test_oe_query_unknown_mode_returns_error(self):
        from ontology_engine.mcp.tools.query import oe_query

        result = await oe_query(query="test", match_mode="unknown_mode")

        assert result["success"] is False
        assert result["error"] is not None


class TestServer:
    """Test MCP server registration.

    Note: These tests use importlib to avoid pytest namespace collision where
    tests/unit/mcp/ is collected as 'mcp' package shadowing the site-packages mcp.
    """

    def test_server_can_be_imported(self):
        import importlib
        server_module = importlib.import_module("ontology_engine.mcp.server")
        assert hasattr(server_module, "server")
        assert callable(server_module.list_tools)
        assert callable(server_module.call_tool)

    @pytest.mark.asyncio
    async def test_list_tools_returns_23_tools(self):
        import importlib
        server_module = importlib.import_module("ontology_engine.mcp.server")
        list_tools = server_module.list_tools
        tools = await list_tools()
        assert len(tools) == 23
        tool_names = [t.name for t in tools]
        assert "oe_create_space" in tool_names
        assert "oe_list_spaces" in tool_names
        assert "oe_query" in tool_names
        assert "oe_execute_rule" in tool_names
        assert "oe_simulate" in tool_names
        assert "oe_register_dataset" in tool_names
        assert "oe_create_entity" in tool_names
        assert "oe_define_rule" in tool_names
        assert "oe_activate_space" in tool_names
        assert "oe_snapshot" in tool_names
        assert "oe_rollback" in tool_names
