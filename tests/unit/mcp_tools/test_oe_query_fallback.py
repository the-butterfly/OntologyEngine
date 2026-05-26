from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOEQueryFallback:
    @pytest.mark.asyncio
    async def test_fallback_used_false_on_normal_query(self):
        with patch("ontology_engine.mcp.tools.query.get_service") as mock_get:
            query_service = MagicMock()
            query_service.hybrid_search = AsyncMock(return_value=[])
            mock_get.return_value = query_service

            from ontology_engine.mcp.tools.query import oe_query
            result = await oe_query(query="test", match_mode="hybrid")
            assert result["success"] is True
            assert result["data"]["fallback_used"] is False

    @pytest.mark.asyncio
    async def test_fallback_used_true_on_not_implemented(self):
        with patch("ontology_engine.mcp.tools.query.get_service") as mock_get:
            query_service = MagicMock()
            query_service.hybrid_search = AsyncMock(side_effect=NotImplementedError)
            query_service.pattern_match = AsyncMock(return_value=[])
            mock_get.return_value = query_service

            from ontology_engine.mcp.tools.query import oe_query
            result = await oe_query(query="test", match_mode="hybrid")
            assert result["success"] is True
            assert result["data"]["fallback_used"] is True
            assert result["data"]["fallback_mode"] == "pattern_match"
