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


class TestGetEvidence:
    def test_get_evidence_success(self, client, mock_memory_service):
        mock_memory_service.get_evidence = AsyncMock(return_value={
            "data": {
                "node_id": "mem:fragment:test:abc123",
                "source_fragment_ids": ["mem:fragment:test:frag1"],
                "proof_count": 1,
                "related_edges": [
                    {
                        "doc_id": "mem:fragment:test:frag1",
                        "content": "evidence content",
                        "source": "evidence_depth_1",
                        "memory_type": "fragment",
                        "cognitive_layer": "L0",
                        "edge_type": "SUPPORTS",
                        "confidence": 0.9,
                        "contribution": 1.0,
                    }
                ],
            }
        })
        response = client.get("/v1/spaces/test-space/memory/mem:fragment:test:abc123/evidence")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["node_id"] == "mem:fragment:test:abc123"
        assert data["data"]["proof_count"] == 1
        assert "source_fragment_ids" in data["data"]
        assert "related_edges" in data["data"]

    def test_get_evidence_node_not_found(self, client, mock_memory_service):
        from ontology_engine.engine.cognitive.errors import CognitiveNodeNotFoundError
        mock_memory_service.get_evidence = AsyncMock(side_effect=CognitiveNodeNotFoundError("nonexistent"))
        mock_memory_service.is_node_not_found_error = MagicMock(return_value=True)
        response = client.get("/v1/spaces/test-space/memory/nonexistent/evidence")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NODE_NOT_FOUND"

    def test_get_evidence_with_depth(self, client, mock_memory_service):
        mock_memory_service.get_evidence = AsyncMock(return_value={
            "data": {
                "node_id": "mem:fragment:test:abc123",
                "source_fragment_ids": [],
                "proof_count": 0,
                "related_edges": [],
            }
        })
        response = client.get("/v1/spaces/test-space/memory/mem:fragment:test:abc123/evidence?depth=2")
        assert response.status_code == 200
        mock_memory_service.get_evidence.assert_called_once_with("test-space", "mem:fragment:test:abc123", depth=2)
