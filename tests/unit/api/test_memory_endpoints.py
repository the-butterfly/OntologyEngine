from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ontology_engine.api.routes.memory import router as memory_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(memory_router)
    return TestClient(app)


@pytest.fixture
def mock_memory_service():
    with patch("ontology_engine.api.routes.memory.get_memory_service") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


class TestMemoryPydanticModels:
    def test_remember_with_valid_body(self, client, mock_memory_service):
        mock_memory_service.remember = AsyncMock(return_value={"data": {"node_id": "n1"}})
        response = client.post(
            "/v1/spaces/test-space/memory/remember",
            json={"content": "test content", "memory_type": "fragment"},
        )
        assert response.status_code == 200

    def test_remember_with_defaults(self, client, mock_memory_service):
        mock_memory_service.remember = AsyncMock(return_value={"data": {"node_id": "n1"}})
        response = client.post(
            "/v1/spaces/test-space/memory/remember",
            json={},
        )
        assert response.status_code == 200

    def test_recall_with_valid_body(self, client, mock_memory_service):
        mock_memory_service.recall = AsyncMock(return_value={"data": {"results": []}})
        response = client.post(
            "/v1/spaces/test-space/memory/recall",
            json={"query": "test", "max_results": 5},
        )
        assert response.status_code == 200

    def test_reflect_with_valid_body(self, client, mock_memory_service):
        mock_memory_service.reflect = AsyncMock(return_value={"data": {"reflection_id": "r1"}})
        response = client.post(
            "/v1/spaces/test-space/memory/reflect",
            json={"query": "test", "max_iterations": 5},
        )
        assert response.status_code == 200

    def test_approve_with_valid_body(self, client, mock_memory_service):
        mock_memory_service.approve_memory = AsyncMock(return_value={"data": {"approved": True}})
        response = client.post(
            "/v1/spaces/test-space/memory/approve",
            json={"node_id": "n1", "action": "approve"},
        )
        assert response.status_code == 200

    def test_forget_with_valid_body(self, client, mock_memory_service):
        mock_memory_service.run_forgetting = AsyncMock(return_value={"data": {"forgotten": 0}})
        response = client.post(
            "/v1/spaces/test-space/memory/forget",
            json={"days_elapsed": 30},
        )
        assert response.status_code == 200

    def test_consolidate_with_empty_body(self, client, mock_memory_service):
        mock_memory_service.run_consolidation = AsyncMock(return_value={"data": {"consolidated": 0}})
        response = client.post(
            "/v1/spaces/test-space/memory/consolidate",
            json={},
        )
        assert response.status_code == 200
