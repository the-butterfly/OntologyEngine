# tests/unit/services/test_ingestion_service.py
"""Tests for IngestionService."""

import pytest
from unittest.mock import AsyncMock

from ontology_engine.services.ingestion_service import IngestionService
from ontology_engine.services.dto import (
    IngestionRequest,
    EntityCreateRequest,
    RelationCreateRequest,
)
from ontology_engine.services.entity_service import EntityService


class TestIngestionService:
    """Test IngestionService operations."""

    @pytest.fixture
    def storage(self):
        """Create mock storage."""
        storage = AsyncMock()
        storage.save_entity = AsyncMock()
        storage.save_relation = AsyncMock()
        return storage

    @pytest.fixture
    def entity_service(self, storage):
        """Create mock entity service."""
        return AsyncMock(spec=EntityService)

    @pytest.fixture
    def service(self, storage, entity_service):
        """Create IngestionService instance."""
        return IngestionService(storage=storage, entity_service=entity_service)

    @pytest.mark.asyncio
    async def test_import_instances_empty(self, service):
        """Test importing empty instance list."""
        request = IngestionRequest(entities=[], relations=[])

        result = await service.import_instances(request)

        assert result.entity_count == 0
        assert result.relation_count == 0
        assert result.error_count == 0

    @pytest.mark.asyncio
    async def test_import_instances_with_entities(self, service, storage):
        """Test importing entities."""
        request = IngestionRequest(
            entities=[
                EntityCreateRequest(
                    fact_object="Supplier",
                    entity_id="SUP_001",
                    attributes={"name": "Test Supplier"}
                ),
            ],
            relations=[]
        )

        result = await service.import_instances(request)

        assert result.entity_count == 1
        assert result.relation_count == 0
        assert result.error_count == 0
        storage.save_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_instances_with_relations(self, service, storage):
        """Test importing relations."""
        request = IngestionRequest(
            entities=[],
            relations=[
                RelationCreateRequest(
                    relation_name="has_invoice",
                    from_id="SUP_001",
                    to_id="INV_001",
                    attributes={}
                ),
            ]
        )

        result = await service.import_instances(request)

        assert result.entity_count == 0
        assert result.relation_count == 1
        assert result.error_count == 0
        storage.save_relation.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_instances_partial_failure(self, service, storage):
        """Test import with partial failure."""
        storage.save_entity.side_effect = [None, Exception("DB error")]

        request = IngestionRequest(
            entities=[
                EntityCreateRequest(fact_object="Supplier", entity_id="SUP_001", attributes={}),
                EntityCreateRequest(fact_object="Supplier", entity_id="SUP_002", attributes={}),
            ],
            relations=[]
        )

        result = await service.import_instances(request)

        assert result.entity_count == 1
        assert result.error_count == 1
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_import_from_dict(self, service, storage):
        """Test importing from dictionary format."""
        data = {
            "entities": [
                {"fact_object": "Supplier", "entity_id": "SUP_001", "attributes": {"name": "Test"}}
            ],
            "relations": [
                {"relation_type": "has_invoice", "from_id": "SUP_001", "to_id": "INV_001"}
            ]
        }

        result = await service.import_from_dict(data)

        assert result.entity_count == 1
        assert result.relation_count == 1

    @pytest.mark.asyncio
    async def test_import_from_dict_empty(self, service):
        """Test importing empty dictionary."""
        data = {"entities": [], "relations": []}

        result = await service.import_from_dict(data)

        assert result.entity_count == 0
        assert result.relation_count == 0

    @pytest.mark.asyncio
    async def test_validate_import_valid(self, service):
        """Test validating valid import data."""
        request = IngestionRequest(
            entities=[
                EntityCreateRequest(fact_object="Supplier", entity_id="SUP_001", attributes={}),
                EntityCreateRequest(fact_object="Invoice", entity_id="INV_001", attributes={}),
            ],
            relations=[
                RelationCreateRequest(
                    relation_name="has_invoice",
                    from_id="SUP_001",
                    to_id="INV_001",
                    attributes={}
                ),
            ]
        )

        valid, invalid = await service.validate_import(request)

        assert len(valid) == 2
        assert len(invalid) == 0

    @pytest.mark.asyncio
    async def test_validate_import_missing_entity_id(self, service):
        """Test validating with missing entity_id."""
        request = IngestionRequest(
            entities=[
                EntityCreateRequest(fact_object="Supplier", entity_id="", attributes={}),
            ],
            relations=[]
        )

        valid, invalid = await service.validate_import(request)

        assert len(valid) == 0
        assert len(invalid) == 1
        assert "entity_id is required" in invalid[0]["error"]

    @pytest.mark.asyncio
    async def test_validate_import_missing_fact_object(self, service):
        """Test validating with missing fact_object."""
        request = IngestionRequest(
            entities=[
                EntityCreateRequest(fact_object="", entity_id="SUP_001", attributes={}),
            ],
            relations=[]
        )

        valid, invalid = await service.validate_import(request)

        assert len(invalid) == 1
        assert "fact_object is required" in invalid[0]["error"]

    @pytest.mark.asyncio
    async def test_validate_import_relation_missing_from_id(self, service):
        """Test validating relation with missing from_id."""
        request = IngestionRequest(
            entities=[
                EntityCreateRequest(fact_object="Supplier", entity_id="SUP_001", attributes={}),
            ],
            relations=[
                RelationCreateRequest(
                    relation_name="has_invoice",
                    from_id="",
                    to_id="INV_001",
                    attributes={}
                ),
            ]
        )

        valid, invalid = await service.validate_import(request)

        assert len(invalid) == 1
        assert "from_id and to_id are required" in invalid[0]["error"]

    @pytest.mark.asyncio
    async def test_validate_import_relation_entity_not_in_list(self, service):
        """Test validating relation where entity not in entity list."""
        request = IngestionRequest(
            entities=[
                EntityCreateRequest(fact_object="Supplier", entity_id="SUP_001", attributes={}),
            ],
            relations=[
                RelationCreateRequest(
                    relation_name="has_invoice",
                    from_id="SUP_001",
                    to_id="INV_001",  # Not in entity list
                    attributes={}
                ),
            ]
        )

        valid, invalid = await service.validate_import(request)

        # Should have 1 valid entity, and 1 error for to_id not in list
        assert len(invalid) == 1
        assert "to_id not in entity list" in invalid[0]["error"]
