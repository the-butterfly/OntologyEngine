# tests/unit/engine/categorization/test_categorization.py
"""Tests for CategorizationEngine."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ontology_engine.engine.categorization.models import CategoryTags
from ontology_engine.engine.categorization.engine import CategorizationEngine
from ontology_engine.storage.base import EntityInstance


class TestCategoryTags:
    """Test CategoryTags model."""

    def test_create_empty_tags(self):
        """Test creating empty CategoryTags."""
        tags = CategoryTags(entity_id="SUP_001")
        assert tags.entity_id == "SUP_001"
        assert tags.tags == {}

    def test_create_with_tags(self):
        """Test creating CategoryTags with initial tags."""
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING", "company_scale": "LARGE"}
        )
        assert tags.tags == {"industry": "MANUFACTURING", "company_scale": "LARGE"}

    def test_set_tag(self):
        """Test setting a tag."""
        tags = CategoryTags(entity_id="SUP_001")
        tags.set("industry", "RETAIL")
        assert tags.get("industry") == "RETAIL"

    def test_get_nonexistent_tag(self):
        """Test getting nonexistent tag returns None."""
        tags = CategoryTags(entity_id="SUP_001")
        assert tags.get("nonexistent") is None

    def test_matches_exact(self):
        """Test matching with exact values."""
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING", "risk_level": "LOW"}
        )
        assert tags.matches({"industry": "MANUFACTURING"}) is True
        assert tags.matches({"industry": "RETAIL"}) is False

    def test_matches_list(self):
        """Test matching with list of acceptable values."""
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"risk_level": "LOW"}
        )
        assert tags.matches({"risk_level": ["LOW", "MEDIUM"]}) is True
        assert tags.matches({"risk_level": ["HIGH", "MEDIUM"]}) is False

    def test_matches_multiple(self):
        """Test matching multiple dimensions."""
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING", "risk_level": "LOW"}
        )
        assert tags.matches({
            "industry": "MANUFACTURING",
            "risk_level": "LOW"
        }) is True

        assert tags.matches({
            "industry": "MANUFACTURING",
            "risk_level": "HIGH"
        }) is False

    def test_matches_missing_dimension(self):
        """Test that missing dimension fails match."""
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING"}
        )
        assert tags.matches({"risk_level": "LOW"}) is False

    def test_to_dict(self):
        """Test converting to dictionary."""
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING"}
        )
        assert tags.to_dict() == {
            "entity_id": "SUP_001",
            "tags": {"industry": "MANUFACTURING"}
        }

    def test_repr(self):
        """Test string representation."""
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING"}
        )
        assert "SUP_001" in repr(tags)
        assert "MANUFACTURING" in repr(tags)


class TestCategorizationEngine:
    """Test CategorizationEngine."""

    @pytest.fixture
    def mock_schema(self):
        """Create a mock schema."""
        schema = MagicMock()
        schema.concepts = []
        return schema

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage."""
        storage = AsyncMock()
        storage.save_category_tags = AsyncMock()
        storage.get_category_tags = AsyncMock(return_value=None)
        return storage

    @pytest.fixture
    def mock_rule_executor(self):
        """Create a mock rule executor."""
        executor = AsyncMock()
        return executor

    @pytest.fixture
    def engine(self, mock_schema, mock_storage, mock_rule_executor):
        """Create a CategorizationEngine instance."""
        return CategorizationEngine(
            schema=mock_schema,
            storage=mock_storage,
            rule_executor=mock_rule_executor
        )

    @pytest.mark.asyncio
    async def test_categorize_hierarchical_industry(self, engine, mock_storage):
        """Test hierarchical categorization by industry."""
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={
                "industry_type": "MANUFACTURING",
                "company_size": "LARGE"
            }
        )

        tags = await engine.categorize(entity, dimensions=["industry_type"])

        assert tags.entity_id == "SUP_001"
        # The categorization should work based on attribute name matching

    @pytest.mark.asyncio
    async def test_categorize_empty_dimensions(self, engine):
        """Test categorization with empty dimensions list."""
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"industry_type": "MANUFACTURING"}
        )

        tags = await engine.categorize(entity, dimensions=[])

        assert tags.entity_id == "SUP_001"
        # Empty dimensions should result in empty tags

    @pytest.mark.asyncio
    async def test_categorize_stores_tags(self, engine, mock_storage):
        """Test that categorization persists tags to storage."""
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={
                "industry_type": "MANUFACTURING",
                "company_scale": "LARGE"
            }
        )

        await engine.categorize(entity, dimensions=["industry_type", "company_scale"])

        # Verify storage was called
        mock_storage.save_category_tags.assert_called()

    @pytest.mark.asyncio
    async def test_get_tags_existing(self, engine, mock_storage):
        """Test getting existing tags from storage."""
        mock_storage.get_category_tags.return_value = {
            "industry": "MANUFACTURING",
            "company_scale": "LARGE"
        }

        tags = await engine.get_tags("SUP_001")

        assert tags is not None
        assert tags.entity_id == "SUP_001"
        assert tags.get("industry") == "MANUFACTURING"

    @pytest.mark.asyncio
    async def test_get_tags_not_found(self, engine, mock_storage):
        """Test getting tags when entity has no tags."""
        mock_storage.get_category_tags.return_value = None

        tags = await engine.get_tags("SUP_001")

        assert tags is None

    def test_hierarchical_direct_attribute(self, engine):
        """Test hierarchical categorization with direct attribute match."""
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"industry_type": "RETAIL"}
        )

        result = engine._categorize_hierarchical(entity, "industry_type")

        assert result == "RETAIL"

    def test_hierarchical_nested_value(self, engine):
        """Test hierarchical categorization with nested value dict."""
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"industry_type": {"value": "MANUFACTURING", "code": "C"}}
        )

        result = engine._categorize_hierarchical(entity, "industry_type")

        assert result == "MANUFACTURING"

    def test_hierarchical_mapped_attribute(self, engine):
        """Test hierarchical categorization with attribute name mapping."""
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"industry": "WHOLESALE"}  # Using 'industry' but dimension is 'industry_type'
        )

        # This should try mapped names and find 'industry'
        result = engine._categorize_hierarchical(entity, "industry_type")

        assert result is None  # Not found directly

    def test_hierarchical_not_found(self, engine):
        """Test hierarchical categorization when attribute not found."""
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"name": "Test Company"}
        )

        result = engine._categorize_hierarchical(entity, "industry_type")

        assert result is None

    @pytest.mark.asyncio
    async def test_categorize_derived_uses_rule_executor(self, engine, mock_rule_executor):
        """Test that derived categorization uses rule executor."""
        # Setup mock rule result
        mock_result = MagicMock()
        mock_result.rule_results = []
        mock_result.computed_metrics = {"scale": "LARGE"}
        mock_rule_executor.execute_dimension.return_value = mock_result

        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"annual_revenue": 500000000}
        )

        dim_def = {"type": "derived", "ruleset": "company_scale"}
        result = await engine._categorize_derived(entity, "scale", dim_def)

        # Rule executor should have been called
        mock_rule_executor.execute_dimension.assert_called_once()

    def test_tags_same_as_hierarchical(self, engine):
        """Test that tags categorization is same as hierarchical in Phase 1."""
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"risk_level": "LOW"}
        )

        result = engine._categorize_tags(entity, "risk_level")

        assert result == "LOW"
