from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ontology_engine.api.routes.semantic_spaces import router as spaces_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(spaces_router)
    return TestClient(app)


@pytest.fixture
def mock_space_service():
    with patch("ontology_engine.api.routes.semantic_spaces.get_space_service") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


class TestSchemaDelete:
    def test_delete_categorization_success(self, client, mock_space_service):
        space = MagicMock()
        space.layers.L2_categorizations = [{"id": "cat-1", "name": "TestCat"}]
        mock_space_service.get_space = AsyncMock(return_value=space)
        mock_space_service.save_space = AsyncMock()
        response = client.delete("/v1/spaces/test-space/schema/L2/categorizations/cat-1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deleted"] is True

    def test_delete_categorization_not_found(self, client, mock_space_service):
        space = MagicMock()
        space.layers.L2_categorizations = [{"id": "cat-1", "name": "TestCat"}]
        mock_space_service.get_space = AsyncMock(return_value=space)
        response = client.delete("/v1/spaces/test-space/schema/L2/categorizations/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_delete_analytical_element_success(self, client, mock_space_service):
        space = MagicMock()
        space.layers.L3_analytical_elements = [{"id": "ae-1", "name": "TestAE"}]
        mock_space_service.get_space = AsyncMock(return_value=space)
        mock_space_service.save_space = AsyncMock()
        response = client.delete("/v1/spaces/test-space/schema/L3/analytical-elements/ae-1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deleted"] is True

    def test_delete_analytical_element_not_found(self, client, mock_space_service):
        space = MagicMock()
        space.layers.L3_analytical_elements = [{"id": "ae-1", "name": "TestAE"}]
        mock_space_service.get_space = AsyncMock(return_value=space)
        response = client.delete("/v1/spaces/test-space/schema/L3/analytical-elements/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
