"""Tests for SQLiteStorage."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from ontology_engine.storage.sqlite.store import SQLiteStorage
from ontology_engine.storage.base import EntityInstance, RelationInstance


class TestSQLiteStorage:
    """Exercise storage behavior against real SQLite."""

    @pytest_asyncio.fixture
    async def storage(self) -> SQLiteStorage:
        db = SQLiteStorage(":memory:")
        await db.initialize()
        try:
            yield db
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_entity_crud(self, storage: SQLiteStorage) -> None:
        entity = EntityInstance(
            _fact_object="Supplier",
            entity_id="SUP_001",
            data={"company_name": "测试供应商", "status": "ACTIVE"},
        )

        saved_id = await storage.save_entity(entity)
        loaded = await storage.get_entity("Supplier", "SUP_001")

        assert saved_id == "SUP_001"
        assert loaded is not None
        assert loaded.data["company_name"] == "测试供应商"

    @pytest.mark.asyncio
    async def test_get_entity_by_id(self, storage: SQLiteStorage) -> None:
        await storage.save_entity(EntityInstance("Supplier", "SUP_001", {"status": "ACTIVE"}))
        await storage.save_entity(EntityInstance("Invoice", "INV_001", {"status": "PAID"}))

        result = await storage.get_entity_by_id("SUP_001")
        assert result is not None
        assert result.concept == "Supplier"
        assert result.data["status"] == "ACTIVE"

        missing = await storage.get_entity_by_id("MISSING")
        assert missing is None

    @pytest.mark.asyncio
    async def test_query_entities_supports_all_concepts(self, storage: SQLiteStorage) -> None:
        await storage.save_entity(EntityInstance("Supplier", "SUP_001", {"status": "ACTIVE"}))
        await storage.save_entity(EntityInstance("Invoice", "INV_001", {"status": "PAID"}))

        all_entities = await storage.query_entities(fact_object=None)
        supplier_entities = await storage.query_entities(fact_object="Supplier")

        assert {entity.entity_id for entity in all_entities} == {"SUP_001", "INV_001"}
        assert [entity.entity_id for entity in supplier_entities] == ["SUP_001"]

    @pytest.mark.asyncio
    async def test_query_entities_with_json_filters(self, storage: SQLiteStorage) -> None:
        await storage.save_entity(EntityInstance("Supplier", "SUP_001", {"status": "ACTIVE"}))
        await storage.save_entity(EntityInstance("Supplier", "SUP_002", {"status": "SUSPENDED"}))

        results = await storage.query_entities(fact_object="Supplier", filters={"status": "ACTIVE"})

        assert [entity.entity_id for entity in results] == ["SUP_001"]

    @pytest.mark.asyncio
    async def test_relations_and_neighbors(self, storage: SQLiteStorage) -> None:
        supplier = EntityInstance("Supplier", "SUP_001", {"company_name": "A"})
        invoice = EntityInstance("Invoice", "INV_001", {"amount": {"value": 10}})
        await storage.save_entity(supplier)
        await storage.save_entity(invoice)
        await storage.save_relation(RelationInstance("has_invoice", "SUP_001", "INV_001", {"source": "demo"}))

        relations = await storage.get_relations("SUP_001", "has_invoice")
        neighbors = await storage.get_neighbors("SUP_001", "has_invoice")

        assert len(relations) == 1
        assert relations[0].to_entity_id == "INV_001"
        assert len(neighbors) == 1
        assert neighbors[0][0].entity_id == "INV_001"
        assert neighbors[0][1].data["source"] == "demo"

    @pytest.mark.asyncio
    async def test_metric_and_category_persistence(self, storage: SQLiteStorage) -> None:
        await storage.save_metric("SUP_001", "credit_score", 88)
        await storage.save_category_tags("SUP_001", {"risk_level": "LOW"})

        assert await storage.get_metric("SUP_001", "credit_score") == 88
        assert await storage.get_category_tags("SUP_001") == {"risk_level": "LOW"}

    @pytest.mark.asyncio
    async def test_rule_execution_log_accepts_multiple_rows(self, storage: SQLiteStorage) -> None:
        await storage.log_rule_execution("SUP_001", "R001", "passed")
        await storage.log_rule_execution("SUP_001", "R002", "failed")

        assert storage._conn is not None

        def _fetch_count() -> int:
            cursor = storage._conn.execute("SELECT COUNT(*) FROM rule_execution_log")
            row = cursor.fetchone()
            assert row is not None
            return int(row[0])

        count = await asyncio.to_thread(_fetch_count)
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_rule_execution_log_returns_all(self, storage: SQLiteStorage) -> None:
        await storage.log_rule_execution("SUP_001", "R001", "passed")
        await storage.log_rule_execution("SUP_001", "R002", "failed")
        await storage.log_rule_execution("SUP_002", "R001", "passed")

        result = await storage.get_rule_execution_log("SUP_001")

        assert len(result) == 2
        rule_ids = {r["rule_id"] for r in result}
        assert rule_ids == {"R001", "R002"}
        results = {r["result"] for r in result}
        assert results == {"passed", "failed"}

    @pytest.mark.asyncio
    async def test_get_rule_execution_log_filter_by_rule_id(self, storage: SQLiteStorage) -> None:
        await storage.log_rule_execution("SUP_001", "R001", "passed")
        await storage.log_rule_execution("SUP_001", "R002", "failed")
        await storage.log_rule_execution("SUP_001", "R001", "passed_again")

        result = await storage.get_rule_execution_log("SUP_001", rule_id="R001")

        assert len(result) == 2
        assert all(r["rule_id"] == "R001" for r in result)

    @pytest.mark.asyncio
    async def test_get_rule_execution_log_empty(self, storage: SQLiteStorage) -> None:
        result = await storage.get_rule_execution_log("NONEXISTENT")

        assert result == []
