# tests/unit/engine/categorization/test_categorization.py
"""Tests for CategorizationEngine."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ontology_engine.engine.categorization.models import CategoryTags
from ontology_engine.engine.categorization.engine import CategorizationEngine
from ontology_engine.storage.base import CategoryTag, EntityInstance


class TestCategoryTags:
    """Test CategoryTags model."""

    def test_create_empty_tags(self):
        tags = CategoryTags(entity_id="SUP_001")
        assert tags.entity_id == "SUP_001"
        assert tags.tags == {}

    def test_create_with_dict_tags(self):
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING", "company_scale": "LARGE"}
        )
        assert tags.tags == {"industry": "MANUFACTURING", "company_scale": "LARGE"}

    def test_create_with_category_tag_list(self):
        tag_list = [
            CategoryTag(entity_id="SUP_001", dimension_name="industry", value_code="MANUFACTURING"),
            CategoryTag(entity_id="SUP_001", dimension_name="risk_level", value_code="LOW", assigned_by="llm", confidence=0.85),
        ]
        tags = CategoryTags(entity_id="SUP_001", tags=tag_list)
        assert tags.tags == {"industry": "MANUFACTURING", "risk_level": "LOW"}
        assert tags.get_tag("risk_level").assigned_by == "llm"
        assert tags.get_tag("risk_level").confidence == 0.85

    def test_set_tag(self):
        tags = CategoryTags(entity_id="SUP_001")
        tags.set("industry", "RETAIL")
        assert tags.get("industry") == "RETAIL"

    def test_set_tag_with_metadata(self):
        tags = CategoryTags(entity_id="SUP_001")
        tags.set("industry", "RETAIL", assigned_by="llm", confidence=0.9)
        record = tags.get_tag("industry")
        assert record is not None
        assert record.assigned_by == "llm"
        assert record.confidence == 0.9

    def test_add_tag(self):
        tags = CategoryTags(entity_id="SUP_001")
        tag = CategoryTag(
            entity_id="SUP_001",
            dimension_name="industry",
            value_code="MANUFACTURING",
            assigned_by="manual",
            confidence=0.95,
        )
        tags.add_tag(tag)
        assert tags.get("industry") == "MANUFACTURING"
        assert tags.get_tag("industry").assigned_by == "manual"

    def test_add_tag_replaces_existing(self):
        tags = CategoryTags(entity_id="SUP_001", tags={"industry": "RETAIL"})
        tag = CategoryTag(
            entity_id="SUP_001",
            dimension_name="industry",
            value_code="MANUFACTURING",
            assigned_by="llm",
        )
        tags.add_tag(tag)
        assert tags.get("industry") == "MANUFACTURING"
        assert tags.get_tag("industry").assigned_by == "llm"

    def test_get_nonexistent_tag(self):
        tags = CategoryTags(entity_id="SUP_001")
        assert tags.get("nonexistent") is None

    def test_get_tag_nonexistent(self):
        tags = CategoryTags(entity_id="SUP_001")
        assert tags.get_tag("nonexistent") is None

    def test_get_records(self):
        tags = CategoryTags(entity_id="SUP_001", tags={"industry": "MFG", "risk_level": "LOW"})
        records = tags.get_records()
        assert len(records) == 2
        assert all(isinstance(r, CategoryTag) for r in records)

    def test_matches_exact(self):
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING", "risk_level": "LOW"}
        )
        assert tags.matches({"industry": "MANUFACTURING"}) is True
        assert tags.matches({"industry": "RETAIL"}) is False

    def test_matches_list(self):
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"risk_level": "LOW"}
        )
        assert tags.matches({"risk_level": ["LOW", "MEDIUM"]}) is True
        assert tags.matches({"risk_level": ["HIGH", "MEDIUM"]}) is False

    def test_matches_multiple(self):
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
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING"}
        )
        assert tags.matches({"risk_level": "LOW"}) is False

    def test_to_dict(self):
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING"}
        )
        assert tags.to_dict() == {
            "entity_id": "SUP_001",
            "tags": {"industry": "MANUFACTURING"}
        }

    def test_repr(self):
        tags = CategoryTags(
            entity_id="SUP_001",
            tags={"industry": "MANUFACTURING"}
        )
        assert "SUP_001" in repr(tags)
        assert "MANUFACTURING" in repr(tags)

    def test_set_replaces_existing_dimension(self):
        tags = CategoryTags(entity_id="SUP_001", tags={"industry": "RETAIL"})
        tags.set("industry", "MANUFACTURING")
        assert tags.get("industry") == "MANUFACTURING"
        records = tags.get_records()
        assert len(records) == 1

    def test_metadata_preserved_from_dict_init(self):
        tags = CategoryTags(entity_id="SUP_001", tags={"industry": "MFG"})
        record = tags.get_tag("industry")
        assert record is not None
        assert record.assigned_by == "rule"
        assert record.confidence == 1.0
        assert record.assigned_at is not None


class TestCategorizationEngine:
    """Test CategorizationEngine."""

    @pytest.fixture
    def mock_schema(self):
        schema = MagicMock()
        schema.concepts = []
        return schema

    @pytest.fixture
    def mock_storage(self):
        storage = AsyncMock()
        storage.save_category_tag = AsyncMock()
        storage.get_category_tags = AsyncMock(return_value=[])
        return storage

    @pytest.fixture
    def mock_rule_executor(self):
        executor = AsyncMock()
        return executor

    @pytest.fixture
    def engine(self, mock_schema, mock_storage, mock_rule_executor):
        return CategorizationEngine(
            schema=mock_schema,
            storage=mock_storage,
            rule_executor=mock_rule_executor
        )

    @pytest.mark.asyncio
    async def test_categorize_hierarchical_industry(self, engine, mock_storage):
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

    @pytest.mark.asyncio
    async def test_categorize_empty_dimensions(self, engine):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"industry_type": "MANUFACTURING"}
        )

        tags = await engine.categorize(entity, dimensions=[])

        assert tags.entity_id == "SUP_001"

    @pytest.mark.asyncio
    async def test_categorize_uses_save_category_tag(self, engine, mock_storage):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={
                "industry_type": "MANUFACTURING",
                "company_scale": "LARGE"
            }
        )

        await engine.categorize(entity, dimensions=["industry_type", "company_scale"])

        mock_storage.save_category_tag.assert_called()
        for call in mock_storage.save_category_tag.call_args_list:
            tag = call[0][0]
            assert isinstance(tag, CategoryTag)
            assert tag.entity_id == "SUP_001"

    @pytest.mark.asyncio
    async def test_get_tags_existing(self, engine, mock_storage):
        mock_storage.get_category_tags.return_value = [
            CategoryTag(entity_id="SUP_001", dimension_name="industry", value_code="MANUFACTURING"),
            CategoryTag(entity_id="SUP_001", dimension_name="company_scale", value_code="LARGE"),
        ]

        tags = await engine.get_tags("SUP_001")

        assert tags is not None
        assert tags.entity_id == "SUP_001"
        assert tags.get("industry") == "MANUFACTURING"

    @pytest.mark.asyncio
    async def test_get_tags_not_found(self, engine, mock_storage):
        mock_storage.get_category_tags.return_value = []

        tags = await engine.get_tags("SUP_001")

        assert tags is not None
        assert tags.tags == {}

    @pytest.mark.asyncio
    async def test_get_tags_preserves_metadata(self, engine, mock_storage):
        mock_storage.get_category_tags.return_value = [
            CategoryTag(entity_id="SUP_001", dimension_name="risk_level", value_code="LOW", assigned_by="llm", confidence=0.85),
        ]

        tags = await engine.get_tags("SUP_001")

        assert tags is not None
        record = tags.get_tag("risk_level")
        assert record.assigned_by == "llm"
        assert record.confidence == 0.85

    def test_hierarchical_direct_attribute(self, engine):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"industry_type": "RETAIL"}
        )

        result = engine._categorize_hierarchical(entity, "industry_type")

        assert result == "RETAIL"

    def test_hierarchical_nested_value(self, engine):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"industry_type": {"value": "MANUFACTURING", "code": "C"}}
        )

        result = engine._categorize_hierarchical(entity, "industry_type")

        assert result == "MANUFACTURING"

    def test_hierarchical_mapped_attribute(self, engine):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"industry": "WHOLESALE"}
        )

        result = engine._categorize_hierarchical(entity, "industry_type")

        assert result is None

    def test_hierarchical_not_found(self, engine):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"name": "Test Company"}
        )

        result = engine._categorize_hierarchical(entity, "industry_type")

        assert result is None

    @pytest.mark.asyncio
    async def test_categorize_derived_uses_rule_executor(self, engine, mock_rule_executor):
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

        mock_rule_executor.execute_dimension.assert_called_once()

    def test_tags_same_as_hierarchical(self, engine):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"risk_level": "LOW"}
        )

        result = engine._categorize_tags(entity, "risk_level")

        assert result == "LOW"
