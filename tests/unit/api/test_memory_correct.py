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


class TestCorrectNode:
    def test_correct_node_success(self, client, mock_memory_service):
        mock_memory_service.correct_node = AsyncMock(return_value={
            "data": {
                "new_node_id": "mem:fragment:test:new123",
                "old_node_id": "mem:fragment:test:abc123",
            }
        })
        response = client.patch(
            "/v1/spaces/test-space/memory/mem:fragment:test:abc123/correct",
            json={"corrected_text": "corrected content", "reason": "typo fix"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "new_node_id" in data["data"]

    def test_correct_node_not_found(self, client, mock_memory_service):
        from ontology_engine.engine.cognitive.errors import CognitiveNodeNotFoundError
        mock_memory_service.correct_node = AsyncMock(side_effect=CognitiveNodeNotFoundError("nonexistent"))
        mock_memory_service.is_node_not_found_error = MagicMock(return_value=True)
        response = client.patch(
            "/v1/spaces/test-space/memory/nonexistent/correct",
            json={"corrected_text": "text"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NODE_NOT_FOUND"

    def test_correct_node_missing_text(self, client, mock_memory_service):
        response = client.patch(
            "/v1/spaces/test-space/memory/mem:fragment:test:abc123/correct",
            json={},
        )
        assert response.status_code == 422
