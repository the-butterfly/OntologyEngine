# tests/unit/engine/metric/test_engine.py
"""Tests for MetricEngine."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import date, timedelta

from ontology_engine.core.schema.models import (
    MetricDefinition, KGMLSchema, SchemaMetadata,
    ConceptDefinition, AttributeDefinition, RelationDefinition,
)
from ontology_engine.engine.metric.engine import MetricEngine, MetricCache
from ontology_engine.engine.metric.errors import MetricNotFoundError, MetricNotComputableError
from ontology_engine.storage.base import EntityInstance


class TestMetricCache:
    """Test MetricCache operations."""

    def test_cache_set_get(self):
        cache = MetricCache()
        cache.set("entity1", "metric1", 100)
        assert cache.get("entity1", "metric1") == 100

    def test_cache_miss(self):
        cache = MetricCache()
        assert cache.get("nonexistent", "metric") is None

    def test_cache_clear(self):
        cache = MetricCache()
        cache.set("entity1", "metric1", 100)
        cache.set("entity2", "metric2", 200)
        cache.clear()
        assert cache.get("entity1", "metric1") is None
        assert cache.get("entity2", "metric2") is None

    def test_cache_clear_entity(self):
        cache = MetricCache()
        cache.set("entity1", "metric1", 100)
        cache.set("entity2", "metric2", 200)
        cache.clear_entity("entity1")
        assert cache.get("entity1", "metric1") is None
        assert cache.get("entity2", "metric2") == 200


def _make_supplier_schema(metrics=None):
    """Create a test schema with Supplier concept and its relations."""
    metadata = SchemaMetadata(id="test_schema", name="test_schema", version="1.0")
    concepts = [
        ConceptDefinition(
            name="Supplier",
            attributes=[
                AttributeDefinition(name="supplier_id", type="string", required=True, unique=True),
            ],
            relations=[
                RelationDefinition(name="has_invoice", target="Invoice"),
                RelationDefinition(name="has_contract", target="Contract"),
                RelationDefinition(name="supplies_to", target="Enterprise"),
            ],
        ),
        ConceptDefinition(
            name="Invoice",
            attributes=[
                AttributeDefinition(name="invoice_no", type="string", required=True, unique=True),
                AttributeDefinition(name="amount", type="Money"),
                AttributeDefinition(name="issue_date", type="date"),
                AttributeDefinition(name="status", type="string"),
            ],
        ),
        ConceptDefinition(
            name="Contract",
            attributes=[
                AttributeDefinition(name="contract_no", type="string", required=True, unique=True),
                AttributeDefinition(name="contract_amount", type="Money"),
            ],
        ),
        ConceptDefinition(
            name="Enterprise",
            attributes=[
                AttributeDefinition(name="enterprise_id", type="string", required=True, unique=True),
            ],
        ),
    ]
    return KGMLSchema(metadata=metadata, concepts=concepts, metrics=metrics or [])


class TestMetricEngine:
    """Test MetricEngine computation."""

    @pytest.fixture
    def schema(self):
        metrics = [
            MetricDefinition(
                name="total_invoice_amount_90d",
                type="atomic",
                description="Total invoice amount in last 90 days"
            ),
            MetricDefinition(
                name="overdue_invoice_amount",
                type="atomic",
                description="Total overdue invoice amount"
            ),
            MetricDefinition(
                name="invoice_count_90d",
                type="atomic",
                description="Count of invoices in last 90 days"
            ),
            MetricDefinition(
                name="overdue_invoice_ratio",
                type="derived",
                formula="overdue_invoice_amount / total_invoice_amount_90d * 100",
                dependencies=["overdue_invoice_amount", "total_invoice_amount_90d"]
            ),
            MetricDefinition(
                name="credit_score",
                type="composite",
                formula="(total_invoice_amount_90d / 1000000) * 10"
            ),
        ]
        return _make_supplier_schema(metrics)

    @pytest.fixture
    def storage(self):
        storage = AsyncMock()
        storage.get_metric = AsyncMock(return_value=None)
        storage.save_metric = AsyncMock()
        storage.get_neighbors = AsyncMock(return_value=[])
        storage.get_entity = AsyncMock(return_value=None)
        return storage

    @pytest.fixture
    def engine(self, schema, storage):
        return MetricEngine(schema=schema, storage=storage)

    @pytest.mark.asyncio
    async def test_compute_metric_not_found(self, engine):
        entity = EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={})
        with pytest.raises(MetricNotFoundError):
            await engine.compute("nonexistent_metric", entity)

    @pytest.mark.asyncio
    async def test_compute_atomic_from_entity_data(self, engine):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"total_invoice_amount_90d": {"value": 500000, "currency": "CNY"}}
        )
        result = await engine.compute("total_invoice_amount_90d", entity)
        assert result == {"value": 500000, "currency": "CNY"}

    @pytest.mark.asyncio
    async def test_compute_atomic_invoice_aggregation(self, engine, storage):
        invoice1 = EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_001",
            data={"amount": {"value": 100000}, "issue_date": str(date.today() - timedelta(days=30))}
        )
        invoice2 = EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_002",
            data={"amount": {"value": 200000}, "issue_date": str(date.today() - timedelta(days=60))}
        )
        storage.get_neighbors.return_value = [
            (invoice1, MagicMock()), (invoice2, MagicMock())
        ]

        entity = EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={})
        result = await engine.compute("total_invoice_amount_90d", entity)
        assert result == 300000

    @pytest.mark.asyncio
    async def test_compute_atomic_overdue_invoices(self, engine, storage):
        invoice1 = EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_001",
            data={"amount": {"value": 100000}, "status": "OVERDUE"}
        )
        invoice2 = EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_002",
            data={"amount": {"value": 200000}, "status": "PAID"}
        )
        storage.get_neighbors.return_value = [
            (invoice1, MagicMock()), (invoice2, MagicMock())
        ]

        entity = EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={})
        result = await engine.compute("overdue_invoice_amount", entity)
        assert result == 300000

    @pytest.mark.asyncio
    async def test_compute_derived_with_dependencies(self, engine, storage):
        engine.cache.set("SUP_001", "total_invoice_amount_90d", {"value": 1000000, "currency": "CNY"})
        engine.cache.set("SUP_001", "overdue_invoice_amount", {"value": 100000, "currency": "CNY"})

        entity = EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={})
        result = await engine.compute("overdue_invoice_ratio", entity)
        assert result == 10.0

    @pytest.mark.asyncio
    async def test_compute_batch_order(self, engine, storage):
        storage.get_metric.return_value = None
        storage.get_neighbors.return_value = []

        engine.cache.set("SUP_001", "total_invoice_amount_90d", {"value": 1000000, "currency": "CNY"})
        engine.cache.set("SUP_001", "overdue_invoice_amount", {"value": 100000, "currency": "CNY"})

        entity = EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={})
        results = await engine.compute_batch(
            ["overdue_invoice_ratio", "total_invoice_amount_90d"],
            entity
        )
        assert "overdue_invoice_ratio" in results
        assert "total_invoice_amount_90d" in results

    @pytest.mark.asyncio
    async def test_compute_uses_cache(self, engine, storage):
        entity = EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={})
        engine.cache.set("SUP_001", "total_invoice_amount_90d", {"value": 999, "currency": "CNY"})
        result = await engine.compute("total_invoice_amount_90d", entity)
        assert result == {"value": 999, "currency": "CNY"}
        storage.save_metric.assert_not_called()

    @pytest.mark.asyncio
    async def test_compute_composite_with_formula(self, engine, storage):
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"total_invoice_amount_90d": {"value": 5000000, "currency": "CNY"}}
        )
        result = await engine.compute("credit_score", entity)
        assert result == 50.0

    @pytest.mark.asyncio
    async def test_atomic_invoice_count_90d(self, engine, storage):
        old_invoice = EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_OLD",
            data={"amount": {"value": 100000}, "issue_date": str(date.today() - timedelta(days=100))}
        )
        recent_invoice = EntityInstance(
            _fact_object="Invoice",
            entity_id="INV_NEW",
            data={"amount": {"value": 200000}, "issue_date": str(date.today() - timedelta(days=30))}
        )
        storage.get_neighbors.return_value = [
            (old_invoice, MagicMock()), (recent_invoice, MagicMock())
        ]

        entity = EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={})
        result = await engine.compute("invoice_count_90d", entity)
        assert result == 2


class TestMetricEngineContractAmount:
    """Test contract amount aggregation."""

    @pytest.fixture
    def schema_with_contract(self):
        metrics = [
            MetricDefinition(name="total_contract_amount", type="atomic"),
        ]
        return _make_supplier_schema(metrics)

    @pytest.fixture
    def storage(self):
        storage = AsyncMock()
        storage.get_metric = AsyncMock(return_value=None)
        storage.save_metric = AsyncMock()
        storage.get_neighbors = AsyncMock(return_value=[])
        return storage

    @pytest.mark.asyncio
    async def test_aggregate_contract_amount(self, schema_with_contract, storage):
        contract1 = EntityInstance(
            _fact_object="Contract",
            entity_id="CTR_001",
            data={"contract_amount": {"value": 1000000}}
        )
        contract2 = EntityInstance(
            _fact_object="Contract",
            entity_id="CTR_002",
            data={"contract_amount": {"value": 2000000}}
        )
        storage.get_neighbors.return_value = [
            (contract1, MagicMock()), (contract2, MagicMock())
        ]

        engine = MetricEngine(schema=schema_with_contract, storage=storage)
        entity = EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={})
        result = await engine.compute("total_contract_amount", entity)
        assert result == 3000000


class TestMetricEngineEdgeCases:
    """Test edge cases."""

    @pytest.fixture
    def schema(self):
        metadata = SchemaMetadata(id="test", name="test", version="1.0")
        return KGMLSchema(metadata=metadata, metrics=[])

    @pytest.fixture
    def storage(self):
        storage = AsyncMock()
        storage.get_metric = AsyncMock(return_value=None)
        storage.save_metric = AsyncMock()
        return storage

    @pytest.mark.asyncio
    async def test_empty_schema(self, schema, storage):
        engine = MetricEngine(schema=schema, storage=storage)
        assert len(engine._metric_defs) == 0

    @pytest.mark.asyncio
    async def test_compute_atomic_missing_raises_error(self, schema, storage):
        schema.metrics = [
            MetricDefinition(name="unknown_metric", type="atomic")
        ]
        engine = MetricEngine(schema=schema, storage=storage)
        entity = EntityInstance(_fact_object="Supplier", entity_id="SUP_001", data={})
        storage.get_metric.return_value = None

        with pytest.raises(MetricNotComputableError):
            await engine.compute("unknown_metric", entity)
