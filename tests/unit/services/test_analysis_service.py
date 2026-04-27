# tests/unit/services/test_analysis_service.py
"""Tests for AnalysisService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ontology_engine.services.analysis_service import AnalysisService
from ontology_engine.services.dto import EntityNotFoundError
from ontology_engine.storage.base import EntityInstance
from ontology_engine.core.schema.models import (
    KGMLSchema, SchemaMetadata, MetricDefinition,
    ConceptDefinition, AttributeDefinition,
)


class MockCategoryTags:
    def __init__(self, tags=None):
        self.tags = tags if tags else {}


class MockRuleResult:
    def __init__(self, rule_id="R001", rule_name="Test Rule", passed=True, output=None, error=None):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.passed = passed
        self.output = output if output else {}
        self.error = error


class MockAnalysisResult:
    def __init__(self):
        self.rule_results = [MockRuleResult()]
        self.alerts = []
        self.computed_metrics = {"test_metric": 100}
        self.decision = "APPROVED"
        self.decision_reasoning = "All rules passed"


def _make_test_schema():
    metadata = SchemaMetadata(id="test", name="test", version="1.0")
    metrics = [MetricDefinition(name="test_metric", type="atomic")]
    concepts = [
        ConceptDefinition(
            name="Supplier",
            attributes=[AttributeDefinition(name="supplier_id", type="string", required=True, unique=True)],
        ),
        ConceptDefinition(
            name="Invoice",
            attributes=[AttributeDefinition(name="invoice_no", type="string", required=True, unique=True)],
        ),
        ConceptDefinition(
            name="Contract",
            attributes=[AttributeDefinition(name="contract_no", type="string", required=True, unique=True)],
        ),
    ]
    return KGMLSchema(metadata=metadata, metrics=metrics, concepts=concepts)


class TestAnalysisService:

    @pytest.fixture
    def mock_categorization_engine(self):
        engine = AsyncMock()
        engine.categorize = AsyncMock(return_value=MockCategoryTags({"risk_level": "LOW"}))
        return engine

    @pytest.fixture
    def mock_metric_engine(self):
        engine = AsyncMock()
        engine.compute_batch = AsyncMock(return_value={"test_metric": {"value": 100}})
        return engine

    @pytest.fixture
    def mock_rule_executor(self):
        executor = AsyncMock()
        executor.execute_dimension = AsyncMock(return_value=MockAnalysisResult())
        return executor

    @pytest.fixture
    def storage(self):
        storage = AsyncMock()
        storage.get_entity = AsyncMock(return_value=None)
        storage.get_entity_by_id = AsyncMock(return_value=None)
        storage.query_entities = AsyncMock(return_value=[])
        return storage

    @pytest.fixture
    def schema(self):
        return _make_test_schema()

    @pytest.fixture
    def service(self, mock_categorization_engine, mock_metric_engine, mock_rule_executor, storage, schema):
        with patch(
            "ontology_engine.services.analysis_service.AnalysisService.__init__",
            return_value=None,
        ):
            svc = AnalysisService.__new__(AnalysisService)
            svc.storage = storage
            svc.schema = schema
            svc.categorization_engine = mock_categorization_engine
            svc.metric_engine = mock_metric_engine
            svc.rule_executor = mock_rule_executor
            return svc

    @pytest.mark.asyncio
    async def test_execute_analysis_entity_not_found(self, service, storage):
        storage.get_entity_by_id.return_value = None
        storage.get_entity.return_value = None
        storage.query_entities.return_value = []

        with pytest.raises(EntityNotFoundError):
            await service.execute_analysis("NONEXISTENT", "credit_assessment")

    @pytest.mark.asyncio
    async def test_execute_analysis_success(self, service, storage, mock_categorization_engine, mock_metric_engine, mock_rule_executor):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"name": "Test Supplier"}
        )
        storage.get_entity_by_id.return_value = entity

        result = await service.execute_analysis("SUP_001", "credit_assessment")

        assert result.entity_id == "SUP_001"
        assert result.fact_object == "Supplier"
        assert result.dimension == "credit_assessment"
        assert result.decision == "APPROVED"
        mock_categorization_engine.categorize.assert_called_once()
        mock_rule_executor.execute_dimension.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_analysis_with_context(self, service, storage, mock_metric_engine):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={}
        )
        storage.get_entity_by_id.return_value = entity

        context = {"override_metric": True}
        result = await service.execute_analysis("SUP_001", "credit_assessment", context=context)

        assert result is not None
        assert mock_metric_engine.compute_batch.called

    @pytest.mark.asyncio
    async def test_execute_dry_run(self, service, storage):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={}
        )
        storage.get_entity_by_id.return_value = entity

        result = await service.execute_dry_run("SUP_001", "credit_assessment")

        assert result.entity_id == "SUP_001"
        assert result.dimension == "credit_assessment"

    @pytest.mark.asyncio
    async def test_find_entity_try_concepts(self, service, storage):
        entity = EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_001",
            data={}
        )
        storage.get_entity_by_id.return_value = None
        storage.get_entity.side_effect = [None, entity]

        result = await service._find_entity("INV_001")

        assert result is not None
        assert result.entity_id == "INV_001"
        assert result.concept == "Invoice"

    @pytest.mark.asyncio
    async def test_find_entity_query_all(self, service, storage):
        entity = EntityInstance(
            _fact_object="Contract",
            entity_id="CTR_001",
            data={}
        )
        storage.get_entity_by_id.return_value = None
        storage.get_entity.return_value = None
        storage.query_entities.return_value = [entity]

        result = await service._find_entity("CTR_001")

        assert result is not None
        assert result.entity_id == "CTR_001"

    @pytest.mark.asyncio
    async def test_collect_required_metrics(self, service):
        metrics = service._collect_required_metrics("credit_assessment")
        assert "test_metric" in metrics

    @pytest.mark.asyncio
    async def test_collect_required_metrics_no_schema(self):
        svc = AnalysisService.__new__(AnalysisService)
        svc.storage = AsyncMock()
        svc.schema = None
        svc.categorization_engine = None
        svc.metric_engine = None
        svc.rule_executor = None

        metrics = svc._collect_required_metrics("credit_assessment")
        assert metrics == []

    @pytest.mark.asyncio
    async def test_serialize_metrics(self, service):
        raw_metrics = {
            "metric1": {"value": 100, "extra": "data"},
            "metric2": "simple_value",
            "metric3": {"value": 200}
        }

        result = service._serialize_metrics(raw_metrics)

        assert result["metric1"] == 100
        assert result["metric2"] == "simple_value"
        assert result["metric3"] == 200
