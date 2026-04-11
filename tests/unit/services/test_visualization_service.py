"""Tests for VisualizationService helper endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ontology_engine.core.schema.models import KGMLSchema, SchemaMetadata
from ontology_engine.services.visualization_service import VisualizationService
from ontology_engine.storage.base import EntityInstance
from ontology_engine.visualization.models import SimulationResult


class DummySchemaService:
    def __init__(self, schema: KGMLSchema) -> None:
        self._schema = schema

    def get_schema(self) -> KGMLSchema:
        return self._schema


class DummyAnalysisService:
    def __init__(self) -> None:
        self.rule_executor = AsyncMock()
        self.metric_engine = AsyncMock()


@pytest.fixture
def schema() -> KGMLSchema:
    return KGMLSchema(metadata=SchemaMetadata(id="test-schema", name="test", version="1.0"))


@pytest.fixture
def service(schema: KGMLSchema) -> VisualizationService:
    storage = AsyncMock()
    return VisualizationService(
        schema_service=DummySchemaService(schema),
        analysis_service=DummyAnalysisService(),
        storage=storage,
        schema=schema,
    )


@pytest.mark.asyncio
async def test_list_entities_filters_by_dimension(service: VisualizationService) -> None:
    service.storage.query_entities.return_value = [
        EntityInstance(
            concept="Supplier",
            entity_id="SUP_001",
            data={"company_name": "正常供应商", "active_dimensions": ["credit_assessment"]},
        ),
        EntityInstance(
            concept="Supplier",
            entity_id="SUP_002",
            data={"company_name": "其他实体", "active_dimensions": ["transaction_monitoring"]},
        ),
    ]

    results = await service.list_entities(concept="Supplier", dimension="credit_assessment")

    assert [item.entity_id for item in results] == ["SUP_001"]
    assert results[0].label == "正常供应商 (SUP_001)"


@pytest.mark.asyncio
async def test_get_metric_snapshot_reuses_simulation(service: VisualizationService) -> None:
    simulation = SimulationResult(
        entity_id="SUP_001",
        dimension="credit_assessment",
        final_outputs={"credit_grade": "AA"},
        final_context={"computed_metrics": {"credit_score": 88}},
        decision="APPROVE",
        decision_reasoning="looks good",
    )
    service.simulate_execution = AsyncMock(return_value=simulation)

    snapshot = await service.get_metric_snapshot("SUP_001", "credit_assessment")

    assert snapshot.entity_id == "SUP_001"
    assert snapshot.metrics["credit_score"] == 88
    assert snapshot.outputs["credit_grade"] == "AA"
    assert snapshot.decision == "APPROVE"
