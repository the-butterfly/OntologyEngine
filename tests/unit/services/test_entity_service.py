# tests/unit/services/test_entity_service.py
"""Tests for EntityService."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ontology_engine.services.entity_service import EntityService
from ontology_engine.services.dto import (
    EntityCreateRequest,
    ConceptNotDefinedError,
)
from ontology_engine.storage.base import EntityInstance
from ontology_engine.core.schema.models import KGMLSchema, SchemaMetadata, ConceptDefinition


class TestEntityService:
    """Test EntityService operations."""

    @pytest.fixture
    def storage(self):
        """Create mock storage."""
        storage = AsyncMock()
        storage.save_entity = AsyncMock(return_value="SUP_001")
        storage.get_entity = AsyncMock(return_value=None)
        storage.query_entities = AsyncMock(return_value=[])
        storage.save_relation = AsyncMock()
        storage.get_neighbors = AsyncMock(return_value=[])
        return storage

    @pytest.fixture
    def schema(self):
        """Create a test schema."""
        metadata = SchemaMetadata(id="test", name="test", version="1.0")
        concepts = [
            ConceptDefinition(name="Supplier", description="A supplier"),
            ConceptDefinition(name="Invoice", description="An invoice"),
        ]
        return KGMLSchema(metadata=metadata, concepts=concepts)

    @pytest.fixture
    def service(self, storage, schema):
        """Create EntityService instance."""
        return EntityService(storage=storage, schema=schema)

    @pytest.mark.asyncio
    async def test_create_entity(self, service, storage):
        """Test creating an entity."""
        request = EntityCreateRequest(
            fact_object="Supplier",
            entity_id="SUP_001",
            attributes={"name": "Test Supplier"}
        )

        result = await service.create_entity(
            fact_object=request.fact_object,
            entity_id=request.entity_id,
            attributes=request.attributes
        )

        assert result.entity_id == "SUP_001"
        assert result.fact_object == "Supplier"
        assert result.attributes == {"name": "Test Supplier"}
        storage.save_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_entity_concept_not_defined(self, service):
        """Test creating entity with undefined concept raises error."""
        request = EntityCreateRequest(
            fact_object="UnknownConcept",
            entity_id="ENT_001",
            attributes={}
        )

        with pytest.raises(ConceptNotDefinedError):
            await service.create_entity(
                fact_object=request.fact_object,
                entity_id=request.entity_id,
                attributes=request.attributes
            )

    @pytest.mark.asyncio
    async def test_batch_create(self, service, storage):
        """Test batch entity creation."""
        requests = [
            EntityCreateRequest(fact_object="Supplier", entity_id="SUP_001", attributes={}),
            EntityCreateRequest(fact_object="Supplier", entity_id="SUP_002", attributes={}),
        ]

        result = await service.batch_create(requests)

        assert result.success_count == 2
        assert result.error_count == 0
        assert len(result.entities) == 2

    @pytest.mark.asyncio
    async def test_batch_create_partial_failure(self, service, storage):
        """Test batch creation with partial failure."""
        requests = [
            EntityCreateRequest(fact_object="Supplier", entity_id="SUP_001", attributes={}),
            EntityCreateRequest(fact_object="UnknownConcept", entity_id="ENT_002", attributes={}),
        ]

        result = await service.batch_create(requests)

        assert result.success_count == 1
        assert result.error_count == 1
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_get_entity(self, service, storage):
        """Test getting an entity."""
        storage.get_entity.return_value = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"name": "Test"}
        )

        result = await service.get_entity("Supplier", "SUP_001")

        assert result is not None
        assert result.entity_id == "SUP_001"
        assert result.fact_object == "Supplier"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, service, storage):
        """Test getting non-existent entity returns None."""
        storage.get_entity.return_value = None

        result = await service.get_entity("Supplier", "NONEXISTENT")

        assert result is None

    @pytest.mark.asyncio
    async def test_query_entities(self, service, storage):
        """Test querying entities."""
        storage.query_entities.return_value = [
            EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={}),
            EntityInstance(_fact_object="Supplier", entity_id="SUP_002", data={}),
        ]

        result = await service.query_entities(fact_object="Supplier")

        assert len(result) == 2
        storage.query_entities.assert_called_once_with(fact_object="Supplier", filters=None)

    @pytest.mark.asyncio
    async def test_query_entities_with_filters(self, service, storage):
        """Test querying entities with filters."""
        filters = {"status": "active"}
        result = await service.query_entities(fact_object="Supplier", filters=filters)

        storage.query_entities.assert_called_once_with(fact_object="Supplier", filters=filters)

    @pytest.mark.asyncio
    async def test_create_relation(self, service, storage):
        """Test creating a relation."""
        result = await service.create_relation(
            relation_name="has_invoice",
            from_id="SUP_001",
            to_id="INV_001",
            attributes={"amount": 100000}
        )

        assert result.relation_name == "has_invoice"
        assert result.from_id == "SUP_001"
        assert result.to_id == "INV_001"
        assert result.attributes == {"amount": 100000}

    @pytest.mark.asyncio
    async def test_get_neighbors(self, service, storage):
        """Test getting neighboring entities."""
        neighbor_entity = EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_001",
            data={"amount": 100000}
        )
        storage.get_neighbors.return_value = [
            (neighbor_entity, MagicMock())
        ]

        result = await service.get_neighbors(entity_id="SUP_001")

        assert len(result) == 1
        assert result[0].entity.entity_id == "INV_001"

    @pytest.mark.asyncio
    async def test_get_neighbors_with_depth_limit(self, service):
        """Test that depth > 2 raises error."""
        with pytest.raises(ValueError):
            await service.get_neighbors(entity_id="SUP_001", depth=3)
