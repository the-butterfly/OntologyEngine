# tests/unit/services/test_schema_service.py
"""Tests for SchemaService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from ontology_engine.services.schema_service import SchemaService
from ontology_engine.services.dto import SchemaValidationError
from ontology_engine.core.schema.models import KGMLSchema, SchemaMetadata, MetricDefinition, ConceptDefinition


class TestSchemaService:
    """Test SchemaService operations."""

    @pytest.fixture
    def storage(self):
        """Create mock storage."""
        storage = AsyncMock()
        return storage

    @pytest.fixture
    def service(self, storage):
        """Create SchemaService instance."""
        return SchemaService(storage=storage)

    @pytest.fixture
    def temp_schema_file(self):
        """Create a temporary schema file."""
        schema_content = """
metadata:
  id: test_schema_id
  name: test_schema
  version: "1.0"
  description: Test schema

metrics:
  - name: test_metric
    type: atomic
    description: A test metric

concepts:
  - name: Supplier
    description: A supplier entity

rules: []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(schema_content)
            f.flush()
            yield f.name
        os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_load_schema(self, service, temp_schema_file):
        """Test loading a schema from file."""
        result = await service.load_schema(temp_schema_file)

        assert result.schema_id == "test_schema_id"
        assert result.version == "v1"
        assert result.entity_count == 1
        assert result.metric_count == 1
        assert result.rule_count == 0

    @pytest.mark.asyncio
    async def test_load_schema_invalid(self, service):
        """Test loading invalid schema raises error."""
        with pytest.raises(FileNotFoundError):
            await service.load_schema("/nonexistent/path.yaml")

    @pytest.mark.asyncio
    async def test_get_schema_none_when_not_loaded(self, service):
        """Test get_schema returns None when no schema loaded."""
        result = await service.get_schema()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_schema_after_load(self, service, temp_schema_file):
        """Test get_schema returns loaded schema."""
        await service.load_schema(temp_schema_file)
        result = await service.get_schema()

        assert result is not None
        assert result.metadata.id == "test_schema_id"

    @pytest.mark.asyncio
    async def test_reload_schema(self, service, temp_schema_file):
        """Test hot-reload schema."""
        # Load initial
        await service.load_schema(temp_schema_file)
        first_version = (await service.get_schema_versions())[0]

        # Reload
        result = await service.reload_schema(temp_schema_file)
        second_version = (await service.get_schema_versions())[1]

        assert second_version["version"] == "v2"
        assert second_version != first_version

    @pytest.mark.asyncio
    async def test_get_schema_versions(self, service, temp_schema_file):
        """Test getting schema version history."""
        await service.load_schema(temp_schema_file)
        await service.load_schema(temp_schema_file)

        versions = await service.get_schema_versions()
        assert len(versions) == 2
        assert versions[0]["version"] == "v1"
        assert versions[1]["version"] == "v2"

    @pytest.mark.asyncio
    async def test_rollback_schema(self, service, temp_schema_file):
        """Test rollback to specific version."""
        await service.load_schema(temp_schema_file)
        await service.load_schema(temp_schema_file)

        result = await service.rollback_schema(1)
        assert result.version == "v1"
        assert "Rollback is informational" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_rollback_invalid_version(self, service):
        """Test rollback to invalid version raises error."""
        with pytest.raises(ValueError):
            await service.rollback_schema(999)
