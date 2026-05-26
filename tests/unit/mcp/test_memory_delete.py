"""Unit tests for oe_delete_memory MCP tool."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_api():
    api = AsyncMock()
    return api


@pytest.fixture(autouse=True)
def patch_get_memory_api(mock_api):
    with patch(
        "ontology_engine.mcp.tools.memory._get_memory_api",
        new_callable=AsyncMock,
        return_value=mock_api,
    ):
        yield mock_api


class TestOEDeleteMemory:

    @pytest.mark.asyncio
    async def test_delete_memory_success(self, mock_api):
        from ontology_engine.mcp.tools.memory import oe_delete_memory

        mock_api.delete_memory.return_value = {
            "success": True,
            "data": {"memory_id": "node_001", "deleted": True, "cascade": False},
            "error": None,
            "meta": {},
        }

        result = await oe_delete_memory(
            node_id="node_001",
            space_id="space_test",
        )

        assert result["success"] is True
        assert result["data"]["memory_id"] == "node_001"
        assert result["data"]["deleted"] is True
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_delete_memory_node_not_found(self, mock_api):
        from ontology_engine.mcp.tools.memory import oe_delete_memory

        mock_api.delete_memory.side_effect = ValueError("Node node_missing not found")

        result = await oe_delete_memory(
            node_id="node_missing",
            space_id="space_test",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "DELETE_ERROR"
        assert "node_missing" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_delete_memory_cascade_passed_through(self, mock_api):
        from ontology_engine.mcp.tools.memory import oe_delete_memory

        mock_api.delete_memory.return_value = {
            "success": True,
            "data": {"memory_id": "node_002", "deleted": True, "cascade": True},
            "error": None,
            "meta": {},
        }

        await oe_delete_memory(
            node_id="node_002",
            space_id="space_test",
            cascade=True,
        )

        mock_api.delete_memory.assert_called_once_with(
            node_id="node_002",
            space_id="space_test",
            cascade=True,
            user_id="mcp_user",
        )

    @pytest.mark.asyncio
    async def test_delete_memory_cascade_default_false(self, mock_api):
        from ontology_engine.mcp.tools.memory import oe_delete_memory

        mock_api.delete_memory.return_value = {
            "success": True,
            "data": {"memory_id": "node_003", "deleted": True, "cascade": False},
            "error": None,
            "meta": {},
        }

        await oe_delete_memory(
            node_id="node_003",
            space_id="space_test",
        )

        call_kwargs = mock_api.delete_memory.call_args
        assert call_kwargs.kwargs["cascade"] is False

    @pytest.mark.asyncio
    async def test_delete_memory_space_id_passed_through(self, mock_api):
        from ontology_engine.mcp.tools.memory import oe_delete_memory

        mock_api.delete_memory.return_value = {
            "success": True,
            "data": {"memory_id": "node_004", "deleted": True, "cascade": False},
            "error": None,
            "meta": {},
        }

        await oe_delete_memory(
            node_id="node_004",
            space_id="space_custom_123",
        )

        call_kwargs = mock_api.delete_memory.call_args
        assert call_kwargs.kwargs["space_id"] == "space_custom_123"

    @pytest.mark.asyncio
    async def test_delete_memory_user_id_passed_through(self, mock_api):
        from ontology_engine.mcp.tools.memory import oe_delete_memory

        mock_api.delete_memory.return_value = {
            "success": True,
            "data": {"memory_id": "node_005", "deleted": True, "cascade": False},
            "error": None,
            "meta": {},
        }

        await oe_delete_memory(
            node_id="node_005",
            space_id="space_test",
            user_id="custom_user",
        )

        call_kwargs = mock_api.delete_memory.call_args
        assert call_kwargs.kwargs["user_id"] == "custom_user"

    @pytest.mark.asyncio
    async def test_delete_memory_generic_exception(self, mock_api):
        from ontology_engine.mcp.tools.memory import oe_delete_memory

        mock_api.delete_memory.side_effect = RuntimeError("Storage unavailable")

        result = await oe_delete_memory(
            node_id="node_006",
            space_id="space_test",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "DELETE_ERROR"
        assert "Storage unavailable" in result["error"]["message"]
